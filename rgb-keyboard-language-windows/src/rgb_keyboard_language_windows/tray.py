"""System tray icon and menu using pystray."""

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from .config import get_config_path

logger = logging.getLogger("rgb_keyboard_language")


def create_color_icon(color: str, size: int = 32) -> Image.Image:
    """
    Create a colored icon for the tray.

    Args:
        color: Color name (e.g., "green", "red") or hex code (e.g., "#00ff00")
        size: Icon size in pixels (default: 32)

    Returns:
        PIL Image object
    """
    # Color mapping
    color_map = {
        "green": (0, 255, 0),
        "red": (255, 0, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "purple": (128, 0, 128),
    }

    # Parse color
    color_lower = color.lower().strip()
    if color_lower in color_map:
        rgb = color_map[color_lower]
    elif color_lower.startswith("#"):
        # Hex color
        hex_color = color_lower[1:]
        try:
            rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            rgb = (128, 128, 128)  # Gray fallback
    else:
        rgb = (128, 128, 128)  # Gray fallback

    # Create image
    image = Image.new("RGB", (size, size), rgb)
    draw = ImageDraw.Draw(image)

    # Add a border for better visibility
    border_color = tuple(max(0, c - 50) for c in rgb)
    draw.rectangle([0, 0, size - 1, size - 1], outline=border_color, width=2)

    return image


class TrayIcon:
    """System tray icon with menu."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_reload_config: Callable[[], None],
        on_toggle_enabled: Callable[[], bool],
    ):
        """
        Initialize tray icon.

        Args:
            on_quit: Callback when Quit is selected
            on_reload_config: Callback when Reload config is selected
            on_toggle_enabled: Callback when Start/Stop is toggled, returns new enabled state
        """
        self.on_quit = on_quit
        self.on_reload_config = on_reload_config
        self.on_toggle_enabled = on_toggle_enabled

        self.icon: Optional[pystray.Icon] = None
        self.current_lang: Optional[str] = None
        self.current_color: Optional[str] = None
        self.enabled: bool = True
        self._lock = threading.Lock()

        # Create initial icon (gray)
        self._create_icon()

    def _create_icon(self) -> None:
        """Create or recreate the tray icon."""
        color = self.current_color or "gray"
        icon_image = create_color_icon(color)
        menu = self._create_menu()

        if self.icon:
            self.icon.icon = icon_image
            self.icon.menu = menu
        else:
            self.icon = pystray.Icon("RGB Keyboard Language", icon_image, menu=menu)

    def _create_menu(self) -> pystray.Menu:
        """Create context menu for tray icon."""
        status_text = "Status: Unknown"
        if self.current_lang:
            color_text = self.current_color or "unknown"
            status_text = f"Status: {self.current_lang} ({color_text})"

        enabled_text = "Stop" if self.enabled else "Start"

        return pystray.Menu(
            pystray.MenuItem(status_text, lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                enabled_text,
                lambda: self._handle_toggle_enabled(),
            ),
            pystray.MenuItem(
                "Colors",
                pystray.Menu(
                    pystray.MenuItem(
                        "Open config",
                        lambda: self._handle_open_config(),
                    ),
                    pystray.MenuItem(
                        "Reload config",
                        lambda: self._handle_reload_config(),
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self._handle_quit()),
        )

    def _handle_toggle_enabled(self) -> None:
        """Handle Start/Stop toggle."""
        self.enabled = self.on_toggle_enabled()
        self._update_menu()

    def _handle_reload_config(self) -> None:
        """Handle Reload config."""
        self.on_reload_config()
        self._update_menu()

    def _handle_open_config(self) -> None:
        """Open config file in default editor."""
        config_path = get_config_path()
        try:
            if os.name == "nt":  # Windows
                os.startfile(str(config_path))
            else:
                subprocess.run(["xdg-open", str(config_path)])
        except Exception as e:
            logger.error(f"Failed to open config file: {e}")

    def _handle_quit(self) -> None:
        """Handle Quit menu item."""
        self.on_quit()

    def _update_menu(self) -> None:
        """Update menu items."""
        if self.icon:
            # Update menu by recreating it
            menu = self._create_menu()
            self.icon.menu = menu
            # Force menu update
            try:
                self.icon.update_menu()
            except AttributeError:
                # update_menu might not be available in all pystray versions
                pass

    def update_status(self, lang: Optional[str], color: Optional[str]) -> None:
        """
        Update tray icon status (thread-safe).

        Args:
            lang: Current language code
            color: Current color
        """
        with self._lock:
            changed = False
            if lang != self.current_lang:
                self.current_lang = lang
                changed = True
            if color != self.current_color:
                self.current_color = color
                changed = True

            if changed:
                self._create_icon()
                if self.icon:
                    # Update icon and menu
                    try:
                        self.icon.update_menu()
                    except AttributeError:
                        # update_menu might not be available in all pystray versions
                        pass

    def run(self) -> None:
        """Run the tray icon (blocking)."""
        if self.icon:
            self.icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self.icon:
            try:
                # Check if already stopped (if attribute exists)
                if hasattr(self.icon, '_running') and not self.icon._running:
                    logger.debug("Tray icon already stopped")
                    return
                self.icon.stop()
                logger.debug("Tray icon stopped")
            except Exception as e:
                logger.error(f"Error stopping tray icon: {e}", exc_info=True)
            finally:
                # Clear reference even if stop() failed
                self.icon = None

