# 📐 Архитектурный обзор и рекомендации (Menu Processor)

> Дата: 2026-08-01 · Анализ проведён по состоянию текущей кодовой базы.

## 1. Общее описание системы

Проект — **Python-генератор C-кода** системы меню для embedded LCD1602.
Меню описывается декларативно в конфигурационных файлах, а генератор создаёт
полный набор C-файлов (таблицы данных, навигация, отрисовка, редактирование и т.д.).

Конвейер работы:

```
config/config.yaml
  → MenuConfig            — загрузка всех конфигурационных файлов
  → MenuValidator         — JSON Schema + кастомная валидация дерева
  → MenuFlattener         — разворачивание дерева в плоский список + связи
  → FlatNode/BaseFlatNode — узел из композиции менеджеров
  → MenuCraft             — координатор, агрегация данных для шаблонов
  → MenuGenerator         — рендер Jinja2 шаблонов → C-файлы
```

### Структура репозитория

```
MenuCraft/
├── generate_menu.py              # Корневая точка входа (chdir в пакет)
├── generate_menu/                # Python-пакет
│   ├── __init__.py
│   ├── i18n.py                   # gettext-хелпер (_) с самокорректирующимся каталогом
│   ├── common.py                 # загрузчики конфигов (JSON/YAML), json-хелперы
│   ├── menu_config.py            # загрузка и проверка всех конфигов
│   ├── menu_data.py              # правила типов/ролей/контролов/навигации
│   ├── menu_validator.py         # schema + кастомная валидация
│   ├── menu_flattener.py         # дерево → плоский список, cyclic/limit навигация
│   ├── base_flat_node.py         # BaseFlatNode (композиция менеджеров)
│   ├── flat_node.py              # FlatNode (финальный класс узла)
│   ├── menucraft.py              # координатор и агрегатор
│   ├── menu_generator.py         # рендер Jinja2 → C-файлы
│   ├── managers/
│   │   ├── node_data_manager.py      # данные: значения, множители, типы, категории
│   │   ├── node_control_manager.py   # контролы + генерация автоматических функций
│   │   ├── node_navigation_manager.py# навигационные связи и циклическая логика
│   │   ├── callback_manager.py       # callback-функции узла
│   │   └── function_info.py          # dataclass FunctionInfo + фабрики
│   ├── config/                   # конфигурационные файлы YAML/JSON
│   ├── menu/                     # дерево меню (menu.yaml / menu.json)
│   ├── templates/                # Jinja2-шаблоны (*.jinja)
│   ├── locale/                   # gettext-каталоги (messages.pot, ru/...)
│   └── output/                   # сгенерированные C-файлы (include/ + исходники)
├── docs/                         # Документация (эта папка)
│   ├── architect.md / architect_ru.md
│   └── changes.md / changes_ru.md
├── README.md
└── requirements.txt
```

### Положительные стороны архитектуры

- ✅ Чистая **композиция менеджеров** в узле: [`NodeDataManager`](../generate_menu/managers/node_data_manager.py:4), [`NodeControlManager`](../generate_menu/managers/node_control_manager.py:8), [`NodeNavigationManager`](../generate_menu/managers/node_navigation_manager.py:5), [`CallbackManager`](../generate_menu/managers/callback_manager.py:5) — хорошее разделение ответственности.
- ✅ Разделение конвейера: загрузка → валидация → флаттенинг → генерация.
- ✅ Dataclass [`FunctionInfo`](../generate_menu/managers/function_info.py:6) + фабричные методы.
- ✅ Jinja2-шаблоны вынесены из кода.
- ✅ Конфиг доступен и в **JSON, и в YAML** (универсальный загрузчик в [`common.py`](../generate_menu/common.py:25)).
- ✅ Все пользовательские сообщения интернационализированы через **gettext / Babel** ([`i18n.py`](../generate_menu/i18n.py)).

---

## 2. Модули подробнее

### 2.1 [`menu_config.py`](../generate_menu/menu_config.py:17) — `MenuConfig`

Загружает главный конфигурационный файл и, на его основе, все обязательные файлы
(`menu`, `menu_schema`, `menu_config`, `generation_files`). Обязательные файлы
резолвятся **относительно главного конфига** через [`_load_required_file`](../generate_menu/menu_config.py:32).
Значения, зависящие от рабочей директории (`templates_path`, `output_directory`,
`output_flattern`), используются как есть — именно поэтому корневая точка входа
меняет рабочую директорию на пакет.

