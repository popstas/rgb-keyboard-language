"""System tray icon and menu using ctypes Windows API."""

import ctypes
import ctypes.wintypes as wt
import logging
import os
import struct
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

from .config import get_config_path

logger = logging.getLogger("rgb_keyboard_language")

# --- Windows constants ---
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_GRAYED = 0x0001
MF_POPUP = 0x0010

WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

TPM_LEFTALIGN = 0x0000
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

IMAGE_ICON = 1
LR_DEFAULTCOLOR = 0x0000

DIB_RGB_COLORS = 0
BI_RGB = 0

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001

# LRESULT is pointer-sized (64-bit on Win64)
LRESULT = ctypes.c_longlong

# DLL references
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
gdi32 = ctypes.windll.gdi32

# Set DefWindowProcW signature for proper 64-bit parameter handling
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT

# --- Menu item IDs ---
IDM_STATUS = 1000
IDM_TOGGLE = 1001
IDM_OPEN_CONFIG = 1002
IDM_RELOAD_CONFIG = 1003
IDM_QUIT = 1004


# --- Structures ---
class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wt.DWORD * 3),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wt.BOOL),
        ("xHotspot", wt.DWORD),
        ("yHotspot", wt.DWORD),
        ("hbmMask", wt.HBITMAP),
        ("hbmColor", wt.HBITMAP),
    ]


# --- Color helpers ---
COLOR_MAP = {
    "green": (0, 255, 0),
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "purple": (128, 0, 128),
    "gray": (128, 128, 128),
}


def _parse_color(color: str) -> tuple:
    """Parse a color string to (r, g, b) tuple."""
    color_lower = color.lower().strip()
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    if color_lower.startswith("#"):
        hex_color = color_lower[1:]
        try:
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            pass
    return (128, 128, 128)


def _create_color_hicon(color: str, size: int = 32):
    """Create an HICON with the given color (solid fill with darker border)."""
    r, g, b = _parse_color(color)
    br = max(0, r - 50)
    bg = max(0, g - 50)
    bb = max(0, b - 50)

    # Create DIB section for the color bitmap
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size  # Top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    hdc = user32.GetDC(0)
    bits = ctypes.c_void_p()
    hbm_color = gdi32.CreateDIBSection(
        hdc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
    )

    if hbm_color and bits:
        # Fill pixel data: BGRA format
        pixel_data = (ctypes.c_uint8 * (size * size * 4)).from_address(bits.value)
        for y in range(size):
            for x in range(size):
                offset = (y * size + x) * 4
                # Border: 2px
                if x < 2 or x >= size - 2 or y < 2 or y >= size - 2:
                    pixel_data[offset] = bb      # B
                    pixel_data[offset + 1] = bg  # G
                    pixel_data[offset + 2] = br  # R
                    pixel_data[offset + 3] = 255  # A
                else:
                    pixel_data[offset] = b        # B
                    pixel_data[offset + 1] = g    # G
                    pixel_data[offset + 2] = r    # R
                    pixel_data[offset + 3] = 255  # A

    # Create monochrome mask bitmap (all opaque)
    hbm_mask = gdi32.CreateBitmap(size, size, 1, 1, None)

    # Create icon
    icon_info = ICONINFO()
    icon_info.fIcon = True
    icon_info.xHotspot = 0
    icon_info.yHotspot = 0
    icon_info.hbmMask = hbm_mask
    icon_info.hbmColor = hbm_color

    hicon = user32.CreateIconIndirect(ctypes.byref(icon_info))

    # Cleanup bitmaps (icon keeps a copy)
    gdi32.DeleteObject(hbm_color)
    gdi32.DeleteObject(hbm_mask)
    user32.ReleaseDC(0, hdc)

    return hicon


