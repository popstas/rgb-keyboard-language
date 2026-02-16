"""Hue sender - calls keychron-via-hue CLI with rate limiting and deduplication."""

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
    Sends color commands to keyboard via keychron-via-hue CLI.

    Features:
    - Non-blocking async send via background thread
    - Rate limiting (skip-based, no blocking sleeps)
    - Deduplication (don't send if color hasn't changed)
    - Exponential backoff on errors (skip-based)
    - Graceful shutdown of active subprocess
    """

    def __init__(
        self,
        vid: str,
        pid: str,
        step: int = 8,
        delay_ms: int = 15,
        rate_limit_ms: int = 50,
    ):
        self.vid = vid
        self.pid = pid
        self.step = step
        self.delay_ms = delay_ms
        self.rate_limit_ms = rate_limit_ms

        # State tracking
        self.last_color: Optional[str] = None
        self.last_send_time: float = 0.0
        self.consecutive_errors: int = 0
        self.backoff_until: float = 0.0

        # Track active subprocess for graceful shutdown
        self.active_processes: List[subprocess.Popen] = []
        self._process_lock = threading.Lock()

        # Background executor for non-blocking sends
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pending_color: Optional[str] = None
        self._send_lock = threading.Lock()

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
        """Shut down the background executor and clean up processes."""
        self._executor.shutdown(wait=False)
        self.cleanup()

    def send_color(self, color: str) -> bool:
        """
        Send color to keyboard (non-blocking).

        Submits the color change to a background thread. If a send is already
        in progress, the new color is queued and will replace any pending send.

        Returns:
            True if the send was submitted or skipped (dedup), False if skipped
            due to rate limit or backoff.
        """
        # Deduplication: don't send if color hasn't changed
        if color == self.last_color:
            logger.debug(f"Color unchanged ({color}), skipping send")
            return True

        current_time = time.time()

        # Non-blocking rate limit: skip if too soon
        time_since_last = (current_time - self.last_send_time) * 1000  # ms
        if time_since_last < self.rate_limit_ms:
            logger.debug(f"Rate limit: {time_since_last:.0f}ms < {self.rate_limit_ms}ms, skipping (will retry next poll)")
            return False

        # Non-blocking backoff: skip if still in backoff period
        if current_time < self.backoff_until:
            remaining = self.backoff_until - current_time
            logger.debug(f"Backoff: {remaining:.1f}s remaining, skipping")
            return False

        # Submit to background thread
        with self._send_lock:
            self._pending_color = color

        self._executor.submit(self._do_send, color)
        # Update last_color immediately so the watch loop doesn't re-trigger
        self.last_color = color
        self.last_send_time = current_time
        return True

    def _do_send(self, color: str) -> None:
        """Actually send the color command (runs in background thread)."""
        # Check if a newer color was requested while we were queued
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
            logger.info(f"Sending color: {color} (VID: {self.vid}, PID: {self.pid})")

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
                logger.error(f"keychron-via-hue failed: {error_msg}")
                self.consecutive_errors += 1
                self.backoff_until = time.time() + self._get_backoff_delay()
                # Reset last_color so next poll retries
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