### 2.2 [`menu_data.py`](../generate_menu/menu_data.py:17) — `MenuData`

Хранит правила: типы → C-типы, роли → допустимые типы, контролы по ролям,
правила навигации по контролам, role-правила (назначение, обязательные контролы,
внешние callbacks). Предоставляет поиск для менеджеров:
[`get_controls_for_type`](../generate_menu/menu_data.py:40),
[`get_navigation_rules`](../generate_menu/menu_data.py:57), [`get_control_config`](../generate_menu/menu_data.py:95).

### 2.3 [`menu_validator.py`](../generate_menu/menu_validator.py:16) — `MenuValidator`

Валидирует дерево меню: JSON Schema (`Draft7Validator`) плюс кастомный обход
([`_validate_item`](../generate_menu/menu_validator.py:63), значения по умолчанию,
множители, значения). Собирает ошибки как `{путь: [сообщения]}`.

### 2.4 [`menu_flattener.py`](../generate_menu/menu_flattener.py:16) — `MenuFlattener`

Превращает вложенное дерево меню в плоский список объектов [`FlatNode`](../generate_menu/flat_node.py:6)
и настраивает навигацию: связи sibling'ов, правила родителя/ветвей, циклическая
обёртка ([`_create_cyclic_siblings`](../generate_menu/menu_flattener.py:87)).

### 2.5 [`base_flat_node.py`](../generate_menu/base_flat_node.py:9) — `BaseFlatNode`

Базовый класс узла, собранный из менеджеров: данные, контролы, навигация, callbacks.
Предоставляет высокоуровневые свойства для шаблонов и процессора
(`controls`, `all_function_infos`, `get_control_summary`, ...).

### 2.6 Менеджеры

- [`NodeDataManager`](../generate_menu/managers/node_data_manager.py:4) — значения, множители, `c_str_*`-хелперы, сводка данных.
- [`NodeControlManager`](../generate_menu/managers/node_control_manager.py:8) — строит контролы из role-правил, генерирует имена автоматических функций, проверяет обязательные функции.
- [`NodeNavigationManager`](../generate_menu/managers/node_navigation_manager.py:5) — связи sibling/cyclic, свойства структуры дерева, цепочка sibling'ов, отладочный вывод.
- [`CallbackManager`](../generate_menu/managers/callback_manager.py:5) — авто vs пользовательские callbacks, эффективные имена, сводки.
- [`FunctionInfo`](../generate_menu/managers/function_info.py:6) — dataclass, описывающий генерируемую функцию; фабрики `create_auto` / `create_custom`.

### 2.7 [`menucraft.py`](../generate_menu/menucraft.py:17) — `MenuCraft`

Координатор. Загружает конфиг, валидирует, флаттенит, затем отдаёт множество
агрегирующих свойств (`functions`, `categories`, `functions_by_event_type`,
`functions_by_navigation`, `required_functions`, `custom_callbacks`,
`auto_generated_functions`, `callback_summary_by_category`, ...) и сохраняет
промежуточные JSON (`output/flatterned.json`, `output/functions.json`).

### 2.8 [`menu_generator.py`](../generate_menu/menu_generator.py:15) — `MenuGenerator`

Собирает контекст Jinja2 из процессора и рендерит каждый шаблон из
`generation_files` (files.yaml) в выходную директорию.

### 2.9 Точка входа [`generate_menu.py`](../generate_menu.py:1)

Единственный файл в корне проекта. Резолвит директорию пакета `generate_menu/`,
**меняет рабочую директорию на неё** (т.к. `templates_path`, `output_directory`
и `output_flattern` зависят от CWD), добавляет корень проекта в `sys.path`, затем
создаёт [`MenuGenerator`](../generate_menu/menu_generator.py:15) с `./config/config.yaml`.

---

## 3. Конфигурация и разрешение путей