class TrayIcon:
    """System tray icon with menu using ctypes Windows API."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_reload_config: Callable[[], None],
        on_toggle_enabled: Callable[[], bool],
    ):
        self.on_quit = on_quit
        self.on_reload_config = on_reload_config
        self.on_toggle_enabled = on_toggle_enabled

        self.current_lang: Optional[str] = None
        self.current_color: Optional[str] = None
        self.enabled: bool = True
        self._lock = threading.Lock()

        self._hwnd: Optional[int] = None
        self._hicon: Optional[int] = None
        self._nid: Optional[NOTIFYICONDATAW] = None
        self._class_atom = None
        self._wndproc = None  # prevent GC
        self._icon_cache: dict[str, int] = {}  # color -> HICON handle

    def _build_menu(self):
        """Build and return an HMENU for the popup context menu."""
        hmenu = user32.CreatePopupMenu()

        # Status line (grayed)
        status_text = "Status: Unknown"
        if self.current_lang:
            color_text = self.current_color or "unknown"
            status_text = f"Status: {self.current_lang} ({color_text})"
        user32.AppendMenuW(hmenu, MF_STRING | MF_GRAYED, IDM_STATUS, status_text)

        # Separator
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        # Start/Stop
        enabled_text = "Stop" if self.enabled else "Start"
        user32.AppendMenuW(hmenu, MF_STRING, IDM_TOGGLE, enabled_text)

        # Colors submenu
        hsubmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hsubmenu, MF_STRING, IDM_OPEN_CONFIG, "Open config")
        user32.AppendMenuW(hsubmenu, MF_STRING, IDM_RELOAD_CONFIG, "Reload config")
        user32.AppendMenuW(hmenu, MF_STRING | MF_POPUP, hsubmenu, "Colors")

        # Separator
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        # Quit
        user32.AppendMenuW(hmenu, MF_STRING, IDM_QUIT, "Quit")

        return hmenu

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure for the hidden tray window."""
        if msg == WM_TRAYICON:
            if lparam == WM_RBUTTONUP:
                # Show context menu
                hmenu = self._build_menu()
                pt = wt.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.SetForegroundWindow(hwnd)
                cmd = user32.TrackPopupMenu(
                    hmenu,
                    TPM_LEFTALIGN | TPM_RETURNCMD | TPM_NONOTIFY,
                    pt.x, pt.y, 0, hwnd, None,
                )
                user32.DestroyMenu(hmenu)
                if cmd == IDM_TOGGLE:
                    self._handle_toggle_enabled()
                elif cmd == IDM_OPEN_CONFIG:
                    self._handle_open_config()
                elif cmd == IDM_RELOAD_CONFIG:
                    self._handle_reload_config()
                elif cmd == IDM_QUIT:
                    self._handle_quit()
                return 0
        elif msg == WM_DESTROY:
            self._remove_icon()
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _handle_toggle_enabled(self) -> None:
        self.enabled = self.on_toggle_enabled()

    def _handle_reload_config(self) -> None:
        self.on_reload_config()

    def _handle_open_config(self) -> None:
        config_path = get_config_path()
        try:
            if os.name == "nt":
                os.startfile(str(config_path))
            else:
                subprocess.run(["xdg-open", str(config_path)])
        except Exception as e:
            logger.error(f"Failed to open config file: {e}")

    def _handle_quit(self) -> None:
        self.on_quit()

    def _add_icon(self) -> None:
        """Add the tray icon via Shell_NotifyIconW."""
        color = self.current_color or "gray"
        self._hicon = self._get_cached_hicon(color)

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = "RGB Keyboard Language"
        self._nid = nid

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _get_cached_hicon(self, color: str) -> int:
        """Get or create a cached HICON for the given color."""
        if color not in self._icon_cache:
            self._icon_cache[color] = _create_color_hicon(color)
        return self._icon_cache[color]

    def _modify_icon(self, color: str) -> None:
        """Update the tray icon color."""
        if not self._nid or not self._hwnd:
            return

        self._hicon = self._get_cached_hicon(color)
        self._nid.hIcon = self._hicon
        self._nid.uFlags = NIF_ICON | NIF_TIP

        tip = "RGB Keyboard Language"
        if self.current_lang:
            color_text = self.current_color or "unknown"
            tip = f"RGB: {self.current_lang} ({color_text})"
        # Update tooltip (max 127 chars, ctypes handles null-termination)
        self._nid.szTip = tip[:127]

        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _remove_icon(self) -> None:
        """Remove the tray icon and destroy all cached icons."""
        if self._nid:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
        # Destroy all cached icons
        for cached_hicon in self._icon_cache.values():
            user32.DestroyIcon(cached_hicon)
        self._icon_cache.clear()
        self._hicon = None

    def update_status(self, lang: Optional[str], color: Optional[str]) -> None:
        """Update tray icon status (thread-safe)."""
        with self._lock:
            changed = False
            if lang != self.current_lang:
                self.current_lang = lang
                changed = True
            if color != self.current_color:
                self.current_color = color
                changed = True

            if changed and self._hwnd and color:
                self._modify_icon(color)

    def run(self) -> None:
        """Run the tray icon message loop (blocking)."""
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self._wndproc = WNDPROC(self._wnd_proc)

        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "RGBKeyboardLanguageTray"

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinstance
        wc.lpszClassName = class_name

        self._class_atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not self._class_atom:
            logger.error("Failed to register window class")
            return

        self._hwnd = user32.CreateWindowExW(
            0, class_name, "RGB Keyboard Language Tray",
            0,  # WS_OVERLAPPED but invisible
            0, 0, 0, 0,
            0, 0, hinstance, None,
        )
        if not self._hwnd:
            logger.error("Failed to create hidden window")
            return

        self._add_icon()
        logger.info("Tray icon created")

        # Message loop
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        logger.info("Tray message loop ended")

    def stop(self) -> None:
        """Stop the tray icon by posting WM_CLOSE to the hidden window."""
        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
                logger.debug("Tray icon stop requested")
            except Exception as e:
                logger.error(f"Error stopping tray icon: {e}", exc_info=True)
            finally:
                self._hwnd = None
