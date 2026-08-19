# 🇷🇺 Русская версия

**Генерация C-кода для встраиваемой (embedded) системы меню LCD1602 из декларативного
конфигурационного файла.** Вы описываете дерево меню в YAML/JSON — генератор создаёт
полный набор C-файлов (таблицы данных, навигация, отрисовка, редактирование,
callback-функции), готовых к компиляции в вашу прошивку.

## Зачем нужен этот проект

Писать систему меню на C вручную — утомительно и чревато ошибками: таблицы данных,
связи навигации, функции отрисовки/редактирования значений, правила циклической или
ограниченной навигации — каждому устройству нужна своя версия одного и того же шаблона.

Этот проект **рассматривает меню как данные**. Вместо C-кода вы пишете небольшой
декларативный конфиг:

- **types** → C-типы (byte, uword, string, …);
- **roles** → как ведёт себя значение (`simple`, `factor`, `fixed`, `callback`);
- **controls** → какие действия энкодера поддерживаются (`click`, `position`);
- **navigate** → циклическая или ограниченная навигация (`cyclic` / `limit`);
- **callbacks** → собственные обработчики или автогенерируемые.

Генератор проверяет конфигурацию, разворачивает дерево в плоскую навигируемую структуру
и рендерит Jinja2-шаблоны в C-файлы для вашей прошивки.

## Как это работает

```
config/config.yaml
  → MenuConfig            загрузка всех конфигурационных файлов
  → MenuValidator         JSON Schema + кастомная валидация дерева
  → MenuFlattener         дерево → плоский список + связи навигации
  → FlatNode/BaseFlatNode узел из композиции менеджеров
  → MenuCraft             координатор, агрегация данных для шаблонов
  → MenuGenerator         рендер Jinja2-шаблонов → C-файлы
```

Конвейер полностью управляется данными: один и тот же генератор обрабатывает любое меню —
от одного экрана «Start» до многоуровневого дерева настроек с десятками узлов.

## Структура репозитория

```
MenuCraft/
├── generate_menu.py              # ← запускается отсюда: единственная точка входа в корне
├── generate_menu/                # Python-пакет со всеми исходниками
│   ├── cli.py                    # интерфейс командной строки (argparse)
│   ├── i18n.py                   # gettext-хелпер
│   ├── common.py                 # загрузчики JSON/YAML и хелперы
│   ├── menu_config.py            # загрузка и проверка всех конфигов
│   ├── menu_data.py              # правила типов/ролей/контролов/навигации
│   ├── menu_validator.py         # schema + кастомная валидация
│   ├── menu_flattener.py         # дерево → плоский список, связи навигации
│   ├── base_flat_node.py         # базовый узел (композиция менеджеров)
│   ├── flat_node.py              # финальный класс узла
│   ├── menucraft.py              # координатор (делегирует агрегатору)
│   ├── menu_data_aggregator.py   # кэшируемая агрегация
│   ├── menu_generator.py         # рендер Jinja2 → C-файлы
│   ├── locale/                   # gettext-каталоги (messages.pot, ru/...)
│   └── managers/                 # менеджеры узла
├── config/                       # конфигурационные файлы YAML/JSON
├── menu/                         # дерево меню (menu.yaml / menu.json)
├── templates/                    # Jinja2-шаблоны (*.jinja)
├── output/                       # сгенерированные C-файлы (include/ + исходники, в .gitignore)
├── docs/                         # документация (см. ниже)
├── tests/                        # модульные и smoke-тесты (pytest)
├── test/                         # интеграционные тесты (pytest)
├── conftest.py                   # общие pytest-фикстуры
├── pytest.ini
└── requirements.txt
```

