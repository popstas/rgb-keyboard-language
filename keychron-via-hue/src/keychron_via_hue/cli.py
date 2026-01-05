"""CLI entry point for keychron-via-hue."""

import argparse
import subprocess
import sys

from . import color_parser
from . import hue_adjuster
from . import qmk_hid


def parse_hex_id(value: str) -> str:
    """
    Нормализует hex ID (VID/PID) - убирает 0x префикс если есть.

    Args:
        value: Hex строка (например "0x3434" или "3434")

    Returns:
        Нормализованная hex строка без 0x префикса
    """
    value = value.strip().lower()
    if value.startswith("0x"):
        return value[2:]
    return value


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage RGB hue of QMK/VIA-compatible keyboards via qmk_hid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  keychron-via-hue green --vid 0x3434 --pid 0x0011
  keychron-via-hue red --vid 0x3434 --pid 0x0011 --save
  keychron-via-hue "#00ff00" --vid 0x3434 --pid 0x0011
  keychron-via-hue hsv:120 --vid 3434 --pid 0011 --step 4 --delay-ms 20
        """
    )

    parser.add_argument(
        "color",
        help="Color in one of formats: named (red, green, blue, yellow, cyan, purple), "
             "hex (#RRGGBB or RRGGBB), or hsv (hsv:<H> where H is 0..360 degrees or 0..255)"
    )

    parser.add_argument(
        "--vid",
        required=False,
        help="Vendor ID in hex (e.g., 0x3434 or 3434). Optional for named colors."
    )

    parser.add_argument(
        "--pid",
        required=False,
        help="Product ID in hex (e.g., 0x0011 or 0011). Optional for named colors."
    )

    parser.add_argument(
        "--step",
        type=int,
        default=8,
        help="Hue step size in units 0..255 (default: 8)"
    )

    parser.add_argument(
        "--delay-ms",
        type=int,
        default=15,
        dest="delay_ms",
        help="Delay between steps in milliseconds (default: 15)"
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help="Save hue to EEPROM (if firmware supports it)"
    )

    args = parser.parse_args()

    try:
        # Проверяем, является ли цвет именованным
        color_lower = args.color.strip().lower()
        is_named_color = color_lower in color_parser.NAMED_COLORS

        # Если это именованный цвет и VID/PID не указаны, используем прямой вызов qmk_hid
        if is_named_color and not args.vid and not args.pid:
            qmk_hid.set_rgb_color(color_lower, save=args.save)
            print(f"OK: color set to {color_lower}", file=sys.stdout)
            sys.exit(0)

        # Для остальных случаев требуем VID/PID
        if not args.vid or not args.pid:
            print("Error: --vid and --pid are required for hex and hsv colors, or when using step/delay options", file=sys.stderr)
            sys.exit(1)

        # Парсим цвет
        target_hue = color_parser.parse_color(args.color)

        # Нормализуем VID/PID
        vid = parse_hex_id(args.vid)
        pid = parse_hex_id(args.pid)

        # Изменяем hue
        hue_adjuster.adjust_hue(
            target_hue=target_hue,
            vid=vid,
            pid=pid,
            step=args.step,
            delay_ms=args.delay_ms,
        )

        # Сохраняем если нужно
        if args.save:
            qmk_hid.save_hue(vid, pid)

        # Выводим успешное сообщение
        print(f"OK: hue set to {target_hue}", file=sys.stdout)
        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        error_msg = str(e)
        if hasattr(e, 'stderr') and e.stderr:
            error_msg = e.stderr
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

