# keychron-via-hue

CLI-утилита на Python для управления hue подсветки QMK/VIA-совместимой клавиатуры (например Keychron K8 Pro), используя внешний инструмент `qmk_hid` (VIA API).

## Требования

- Python 3.10+
- `qmk_hid` - внешний бинарь, должен быть доступен в `PATH`

### Установка qmk_hid

Утилита `qmk_hid` требуется для работы с клавиатурой через VIA API.

**Для Windows:**
1. Скачайте последнюю версию `qmk_hid.exe` с [GitHub releases](https://github.com/FrameworkComputer/qmk_hid/releases)
2. Сохраните файл в удобном месте (например, `C:\Program Files\qmk_hid\`)
3. Добавьте путь к директории в переменную окружения PATH

**Для Linux:**
1. Установите зависимости (Rust, libudev)
2. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/FrameworkComputer/qmk_hid.git
   cd qmk_hid
   cargo build --release
   sudo cp target/release/qmk_hid /usr/local/bin/
   ```

**Проверка установки:**
```bash
qmk_hid --version
```

Дополнительная информация: [qmk_hid на GitHub](https://github.com/FrameworkComputer/qmk_hid)

## Установка

```bash
pip install -e ./keychron-via-hue
```

## Использование

```bash
keychron-via-hue <color> --vid <VID> --pid <PID> [options]
```

### Параметры

- `<color>` - цвет в одном из форматов:
  - именованный: `red`, `green`, `blue`, `yellow`, `cyan`, `purple`
  - hex: `#RRGGBB` или `RRGGBB` (например `#00ff00`)
  - hsv: `hsv:<H>` где `H` в градусах 0..360 или в единицах 0..255 (например `hsv:120`)

- `--vid` - Vendor ID в hex (например `0x3434` или `3434`)
- `--pid` - Product ID в hex (например `0x0011` или `0011`)

### Опции

- `--step <N>` - шаг hue (Hue+/Hue-) в единицах 0..255, по умолчанию `8`
- `--delay-ms <N>` - задержка между шагами в миллисекундах, по умолчанию `15`
- `--save` - сохранить hue в EEPROM (если прошивка поддерживает сохранение через VIA API)

### Примеры

Установить зеленый:
```bash
keychron-via-hue green --vid 0x3434 --pid 0x0011
```

Установить красный и сохранить:
```bash
keychron-via-hue red --vid 0x3434 --pid 0x0011 --save
```

Установить по HEX:
```bash
keychron-via-hue "#00ff00" --vid 0x3434 --pid 0x0011
```

Установить по HSV с кастомными параметрами:
```bash
keychron-via-hue hsv:120 --vid 3434 --pid 0011 --step 4 --delay-ms 20
```

## Выход

- Код `0` при успехе
- Код `!=0` при ошибке (нет `qmk_hid`, устройство не найдено, не распарсился hue, отказ доступа и т.п.)
- stdout: строка `OK: hue set to <value>` при успехе
- stderr: диагностика при ошибке

## Как это работает

1. Утилита парсит переданный цвет и вычисляет целевой hue (0..255)
2. Читает текущий hue с клавиатуры через `qmk_hid via --rgb-hue`
3. Вычисляет кратчайший путь от текущего к целевому hue (с учетом циклического характера hue, где 0 и 255 соседние)
4. Пошагово "докручивает" hue в нужном направлении (эмулируя нажатия Hue+/Hue-)
5. При необходимости сохраняет значение в EEPROM

## Тестирование

```bash
pytest tests/
```

## Примечания

- Утилита не общается с HID напрямую, только запускает `qmk_hid`
- Если `qmk_hid` отсутствует или не видит устройство - утилита завершится с ненулевым кодом и понятным сообщением об ошибке
- Утилита рассчитана на прошивки, где `qmk_hid via --rgb-hue` умеет вернуть текущий hue и установить hue
- Если прошивка не поддерживает `--rgb-hue`, это считается ошибкой среды (не баг утилиты) - сообщение будет явным

