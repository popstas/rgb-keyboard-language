"""Tests for config module."""

import json
import tempfile
from pathlib import Path

import pytest

from rgb_keyboard_language_windows.config import (
    DEFAULT_CONFIG,
    get_config_path,
    load_config,
    save_config,
    validate_config,
    get_color_for_layout,
)


def test_default_config():
    """Test that default config has all required keys."""
    assert "device" in DEFAULT_CONFIG
    assert "vid" in DEFAULT_CONFIG["device"]
    assert "pid" in DEFAULT_CONFIG["device"]
    assert "step" in DEFAULT_CONFIG
    assert "delay_ms" in DEFAULT_CONFIG
    assert "layout_colors" in DEFAULT_CONFIG
    assert "default_color" in DEFAULT_CONFIG
    assert "poll_interval_ms" in DEFAULT_CONFIG
    assert "rate_limit_ms" in DEFAULT_CONFIG
    assert "enabled" in DEFAULT_CONFIG


def test_validate_config():
    """Test config validation."""
    # Valid config
    config = {
        "device": {"vid": "0x1234", "pid": "0x5678"},
        "step": 4,
        "delay_ms": 20,
        "enabled": False,
    }
    validated = validate_config(config)
    assert validated["device"]["vid"] == "0x1234"
    assert validated["device"]["pid"] == "0x5678"
    assert validated["step"] == 4
    assert validated["delay_ms"] == 20
    assert validated["enabled"] is False

    # Invalid numeric values should fall back to defaults
    config_invalid = {
        "step": -5,
        "delay_ms": "not a number",
    }
    validated = validate_config(config_invalid)
    assert validated["step"] == DEFAULT_CONFIG["step"]
    assert validated["delay_ms"] == DEFAULT_CONFIG["delay_ms"]


def test_save_and_load_config(tmp_path, monkeypatch):
    """Test saving and loading config."""
    # Mock app data directory
    monkeypatch.setattr(
        "rgb_keyboard_language_windows.config.get_app_data_dir",
        lambda: tmp_path,
    )

    config = {
        "device": {"vid": "0x1234", "pid": "0x5678"},
        "step": 4,
        "enabled": False,
    }

    save_config(config)
    assert (tmp_path / "config.json").exists()

    loaded = load_config()
    assert loaded["device"]["vid"] == "0x1234"
    assert loaded["device"]["pid"] == "0x5678"
    assert loaded["step"] == 4
    assert loaded["enabled"] is False


def test_load_config_creates_default(tmp_path, monkeypatch):
    """Test that loading non-existent config creates default."""
    # Mock app data directory
    monkeypatch.setattr(
        "rgb_keyboard_language_windows.config.get_app_data_dir",
        lambda: tmp_path,
    )

    assert not (tmp_path / "config.json").exists()

    config = load_config()
    assert (tmp_path / "config.json").exists()
    assert config == DEFAULT_CONFIG


def test_get_color_for_layout():
    """Test color matching logic."""
    config = {
        "layout_colors": {
            "en-US": "blue",
            "en": "green",
            "ru": "red",
        },
        "default_color": "yellow",
    }

    # Exact match
    assert get_color_for_layout("en-US", config) == "blue"

    # Prefix match
    assert get_color_for_layout("en-GB", config) == "green"

    # Another prefix match
    assert get_color_for_layout("ru-RU", config) == "red"

    # Fallback to default
    assert get_color_for_layout("fr-FR", config) == "yellow"

    # None language
    assert get_color_for_layout(None, config) == "yellow"

    # Empty config
    empty_config = {"default_color": "red"}
    assert get_color_for_layout("en-US", empty_config) == "red"

