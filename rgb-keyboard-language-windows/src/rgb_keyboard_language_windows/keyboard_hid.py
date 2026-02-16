"""Direct USB HID communication with QMK keyboards using VIA protocol."""

import logging
import re
from typing import Optional

logger = logging.getLogger("rgb_keyboard_language")

# VIA protocol constants
VIA_SET_VALUE = 0x07
VIA_GET_VALUE = 0x08
VIA_SAVE = 0x09

# VIA value IDs for RGB
VIA_RGB_BRIGHTNESS = 1
VIA_RGB_EFFECT = 2
VIA_RGB_SPEED = 3
VIA_RGB_COLOR = 4

# HID report size (VIA uses 32-byte reports)
REPORT_SIZE = 32

# Named colors → QMK hue (0-255)
NAMED_COLORS = {
    "red": 0,
    "yellow": 42,
    "green": 85,
    "cyan": 128,
    "blue": 170,
    "purple": 213,
}


def color_to_hsv(color: str) -> tuple[int, int]:
    """
    Convert color string to (hue, saturation) for VIA protocol.

    Supports:
    - Named colors: red, green, blue, yellow, cyan, purple
    - Hex: #RRGGBB or RRGGBB
    - HSV: hsv:<H> where H is 0-360 degrees or 0-255

    Returns:
        (hue, saturation) both in 0-255 range
    """
    color = color.strip().lower()

    # Named color
    if color in NAMED_COLORS:
        return NAMED_COLORS[color], 255

    # HSV format: hsv:<H>
    if color.startswith("hsv:"):
        h_str = color[4:].strip()
        h_value = float(h_str)
        if h_value > 255:
            # Degrees (0-360) → 0-255
            if h_value == 360:
                return 0, 255
            return int((h_value / 360) * 255) % 256, 255
        return int(h_value) % 256, 255

    # Hex format: #RRGGBB or RRGGBB
    hex_match = re.match(r"^#?([0-9a-f]{6})$", color)
    if hex_match:
        hex_code = hex_match.group(1)
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return _rgb_to_hue(r, g, b), 255

    raise ValueError(f"Unknown color format: {color}")


def _rgb_to_hue(r: int, g: int, b: int) -> int:
    """Convert RGB to QMK hue (0-255)."""
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_val = max(r_norm, g_norm, b_norm)
    min_val = min(r_norm, g_norm, b_norm)
    delta = max_val - min_val

    if delta == 0:
        return 0

    if max_val == r_norm:
        hue_degrees = 60 * (((g_norm - b_norm) / delta) % 6)
    elif max_val == g_norm:
        hue_degrees = 60 * (((b_norm - r_norm) / delta) + 2)
    else:
        hue_degrees = 60 * (((r_norm - g_norm) / delta) + 4)

    if hue_degrees < 0:
        hue_degrees += 360

    return int((hue_degrees / 360) * 255) % 256


class KeyboardHID:
    """Persistent USB HID connection to QMK keyboard using VIA protocol."""

    def __init__(
        self,
        vid: int,
        pid: int,
        usage_page: int = 0xFF60,
        usage: int = 0x61,
    ):
        self.vid = vid
        self.pid = pid
        self.usage_page = usage_page
        self.usage = usage
        self._device = None

    def connect(self) -> bool:
        """Open HID device, filtering by usage_page/usage for RAW HID interface."""
        try:
            import hid
        except ImportError:
            logger.error("hidapi not installed. Install with: pip install hidapi")
            return False

        try:
            # Enumerate to find the correct interface (RAW HID)
            devices = hid.enumerate(self.vid, self.pid)
            target_path = None

            for dev_info in devices:
                if (dev_info.get("usage_page") == self.usage_page
                        and dev_info.get("usage") == self.usage):
                    target_path = dev_info["path"]
                    logger.debug(
                        f"Found RAW HID interface: "
                        f"usage_page=0x{self.usage_page:04X}, "
                        f"usage=0x{self.usage:02X}"
                    )
                    break

            if target_path is None:
                logger.warning(
                    f"No RAW HID interface found for "
                    f"VID=0x{self.vid:04X} PID=0x{self.pid:04X} "
                    f"(usage_page=0x{self.usage_page:04X}, usage=0x{self.usage:02X})"
                )
                return False

            device = hid.Device(path=target_path)
            self._device = device
            logger.info(
                f"Connected to keyboard: "
                f"VID=0x{self.vid:04X} PID=0x{self.pid:04X}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to keyboard: {e}")
            self._device = None
            return False

    def disconnect(self):
        """Close HID device."""
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
            logger.debug("Disconnected from keyboard")

    def is_connected(self) -> bool:
        """Check if device is still connected."""
        return self._device is not None

    def set_color(self, hue: int, saturation: int = 255, channel: int = 0) -> bool:
        """
        Send VIA set_color command.

        Args:
            hue: Hue value (0-255)
            saturation: Saturation value (0-255)
            channel: RGB channel (0 for first RGB module)

        Returns:
            True on success, False on failure
        """
        if self._device is None:
            return False

        # Build 32-byte VIA report
        report = bytearray(REPORT_SIZE)
        report[0] = VIA_SET_VALUE
        report[1] = channel
        report[2] = VIA_RGB_COLOR
        report[3] = hue
        report[4] = saturation

        try:
            # Prepend report ID 0x00 for hidapi
            self._device.write(bytes([0x00]) + bytes(report))
            return True
        except Exception as e:
            logger.error(f"Failed to send color: {e}")
            self._device = None  # Mark as disconnected
            return False

    def get_color(self, channel: int = 0) -> Optional[tuple[int, int]]:
        """
        Read current (hue, saturation) from keyboard.

        Returns:
            (hue, saturation) tuple or None on failure
        """
        if self._device is None:
            return None

        report = bytearray(REPORT_SIZE)
        report[0] = VIA_GET_VALUE
        report[1] = channel
        report[2] = VIA_RGB_COLOR

        try:
            self._device.write(bytes([0x00]) + bytes(report))
            response = self._device.read(REPORT_SIZE, timeout=1000)
            if response and len(response) >= 5:
                return response[3], response[4]
            return None
        except Exception as e:
            logger.error(f"Failed to get color: {e}")
            self._device = None
            return None

    def save(self, channel: int = 0) -> bool:
        """Save current settings to EEPROM."""
        if self._device is None:
            return False

        report = bytearray(REPORT_SIZE)
        report[0] = VIA_SAVE
        report[1] = channel
        report[2] = VIA_RGB_COLOR

        try:
            self._device.write(bytes([0x00]) + bytes(report))
            return True
        except Exception as e:
            logger.error(f"Failed to save: {e}")
            self._device = None
            return False