## Быстрый старт

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Запуск генератора из корня проекта
python generate_menu.py
```

Сгенерированные C-файлы появляются в [`output/`](output/)
(исходники) и [`output/include/`](output/include/) (заголовки).

> 💡 В корне лежат точка входа [`generate_menu.py`](generate_menu.py), директории
> ресурсов (`config/`, `menu/`, `templates/`, `output/`) и документация; все
> Python-исходники находятся внутри пакета [`generate_menu/`](generate_menu/).

### Опции командной строки

| Флаг | Назначение |
|------|------------|
| `--config PATH` | Главный конфиг (по умолчанию: `config/config.yaml`) |
| `--menu PATH` | Подменить только дерево `menu` из `--config`, оставив schema/data-rules/шаблоны как есть — позволяет сгенерировать меню другого устройства без отдельного главного конфига под него |
| `--flat-only` | Провалидировать, сплющить дерево и сохранить JSON, но пропустить генерацию C-кода |
| `--debug` | Включить DEBUG-логирование и подробные сводки |
| `--quiet` | Логировать только ошибки |

```bash
# Сгенерировать дерево другого устройства без нового config/*.yaml
python generate_menu.py --menu menu/hipims.yaml
```

## Конфигурация

Главный конфигурационный файл — [`config/config.yaml`](config/config.yaml).

### Главный конфиг: `config/config.yaml`

```yaml
# Пути задаются относительно этого файла (директория config/)
menu: ../menu/menu.yaml          # дерево меню
menu_schema: menu_schema.yaml    # JSON Schema для валидации
menu_config: menu_data.yaml      # правила типов/ролей/контролов/навигации
output_flattern: output/flatterned.json   # дамп плоского списка (отладка)
generation_files: files.yaml     # какие шаблоны какие файлы создают
```

### Дерево меню: `menu/menu.yaml`

```yaml
config:
  version: "1.0"
  default_navigate: limit
  default_control: position
  default_branch_navigate: cyclic
  root_navigate: cyclic
  output_directory: ./output/    # куда генерируются C-файлы
  include_files: [pulse_config.h]

menu:
  - id: start                    # узел задаётся через id + title
    title: Start
    type: string                 # тип данных (см. правила ниже)
    role: fixed                  # роль: simple / factor / fixed / callback
    values: [Start, Started]     # фиксированный набор значений
    default_idx: 0
    navigate: cyclic             # cyclic или limit

  - id: settings
    title: Settings
    navigate: limit
    items:                       # вложенные элементы → подменю
      - id: hi_delay
        title: Delay
        type: udword
        role: factor
        default: 10
        min: 10
        max: 10000
        factors: [1, 10, 100, 1000]   # множители для роли factor
```

### Правила типов/ролей/контролов: `config/menu_data.yaml`

```yaml
types:
  ubyte: {c_type: uint8_t}
  string: {c_type: "const char*"}

roles:
  simple: [byte, ubyte, word, uword, dword, udword]
  fixed: [string, byte, ubyte, word, uword, dword, udword]
  factor: [byte, ubyte, word, uword, dword, udword]
  callback: [callback]

navigation_rules:
  position:
    allowed_navigate: [limit, cyclic]
    default: limit
```

### Генерация файлов: `config/files.yaml`

```yaml
templates_path: ./templates/     # где лежат Jinja2-шаблоны
files:
  handle.h.jinja: include/menu.h
  handle.c.jinja: menu.c
  context.h.jinja: include/menu_context.h
  context.c.jinja: menu_context.c
  # ... каждый шаблон соответствует одному генерируемому C-файлу
