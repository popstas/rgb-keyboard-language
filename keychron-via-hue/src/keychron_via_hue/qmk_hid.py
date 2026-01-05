"""Interaction with qmk_hid command-line tool."""

import subprocess
import shutil
import sys


def find_qmk_hid() -> str:
    """
    Проверяет доступность qmk_hid в PATH.

    Returns:
        Имя команды 'qmk_hid'

    Raises:
        FileNotFoundError: Если qmk_hid не найден в PATH
    """
    qmk_hid_path = shutil.which("qmk_hid")
    if qmk_hid_path is None:
        raise FileNotFoundError(
            "qmk_hid not found in PATH. Please ensure qmk_hid is installed and available."
        )
    return "qmk_hid"


def get_current_hue(vid: str, pid: str) -> int:
    """
    Читает текущий hue значение с клавиатуры через qmk_hid.

    Args:
        vid: Vendor ID в hex (например "0x3434" или "3434")
        pid: Product ID в hex (например "0x0011" или "0011")

    Returns:
        Текущий hue значение (0..255)

    Raises:
        FileNotFoundError: Если qmk_hid не найден
        subprocess.CalledProcessError: Если qmk_hid завершился с ошибкой
        ValueError: Если не удалось распарсить hue из вывода
    """
    qmk_hid_cmd = find_qmk_hid()

    # Нормализуем VID/PID (убираем 0x префикс если есть, qmk_hid может принимать оба формата)
    vid_clean = vid.lower().replace("0x", "")
    pid_clean = pid.lower().replace("0x", "")

    try:
        # Команда для чтения текущего hue
        # Предполагаем формат: qmk_hid via --vid <VID> --pid <PID> --rgb-hue
        # или qmk_hid via <VID>:<PID> --rgb-hue
        # Реальный формат может отличаться, но логика работы будет аналогичной
        result = subprocess.run(
            [
                qmk_hid_cmd,
                "via",
                "--vid", vid_clean,
                "--pid", pid_clean,
                "--rgb-hue"
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0
        )

        # Парсим вывод - ожидаем число от 0 до 255
        output = result.stdout.strip()
        try:
            hue = int(output)
            if hue < 0 or hue > 255:
                raise ValueError(f"Invalid hue value from qmk_hid: {hue} (expected 0..255)")
            return hue
        except ValueError as e:
            if "Invalid hue value" in str(e):
                raise
            raise ValueError(f"Could not parse hue value from qmk_hid output: {output}") from e

    except subprocess.TimeoutExpired:
        raise subprocess.CalledProcessError(
            -1, qmk_hid_cmd, "Command timed out"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if (hasattr(e, 'stderr') and e.stderr) else str(e)
        # Создаем новое исключение с улучшенным сообщением
        raise subprocess.CalledProcessError(
            e.returncode, e.cmd,
            stderr=f"qmk_hid failed: {error_msg}"
        ) from e


def set_hue_step(vid: str, pid: str, direction: str, count: int = 1) -> None:
    """
    Выполняет шаги изменения hue (эмуляция нажатий Hue+ или Hue-).

    Args:
        vid: Vendor ID в hex
        pid: Product ID в hex
        direction: "up" для Hue+ или "down" для Hue-
        count: Количество шагов (по умолчанию 1)

    Raises:
        FileNotFoundError: Если qmk_hid не найден
        subprocess.CalledProcessError: Если qmk_hid завершился с ошибкой
        ValueError: Если direction некорректен
    """
    if direction not in ("up", "down"):
        raise ValueError(f"Invalid direction: {direction} (expected 'up' or 'down')")

    qmk_hid_cmd = find_qmk_hid()
    vid_clean = vid.lower().replace("0x", "")
    pid_clean = pid.lower().replace("0x", "")

    # Команда для изменения hue
    # Предполагаем, что есть опции --rgb-hue-up и --rgb-hue-down
    # или аналогичные. Реальный формат может отличаться.
    hue_option = "--rgb-hue-up" if direction == "up" else "--rgb-hue-down"

    for _ in range(count):
        try:
            subprocess.run(
                [
                    qmk_hid_cmd,
                    "via",
                    "--vid", vid_clean,
                    "--pid", pid_clean,
                    hue_option
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=2.0
            )
        except subprocess.TimeoutExpired:
            raise subprocess.CalledProcessError(
                -1, qmk_hid_cmd, "Command timed out"
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            new_error = subprocess.CalledProcessError(e.returncode, e.cmd, stderr=error_msg)
            new_error.stderr = f"qmk_hid failed: {error_msg}"
            raise new_error from e


def set_rgb_color(color: str, save: bool = False) -> None:
    """
    Устанавливает цвет напрямую через qmk_hid via --rgb-color.

    Args:
        color: Именованный цвет (red, green, blue, yellow, cyan, purple)
        save: Сохранить в EEPROM (если поддерживается прошивкой)

    Raises:
        FileNotFoundError: Если qmk_hid не найден
        subprocess.CalledProcessError: Если qmk_hid завершился с ошибкой
    """
    qmk_hid_cmd = find_qmk_hid()

    try:
        cmd = [qmk_hid_cmd, "via", "--rgb-color", color]
        if save:
            cmd.append("--save")

        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0
        )
    except subprocess.TimeoutExpired:
        raise subprocess.CalledProcessError(
            -1, qmk_hid_cmd, "Command timed out"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        new_error = subprocess.CalledProcessError(e.returncode, e.cmd, stderr=error_msg)
        new_error.stderr = f"qmk_hid failed: {error_msg}"
        raise new_error from e


def save_hue(vid: str, pid: str) -> None:
    """
    Сохраняет текущий hue в EEPROM (если поддерживается прошивкой).

    Args:
        vid: Vendor ID в hex
        pid: Product ID в hex

    Raises:
        FileNotFoundError: Если qmk_hid не найден
        subprocess.CalledProcessError: Если qmk_hid завершился с ошибкой
    """
    qmk_hid_cmd = find_qmk_hid()
    vid_clean = vid.lower().replace("0x", "")
    pid_clean = pid.lower().replace("0x", "")

    try:
        # Команда для сохранения в EEPROM
        # Предполагаем опцию --save или --rgb-hue-save
        subprocess.run(
            [
                qmk_hid_cmd,
                "via",
                "--vid", vid_clean,
                "--pid", pid_clean,
                "--rgb-hue-save"
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0
        )
    except subprocess.TimeoutExpired:
        raise subprocess.CalledProcessError(
            -1, qmk_hid_cmd, "Command timed out"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        new_error = subprocess.CalledProcessError(e.returncode, e.cmd, stderr=error_msg)
        new_error.stderr = f"qmk_hid failed to save: {error_msg}"
        raise new_error from e

