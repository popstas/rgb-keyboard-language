"""Hue sender - calls keychron-via-hue CLI with rate limiting and deduplication."""

import subprocess
import time
import logging
import os
import sys
from typing import Optional

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
    - Rate limiting
    - Deduplication (don't send if color hasn't changed)
    - Exponential backoff on errors
    """

    def __init__(
        self,
        vid: str,
        pid: str,
        step: int = 8,
        delay_ms: int = 15,
        rate_limit_ms: int = 200,
    ):
        """
        Initialize HueSender.

        Args:
            vid: Vendor ID in hex (e.g., "0x3434" or "3434")
            pid: Product ID in hex (e.g., "0x0011" or "0011")
            step: Hue step size (default: 8)
            delay_ms: Delay between steps in milliseconds (default: 15)
            rate_limit_ms: Minimum time between commands in milliseconds (default: 200)
        """
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

    def _normalize_hex_id(self, value: str) -> str:
        """
        Normalize hex ID by removing 0x prefix if present.

        Args:
            value: Hex string (e.g., "0x3434" or "3434")

        Returns:
            Normalized hex string without 0x prefix
        """
        value = value.strip().lower()
        if value.startswith("0x"):
            return value[2:]
        return value

    def _get_backoff_delay(self) -> float:
        """
        Calculate exponential backoff delay based on consecutive errors.

        Returns:
            Delay in seconds (max 10 seconds)
        """
        if self.consecutive_errors == 0:
            return 0.0

        delays = [1.0, 2.0, 5.0, 10.0]
        index = min(self.consecutive_errors - 1, len(delays) - 1)
        return delays[index]

    def send_color(self, color: str) -> bool:
        """
        Send color to keyboard via keychron-via-hue CLI.

        Args:
            color: Color string (e.g., "green", "red", "#00ff00")

        Returns:
            True if sent successfully, False otherwise
        """
        # Deduplication: don't send if color hasn't changed
        if color == self.last_color:
            logger.debug(f"Color unchanged ({color}), skipping send")
            return True

        # Rate limiting
        current_time = time.time()
        time_since_last = (current_time - self.last_send_time) * 1000  # ms

        if time_since_last < self.rate_limit_ms:
            wait_time = (self.rate_limit_ms - time_since_last) / 1000.0
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            current_time = time.time()

        # Check backoff
        if current_time < self.backoff_until:
            wait_time = self.backoff_until - current_time
            logger.debug(f"Backoff: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            current_time = time.time()

        # Determine if color is named (for direct qmk_hid call)
        # For named colors (green, red, etc.), call qmk_hid directly to avoid console window
        # For other colors (hex, hsv), use keychron-via-hue
        named_colors = {"green", "red", "blue", "yellow", "cyan", "purple"}
        is_named_color = color.lower().strip() in named_colors

        # Build command
        if is_named_color:
            # Call qmk_hid directly to avoid console window popup
            cmd = [
                "qmk_hid",
                "via",
                "--rgb-color",
                color.lower().strip(),
            ]
        else:
            # For hex/hsv colors, use keychron-via-hue (requires VID/PID)
            vid_normalized = self._normalize_hex_id(self.vid)
            pid_normalized = self._normalize_hex_id(self.pid)

            cmd = [
                "keychron-via-hue",
                color,
                "--vid",
                self.vid,
                "--pid",
                self.pid,
                "--step",
                str(self.step),
                "--delay-ms",
                str(self.delay_ms),
            ]

        try:
            logger.info(f"Sending color: {color} (VID: {self.vid}, PID: {self.pid})")
            
            # Prepare subprocess creation flags to hide console window on Windows
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = CREATE_NO_WINDOW
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                creationflags=creation_flags if sys.platform == "win32" else 0,
            )

            if result.returncode == 0:
                # Success
                self.last_color = color
                self.last_send_time = current_time
                self.consecutive_errors = 0
                self.backoff_until = 0.0

                # For direct qmk_hid calls, no "OK:" message expected
                # For keychron-via-hue, check for "OK:" in output
                if "keychron-via-hue" in cmd[0] and "OK:" not in result.stdout:
                    logger.warning(f"Command succeeded but no 'OK:' in output: {result.stdout}")
                else:
                    logger.info(f"Color sent successfully: {color}")

                return True
            else:
                # Command failed
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"keychron-via-hue failed: {error_msg}")
                self.consecutive_errors += 1
                backoff_delay = self._get_backoff_delay()
                self.backoff_until = current_time + backoff_delay
                return False

        except FileNotFoundError:
            tool_name = "qmk_hid" if is_named_color else "keychron-via-hue"
            logger.error(f"{tool_name} not found in PATH. Make sure it's installed.")
            self.consecutive_errors += 1
            backoff_delay = self._get_backoff_delay()
            self.backoff_until = current_time + backoff_delay
            return False

        except subprocess.TimeoutExpired:
            tool_name = "qmk_hid" if is_named_color else "keychron-via-hue"
            logger.error(f"{tool_name} command timed out")
            self.consecutive_errors += 1
            backoff_delay = self._get_backoff_delay()
            self.backoff_until = current_time + backoff_delay
            return False

        except Exception as e:
            tool_name = "qmk_hid" if is_named_color else "keychron-via-hue"
            logger.error(f"Unexpected error calling {tool_name}: {e}", exc_info=True)
            self.consecutive_errors += 1
            backoff_delay = self._get_backoff_delay()
            self.backoff_until = current_time + backoff_delay
            return False

