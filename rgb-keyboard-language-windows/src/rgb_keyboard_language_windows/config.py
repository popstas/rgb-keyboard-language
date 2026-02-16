"""Configuration management for rgb-keyboard-language-windows."""

import json
import os
from pathlib import Path
from typing import Any

# Default configuration values
DEFAULT_CONFIG = {
    "device": {
        "vid": "0x3434",
        "pid": "0x0011",
        "usage_page": "0xFF60",
        "usage": "0x61",
    },
    "step": 8,
    "delay_ms": 15,
    "layout_colors": {
        "en": "green",
    },
    "default_color": "red",
    "poll_interval_ms": 100,
    "rate_limit_ms": 50,
    "enabled": True,
}


def get_app_data_dir() -> Path:
    """
    Get application data directory.

    Returns:
        Path to %APPDATA%/rgb-keyboard-language-windows
    """
    appdata = os.getenv("APPDATA")
    if not appdata:
        # Fallback for non-Windows (though this is Windows-only app)
        appdata = os.path.expanduser("~/.config")
    return Path(appdata) / "rgb-keyboard-language-windows"


def get_config_path() -> Path:
    """
    Get path to config.json file.

    Returns:
        Path to config.json
    """
    return get_app_data_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """
    Load configuration from file, creating default if missing.

    Returns:
        Configuration dictionary
    """
    config_path = get_config_path()
    app_data_dir = config_path.parent

    # Create directory if it doesn't exist
    app_data_dir.mkdir(parents=True, exist_ok=True)

    # Load config or create default
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config)
            return merged_config
        except (json.JSONDecodeError, IOError) as e:
            # If config is corrupted, create new one
            config = DEFAULT_CONFIG.copy()
            save_config(config)
            return config
    else:
        # Create default config
        config = DEFAULT_CONFIG.copy()
        save_config(config)
        return config


def save_config(config: dict[str, Any]) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary to save
    """
    config_path = get_config_path()
    app_data_dir = config_path.parent

    # Create directory if it doesn't exist
    app_data_dir.mkdir(parents=True, exist_ok=True)

    # Validate and save
    validated_config = validate_config(config)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(validated_config, f, indent=2, ensure_ascii=False)


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and normalize configuration values.

    Args:
        config: Configuration dictionary to validate

    Returns:
        Validated configuration dictionary
    """
    validated = DEFAULT_CONFIG.copy()
    validated.update(config)

    # Validate device
    if "device" in config:
        device = config["device"]
        if isinstance(device, dict):
            validated["device"] = {
                "vid": str(device.get("vid", DEFAULT_CONFIG["device"]["vid"])),
                "pid": str(device.get("pid", DEFAULT_CONFIG["device"]["pid"])),
                "usage_page": str(device.get("usage_page", DEFAULT_CONFIG["device"]["usage_page"])),
                "usage": str(device.get("usage", DEFAULT_CONFIG["device"]["usage"])),
            }

    # Validate numeric values
    for key in ["step", "delay_ms", "poll_interval_ms", "rate_limit_ms"]:
        if key in config:
            try:
                value = int(config[key])
                if value < 0:
                    value = DEFAULT_CONFIG[key]
                validated[key] = value
            except (ValueError, TypeError):
                validated[key] = DEFAULT_CONFIG[key]

    # Validate boolean
    if "enabled" in config:
        validated["enabled"] = bool(config.get("enabled", True))

    # Validate colors
    if "layout_colors" in config and isinstance(config["layout_colors"], dict):
        validated["layout_colors"] = config["layout_colors"]

    if "default_color" in config:
        validated["default_color"] = str(config["default_color"])

    return validated


def get_color_for_layout(lang_code: str | None, config: dict[str, Any]) -> str:
    """
    Get color for given language code based on configuration.

    Matching order:
    1. Exact match (e.g., "en-US")
    2. Prefix match (e.g., "en")
    3. Default color

    Args:
        lang_code: BCP-47 language code (e.g., "en-US", "ru-RU") or None
        config: Configuration dictionary

    Returns:
        Color string (e.g., "green", "red", "#00ff00")
    """
    if not lang_code:
        return config.get("default_color", "red")

    layout_colors = config.get("layout_colors", {})
    default_color = config.get("default_color", "red")

    # Try exact match first
    if lang_code in layout_colors:
        return layout_colors[lang_code]

    # Try prefix match (e.g., "en" for "en-US")
    lang_prefix = lang_code.split("-")[0].lower()
    if lang_prefix in layout_colors:
        return layout_colors[lang_prefix]

    # Fallback to default
    return default_color

