# 📝 Changelog (Menu Processor)

All notable changes are listed in reverse chronological order.
The format is inspired by [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### 🖥️ GUI: "New" document flow + "Project" tab

- Added `File > New` (`Ctrl+N`) to [`gui/main_window.py`](../gui/main_window.py):
  starts a fresh, minimal, unsaved document. Since `MenuConfig` only ever
  loads from a real file, this writes a small schema-valid template to a
  GUI-owned scratch file (`menu/.new.yaml`, gitignored) and opens that, then
  clears `current_path` so `Save`/`Generate` still route through `Save As...`
  instead of quietly writing back to the scratch file.
- Added a "Project" tab ([`gui/project_form.py`](../gui/project_form.py))
  alongside the node form, for the document's own `config:` block —
  `version`, `author`, the navigate/control defaults, `output_directory`,
  `include_files`, `wrap_by_name_functions`, `enable_node_names`. Shares the
  same in-memory dict as the "Set output directory..." toolbar action, so
  both stay in sync.

### 🔒 YAML boolean parsing narrowed to `true`/`false`

- `generate_menu/common.py::load_config_file` used plain `yaml.safe_load`,
  which follows YAML 1.1 and silently turns unquoted `yes`/`no`/`on`/`off`
  (any case) into Python booleans — so `values: [Off, On]` on a `fixed`-role
  node became `[False, True]` before schema validation ever saw a string,
  surfacing only as a confusing `False is not of type 'string', 'number'`.
  Added `_StrictBoolLoader` (a `yaml.SafeLoader` subclass whose bool resolver
  only matches `true`/`false`, i.e. the YAML 1.2 core schema) and switched
  `load_config_file` to use it — the only place in the codebase that reads
  YAML.

### ✅ Validation consolidated into a single `MenuValidator` pass

- `min > max` is now checked in [`MenuValidator`](../generate_menu/menu_validator.py)
  regardless of whether `default` is present — previously a node with
  `min: 100, max: 10` and no `default` slipped past the raw-tree validator and
  was only caught on the flattened tree. The GUI's Validate button (which calls
  `MenuValidator` directly, without flattening) catches it too.
- Removed the duplicated flattened-tree pass as fully redundant:
  `MenuCraft._validate_flat_data()` (and its call in `MenuCraft.__init__`),
  `NodeDataManager.validate_numeric_range()`/`validate_fixed_values()` and
  `BaseFlatNode.validate_data()` are gone — the pipeline is back to a single
  pre-flatten validation via `MenuValidator`.

### 🔢 printf-format moved from templates to config

- `printf_format`/`printf_cast` are now part of `types:` in
  [`config/menu_data.yaml`](../config/menu_data.yaml) for the six integer types
  (`byte`/`ubyte`/`word`/`uword`/`dword`/`udword`) — `%ld` + `(long)` for signed,
  `%lu` + `(unsigned long)` for unsigned — and flow through `MenuData.printf_format()`/
  `printf_cast()` into `FunctionInfo` for the templates.
- [`draw_simple.c.jinja`](../templates/draw_simple.c.jinja),
  [`draw_factor.c.jinja`](../templates/draw_factor.c.jinja) and
  [`draw_fixed.c.jinja`](../templates/draw_fixed.c.jinja) now use those fields
  instead of hardcoded `if/elif` over type lists (generated C is byte-identical,
  verified by a golden diff).
- `float` is deliberately left as-is: its precision is role-dependent
  (`%3.3f` in `simple`, `%2.2f` in `factor`/`fixed`), so it stays in the templates.

### 📏 `menu_draw_pad_marker()` made public

- The line-padding/state-marker helper in [`draw.c.jinja`](../templates/draw.c.jinja)
  was `static` and undeclared, so any custom `draw_value_cb` had to hand-copy its
  padding/marker logic — found via a real duplicate (`draw_value_marker()`) in
  HiPIMS_Menu's glue code, independently reimplementing it against a hardcoded
  row length that would silently drift if `MENU_LINE_LEN` or the marker
  characters ever changed. Renamed to `menu_draw_pad_marker(ctx)`, dropped
  `static`, declared in [`draw.h.jinja`](../templates/draw.h.jinja) — same
  simple signature (measures `strlen(ctx->value_buf)` itself), now callable
  directly from custom callbacks instead of being reimplemented per project.