| Значение | Резолвится относительно | Пример |
|----------|-------------------------|--------|
| `menu`, `menu_schema`, `menu_config`, `generation_files` | самого конфиг-файла (`config/`) | `../menu/menu.yaml` |
| `templates_path` (в `files.yaml`) | текущей рабочей директории | `./templates/` |
| `output_directory` (в `menu.yaml`) | текущей рабочей директории | `./output/` |
| `output_flattern` (в `config.yaml`) | текущей рабочей директории | `output/flatterned.json` |

Поскольку CWD-зависимые значения указывают внутрь `generate_menu/`, корневая точка
входа выполняет `os.chdir(package_dir)` перед созданием объектов.

Главный конфиг [`config.yaml`](../generate_menu/config/config.yaml:1):

```yaml
menu: ../menu/menu.yaml
menu_schema: menu_schema.yaml
menu_config: menu_data.yaml
output_flattern: output/flatterned.json
generation_files: files.yaml
```

---

## 4. Проблемы и рекомендации

### 4.1 Критические / архитектурные

#### 🔴 A1. «God-object» в `MenuCraft`
[`menucraft.py`](../generate_menu/menucraft.py:17) содержит **20+ свойств**, каждое из которых
заново обходит `_flat_nodes` и собирает агрегированные словари (`functions`,
`categories`, `functions_by_event_type`, `functions_by_navigation`,
`functions_by_type_role`, `functions_by_type`, `functions_by_role`,
`callback_summary_by_category`, `required_functions`, `custom_callbacks`,
`auto_generated_functions`, ...).

Проблемы:
- O(N × M) повторных итераций по узлам;
- много почти одинакового кода «группировка по ключу»;
- класс трудно тестировать.

**Рекомендация:** вынести агрегацию в отдельный `MenuDataAggregator` (или серию
функций), который один раз обходит узлы и кэширует результат
(`functools.cached_property`). Это упростит [`MenuCraft`](../generate_menu/menucraft.py:17)
и ускорит генерацию.

#### 🔴 A2. Мёртвый / недостижимый код
В [`managers/node_control_manager.py`](../generate_menu/managers/node_control_manager.py:172)
у `all_function_infos` есть **недостижимое продолжение** после `return infos` — мёртвый
код, который никогда не выполняется, но сбивает читателя. Также:
- [`_apply_parent_navigation_rules`](../generate_menu/menu_flattener.py:62) — не вызывается (дубликат `_apply_branch_navigation_rules`);
- [`MenuValidator._validate_data_type`](../generate_menu/menu_validator.py:111) — возвращает пустой список (заглушка);
- много закомментированных `print(f"DEBUG ...")` по всем менеджерам.

**Рекомендация:** удалить недостижимые блоки и заглушки; вычистить закомментированные отладочные строки.

#### 🔴 A3. `print()` вместо логирования
Весь код завязан на `print()` с эмодзи (в том числе в production-путях).

**Рекомендация:** перейти на модуль `logging`: `logger = logging.getLogger(__name__)`.
Вывод останется читаемым, но станет управляемым (уровни, файлы, отключение).

#### 🔴 A4. Конфиг: неконсистентность ключей и опечатки
- `output_flattern` — опечатка (`flatten`), она же в [`save_flattern_json`](../generate_menu/menucraft.py:50).
- Ключ `menu_config` указывает на `menu_data.json` — путаница между «конфигом меню» и «правилами типов/ролей».
- `files.json` использует `templates_path`, а некоторые легаси-файлы — `templates`.
- Ключ `menu` загружает дерево меню, а `menu_config` — правила данных.

**Рекомендация:** унифицировать имена ключей (например `menu_tree`, `data_rules`,
`generation_files`, `templates_path`), исправить опечатки, привести схему в соответствие с правилами.

#### 🔴 A5. Пути: абсолютные пути и непереносимость
Некоторые легаси JSON-файлы (`menu.json`, `files_orig.json`, `files_test01.json`)
содержали жёстко зашитые абсолютные пути (`/home/yevst/...`).

**Рекомендация:** держать `output_directory` в конфиге меню со значением по умолчанию
`./output/` и резолвить все пути конфигов относительно корня проекта (сделано для YAML-конфигов).

#### 🔴 A6. Конструкторы с побочными эффектами
- [`MenuCraft.__init__`](../generate_menu/menucraft.py:18) выполняет всю загрузку/валидацию/флаттенинг и бросает исключения.
- [`MenuGenerator.__init__`](../generate_menu/menu_generator.py:16) сразу вызывает `_generate_code()`.