```

## Поля узла

Узел дерева меню может содержать:

| Поле | Назначение |
|------|------------|
| `id` | Уникальный идентификатор узла |
| `title` | Текст на дисплее |
| `type` | Тип данных: `byte`, `ubyte`, `word`, `uword`, `dword`, `udword`, `string`, `callback` |
| `role` | Поведение: `simple`, `factor`, `fixed`, `callback` |
| `min` / `max` / `step` | Числовой диапазон для `simple` / `factor` |
| `default` | Значение по умолчанию |
| `factors` | Множители для роли `factor` |
| `values` / `default_idx` | Фиксированный набор значений для роли `fixed` |
| `raw_values` | Необязательно, только для роли `fixed` — реальные числовые значения параллельно `values` по индексу (например, коды регистра за отображаемыми строками); длина должна совпадать с `values`. `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32` используют их вместо сырого индекса, если поле задано |
| `controls` | Контролы энкодера: `click`, `position` |
| `navigate` | Навигация: `cyclic`, `limit` |
| `items` | Дочерние узлы (подменю) |
| `click_cb`, `position_cb`, `double_click_cb`, `long_click_cb`, `event_cb`, `draw_value_cb` | Пользовательские callbacks |
| `tag` | Необязательные статические целочисленные метаданные узла (например, адрес аппаратного регистра), доступны только для чтения как `ctx->configs[id].tag` — никогда не входят в изменяемый union значения |

Если callback **не указан**, он генерируется автоматически
(например, `menu_draw_{type}_{role}_value_cb` для отрисовки,
`{type}_{role}_{control}_{navigate}_cb` для обработки).

## GUI

Для редактирования дерева меню без ручного правки YAML доступен опциональный
PyQt6-интерфейс:

```bash
python gui.py
```

Это тонкая обёртка над тем же конвейером, что описан выше — дерево меню плюс форма
свойств выбранного узла (набор полей зависит от `type`/`role` узла, по тем же
правилам из `config/menu_data.yaml`), явная кнопка **Validate** и кнопка
**Generate C files**, запускающая настоящий `MenuGenerator` в фоновом потоке. Внизу —
панель логов со всем, что и так пишет backend, с поиском и копированием. Полное
описание — в [docs/gui_ru.md](docs/gui_ru.md), включая то, как GUI не трогает
`config/config.yaml` при генерации.

## Генерируемые файлы

Генератор создаёт полный C-модуль:

- `menu_context.h/c` — контекст меню и основные структуры
- `menu_type.h/c` — типы данных и enum'ы
- `menu_data_*.h/c` — конфигурация данных, контекст, значения и имена
- `menu_tree.h/c` — дерево меню со связями навигации
- `menu_value.h/c` — функции доступа к значениям
- `menu_value_access.h/c` — общие `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32`, диспетчеризация по категории узла независимо от роли
- `menu_navigate.h/c` — функции навигации
- `menu_edit.h/c` — функции редактирования
- `menu_draw.h/c` — функции отрисовки
- `menu_name.h/c` — поиск имён узлов
- `menu.h/c` — верхнеуровневый вход

## Интернационализация (i18n / gettext)

Все пользовательские сообщения переведены на **gettext (Babel)**; основной язык —
**английский**.

Язык выбирается через переменную окружения `MENU_PROCESSOR_LANG`:

```bash
# Английский (по умолчанию)
python -X utf8 generate_menu.py

# Русский (используется каталог locale/ru)
set MENU_PROCESSOR_LANG=ru
python -X utf8 generate_menu.py
```

Если каталог переводов отсутствует или язык неизвестен, используется английский (fallback).

## Тесты

Запуск всего набора (модульные + интеграционные) из корня проекта:

```bash
python -m pytest -q
```

- [`docs/tests_ru.md`](docs/tests_ru.md) — модульные и smoke-тесты (`tests/`)
- [`docs/test_ru.md`](docs/test_ru.md) — интеграционные тесты (`test/`)

## Документация

| Документ | Язык |
|----------|------|
| [docs/architect.md](docs/architect.md) | 🇬🇧 Architecture overview & recommendations |
| [docs/architect_ru.md](docs/architect_ru.md) | 🇷🇺 Обзор архитектуры и рекомендации |
| [docs/gui.md](docs/gui.md) | 🇬🇧 GUI (PyQt6): layout, actions, design notes |
| [docs/gui_ru.md](docs/gui_ru.md) | 🇷🇺 GUI (PyQt6): раскладка, действия, особенности реализации |
| [docs/jinja_templates.md](docs/jinja_templates.md) | 🇬🇧 Generated C code: architecture & integration |
| [docs/jinja_templates_ru.md](docs/jinja_templates_ru.md) | 🇷🇺 Генерируемый C-код: архитектура и встраивание |
| [docs/tests.md](docs/tests.md) | 🇬🇧 Unit & smoke tests (`tests/`) |
| [docs/tests_ru.md](docs/tests_ru.md) | 🇷🇺 Модульные и smoke-тесты (`tests/`) |
| [docs/test.md](docs/test.md) | 🇬🇧 Integration tests (`test/`) |
| [docs/test_ru.md](docs/test_ru.md) | 🇷🇺 Интеграционные тесты (`test/`) |
| [docs/changes.md](docs/changes.md) | 🇬🇧 Changelog |
| [docs/changes_ru.md](docs/changes_ru.md) | 🇷🇺 Журнал изменений |
