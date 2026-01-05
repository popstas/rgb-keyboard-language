"""Parsing and conversion of color formats to hue value (0..255)."""

import re


# Именованные цвета и их hue значения (HSV H в градусах)
# Hue в HSV: 0° = красный, 60° = желтый, 120° = зеленый, 180° = cyan,
# 240° = синий, 300° = пурпурный
# Для конвертации в 0..255: hue_255 = (hue_degrees / 360) * 255
NAMED_COLORS = {
    "red": 0,      # 0°
    "yellow": 42,  # 60° / 360 * 255 ≈ 42
    "green": 85,   # 120° / 360 * 255 ≈ 85
    "cyan": 128,   # 180° / 360 * 255 = 128
    "blue": 170,   # 240° / 360 * 255 ≈ 170
    "purple": 213, # 300° / 360 * 255 ≈ 213
}


def parse_color(color_str: str) -> int:
    """
    Парсит строку цвета и возвращает hue значение в диапазоне 0..255.

    Поддерживаемые форматы:
    - именованный цвет: red, green, blue, yellow, cyan, purple
    - hex: #RRGGBB или RRGGBB
    - hsv: hsv:<H> где H в градусах 0..360 или в единицах 0..255

    Args:
        color_str: Строка с цветом

    Returns:
        Hue значение в диапазоне 0..255

    Raises:
        ValueError: Если цвет не может быть распарсен
    """
    color_str = color_str.strip().lower()

    # Именованный цвет
    if color_str in NAMED_COLORS:
        return NAMED_COLORS[color_str]

    # HSV формат: hsv:<H>
    if color_str.startswith("hsv:"):
        h_str = color_str[4:].strip()
        try:
            h_value = float(h_str)
            # Если значение > 255, считаем что это градусы (0..360)
            if h_value > 255:
                if h_value > 360:
                    raise ValueError(f"HSV hue value {h_value} is out of range (0..360 degrees)")
                # Конвертируем градусы в 0..255
                hue_result = int((h_value / 360) * 255) % 256
                # Если результат 255 и значение было 360, возвращаем 0 (циклический характер)
                if h_value == 360:
                    return 0
                return hue_result
            else:
                # Уже в диапазоне 0..255
                if h_value < 0:
                    raise ValueError(f"HSV hue value {h_value} is negative")
                return int(h_value) % 256
        except ValueError as e:
            if "out of range" in str(e) or "negative" in str(e):
                raise
            raise ValueError(f"Invalid HSV hue value: {h_str}") from e

    # HEX формат: #RRGGBB или RRGGBB
    hex_match = re.match(r"^#?([0-9a-f]{6})$", color_str)
    if hex_match:
        hex_code = hex_match.group(1)
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return rgb_to_hue(r, g, b)

    raise ValueError(f"Unknown color format: {color_str}")


def rgb_to_hue(r: int, g: int, b: int) -> int:
    """
    Конвертирует RGB в HSV hue (0..255).

    Args:
        r: Красный компонент (0..255)
        g: Зеленый компонент (0..255)
        b: Синий компонент (0..255)

    Returns:
        Hue значение в диапазоне 0..255
    """
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    # Конвертация RGB в HSV
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_val = max(r_norm, g_norm, b_norm)
    min_val = min(r_norm, g_norm, b_norm)
    delta = max_val - min_val

    # Если все компоненты равны, hue = 0 (оттенок серого)
    if delta == 0:
        return 0

    # Вычисляем hue в градусах (0..360)
    if max_val == r_norm:
        hue_degrees = 60 * (((g_norm - b_norm) / delta) % 6)
    elif max_val == g_norm:
        hue_degrees = 60 * (((b_norm - r_norm) / delta) + 2)
    else:  # max_val == b_norm
        hue_degrees = 60 * (((r_norm - g_norm) / delta) + 4)

    # Нормализуем в диапазон 0..360
    if hue_degrees < 0:
        hue_degrees += 360

    # Конвертируем в 0..255
    return int((hue_degrees / 360) * 255) % 256

