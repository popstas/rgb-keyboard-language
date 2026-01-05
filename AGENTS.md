# Agents Knowledge Base

## Проект: rgb-keyboard-language

### Архитектурные решения

#### Монорепо структура
- `keychron-via-hue/` - CLI утилита для управления RGB hue через qmk_hid
- `rgb-keyboard-language-windows/` - Windows tray приложение, использующее keychron-via-hue

#### Принцип разделения
- **Не импортировать** модули `keychron_via_hue.*` из сервиса
- Только внешний вызов через subprocess
- Это позволяет независимую версионизацию и не тащит лишние зависимости

### Windows tray приложения

#### Скрытие окон терминала
При вызове subprocess на Windows для фоновых приложений:
```python
CREATE_NO_WINDOW = 0x08000000  # Windows flag
subprocess.run(cmd, creationflags=CREATE_NO_WINDOW, capture_output=True)
```

#### Прямой вызов vs обертка
- Для простых команд (именованные цвета) - прямой вызов `qmk_hid`
- Для сложных (hex/hsv с hue adjustment) - через обертку `keychron-via-hue`
- Это избегает лишних окон терминала и ускоряет выполнение

### Threading паттерны

#### Watcher thread
- Отдельный daemon thread для polling раскладки
- Thread-safe обновление конфига через lock
- Graceful shutdown через флаг `running` и `thread.join()`

#### Tray иконка обновления
- Thread-safe через `threading.Lock()`
- Обновление меню через `icon.update_menu()`
- Callback-based архитектура для действий из меню

### Обработка ошибок

#### Экспоненциальный backoff
```python
delays = [1.0, 2.0, 5.0, 10.0]  # Максимум 10 секунд
backoff_until = current_time + delays[min(errors - 1, len(delays) - 1)]
```

#### Rate limiting
- Минимальный интервал между командами (200ms по умолчанию)
- Дедупликация: не отправлять, если цвет не изменился
- Проверка времени перед отправкой

### Конфигурация

#### Автосоздание и валидация
- Создание дефолтного config.json при первом запуске
- Валидация и нормализация значений
- Thread-safe обновление в runtime

#### Маппинг цветов
- Exact match (en-US) → prefix match (en) → default
- Поддержка именованных, hex, hsv цветов
- Разные требования для разных типов цветов

### Windows API

#### Определение раскладки
- `GetForegroundWindow()` → `GetWindowThreadProcessId()` → `GetKeyboardLayout()`
- `LCIDToLocaleName()` для BCP-47 кода
- Fallback маппинг LCID → lang code

#### Polling vs события
- Событийное отслеживание раскладки сложно в Windows
- Polling 5-10 раз/сек (100-200ms) - оптимальный баланс
- Можно ускорить при смене активного окна

### Сборка и распространение

#### PyInstaller
- `--windowed` для tray приложений (без консоли)
- `--onefile` для одного exe
- `--hidden-import` для pystray и PIL на Windows
- `--collect-all` для всех зависимостей библиотек

#### Виртуальное окружение
- Всегда использовать Python из `.venv` для разработки
- Указывать в launch.json: `"python": "${workspaceFolder}/.venv/Scripts/python.exe"`
- Устанавливать пакеты в editable mode: `pip install -e .`

### Тестирование

#### Unit-тесты
- Тесты для config (чтение/запись, валидация)
- Тесты для color matching логики
- Использовать pytest с временными директориями

#### Интеграционное тестирование
- Требует реальной клавиатуры
- Проверка переключения раскладки
- Проверка отправки команд

### Логирование

#### Файловое + консоль
- По умолчанию: только файл (`%APPDATA%/app.log`)
- С `--debug`: дублирование в stdout
- Rotating file handler (1MB, 3 backups)

### Известные проблемы и решения

1. **Окна терминала при subprocess**
   - Решение: `CREATE_NO_WINDOW` флаг + прямой вызов qmk_hid для именованных цветов

2. **Относительные импорты при прямом запуске**
   - Решение: Поддержка обоих режимов (прямой запуск и модуль)

3. **qmk_hid не принимает --vid/--pid в команде via**
   - Решение: Для именованных цветов не передавать VID/PID, использовать прямой вызов

4. **Thread-safe обновления tray**
   - Решение: Lock + update_menu() вместо пересоздания иконки

