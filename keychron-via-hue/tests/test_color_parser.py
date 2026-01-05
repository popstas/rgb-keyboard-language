"""Tests for color_parser module."""

import pytest

from keychron_via_hue import color_parser


class TestNamedColors:
    """Tests for named color parsing."""

    def test_red(self):
        assert color_parser.parse_color("red") == 0

    def test_yellow(self):
        assert color_parser.parse_color("yellow") == 42

    def test_green(self):
        assert color_parser.parse_color("green") == 85

    def test_cyan(self):
        assert color_parser.parse_color("cyan") == 128

    def test_blue(self):
        assert color_parser.parse_color("blue") == 170

    def test_purple(self):
        assert color_parser.parse_color("purple") == 213

    def test_case_insensitive(self):
        assert color_parser.parse_color("RED") == 0
        assert color_parser.parse_color("Green") == 85
        assert color_parser.parse_color("  BLUE  ") == 170


class TestHexColors:
    """Tests for hex color parsing."""

    def test_hex_with_hash(self):
        # Зеленый #00ff00 -> hue примерно 85 (120°)
        hue = color_parser.parse_color("#00ff00")
        assert 80 <= hue <= 90

    def test_hex_without_hash(self):
        # Красный ff0000 -> hue 0
        hue = color_parser.parse_color("ff0000")
        assert hue == 0 or hue == 255  # Может быть 0 или 255 из-за округления

    def test_hex_blue(self):
        # Синий 0000ff -> hue примерно 170 (240°)
        hue = color_parser.parse_color("#0000ff")
        assert 165 <= hue <= 175

    def test_hex_lowercase(self):
        hue1 = color_parser.parse_color("#FF0000")
        hue2 = color_parser.parse_color("#ff0000")
        assert hue1 == hue2


class TestHsvColors:
    """Tests for HSV color parsing."""

    def test_hsv_degrees(self):
        # Если значение <= 255, интерпретируем как прямое значение 0..255
        # 0 -> 0
        assert color_parser.parse_color("hsv:0") == 0
        # 120 -> 120 (прямое значение, не градусы)
        assert color_parser.parse_color("hsv:120") == 120
        # Для градусов нужно значение > 255
        # 360° -> 0 (специальная обработка для 360)
        assert color_parser.parse_color("hsv:360") == 0
        # 300° в градусах -> 213 (300/360 * 255)
        hue_300_deg = color_parser.parse_color("hsv:300")  # 300 > 255, значит градусы
        assert 210 <= hue_300_deg <= 215  # Примерно 213
        # 120° в градусах -> 85 (120/360 * 255), но нужно значение > 255
        # Используем значение больше 255 для проверки конвертации градусов
        # Для проверки 120° используем значение > 255, например 120.1 не подойдет
        # Используем 300° как пример

    def test_hsv_direct_value(self):
        # Прямое значение 0..255
        assert color_parser.parse_color("hsv:85") == 85
        assert color_parser.parse_color("hsv:255") == 255

    def test_hsv_case_insensitive(self):
        # 120 как прямое значение (<= 255)
        assert color_parser.parse_color("HSV:120") == 120
        assert color_parser.parse_color("  hsv:0  ") == 0


class TestRgbToHue:
    """Tests for RGB to hue conversion."""

    def test_red(self):
        assert color_parser.rgb_to_hue(255, 0, 0) == 0

    def test_green(self):
        hue = color_parser.rgb_to_hue(0, 255, 0)
        assert 80 <= hue <= 90  # Примерно 85 (120°)

    def test_blue(self):
        hue = color_parser.rgb_to_hue(0, 0, 255)
        assert 165 <= hue <= 175  # Примерно 170 (240°)

    def test_yellow(self):
        hue = color_parser.rgb_to_hue(255, 255, 0)
        assert 40 <= hue <= 45  # Примерно 42 (60°)

    def test_white_gray(self):
        # Белый/серый -> hue = 0 (неопределенный оттенок)
        assert color_parser.rgb_to_hue(255, 255, 255) == 0
        assert color_parser.rgb_to_hue(128, 128, 128) == 0

    def test_clamping(self):
        # Значения за пределами 0..255 должны быть зажаты
        assert 0 <= color_parser.rgb_to_hue(-10, 300, 0) <= 255


class TestInvalidColors:
    """Tests for invalid color formats."""

    def test_unknown_named_color(self):
        with pytest.raises(ValueError, match="Unknown color format"):
            color_parser.parse_color("unknown")

    def test_invalid_hex(self):
        with pytest.raises(ValueError, match="Unknown color format"):
            color_parser.parse_color("#gggggg")
        with pytest.raises(ValueError, match="Unknown color format"):
            color_parser.parse_color("#ff00")  # Неполный hex

    def test_invalid_hsv(self):
        with pytest.raises(ValueError):
            color_parser.parse_color("hsv:abc")
        with pytest.raises(ValueError, match="out of range"):
            color_parser.parse_color("hsv:400")  # > 360
        with pytest.raises(ValueError, match="negative"):
            color_parser.parse_color("hsv:-10")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            color_parser.parse_color("")

