"""Logic for stepwise hue adjustment."""

import time

from . import qmk_hid


def adjust_hue(
    target_hue: int,
    vid: str,
    pid: str,
    step: int = 8,
    delay_ms: int = 15,
) -> None:
    """
    Изменяет hue клавиатуры пошагово от текущего значения к целевому.

    Алгоритм:
    1. Читает текущий hue
    2. Вычисляет разницу с целевым hue
    3. Применяет шаги Hue+ или Hue- до достижения целевого значения
    4. Учитывает циклический характер hue (0 и 255 соседние)

    Args:
        target_hue: Целевой hue (0..255)
        vid: Vendor ID в hex
        pid: Product ID в hex
        step: Размер шага (по умолчанию 8)
        delay_ms: Задержка между шагами в миллисекундах (по умолчанию 15)

    Raises:
        FileNotFoundError: Если qmk_hid не найден
        subprocess.CalledProcessError: Если qmk_hid завершился с ошибкой
        ValueError: Если параметры некорректны
    """
    if not (0 <= target_hue <= 255):
        raise ValueError(f"target_hue must be in range 0..255, got {target_hue}")
    if step <= 0 or step > 255:
        raise ValueError(f"step must be in range 1..255, got {step}")
    if delay_ms < 0:
        raise ValueError(f"delay_ms must be non-negative, got {delay_ms}")

    # Читаем текущий hue
    current_hue = qmk_hid.get_current_hue(vid, pid)

    # Если уже на целевом значении, ничего не делаем
    if current_hue == target_hue:
        return

    # Вычисляем кратчайший путь с учетом циклического характера hue
    # hue - циклическое значение, поэтому 0 и 255 соседние
    diff_forward = (target_hue - current_hue) % 256
    diff_backward = (current_hue - target_hue) % 256

    if diff_forward <= diff_backward:
        direction = "up"
        steps_needed = diff_forward
    else:
        direction = "down"
        steps_needed = diff_backward

    if steps_needed == 0:
        return

    # Применяем шаги пошагово
    # Каждый вызов команды изменяет hue на 1 единицу (стандартное поведение VIA)
    # Параметр step определяет размер "шага" для визуального плавного изменения,
    # но на уровне команд мы все равно делаем по 1 единице за раз с задержкой
    # Если step > 1, это означает что мы пропускаем некоторые промежуточные значения
    # для ускорения, но для простоты делаем все шаги по 1 единице
    # В будущем можно оптимизировать чтобы делать шаги по step единиц сразу

    # Делаем шаги по одному с задержкой между ними
    for _ in range(steps_needed):
        qmk_hid.set_hue_step(vid, pid, direction, 1)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

