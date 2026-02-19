"""Main entry point for rgb-keyboard-language-windows."""

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Support both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    # Add parent directory to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rgb_keyboard_language_windows.config import load_config, get_color_for_layout, save_config
    from rgb_keyboard_language_windows.hue_sender import HueSender
    from rgb_keyboard_language_windows.layout_win import WindowsLayoutDetector
    from rgb_keyboard_language_windows.logging_ import setup_logging
    from rgb_keyboard_language_windows.tray import TrayIcon
else:
    # Normal relative imports for module execution
    from .config import load_config, get_color_for_layout, save_config
    from .hue_sender import HueSender
    from .layout_win import WindowsLayoutDetector
    from .logging_ import setup_logging
    from .tray import TrayIcon

logger = logging.getLogger("rgb_keyboard_language")

# Global flag for preventing multiple shutdown attempts
_shutdown_initiated = False
_shutdown_lock = threading.Lock()


class KeyboardLayoutWatcher:
    """Watcher thread that monitors keyboard layout and sends color commands."""

    def __init__(
        self,
        layout_detector: WindowsLayoutDetector,
        hue_sender: HueSender,
        tray_icon: TrayIcon,
        config: dict,
    ):
        """
        Initialize watcher.

        Args:
            layout_detector: Layout detector instance
            hue_sender: Hue sender instance
            tray_icon: Tray icon instance
            config: Configuration dictionary
        """
        self.layout_detector = layout_detector
        self.hue_sender = hue_sender
        self.tray_icon = tray_icon
        self.config = config

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def update_hue_sender_params(
        self,
        vid: str,
        pid: str,
        step: int,
        delay_ms: int,
        rate_limit_ms: int,
    ) -> None:
        """
        Update hue sender parameters (thread-safe).

        Args:
            vid: Vendor ID
            pid: Product ID
            step: Step size
            delay_ms: Delay in milliseconds
            rate_limit_ms: Rate limit in milliseconds
        """
        with self._lock:
            self.hue_sender.vid = vid
            self.hue_sender.pid = pid
            self.hue_sender.step = step
            self.hue_sender.delay_ms = delay_ms
            self.hue_sender.rate_limit_ms = rate_limit_ms

    def start(self) -> None:
        """Start the watcher thread."""
        with self._lock:
            if self.running:
                return
            self.running = True
            self.thread = threading.Thread(target=self._watch_loop, daemon=True)
            self.thread.start()
            logger.info("Watcher thread started")

    def stop(self) -> None:
        """Stop the watcher thread."""
        with self._lock:
            if not self.running:
                return
            self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Watcher thread stopped")

    def update_config(self, new_config: dict) -> None:
        """
        Update configuration (thread-safe).

        Args:
            new_config: New configuration dictionary
        """
        with self._lock:
            self.config = new_config

    def _watch_loop(self) -> None:
        """Main watcher loop."""
        last_lang: Optional[str] = None
        last_color: Optional[str] = None

        # Send initial color on startup
        initial_sent = False

        while self.running:
            try:
                with self._lock:
                    poll_interval = self.config.get("poll_interval_ms", 150) / 1000.0
                    enabled = self.config.get("enabled", True)

                # Get current layout
                lang = self.layout_detector.get_current_layout()

                # Determine target color
                with self._lock:
                    target_color = get_color_for_layout(lang, self.config)

                # Update tray icon
                self.tray_icon.update_status(lang, target_color)

                # Send color if changed or on first run
                if enabled:
                    if target_color != last_color or not initial_sent:
                        logger.info(
                            f"Layout changed: {last_lang} -> {lang}, "
                            f"color: {last_color} -> {target_color}"
                        )
                        # send_color is non-blocking: returns True if submitted/deduped,
                        # False if skipped (rate limit/backoff) - will retry next poll
                        submitted = self.hue_sender.send_color(target_color)
                        if submitted:
                            last_color = target_color
                            initial_sent = True
                    else:
                        logger.debug(f"Layout unchanged: {lang}, color: {target_color}")

                last_lang = lang

                # Sleep
                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error in watcher loop: {e}", exc_info=True)
                time.sleep(1.0)  # Prevent tight error loop


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RGB Keyboard Language - Windows tray app for automatic keyboard RGB color"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to console",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger.info("Starting rgb-keyboard-language-windows")

    # Load config
    try:
        config = load_config()
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        sys.exit(1)

    # Create components
    try:
        device = config.get("device", {})
        vid = device.get("vid", "0x3434")
        pid = device.get("pid", "0x0011")
        usage_page_str = device.get("usage_page", "0xFF60")
        usage_str = device.get("usage", "0x61")
        step = config.get("step", 8)
        delay_ms = config.get("delay_ms", 15)
        rate_limit_ms = config.get("rate_limit_ms", 50)

        # Parse hex strings for usage_page/usage
        usage_page = int(usage_page_str, 16) if isinstance(usage_page_str, str) else int(usage_page_str)
        usage = int(usage_str, 16) if isinstance(usage_str, str) else int(usage_str)

        hue_sender = HueSender(
            vid=vid,
            pid=pid,
            usage_page=usage_page,
            usage=usage,
            step=step,
            delay_ms=delay_ms,
            rate_limit_ms=rate_limit_ms,
        )

        layout_detector = WindowsLayoutDetector()

        # Create tray icon first (callbacks will be set up after watcher)
        tray_icon = TrayIcon(
            on_quit=lambda: None,  # Will be set below
            on_reload_config=lambda: None,  # Will be set below
            on_toggle_enabled=lambda: True,  # Will be set below
        )

        watcher = KeyboardLayoutWatcher(
            layout_detector=layout_detector,
            hue_sender=hue_sender,
            tray_icon=tray_icon,
            config=config,
        )

        # Shutdown function (idempotent)
        def initiate_shutdown() -> None:
            """Initiate graceful shutdown (idempotent)."""
            global _shutdown_initiated
            
            with _shutdown_lock:
                if _shutdown_initiated:
                    logger.debug("Shutdown already initiated, ignoring")
                    return
                _shutdown_initiated = True
            
            def shutdown_thread():
                try:
                    logger.info("Starting graceful shutdown")
                    watcher.stop()
                    hue_sender.shutdown()
                    time.sleep(0.1)  # Give time for cleanup to complete
                    tray_icon.stop()
                    logger.info("Shutdown completed")
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}", exc_info=True)
                    try:
                        tray_icon.stop()
                    except:
                        pass
                    sys.exit(1)
            
            thread = threading.Thread(target=shutdown_thread, daemon=False, name="ShutdownThread")
            thread.start()

        # Tray icon callbacks (now that watcher exists)
        def on_quit() -> None:
            """Handle quit request - must be non-blocking."""
            logger.info("Quit requested from tray menu")
            initiate_shutdown()

        def on_reload_config() -> None:
            logger.info("Reloading configuration")
            try:
                new_config = load_config()
                watcher.update_config(new_config)

                # Update hue_sender parameters if changed
                new_device = new_config.get("device", {})
                new_vid = new_device.get("vid", "0x3434")
                new_pid = new_device.get("pid", "0x0011")
                new_step = new_config.get("step", 8)
                new_delay_ms = new_config.get("delay_ms", 15)
                new_rate_limit_ms = new_config.get("rate_limit_ms", 200)

                # Update hue_sender parameters
                watcher.update_hue_sender_params(
                    vid=new_vid,
                    pid=new_pid,
                    step=new_step,
                    delay_ms=new_delay_ms,
                    rate_limit_ms=new_rate_limit_ms,
                )
                logger.info("HueSender parameters updated")

                logger.info("Configuration reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload config: {e}", exc_info=True)

        def on_toggle_enabled() -> bool:
            logger.info("Toggling enabled state")
            try:
                config["enabled"] = not config.get("enabled", True)
                save_config(config)
                watcher.update_config(config)
                logger.info(f"Enabled state: {config['enabled']}")
                return config["enabled"]
            except Exception as e:
                logger.error(f"Failed to toggle enabled: {e}", exc_info=True)
                return config.get("enabled", True)

        # Update tray icon callbacks
        tray_icon.on_quit = on_quit
        tray_icon.on_reload_config = on_reload_config
        tray_icon.on_toggle_enabled = on_toggle_enabled

        # Setup signal handlers for graceful shutdown
        def setup_signal_handlers() -> None:
            """Setup signal handlers for graceful shutdown."""
            def signal_handler(signum, frame) -> None:
                logger.info(f"Received signal {signum}, shutting down gracefully")
                initiate_shutdown()

            # Setup POSIX signal handlers
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)

            # Windows-specific: handle CTRL_SHUTDOWN_EVENT
            if sys.platform == "win32":
                try:
                    import ctypes

                    CTRL_SHUTDOWN_EVENT = 6
                    HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

                    def windows_console_handler(ctrl_type: int) -> bool:
                        """Handle Windows console control events."""
                        if ctrl_type == CTRL_SHUTDOWN_EVENT:
                            logger.info("Received CTRL_SHUTDOWN_EVENT")
                            initiate_shutdown()
                            return True  # Indicate we handled the event
                        return False  # Let other handlers process other events

                    # Must keep reference to prevent garbage collection
                    _handler = HandlerRoutine(windows_console_handler)
                    ctypes.windll.kernel32.SetConsoleCtrlHandler(_handler, True)
                    logger.debug("Windows console control handler registered")
                except Exception:
                    logger.warning("Failed to register Windows shutdown handler")
            
            # atexit fallback for cleanup
            import atexit
            atexit.register(initiate_shutdown)

        # Setup signal handlers
        setup_signal_handlers()

        # Start watcher
        watcher.start()

        # Run tray icon (blocking)
        logger.info("Starting tray icon")
        try:
            tray_icon.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            initiate_shutdown()
        finally:
            # If we reach here without shutdown initiated, it means normal exit
            if not _shutdown_initiated:
                logger.info("Normal exit, performing cleanup")
                watcher.stop()
                hue_sender.shutdown()
            logger.info("Application stopped")

    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

