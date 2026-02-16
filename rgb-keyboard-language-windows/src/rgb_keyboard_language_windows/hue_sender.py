"""Hue sender - sends color commands via direct USB HID (VIA protocol) or subprocess fallback."""

import subprocess
import time
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List

logger = logging.getLogger("rgb_keyboard_language")

# Windows flag to hide console window
if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class HueSender:
    """
    Sends color commands to keyboard.

    Primary: Direct USB HID via VIA protocol (fast, ~10ms).
    Fallback: subprocess calls to qmk_hid/keychron-via-hue (slow, ~500ms-2s).

    Features:
    - Persistent HID connection with auto-reconnect
    - Rate limiting (skip-based, no blocking sleeps)
    - Deduplication (don't send if color hasn't changed)
    - Exponential backoff on errors (skip-based)
    - Subprocess fallback if hidapi unavailable or HID connection fails
    """

    def __init__(
        self,
        vid: str,
        pid: str,
        usage_page: int = 0xFF60,
        usage: int = 0x61,
        step: int = 8,
        delay_ms: int = 15,
        rate_limit_ms: int = 50,
    ):
        self.vid = vid
        self.pid = pid
        self.usage_page = usage_page
        self.usage = usage
        self.step = step
        self.delay_ms = delay_ms
        self.rate_limit_ms = rate_limit_ms

        # State tracking
        self.last_color: Optional[str] = None
        self.last_send_time: float = 0.0
        self.consecutive_errors: int = 0
        self.backoff_until: float = 0.0

        # Direct HID connection
        self._keyboard_hid = None
        self._hid_available = True  # Will be set False if hidapi not installed
        self._init_hid()

        # Subprocess fallback state
        self.active_processes: List[subprocess.Popen] = []
        self._process_lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._pending_color: Optional[str] = None
        self._send_lock = threading.Lock()

    def _init_hid(self) -> None:
        """Initialize direct HID connection."""
        try:
            from .keyboard_hid import KeyboardHID
        except ImportError:
            try:
                from keyboard_hid import KeyboardHID
            except ImportError:
                logger.warning("keyboard_hid module not available")
                self._hid_available = False
                return

        vid_int = self._parse_hex_id(self.vid)
        pid_int = self._parse_hex_id(self.pid)

        self._keyboard_hid = KeyboardHID(
            vid=vid_int,
            pid=pid_int,
            usage_page=self.usage_page,
            usage=self.usage,
        )

        if self._keyboard_hid.connect():
            logger.info("Direct HID connection established")
        else:
            logger.warning("Direct HID connection failed, will use subprocess fallback")

    def _parse_hex_id(self, value: str) -> int:
        """Parse hex string like '0x3434' or '3434' to int."""
        value = value.strip()
        if value.startswith("0x") or value.startswith("0X"):
            return int(value, 16)
        try:
            return int(value, 16)
        except ValueError:
            return int(value)

    def _normalize_hex_id(self, value: str) -> str:
        value = value.strip().lower()
        if value.startswith("0x"):
            return value[2:]
        return value

    def _get_backoff_delay(self) -> float:
        if self.consecutive_errors == 0:
            return 0.0
        delays = [1.0, 2.0, 5.0, 10.0]
        index = min(self.consecutive_errors - 1, len(delays) - 1)
        return delays[index]

    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Lazily create executor only when subprocess fallback is needed."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1)
        return self._executor

    def cleanup(self, timeout: float = 2.0) -> None:
        """Gracefully terminate all active subprocesses."""
        with self._process_lock:
            processes_to_cleanup = self.active_processes[:]
            self.active_processes.clear()

        for process in processes_to_cleanup:
            try:
                if process.poll() is not None:
                    continue
                logger.debug(f"Terminating process {process.pid}")
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                    logger.debug(f"Process {process.pid} terminated gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process {process.pid} didn't terminate, killing forcefully")
                    process.kill()
                    process.wait()
            except Exception as e:
                logger.error(f"Error during cleanup of process {process.pid}: {e}", exc_info=True)
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                except Exception:
                    pass

    def shutdown(self) -> None:
        """Shut down HID connection, background executor, and clean up processes."""
        if self._keyboard_hid is not None:
            self._keyboard_hid.disconnect()
        if self._executor is not None:
            self._executor.shutdown(wait=False)
        self.cleanup()

    def send_color(self, color: str) -> bool:
        """
        Send color to keyboard.

        Uses direct HID if available (synchronous, fast).
        Falls back to subprocess (async, slow).

        Returns:
            True if sent/submitted or skipped (dedup), False if skipped
            due to rate limit or backoff.
        """
        # Deduplication
        if color == self.last_color:
            logger.debug(f"Color unchanged ({color}), skipping send")
            return True

        current_time = time.time()

        # Non-blocking rate limit
        time_since_last = (current_time - self.last_send_time) * 1000
        if time_since_last < self.rate_limit_ms:
            logger.debug(f"Rate limit: {time_since_last:.0f}ms < {self.rate_limit_ms}ms, skipping")
            return False

        # Non-blocking backoff
        if current_time < self.backoff_until:
            remaining = self.backoff_until - current_time
            logger.debug(f"Backoff: {remaining:.1f}s remaining, skipping")
            return False

        # Try direct HID first
        if self._hid_available and self._keyboard_hid is not None:
            success = self._send_via_hid(color)
            if success:
                self.last_color = color
                self.last_send_time = current_time
                self.consecutive_errors = 0
                self.backoff_until = 0.0
                return True
            else:
                # HID failed, try reconnecting once
                logger.debug("HID send failed, attempting reconnect")
                if self._keyboard_hid.connect():
                    success = self._send_via_hid(color)
                    if success:
                        self.last_color = color
                        self.last_send_time = current_time
                        self.consecutive_errors = 0
                        self.backoff_until = 0.0
                        return True
                # Fall through to subprocess fallback
                logger.warning("HID reconnect failed, falling back to subprocess")

        # Subprocess fallback
        return self._send_via_subprocess(color, current_time)

    def _send_via_hid(self, color: str) -> bool:
        """Send color via direct HID. Returns True on success."""
        try:
            from .keyboard_hid import color_to_hsv
        except ImportError:
            from keyboard_hid import color_to_hsv

        try:
            hue, saturation = color_to_hsv(color)
        except ValueError as e:
            logger.error(f"Invalid color '{color}': {e}")
            return False

        success = self._keyboard_hid.set_color(hue, saturation)
        if success:
            logger.info(f"Color sent via HID: {color} (hue={hue}, sat={saturation})")
        return success

    def _send_via_subprocess(self, color: str, current_time: float) -> bool:
        """Send color via subprocess (fallback). Non-blocking."""
        with self._send_lock:
            self._pending_color = color

        self._ensure_executor().submit(self._do_send_subprocess, color)
        self.last_color = color
        self.last_send_time = current_time
        return True

    def _do_send_subprocess(self, color: str) -> None:
        """Actually send the color command via subprocess (runs in background thread)."""
        # Check if a newer color was requested
        with self._send_lock:
            latest = self._pending_color
        if latest != color:
            logger.debug(f"Skipping stale send ({color}), newer color pending ({latest})")
            return

        named_colors = {"green", "red", "blue", "yellow", "cyan", "purple"}
        is_named_color = color.lower().strip() in named_colors

        if is_named_color:
            cmd = ["qmk_hid", "via", "--rgb-color", color.lower().strip()]
        else:
            cmd = [
                "keychron-via-hue",
                color,
                "--vid", self.vid,
                "--pid", self.pid,
                "--step", str(self.step),
                "--delay-ms", str(self.delay_ms),
            ]

        creation_flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process: Optional[subprocess.Popen] = None

        try:
            logger.info(f"Sending color via subprocess: {color}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
            )

            with self._process_lock:
                self.active_processes.append(process)

            try:
                stdout, stderr = process.communicate(timeout=30.0)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                logger.warning(f"Command timed out, terminating process {process.pid}")
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=1.0)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    returncode = process.returncode
            finally:
                with self._process_lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)

            if returncode == 0:
                self.consecutive_errors = 0
                self.backoff_until = 0.0
                if "keychron-via-hue" in cmd[0] and "OK:" not in stdout:
                    logger.warning(f"Command succeeded but no 'OK:' in output: {stdout}")
                else:
                    logger.info(f"Color sent successfully: {color}")
            else:
                error_msg = stderr.strip() if stderr else stdout.strip() or "Unknown error"
                logger.error(f"Subprocess failed: {error_msg}")
                self.consecutive_errors += 1
                self.backoff_until = time.time() + self._get_backoff_delay()
                self.last_color = None

        except FileNotFoundError:
            tool_name = "qmk_hid" if is_named_color else "keychron-via-hue"
            logger.error(f"{tool_name} not found in PATH. Make sure it's installed.")
            if process is not None:
                with self._process_lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)
            self.consecutive_errors += 1
            self.backoff_until = time.time() + self._get_backoff_delay()
            self.last_color = None

        except Exception as e:
            tool_name = "qmk_hid" if is_named_color else "keychron-via-hue"
            logger.error(f"Unexpected error calling {tool_name}: {e}", exc_info=True)
            if process is not None:
                with self._process_lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)
            self.consecutive_errors += 1
            self.backoff_until = time.time() + self._get_backoff_delay()
            self.last_color = None