### 🔢 `raw_values` for `role: fixed`

- Added an optional `raw_values` array on `fixed`-role nodes, parallel to
  `values` by index — the real underlying number (e.g. a register code) behind
  each display entry. `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/
  `menu_set_uint32` ([`value_access.c.jinja`](../templates/value_access.c.jinja))
  use it instead of the raw index when set; `menu_set_*` does a linear search
  and leaves `idx` unchanged if the value isn't found, rather than guessing.
  Falls back to `idx` when unset, so existing menus are unaffected.
- Length-checked against `values` in [`MenuValidator`](../generate_menu/menu_validator.py)
  (the only validator wired into the pipeline).
- Exposed in the GUI node form ([`gui/node_form.py`](../gui/node_form.py)) as an
  optional "Raw values" list next to "Values" for `role: fixed`; emptying it
  removes the key rather than leaving `[]`. A generic "Tag" field was also
  added for any leaf, alongside `tag` from the previous round.

### 🖥️ PyQt6 GUI

- Added [`gui.py`](../gui.py) / [`gui/`](../gui/) — tree + node property form, Validate
  and Generate C files buttons, a log panel, and a shadow config
  (`config/.gui_config.yaml`, gitignored) so the real `config/config.yaml` is never
  touched by the GUI. See [`docs/gui.md`](./gui.md) / [`docs/gui_ru.md`](./gui_ru.md).

### 🔀 `--menu PATH` / `menu_override`

- [`MenuConfig`](../generate_menu/menu_config.py), [`MenuCraft`](../generate_menu/menucraft.py)
  and [`MenuGenerator`](../generate_menu/menu_generator.py) accept an optional
  `menu_override` path that replaces just the `menu` tree, keeping
  `menu_schema`/`data_rules`/`generation_files`/`flatten` from the main config.
  Exposed on the CLI as `--menu PATH` — generate a different device's tree without
  writing a new wrapper `config/*.yaml`.
- The test suite uses the same mechanism: [`menu/test.yaml`](../menu/test.yaml) is a
  frozen fixture tree, wired in via `conftest.py`'s `menu_override_path` fixture, so
  tests no longer depend on the actively-edited `menu/menu.yaml`.

### 🐛 Type & callback-generation bug fixes

- `dword` incorrectly mapped to `uint32_t` (duplicating `udword`) instead of the
  signed `int32_t` in [`config/menu_data.yaml`](../config/menu_data.yaml) — broke
  negative-range fields. Fixed, along with hardcoded `(uint32_t)` casts in
  [`edit_factor.c.jinja`](../templates/edit_factor.c.jinja) that broke once `dword`
  became signed.
- `double_click_cb`/`long_click_cb`/`event_cb` had no forward declaration anywhere
  when custom-named — added to [`edit.h.jinja`](../templates/edit.h.jinja).
- A custom `draw_value_cb`/`click_cb`/`position_cb` name only got an honest
  "declaration only" override for `role: callback` — for `factor`/`simple`/`fixed`
  the template still generated a body under that name, because the branch checked
  `role` instead of `function_info.source`. Fixed in
  [`draw.c.jinja`](../templates/draw.c.jinja) and
  [`edit.c.jinja`](../templates/edit.c.jinja).
- `%d`/`%u` on `int32_t`/`uint32_t` values replaced with `%ld`/`%lu` +
  `(long)`/`(unsigned long)` casts in the `draw_*.c.jinja` templates.
- `menu_draw_update()` fell off the end of a `bool`-returning function on the normal
  path — added the missing `return true;`.

### 🖱️ State-aware click dispatch

- Added `menu_click()`/`menu_long_click()` to
  [`handle.c.jinja`](../templates/handle.c.jinja)/`handle.h.jinja`: short click
  always means "advance" (drill in, or exit edit mode if already editing), long
  click is the "alternate action" (up a level while navigating, change
  factor/step while editing). Firmware no longer needs to branch on
  `menu_state()` itself; `menu_enter()`/`menu_back()` are still exposed directly.

### 🏷️ Static `tag` + generic value accessors

- Added an optional `tag` field on menu nodes (e.g. a hardware register id),
  surfaced read-only as `ctx->configs[id].tag` — static config, not the mutable
  value union.
- Added [`value_access.h.jinja`/`.c.jinja`](../templates/value_access.c.jinja) →
  `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32`, which
  dispatch on a node's category to read/write its current value regardless of
  role. Combined with `tag`, replaces a hand-written per-`menu_id_t` `switch`
  (e.g. mapping menu nodes to SPI registers) with a loop over `MENU_ID_COUNT`.

## [2026-08-01] — Package restructure & i18n

### 🏗️ Package restructure

- The project root now contains **only** the entry point [`generate_menu.py`](../generate_menu.py:1).
- All source code, configuration, templates, locale catalogs and generated output moved
  into the [`generate_menu/`](../generate_menu/) Python package:
  - added [`__init__.py`](../generate_menu/__init__.py) and [`managers/__init__.py`](../generate_menu/managers/__init__.py);
  - all intra-package imports converted to **relative imports** (e.g. `from .i18n import _`,
    `from ..menu_data import MenuData`, `from .callback_manager import CallbackManager`);
  - removed the old top-level `generator.py` entry point.
- [`generate_menu.py`](../generate_menu.py:1) changes the working directory into the package before
  constructing [`MenuGenerator`](../generate_menu/menu_generator.py:15), because
  `templates_path`, `output_directory` and `output_flattern` are CWD-relative.
- Fixed `output_flattern` path in [`config.yaml`](../generate_menu/config/config.yaml:1):
  `../output/flatterned.json` → `output/flatterned.json`.

### 🌐 Comments & docstrings translated to English

- All comments and docstrings in every Python source file are now in English
  (previously many were in Russian).
- Cleaned up leftovers: removed a stray debug `print()` in
  [`menu_config.py`](../generate_menu/menu_config.py:145) `main()`, deduplicated an import.

### 📚 Documentation

- Added [`docs/architect.md`](./architect.md) (en) and [`docs/architect_ru.md`](./architect_ru.md) (ru)
  — architecture overview, module breakdown, configuration & path resolution, known issues
  and a prioritized improvement plan.
- Added [`docs/changes.md`](./changes.md) (en) and [`docs/changes_ru.md`](./changes_ru.md) (ru) — this changelog.
- Rewrote [`README.md`](../README.md) (en/ru): project purpose, examples of configuration,
  how it works, plus links to the docs.

## [2026-08-01] — YAML configuration

- Added a universal loader [`load_config_file()`](../generate_menu/common.py:25) that auto-detects
  the format by extension (`.json` / `.yaml` / `.yml`).
- [`MenuConfig`](../generate_menu/menu_config.py:17) now supports both JSON and YAML.
- Added YAML configs:
  - [`config/config.yaml`](../generate_menu/config/config.yaml:1)
  - [`config/files.yaml`](../generate_menu/config/files.yaml:1)
  - [`config/menu_data.yaml`](../generate_menu/config/menu_data.yaml:1)
  - [`config/menu_schema.yaml`](../generate_menu/config/menu_schema.yaml:1)
  - [`menu/menu.yaml`](../generate_menu/menu/menu.yaml:1)
- All entry points now use `./config/config.yaml`.
- JSON files kept as fallback/reference (can be removed once verified).

## [2026-08-01] — Internationalization (gettext / Babel)

- All user-facing messages internationalized with **gettext (Babel)**.
- Primary (source) language: **English**.
- Added [`i18n.py`](../generate_menu/i18n.py) with a self-adjusting locale directory
  (`Path(__file__).resolve().parent / "locale"`).
- Added [`babel.cfg`](../generate_menu/babel.cfg) and the catalog structure
  `locale/messages.pot`, `locale/ru/LC_MESSAGES/messages.{po,mo}`.
- Language is selected via the `MENU_PROCESSOR_LANG` environment variable (e.g. `ru`);
  falls back to English if unset or missing.

## [Earlier] — Initial implementation

- Base pipeline: config loading, validation (JSON Schema + custom), flattening,
  manager-based node model, aggregation, Jinja2 code generation for the LCD1602 menu.
