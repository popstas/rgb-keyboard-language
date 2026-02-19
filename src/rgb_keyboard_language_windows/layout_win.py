"""Windows implementation of keyboard layout detection."""

import ctypes
import logging
from ctypes import wintypes

from .layout_base import LayoutDetector

logger = logging.getLogger("rgb_keyboard_language")

# Windows API constants
WM_INPUTLANGCHANGEREQUEST = 0x0050

# Windows API function signatures
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# GetForegroundWindow
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

# GetWindowThreadProcessId
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

# GetKeyboardLayout
user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
user32.GetKeyboardLayout.restype = wintypes.HKL

# LCIDToLocaleName
kernel32.LCIDToLocaleName.argtypes = [
    wintypes.LCID,
    ctypes.c_wchar_p,
    ctypes.c_int,
    wintypes.DWORD,
]
kernel32.LCIDToLocaleName.restype = ctypes.c_int

LOCALE_NAME_MAX_LENGTH = 85


# Common LCID to language code mapping (fallback)
LCID_TO_LANG: dict[int, str] = {
    0x0409: "en-US",  # English (United States)
    0x0809: "en-GB",  # English (United Kingdom)
    0x0419: "ru-RU",  # Russian (Russia)
    0x043F: "kk-KZ",  # Kazakh (Kazakhstan)
    0x0411: "ja-JP",  # Japanese (Japan)
    0x0804: "zh-CN",  # Chinese (Simplified, China)
    0x0404: "zh-TW",  # Chinese (Traditional, Taiwan)
    0x0407: "de-DE",  # German (Germany)
    0x040C: "fr-FR",  # French (France)
    0x0410: "it-IT",  # Italian (Italy)
    0x040A: "es-ES",  # Spanish (Spain)
    0x0415: "pl-PL",  # Polish (Poland)
    0x0416: "pt-BR",  # Portuguese (Brazil)
    0x0418: "ro-RO",  # Romanian (Romania)
    0x041C: "sq-AL",  # Albanian (Albania)
    0x0422: "uk-UA",  # Ukrainian (Ukraine)
    0x0423: "be-BY",  # Belarusian (Belarus)
}


def get_lcid_from_hkl(hkl: int) -> int:
    """
    Extract LCID from HKL (Keyboard Layout Handle).

    Args:
        hkl: HKL value

    Returns:
        LCID (Language Code Identifier)
    """
    # HKL is typically a 32-bit value where low 16 bits are LCID
    return hkl & 0xFFFF


def lcid_to_locale_name(lcid: int) -> str | None:
    """
    Convert LCID to BCP-47 locale name using Windows API.

    Args:
        lcid: Language Code Identifier

    Returns:
        BCP-47 locale name (e.g., "en-US") or None if conversion fails
    """
    try:
        buffer = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        result = kernel32.LCIDToLocaleName(
            lcid,
            buffer,
            LOCALE_NAME_MAX_LENGTH,
            0,  # LOCALE_ALLOW_NEUTRAL_NAMES
        )
        if result > 0:
            locale_name = buffer.value
            # Convert Windows locale name to BCP-47 if needed
            # Windows returns format like "en-US", which is already BCP-47
            return locale_name if locale_name else None
    except Exception as e:
        logger.debug(f"LCIDToLocaleName failed for LCID {lcid:04X}: {e}")

    return None


def lcid_to_lang_fallback(lcid: int) -> str | None:
    """
    Convert LCID to language code using fallback mapping.

    Args:
        lcid: Language Code Identifier

    Returns:
        BCP-47 language code or None if not found
    """
    return LCID_TO_LANG.get(lcid)


class WindowsLayoutDetector(LayoutDetector):
    """Windows implementation of layout detection using Win32 API."""

    def get_current_layout(self) -> str | None:
        """
        Get current keyboard layout of foreground window.

        Returns:
            BCP-47 language code (e.g., "en-US", "ru-RU") or None if detection fails
        """
        try:
            # Get foreground window
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                logger.debug("GetForegroundWindow returned NULL")
                return None

            # Get thread ID
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            if not thread_id:
                logger.debug("GetWindowThreadProcessId returned 0")
                return None

            # Get keyboard layout
            hkl = user32.GetKeyboardLayout(thread_id)
            if not hkl:
                logger.debug("GetKeyboardLayout returned NULL")
                return None

            # Extract LCID
            lcid = get_lcid_from_hkl(hkl)
            logger.debug(f"Detected HKL: {hkl:08X}, LCID: {lcid:04X}")

            # Try Windows API first
            locale_name = lcid_to_locale_name(lcid)
            if locale_name:
                logger.debug(f"Got locale name from API: {locale_name}")
                return locale_name

            # Fallback to mapping
            lang_code = lcid_to_lang_fallback(lcid)
            if lang_code:
                logger.debug(f"Got language code from fallback: {lang_code}")
                return lang_code

            # If we have LCID but no mapping, try to construct basic code
            # Extract language part from LCID (low 10 bits)
            lang_id = lcid & 0x03FF
            if lang_id == 0x0009:  # English
                return "en"
            elif lang_id == 0x0019:  # Russian
                return "ru"
            elif lang_id == 0x003F:  # Kazakh
                return "kk"

            logger.warning(f"Unknown LCID: {lcid:04X}, could not determine language")
            return None

        except Exception as e:
            logger.error(f"Error detecting keyboard layout: {e}", exc_info=True)
            return None

