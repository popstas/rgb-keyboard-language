# Claude Knowledge Base - rgb-keyboard-language

## Контекст проекта

Проект состоит из двух компонентов:
1. **keychron-via-hue** - CLI утилита для управления RGB hue клавиатур через qmk_hid
2. **rgb-keyboard-language-windows** - Windows tray приложение, автоматически меняющее цвет в зависимости от раскладки

## Ключевые паттерны кода

### 1. Вызов внешних команд без окон (non-blocking)

```python
# HueSender использует ThreadPoolExecutor для неблокирующей отправки:
# send_color() -> немедленный return, subprocess запускается в фоновом потоке
# Rate limit и backoff - skip-based (return False), без time.sleep()

# Для именованных цветов - прямой вызов qmk_hid
if is_named_color:
    cmd = ["qmk_hid", "via", "--rgb-color", color.lower().strip()]
else:
    # Для hex/hsv - через keychron-via-hue
    cmd = ["keychron-via-hue", color, "--vid", vid, "--pid", pid, ...]

# Скрытие окна терминала на Windows
if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
    process = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, ...)
```

### 2. Поддержка прямого запуска и модуля

```python
if __name__ == "__main__" and __package__ is None:
    # Прямой запуск - абсолютные импорты
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rgb_keyboard_language_windows.config import ...
else:
    # Запуск как модуль - относительные импорты
    from .config import ...
```

### 3. Thread-safe конфигурация

```python
class KeyboardLayoutWatcher:
    def __init__(self, ...):
        self._lock = threading.Lock()
        self.config = config

    def update_config(self, new_config: dict):
        with self._lock:
            self.config = new_config

    def _watch_loop(self):
        with self._lock:
            poll_interval = self.config.get("poll_interval_ms", 100) / 1000.0
            enabled = self.config.get("enabled", True)
```

### 4. Экспоненциальный backoff

```python
def _get_backoff_delay(self) -> float:
    if self.consecutive_errors == 0:
        return 0.0
    delays = [1.0, 2.0, 5.0, 10.0]
    index = min(self.consecutive_errors - 1, len(delays) - 1)
    return delays[index]
```

### 5. Windows API для раскладки

```python
# Получение раскладки активного окна
hwnd = user32.GetForegroundWindow()
thread_id = user32.GetWindowThreadProcessId(hwnd, None)
hkl = user32.GetKeyboardLayout(thread_id)
lcid = hkl & 0xFFFF  # LOWORD

# Преобразование в BCP-47
buffer = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
result = kernel32.LCIDToLocaleName(lcid, buffer, LOCALE_NAME_MAX_LENGTH, 0)
locale_name = buffer.value  # "en-US", "ru-RU", etc.
```

## Структура файлов

### Корень проекта (rgb-keyboard-language-windows package)

```
src/rgb_keyboard_language_windows/
├── main.py          # Точка входа, watcher thread, интеграция
├── config.py        # JSON конфиг, автосоздание, валидация
├── layout_base.py   # Абстрактный класс (подготовка под macOS)
├── layout_win.py    # Windows API реализация
├── hue_sender.py    # Отправка цвета (qmk_hid/keychron-via-hue)
├── tray.py          # Tray иконка (ctypes Windows API), меню, кэш HICON
└── logging_.py      # Файловое + консоль логирование
```

## Архитектура: неблокирующий цикл

Главный принцип: **watch loop никогда не блокируется** на отправке цвета.

- `_watch_loop()` опрашивает раскладку каждые 100ms, вызывает `send_color()` — возвращается мгновенно
- `HueSender.send_color()` — ставит задачу в `ThreadPoolExecutor(max_workers=1)`, возвращает True/False
- Rate limit / backoff — не sleep, а skip (return False, retry на следующем poll)
- При ошибке subprocess — `last_color = None` для повторной попытки
- Stale send detection: если пришёл новый цвет пока старый в очереди — старый пропускается
- `shutdown()` останавливает executor + cleanup процессов

## Важные детали реализации

### Именованные vs hex/hsv цвета

- **Именованные** (green, red, blue, yellow, cyan, purple):
  - Вызывают `qmk_hid via --rgb-color <color>` напрямую
  - Не требуют VID/PID
  - Быстрее, без окон терминала
  
- **Hex/hsv** (#00ff00, hsv:120):
  - Требуют `keychron-via-hue` с VID/PID
  - Используют hue adjustment с шагами
  - Медленнее, но более гибкие

### Конфигурация цветов

```python
def get_color_for_layout(lang_code: str | None, config: dict) -> str:
    # 1. Exact match (en-US)
    if lang_code in layout_colors:
        return layout_colors[lang_code]
    
    # 2. Prefix match (en для en-US, en-GB)
    lang_prefix = lang_code.split("-")[0].lower()
    if lang_prefix in layout_colors:
        return layout_colors[lang_prefix]
    
    # 3. Default
    return default_color
```

### Tray иконка (pure ctypes, без Pillow)

```python
# Иконки создаются через CreateDIBSection + CreateIconIndirect (ctypes)
# Кэшируются в _icon_cache: dict[str, HICON] — не пересоздаются при каждом обновлении
# При удалении иконки — все кэшированные HICON уничтожаются через DestroyIcon
```

## VS Code настройки

### launch.json

```json
{
    "name": "RGB Keyboard Language: Run",
    "type": "debugpy",
    "request": "launch",
    "module": "rgb_keyboard_language_windows.main",
    "python": "${workspaceFolder}/.venv/Scripts/python.exe",
    "cwd": "${workspaceFolder}"
}
```

**Важно:** Всегда указывать правильный Python из venv и правильный cwd.

## Сборка exe

```python
# build.py — pure ctypes, без внешних зависимостей (pystray/PIL удалены)
cmd = [
    "pyinstaller",
    "--onefile",
    "--windowed",  # Без консоли
    "--name", "rgb-keyboard-language",
    "src/rgb_keyboard_language_windows/main.py"
]
```

## Типичные проблемы

1. **ModuleNotFoundError при запуске**
   - Решение: Установить пакет в venv: `pip install -e .`
   - Проверить python путь в launch.json

2. **Окна терминала открываются**
   - Решение: Использовать `CREATE_NO_WINDOW` + прямой вызов qmk_hid для именованных цветов

3. **qmk_hid не принимает --vid/--pid**
   - Решение: Для именованных цветов не передавать, использовать прямой вызов

4. **Tray иконка не обновляется**
   - Решение: Thread-safe обновления через `_lock`, кэш HICON в `_icon_cache`

## Тестирование

```bash
# Установка в editable mode
pip install -e .

# Запуск тестов
pytest tests/ -v
```

## Логи

- Файл: `%APPDATA%/rgb-keyboard-language-windows/app.log`
- Debug режим: `rgb-keyboard-language --debug` (дублирует в stdout)
- Rotating: 1MB, 3 backups

