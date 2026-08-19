# 📝 Журнал изменений (Menu Processor)

Все значимые изменения перечислены в обратном хронологическом порядке.
Формат вдохновлён [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### 🖥️ GUI: сценарий «New» + вкладка «Project»

- Добавлен `File > New` (`Ctrl+N`) в [`gui/main_window.py`](../gui/main_window.py):
  создаёт новый, минимальный, несохранённый документ. Поскольку `MenuConfig`
  умеет загружаться только из реального файла, это пишет небольшой валидный
  по схеме шаблон во временный файл GUI (`menu/.new.yaml`, в `.gitignore`) и
  открывает его, а затем сбрасывает `current_path`, чтобы `Save`/`Generate`
  по-прежнему уходили в `Save As...`, а не молча писали обратно во временный
  файл.
- Добавлена вкладка «Project» ([`gui/project_form.py`](../gui/project_form.py))
  рядом с формой узла — для собственного блока `config:` документа: `version`,
  `author`, умолчания навигации/контрола, `output_directory`,
  `include_files`, `wrap_by_name_functions`, `enable_node_names`. Использует
  тот же in-memory dict, что и тулбарное действие «Set output directory...»,
  так что оба остаются синхронными.

### 🔒 Разбор булевых значений YAML сужен до `true`/`false`

- `generate_menu/common.py::load_config_file` использовал обычный
  `yaml.safe_load`, который следует YAML 1.1 и молча превращает нескавыченные
  `yes`/`no`/`on`/`off` (в любом регистре) в Python bool — так `values: [Off, On]`
  для узла с ролью `fixed` становился `[False, True]` ещё до того, как
  валидация схемы вообще увидела строку, и проявлялось это лишь как невнятная
  `False is not of type 'string', 'number'`. Добавлен `_StrictBoolLoader`
  (подкласс `yaml.SafeLoader`, чей резолвер bool matчит только `true`/`false`
  — как в core schema YAML 1.2), и `load_config_file` переключён на него —
  это единственное место в кодовой базе, где читается YAML.

### ✅ Валидация сведена в единый проход `MenuValidator`

- `min > max` теперь проверяется в [`MenuValidator`](../generate_menu/menu_validator.py)
  независимо от наличия `default` — раньше узел с `min: 100, max: 10` и без
  `default` проскакивал валидатор сырого дерева и ловился только на сплющенном.
  Кнопка Validate в GUI (которая вызывает `MenuValidator` напрямую, без flatten)
  теперь тоже его ловит.
- Удалён дублирующий сплющенный проход как полностью избыточный:
  `MenuCraft._validate_flat_data()` (и его вызов в `MenuCraft.__init__`),
  `NodeDataManager.validate_numeric_range()`/`validate_fixed_values()` и
  `BaseFlatNode.validate_data()` — конвейер снова имеет одну проверку до flatten
  через `MenuValidator`.

### 🔢 printf-формат перенесён из шаблонов в конфиг

- `printf_format`/`printf_cast` теперь часть `types:` в
  [`config/menu_data.yaml`](../config/menu_data.yaml) для шести целочисленных
  типов (`byte`/`ubyte`/`word`/`uword`/`dword`/`udword`) — `%ld` + `(long)` для
  знаковых, `%lu` + `(unsigned long)` для беззнаковых — и доходят через
  `MenuData.printf_format()`/`printf_cast()` в `FunctionInfo` до шаблонов.
- [`draw_simple.c.jinja`](../templates/draw_simple.c.jinja),
  [`draw_factor.c.jinja`](../templates/draw_factor.c.jinja) и
  [`draw_fixed.c.jinja`](../templates/draw_fixed.c.jinja) используют эти поля
  вместо захардкоженных `if/elif` по спискам типов (сгенерированный C побайтово
  идентичен — подтверждено golden-сравнением).
- `float` осознанно не тронут: точность зависит от роли (`%3.3f` в `simple`,
  `%2.2f` в `factor`/`fixed`), поэтому ветка остаётся в шаблонах.

### 🐛 Закрыт пробел с типом `float` + защита «тип без c_type»

- `float` был валиден по JSON Schema, но отсутствовал в `types:`/`roles:` в
  [`config/menu_data.yaml`](../config/menu_data.yaml) — узел `type: float`
  молча генерировал `None` в качестве C-типа. Добавлен `float: {c_type: float}`
  и роли `simple`/`factor` (не `fixed` — вне скоупа).
- [`MenuValidator`](../generate_menu/menu_validator.py) теперь отклоняет любой
  используемый тип без `c_type` в `menu_data.yaml` — тип, добавленный в enum
  схемы, но забытый в конфиге, падает на валидации, а не просачивается как
  `None` в сгенерированный C.

###  `menu_draw_pad_marker()` стал публичным

- Хелпер паддинга строки и маркера состояния в
  [`draw.c.jinja`](../templates/draw.c.jinja) был `static` и не объявлялся —
  любому кастомному `draw_value_cb` приходилось вручную копировать его логику.
  Найдено через реальный дубликат (`draw_value_marker()`) в glue-коде
  HiPIMS_Menu — независимая копия под захардкоженной длиной строки, которая
  молча разошлась бы с генератором при изменении `MENU_LINE_LEN` или
  символов-маркеров. Переименован в `menu_draw_pad_marker(ctx)`, убран
  `static`, объявлен в [`draw.h.jinja`](../templates/draw.h.jinja) — та же
  простая сигнатура (сам меряет `strlen(ctx->value_buf)`), теперь можно
  вызывать напрямую из кастомных колбэков вместо копирования в каждый проект.

### 🔢 `raw_values` для `role: fixed`

- Добавлен необязательный массив `raw_values` для узлов с ролью `fixed`,
  параллельный `values` по индексу — реальное число (например, код регистра)
  за каждой строкой отображения. `menu_get_int32`/`menu_set_int32`/
  `menu_get_uint32`/`menu_set_uint32` ([`value_access.c.jinja`](../templates/value_access.c.jinja))
  используют его вместо сырого индекса, если он задан; `menu_set_*` делает
  линейный поиск и оставляет `idx` без изменений, если значение не найдено,
  вместо угадывания. Если поле не задано — поведение как раньше, через `idx`,
  существующие меню не затрагиваются.
- Длина сверяется с `values` в [`MenuValidator`](../generate_menu/menu_validator.py)
  (единственный валидатор, реально подключённый к конвейеру).
- Выведено в форму GUI ([`gui/node_form.py`](../gui/node_form.py)) как
  необязательный список «Raw values» рядом с «Values» для `role: fixed`; при
  опустошении списка ключ удаляется целиком, а не остаётся `[]`. Заодно
  добавлено общее поле «Tag» для любого листа — тот же `tag` из прошлого
  раунда, но теперь редактируемый через GUI.

### 🖥️ PyQt6 GUI

- Добавлены [`gui.py`](../gui.py) / [`gui/`](../gui/) — дерево + форма свойств узла,
  кнопки Validate и Generate C files, панель логов и теневой конфиг
  (`config/.gui_config.yaml`, в .gitignore), чтобы GUI никогда не трогал реальный
  `config/config.yaml`. См. [`docs/gui.md`](./gui.md) / [`docs/gui_ru.md`](./gui_ru.md).

### 🔀 `--menu PATH` / `menu_override`

- [`MenuConfig`](../generate_menu/menu_config.py), [`MenuCraft`](../generate_menu/menucraft.py)
  и [`MenuGenerator`](../generate_menu/menu_generator.py) принимают необязательный
  путь `menu_override`, подменяющий только дерево `menu`, оставляя
  `menu_schema`/`data_rules`/`generation_files`/`flatten` из главного конфига.
  Доступен в CLI как `--menu PATH` — генерирует дерево другого устройства без
  отдельного главного конфига под него.
- Тестовый набор использует тот же механизм: [`menu/test.yaml`](../menu/test.yaml) —
  замороженная фикстура дерева, подключаемая через фикстуру `menu_override_path` в
  `conftest.py`, так что тесты больше не зависят от активно редактируемого
  `menu/menu.yaml`.

### 🐛 Исправления типов и генерации колбэков

- `dword` ошибочно был сопоставлен с `uint32_t` (дублируя `udword`) вместо
  знакового `int32_t` в [`config/menu_data.yaml`](../config/menu_data.yaml) —
  ломало поля с отрицательным диапазоном. Исправлено вместе с зашитыми
  `(uint32_t)`-каст в [`edit_factor.c.jinja`](../templates/edit_factor.c.jinja),
  которые сломались после того, как `dword` стал знаковым.
- `double_click_cb`/`long_click_cb`/`event_cb` при кастомном имени нигде не
  форвард-декларировались — добавлено в [`edit.h.jinja`](../templates/edit.h.jinja).
- Кастомное имя `draw_value_cb`/`click_cb`/`position_cb` честно работало как
  «только объявление» лишь для `role: callback` — для `factor`/`simple`/`fixed`
  шаблон всё равно генерировал тело под этим именем, т.к. ветвление шло по `role`,
  а не по `function_info.source`. Исправлено в
  [`draw.c.jinja`](../templates/draw.c.jinja) и
  [`edit.c.jinja`](../templates/edit.c.jinja).
- `%d`/`%u` на значениях `int32_t`/`uint32_t` заменены на `%ld`/`%lu` с явными
  приведениями типов `(long)`/`(unsigned long)` в шаблонах `draw_*.c.jinja`.
- `menu_draw_update()` выпадала из конца `bool`-функции на обычном пути без
  `return` — добавлен недостающий `return true;`.

### 🖱️ Диспетчеризация клика с учётом состояния

- Добавлены `menu_click()`/`menu_long_click()` в
  [`handle.c.jinja`](../templates/handle.c.jinja)/`handle.h.jinja`: короткий клик
  всегда означает «вперёд» (войти глубже, либо выйти из редактирования, если уже
  в нём), долгий клик — «альтернативное действие» (уровень выше при навигации,
  смена множителя/шага при редактировании). Прошивке больше не нужно самой
  ветвиться по `menu_state()`; `menu_enter()`/`menu_back()` по-прежнему доступны
  напрямую.

### 🏷️ Статический `tag` и общие аксессоры значения

- Добавлено необязательное поле `tag` для узлов меню (например, адрес
  аппаратного регистра), доступное только для чтения как `ctx->configs[id].tag`
  — статическая конфигурация, а не изменяемый union значения.
- Добавлены [`value_access.h.jinja`/`.c.jinja`](../templates/value_access.c.jinja) →
  `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32`,
  диспетчеризующие по категории узла чтение/запись текущего значения независимо
  от роли. Вместе с `tag` заменяют ручной `switch` по каждому `menu_id_t`
  (например, отображение узлов меню на SPI-регистры) циклом по `MENU_ID_COUNT`.

## [2026-08-01] — Реструктуризация пакета и i18n

### 🏗️ Реструктуризация пакета

- В корне проекта теперь находится **только** точка входа [`generate_menu.py`](../generate_menu.py:1).
- Весь исходный код, конфигурация, шаблоны, locale-каталоги и сгенерированный вывод
  перенесены в Python-пакет [`generate_menu/`](../generate_menu/):
  - добавлены [`__init__.py`](../generate_menu/__init__.py) и [`managers/__init__.py`](../generate_menu/managers/__init__.py);
  - все внутренние импорты переведены на **относительные** (например, `from .i18n import _`,
    `from ..menu_data import MenuData`, `from .callback_manager import CallbackManager`);
  - удалён старый корневой entry point `generator.py`.
- [`generate_menu.py`](../generate_menu.py:1) меняет рабочую директорию на пакет перед
  созданием [`MenuGenerator`](../generate_menu/menu_generator.py:15), т.к. `templates_path`,
  `output_directory` и `output_flattern` зависят от CWD.
- Исправлен путь `output_flattern` в [`config.yaml`](../generate_menu/config/config.yaml:1):
  `../output/flatterned.json` → `output/flatterned.json`.

### 🌐 Комментарии и докстринги переведены на английский

- Все комментарии и докстринги во всех Python-файлах теперь на английском
  (ранее многие были на русском).
- Убраны остатки: удалён случайный отладочный `print()` в `main()`
  ([`menu_config.py`](../generate_menu/menu_config.py:145)), убран дублирующий импорт.

### 📚 Документация

- Добавлены [`docs/architect.md`](./architect.md) (en) и [`docs/architect_ru.md`](./architect_ru.md) (ru)
  — обзор архитектуры, разбор модулей, конфигурация и разрешение путей, известные проблемы
  и приоритизированный план улучшений.
- Добавлены [`docs/changes.md`](./changes.md) (en) и [`docs/changes_ru.md`](./changes_ru.md) (ru) — этот журнал.
- Переписан [`README.md`](../README.md) (en/ru): назначение проекта, примеры конфигурации,
  как это работает, а также ссылки на документацию.

## [2026-08-01] — YAML-конфигурация

- Добавлен универсальный загрузчик [`load_config_file()`](../generate_menu/common.py:25),
  автоматически определяющий формат по расширению (`.json` / `.yaml` / `.yml`).
- [`MenuConfig`](../generate_menu/menu_config.py:17) теперь поддерживает и JSON, и YAML.
- Добавлены YAML-конфиги:
  - [`config/config.yaml`](../generate_menu/config/config.yaml:1)
  - [`config/files.yaml`](../generate_menu/config/files.yaml:1)
  - [`config/menu_data.yaml`](../generate_menu/config/menu_data.yaml:1)
  - [`config/menu_schema.yaml`](../generate_menu/config/menu_schema.yaml:1)
  - [`menu/menu.yaml`](../generate_menu/menu/menu.yaml:1)
- Все точки входа переведены на `./config/config.yaml`.
- JSON-файлы оставлены как резервные/справочные (могут быть удалены после проверки).

## [2026-08-01] — Интернационализация (gettext / Babel)

- Все пользовательские сообщения интернационализированы через **gettext (Babel)**.
- Основной (исходный) язык — **английский**.
- Добавлен [`i18n.py`](../generate_menu/i18n.py) с самокорректирующимся каталогом locale
  (`Path(__file__).resolve().parent / "locale"`).
- Добавлены [`babel.cfg`](../generate_menu/babel.cfg) и структура каталогов
  `locale/messages.pot`, `locale/ru/LC_MESSAGES/messages.{po,mo}`.
- Язык выбирается через переменную окружения `MENU_PROCESSOR_LANG` (например, `ru`);
  при отсутствии или ошибке используется английский (fallback).

## [Раньше] — Первоначальная реализация

- Базовая цепочка: загрузка конфигов, валидация (JSON Schema + кастомная),
  флаттенинг, модель узла на менеджерах, агрегация, генерация C-кода на Jinja2
  для меню LCD1602.
