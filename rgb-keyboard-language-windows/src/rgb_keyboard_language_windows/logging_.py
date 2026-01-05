"""Logging configuration for rgb-keyboard-language-windows."""

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from .config import get_app_data_dir


def setup_logging(debug: bool = False) -> logging.Logger:
    """
    Setup logging to file and optionally to stdout.

    Args:
        debug: If True, also log to stdout

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("rgb_keyboard_language")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # File handler
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)
    log_file = app_data_dir / "app.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler (only in debug mode)
    if debug:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