**Рекомендация:** конструкторы должны только сохранять зависимости; рабочие методы
вызывать явно (`processor.run()`, `generator.generate()`). Это упростит тестирование и переиспользование.

### 4.2 Оптимизация и улучшения

#### 🟡 B1. Единая точка входа (CLI)
У нескольких модулей есть `main()` + блок `if __name__ == "__main__":` с захардкоженным путём конфига.

**Рекомендация:** один `cli.py`/`__main__.py` с `argparse` (`--config`, `--output`,
`--flat-only`, `--debug`); модули-библиотеки — без `main()`.

#### 🟡 B2. Нет тестов
В проекте нет ни одного теста (ни `pytest`, ни `unittest`); отладочные `main()` служат их заменой.

**Рекомендация:** добавить `tests/` с `pytest`:
- unit: `MenuData` (правила типов/ролей/контролов);
- unit: `MenuValidator` (валидные/невалидные деревья);
- unit: `MenuFlattener` (связи, циклическая навигация);
- e2e: полная генерация из sample-конфига → проверка создания C-файлов.

#### 🟡 B3. Кэшировать агрегации
Считать производные свойства `MenuCraft` один раз; особенно актуально для больших деревьев.

#### ✅ B4. Дублирование валидации — сведено в `MenuValidator`
Валидация теперь живёт в одном месте: [`MenuValidator._validate_item`](../generate_menu/menu_validator.py:63),
который работает на сыром дереве до flatten и именно его напрямую (без flatten) вызывает
кнопка Validate в GUI. Сплющенный проход (`MenuCraft._validate_flat_data()`,
`NodeDataManager.validate_numeric_range/validate_fixed_values`,
`BaseFlatNode.validate_data()`) удалён как полностью избыточный, а единственная проверка,
которую он ловил уникально — `min > max` без `default`, за который можно было бы зацепиться —
перенесена в `MenuValidator` как `_validate_min_max` и теперь срабатывает независимо от
наличия `default`.

#### 🟡 B5. `pathlib.Path` везде
Смешаны `os.path`, строки и `Path`. Привести всё к `pathlib.Path`.

#### 🟡 B6. Временная связность `CallbackManager`
[`CallbackManager`](../generate_menu/managers/callback_manager.py:13) инициализируется с пустыми `_auto_*`
и заполняется позже через [`set_auto_functions`](../generate_menu/managers/callback_manager.py:35) из
`NodeControlManager` — хрупко (легко забыть вызвать). **Рекомендация:** передавать
автоматические функции при конструировании или вычислять их лениво.

#### 🟡 B7. Неконсистентная типизация
Смешаны `Dict`/`dict`, `List`/`list` в аннотациях. Унифицировать (лучше — современный
синтаксис `dict[str, ...]`, Python 3.10+).

#### 🟡 B8. Лишние импорты
- `menu_flattener.py` импортирует `MenuValidator` — не используется.
- `menu_generator.py` импортировал `Environment` дважды (исправлено).

#### 🟡 B9. Схема для `menu_data.yaml`
Правила типов/ролей/контролов не валидируются вообще. Добавить схему/валидацию для этого файла.

---

## 5. Приоритизированный план изменений

| Приоритет | Задача | Файлы |
|-----------|--------|-------|
| 🔴 P0 | Перевести конфиг на YAML (готово) | `common.py`, `menu_config.py`, `config/*.yaml`, `menu/menu.yaml` |
| 🔴 P0 | Удалить dead code и недостижимые блоки | `node_control_manager.py`, `menu_flattener.py`, `menu_validator.py` |
| 🔴 P1 | `logging` вместо `print()` | все модули |
| 🔴 P1 | Исправить опечатки и ключи конфига | `menu_config.py`, `config/*` |
| 🟡 P2 | Вынести агрегацию из `MenuCraft` | новый `aggregator.py` |
| 🟡 P2 | Единый CLI с `argparse` | новый `cli.py` |
| 🟡 P2 | Тесты `pytest` | `tests/` |
| 🟡 P3 | Единая валидация, `pathlib`, типизация | все модули |

> Миграция на YAML (P0) и интеграция gettext/i18n уже реализованы —
> подробности в [changes_ru.md](./changes_ru.md).
