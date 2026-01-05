"""Tests for color matching logic."""

import pytest

from rgb_keyboard_language_windows.config import get_color_for_layout


def test_exact_match():
    """Test exact language code matching."""
    config = {
        "layout_colors": {
            "en-US": "green",
            "ru-RU": "red",
        },
        "default_color": "blue",
    }

    assert get_color_for_layout("en-US", config) == "green"
    assert get_color_for_layout("ru-RU", config) == "red"


def test_prefix_match():
    """Test prefix matching (e.g., 'en' for 'en-US')."""
    config = {
        "layout_colors": {
            "en": "green",
            "ru": "red",
        },
        "default_color": "blue",
    }

    assert get_color_for_layout("en-US", config) == "green"
    assert get_color_for_layout("en-GB", config) == "green"
    assert get_color_for_layout("ru-RU", config) == "red"
    assert get_color_for_layout("ru-BY", config) == "red"


def test_fallback_to_default():
    """Test fallback to default color."""
    config = {
        "layout_colors": {
            "en": "green",
        },
        "default_color": "red",
    }

    assert get_color_for_layout("fr-FR", config) == "red"
    assert get_color_for_layout("de-DE", config) == "red"
    assert get_color_for_layout(None, config) == "red"


def test_priority_exact_over_prefix():
    """Test that exact match takes priority over prefix match."""
    config = {
        "layout_colors": {
            "en": "green",
            "en-US": "blue",
        },
        "default_color": "red",
    }

    assert get_color_for_layout("en-US", config) == "blue"  # Exact match
    assert get_color_for_layout("en-GB", config) == "green"  # Prefix match


def test_case_insensitive():
    """Test that prefix matching is case-insensitive (normalized to lowercase)."""
    config = {
        "layout_colors": {
            "en": "green",
        },
        "default_color": "red",
    }

    # Prefix matching normalizes to lowercase
    assert get_color_for_layout("EN-US", config) == "green"  # Match (normalized)
    assert get_color_for_layout("en-US", config) == "green"  # Match
    assert get_color_for_layout("En-Gb", config) == "green"  # Match (normalized)


def test_hex_colors():
    """Test that hex colors work in config."""
    config = {
        "layout_colors": {
            "en": "#00ff00",
            "ru": "#ff0000",
        },
        "default_color": "#0000ff",
    }

    assert get_color_for_layout("en-US", config) == "#00ff00"
    assert get_color_for_layout("ru-RU", config) == "#ff0000"
    assert get_color_for_layout("fr-FR", config) == "#0000ff"

