# 🎛️ C Menu Generator for Embedded LCD1602

> 🇬🇧 English · [🇷🇺 Русский](#русская-версия)

**Generate C source code for an embedded LCD1602 menu system from a declarative
configuration.** You describe the menu tree in YAML/JSON — the generator produces a
complete set of C files (data tables, navigation, drawing, editing, callbacks) ready
to be compiled into your firmware.

---

## 📖 Table of contents

- [Why this project](#why-this-project)
- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Configuration](#configuration)
  - [Main config](#main-config-configconfigyaml)
  - [Menu tree](#menu-tree-menumenuyaml)
  - [Type / role / control rules](#type--role--control-rules-configmenudatayaml)
  - [Generation files](#generation-files-configfilesyaml)
- [Node reference](#node-reference)
- [GUI](#gui)
- [Generated files](#generated-files)
- [Internationalization (i18n / gettext)](#internationalization-i18n--gettext)
- [Tests](#tests)
- [Documentation](#documentation)

---

## Why this project

Writing an LCD menu system in C by hand is repetitive and error-prone: data tables,
navigation links, value drawing and editing callbacks, cyclic/limited navigation rules
— every device needs a slightly different version of the same boilerplate.

This project **treats the menu as data**. Instead of writing C, you write a small
declarative configuration:

- **types** → C types (byte, uword, string, …)
- **roles** → how a value behaves (`simple`, `factor`, `fixed`, `callback`)
- **controls** → which encoder actions are supported (`click`, `position`)
- **navigation** → cyclic or limited (`cyclic` / `limit`)
- **callbacks** → your own handlers or auto-generated ones

The generator validates the configuration, flattens the tree into a navigable
structure, and renders Jinja2 templates into C files that compile into your firmware.

## How it works

```
config/config.yaml
  → MenuConfig            loads all configuration files
  → MenuValidator         JSON Schema + custom validation of the tree
  → MenuFlattener         expands the tree into a flat list + navigation links
  → FlatNode/BaseFlatNode node built from a composition of managers
  → MenuCraft             coordinator, aggregates data for the templates
  → MenuGenerator         renders Jinja2 templates → C files
```

The pipeline is fully data-driven: the same generator handles any menu — from a single
"Start" screen to a multi-level settings tree with dozens of nodes.

## Repository layout

```
MenuCraft/
├── generate_menu.py              # ← run this: the only entry point at the root
├── generate_menu/                # Python package with all sources
│   ├── cli.py                    # command-line interface (argparse)
│   ├── i18n.py                   # gettext helper
│   ├── common.py                 # JSON/YAML loaders and helpers
│   ├── menu_config.py            # loads & validates all config files
│   ├── menu_data.py              # type/role/control/navigation rules
│   ├── menu_validator.py         # schema + custom validation
│   ├── menu_flattener.py         # tree → flat list, navigation links
│   ├── base_flat_node.py         # base node (manager composition)
│   ├── flat_node.py              # final node class
│   ├── menucraft.py              # coordinator (delegates to the aggregator)
│   ├── menu_data_aggregator.py   # cached aggregations
│   ├── menu_generator.py         # Jinja2 rendering → C files
│   ├── locale/                   # gettext catalogs (messages.pot, ru/...)
│   └── managers/                 # per-node managers
├── config/                       # YAML/JSON configuration files
├── menu/                         # the menu tree (menu.yaml / menu.json)
├── templates/                    # Jinja2 templates (*.jinja)
├── output/                       # generated C files (include/ + sources, git-ignored)
├── docs/                         # documentation (see below)
├── tests/                        # unit & smoke tests (pytest)
├── test/                         # integration tests (pytest)
├── conftest.py                   # shared pytest fixtures
├── pytest.ini
└── requirements.txt
```

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the generator from the project root
python generate_menu.py
```

The generated C files appear in [`output/`](output/) (sources) and
[`output/include/`](output/include/) (headers).

> 💡 The root keeps the entry point [`generate_menu.py`](generate_menu.py) plus the
> asset directories (`config/`, `menu/`, `templates/`, `output/`) and the docs; all
> Python sources live inside the [`generate_menu/`](generate_menu/) package.

### CLI options

| Flag | Meaning |
|------|---------|
| `--config PATH` | Main configuration file (default: `config/config.yaml`) |
| `--menu PATH` | Override just the `menu` tree from `--config`, keeping schema/data-rules/templates from there — lets you generate a different device's menu without writing a new main config file for it |
| `--flat-only` | Validate, flatten and save the flattened menu JSON, but skip C-code generation |
| `--debug` | Enable DEBUG logging and detailed summaries |
| `--quiet` | Only log errors |

```bash
# Generate a different device's tree without a new config/*.yaml wrapper
python generate_menu.py --menu menu/hipims.yaml
```

## Configuration

The main configuration file is [`config/config.yaml`](config/config.yaml).

### Main config: `config/config.yaml`

```yaml
# Paths are relative to this file (the config/ directory)
menu: ../menu/menu.yaml          # the menu tree
menu_schema: menu_schema.yaml    # JSON Schema for validation
menu_config: menu_data.yaml      # type/role/control/navigation rules
output_flattern: output/flatterned.json   # flattened JSON dump (debug)
generation_files: files.yaml     # which templates produce which files
```

### Menu tree: `menu/menu.yaml`

```yaml
config:
  version: "1.0"
  default_navigate: limit
  default_control: position
  default_branch_navigate: cyclic
  root_navigate: cyclic
  output_directory: ./output/    # where generated C files go
  include_files: [pulse_config.h]

menu:
  - id: start                    # a node is defined by id + title
    title: Start
    type: string                 # data type (see rules below)
    role: fixed                  # role: simple / factor / fixed / callback
    values: [Start, Started]     # fixed set of values
    default_idx: 0
    navigate: cyclic             # cyclic or limit

  - id: settings
    title: Settings
    navigate: limit
    items:                       # nested items → sub-menu
      - id: hi_delay
        title: Delay
        type: udword
        role: factor
        default: 10
        min: 10
        max: 10000
        factors: [1, 10, 100, 1000]   # multipliers for the factor role
```

### Type / role / control rules: `config/menu_data.yaml`

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

### Generation files: `config/files.yaml`

```yaml
templates_path: ./templates/     # where Jinja2 templates live
files:
  handle.h.jinja: include/menu.h
  handle.c.jinja: menu.c
  context.h.jinja: include/menu_context.h
  context.c.jinja: menu_context.c
  # ... every template maps to a generated C file
```

## Node reference

A node in the menu tree can use the following fields:

| Field | Meaning |
|-------|---------|
| `id` | Unique identifier of the node |
| `title` | Text shown on the display |
| `type` | Data type: `byte`, `ubyte`, `word`, `uword`, `dword`, `udword`, `string`, `callback` |
| `role` | Behavior: `simple`, `factor`, `fixed`, `callback` |
| `min` / `max` / `step` | Numeric range for `simple` / `factor` |
| `default` | Default numeric value |
| `factors` | Multipliers for the `factor` role |
| `values` / `default_idx` | Fixed value set for the `fixed` role |
| `raw_values` | Optional, `fixed` role only — real numeric values parallel to `values` by index (e.g. register codes behind display strings); must be the same length. `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32` use this instead of the raw index when set |
| `controls` | Encoder controls: `click`, `position` |
| `navigate` | Navigation: `cyclic`, `limit` |
| `items` | Child nodes (sub-menu) |
| `click_cb`, `position_cb`, `double_click_cb`, `long_click_cb`, `event_cb`, `draw_value_cb` | Custom callbacks |
| `tag` | Optional static integer metadata (e.g. a hardware register id), exposed read-only as `ctx->configs[id].tag` — never part of the mutable value union |

If a callback is **not** specified, it is generated automatically
(e.g. `menu_draw_{type}_{role}_value_cb` for drawing, `{type}_{role}_{control}_{navigate}_cb`
for handling).

## GUI

For editing the menu tree without hand-writing YAML, an optional PyQt6 GUI is
available:

```bash
python gui.py
```

It's a thin wrapper around the same pipeline described above — a tree view plus a
property form for the selected node (which fields appear depends on the node's
`type`/`role`, following the same rules from `config/menu_data.yaml`), a sibling
**Project** tab for the document's own `config:` block, **File > New** for a
fresh document, an explicit **Validate** button, and a **Generate C files**
button that runs the real `MenuGenerator` on a background thread. A log panel
at the bottom shows everything the backend already logs, with search and copy.
See [docs/gui.md](docs/gui.md) for the full walkthrough, including how it keeps `config/config.yaml` untouched while
generating.

## Generated files

The generator produces a full C module:

- `menu_context.h/c` — menu context and core structures
- `menu_type.h/c` — data types and enums
- `menu_data_*.h/c` — data configuration, context, value and name tables
- `menu_tree.h/c` — menu tree with navigation links
- `menu_value.h/c` — value access functions
- `menu_value_access.h/c` — generic `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32`, dispatching on a node's category regardless of role
- `menu_navigate.h/c` — navigation functions
- `menu_edit.h/c` — editing functions
- `menu_draw.h/c` — drawing functions
- `menu_name.h/c` — node-name lookup
- `menu.h/c` — top-level entry

## Internationalization (i18n / gettext)

All user-facing messages use **gettext (Babel)**; the primary language is **English**.

Choose the language with the `MENU_PROCESSOR_LANG` environment variable:

```bash
# English (default)
python -X utf8 generate_menu.py

# Russian (uses locale/ru catalog)
set MENU_PROCESSOR_LANG=ru
python -X utf8 generate_menu.py
```

If a catalog is missing or the language is unknown, English is used as fallback.

## Tests

Run the whole suite (unit + integration) from the project root:

```bash
python -m pytest -q
```

- [`docs/tests.md`](docs/tests.md) — unit & smoke tests (`tests/`)
- [`docs/test.md`](docs/test.md) — integration tests (`test/`)

## Documentation

| Document | Language |
|----------|----------|
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
