# 📐 Architecture Overview & Recommendations (Menu Processor)

> Date: 2026-08-01 · Analysis performed against the current code base.

## 1. System Overview

The project is a **Python generator of C code** for an embedded LCD1602 menu system.
The menu is described declaratively in configuration files, and the generator produces
a full set of C source and header files (data tables, navigation, drawing, editing, etc.).

The processing pipeline:

```
config/config.yaml
  → MenuConfig            — loads all configuration files
  → MenuValidator         — JSON Schema + custom validation of the tree
  → MenuFlattener         — expands the tree into a flat list + navigation links
  → FlatNode/BaseFlatNode — node built from a composition of managers
  → MenuCraft             — coordinator, aggregates data for the templates
  → MenuGenerator         — renders Jinja2 templates → C files
```

### Repository layout

```
MenuCraft/
├── generate_menu.py              # Root entry point (chdirs into the package)
├── generate_menu/                # Python package
│   ├── __init__.py
│   ├── i18n.py                   # gettext helper (_) with self-adjusting locale dir
│   ├── common.py                 # config loaders (JSON/YAML), json helpers
│   ├── menu_config.py            # loads & validates all config files
│   ├── menu_data.py              # type/role/control/navigation rules
│   ├── menu_validator.py         # schema + custom validation
│   ├── menu_flattener.py         # tree → flat list, cyclic/limit navigation
│   ├── base_flat_node.py         # BaseFlatNode (manager composition)
│   ├── flat_node.py              # FlatNode (final node class)
│   ├── menucraft.py              # coordinator & aggregator
│   ├── menu_generator.py         # Jinja2 rendering → C files
│   ├── managers/
│   │   ├── node_data_manager.py      # data: values, factors, types, categories
│   │   ├── node_control_manager.py   # controls + auto function generation
│   │   ├── node_navigation_manager.py# navigation links & cyclic logic
│   │   ├── callback_manager.py       # callback functions of a node
│   │   └── function_info.py          # FunctionInfo dataclass + factories
│   ├── config/                   # YAML/JSON config files
│   ├── menu/                     # menu tree (menu.yaml / menu.json)
│   ├── templates/                # Jinja2 templates (*.jinja)
│   ├── locale/                   # gettext catalogs (messages.pot, ru/...)
│   └── output/                   # generated C files (include/ + sources)
├── docs/                         # Documentation (this folder)
│   ├── architect.md / architect_ru.md
│   └── changes.md / changes_ru.md
├── README.md
└── requirements.txt
```

### Design strengths

- ✅ Clean **manager composition** per node: [`NodeDataManager`](../generate_menu/managers/node_data_manager.py:4), [`NodeControlManager`](../generate_menu/managers/node_control_manager.py:8), [`NodeNavigationManager`](../generate_menu/managers/node_navigation_manager.py:5), [`CallbackManager`](../generate_menu/managers/callback_manager.py:5) — good separation of concerns.
- ✅ Pipeline separation: load → validate → flatten → generate.
- ✅ [`FunctionInfo`](../generate_menu/managers/function_info.py:6) dataclass + factory methods.
- ✅ Jinja2 templates are extracted from the code.
- ✅ Config is available in both **JSON and YAML** (universal loader in [`common.py`](../generate_menu/common.py:25)).
- ✅ All user-facing messages are internationalized via **gettext / Babel** ([`i18n.py`](../generate_menu/i18n.py)).

---

## 2. Modules in detail

### 2.1 [`menu_config.py`](../generate_menu/menu_config.py:17) — `MenuConfig`

Loads the main configuration file and, based on it, all required files
(`menu`, `menu_schema`, `menu_config`, `generation_files`). Required files are
resolved **relative to the main config file** via [`_load_required_file`](../generate_menu/menu_config.py:32).
CWD-relative values (`templates_path`, `output_directory`, `output_flattern`) are used
as-is — this is why the root entry point changes the working directory into the package.

### 2.2 [`menu_data.py`](../generate_menu/menu_data.py:17) — `MenuData`

Holds the rules: types → C types, roles → allowed types, controls per role,
navigation rules per control, role rules (purpose, required controls, external callbacks).
Provides lookups used by the managers: [`get_controls_for_type`](../generate_menu/menu_data.py:40),
[`get_navigation_rules`](../generate_menu/menu_data.py:57), [`get_control_config`](../generate_menu/menu_data.py:95).
Integer types (`byte`, `ubyte`, `word`, `uword`, `dword`, `udword`) also carry
`printf_format`/`printf_cast` (e.g. `%ld` + `(long)` for signed, `%lu` +
`(unsigned long)` for unsigned). `MenuData.printf_format()`/`printf_cast()`
expose them and the draw templates use them instead of hardcoded type lists.
`float` is present in `types:` with `c_type: float` (roles `simple`/`factor`,
not `fixed`) but deliberately has no `printf_format` — its precision is
role-dependent (`%3.3f` in `simple`, `%2.2f` in `factor`/`fixed`) and stays
hardcoded in the draw templates. [`MenuValidator`](../generate_menu/menu_validator.py)
rejects any used type without a `c_type` mapping in `menu_data.yaml`, so a type
added to the JSON Schema enum but forgotten in the config fails validation
instead of silently generating `None` in C.

### 2.3 [`menu_validator.py`](../generate_menu/menu_validator.py:16) — `MenuValidator`

Validates the menu tree: JSON Schema (`Draft7Validator`) plus custom tree walk
([`_validate_item`](../generate_menu/menu_validator.py:63), default values, factors, values).
Collects errors as `{path: [messages]}`.

### 2.4 [`menu_flattener.py`](../generate_menu/menu_flattener.py:16) — `MenuFlattener`

Turns the nested menu tree into a flat list of [`FlatNode`](../generate_menu/flat_node.py:6) objects
and wires up navigation: sibling links, parent/branch rules, cyclic wrapping
([`_create_cyclic_siblings`](../generate_menu/menu_flattener.py:87)).

### 2.5 [`base_flat_node.py`](../generate_menu/base_flat_node.py:9) — `BaseFlatNode`

Base node class composed of managers: data, control, navigation, callbacks.
Exposes high-level properties used by templates and the processor
(`controls`, `all_function_infos`, `get_control_summary`, ...).

### 2.6 Managers

- [`NodeDataManager`](../generate_menu/managers/node_data_manager.py:4) — values, factors, `c_str_*` helpers, data summary.
- [`NodeControlManager`](../generate_menu/managers/node_control_manager.py:8) — builds controls from role rules, generates automatic function names, validates required functions.
- [`NodeNavigationManager`](../generate_menu/managers/node_navigation_manager.py:5) — sibling/cyclic links, tree structure properties, sibling chain, debug output.
- [`CallbackManager`](../generate_menu/managers/callback_manager.py:5) — auto vs custom callbacks, effective callback names, summaries.
- [`FunctionInfo`](../generate_menu/managers/function_info.py:6) — dataclass describing a generated function; `create_auto` / `create_custom` factories.

### 2.7 [`menucraft.py`](../generate_menu/menucraft.py:17) — `MenuCraft`

Coordinator. Loads config, validates, flattens, then exposes many aggregation
properties (`functions`, `categories`, `functions_by_event_type`,
`functions_by_navigation`, `required_functions`, `custom_callbacks`,
`auto_generated_functions`, `callback_summary_by_category`, ...) and saves
intermediate JSON (`output/flatterned.json`, `output/functions.json`).

### 2.8 [`menu_generator.py`](../generate_menu/menu_generator.py:15) — `MenuGenerator`

Builds the Jinja2 context from the processor, then renders every template listed in
`generation_files` (files.yaml) into the output directory.

### 2.9 Entry point [`generate_menu.py`](../generate_menu.py:1)

The only file at the project root. It resolves the `generate_menu/` package directory,
**changes the working directory into it** (because `templates_path`, `output_directory`
and `output_flattern` are CWD-relative), adds the project root to `sys.path`, then
constructs [`MenuGenerator`](../generate_menu/menu_generator.py:15) with `./config/config.yaml`.

---

## 3. Configuration & path resolution

| Value | Resolved relative to | Example |
|-------|----------------------|---------|
| `menu`, `menu_schema`, `menu_config`, `generation_files` | the config file itself (`config/`) | `../menu/menu.yaml` |
| `templates_path` (in `files.yaml`) | current working directory | `./templates/` |
| `output_directory` (in `menu.yaml`) | current working directory | `./output/` |
| `output_flattern` (in `config.yaml`) | current working directory | `output/flatterned.json` |

Because the CWD-dependent values point into `generate_menu/`, the root entry point
performs `os.chdir(package_dir)` before construction.

Main config [`config.yaml`](../generate_menu/config/config.yaml:1):

```yaml
menu: ../menu/menu.yaml
menu_schema: menu_schema.yaml
menu_config: menu_data.yaml
output_flattern: output/flatterned.json
generation_files: files.yaml
```

---

## 4. Known issues & recommendations

### 4.1 Critical / architectural

#### 🔴 A1. "God-object" in `MenuCraft`
[`menucraft.py`](../generate_menu/menucraft.py:17) contains **20+ properties**, each of which
re-walks `_flat_nodes` and builds aggregated dicts (`functions`, `categories`,
`functions_by_event_type`, `functions_by_navigation`, `functions_by_type_role`,
`functions_by_type`, `functions_by_role`, `callback_summary_by_category`,
`required_functions`, `custom_callbacks`, `auto_generated_functions`, ...).

Problems:
- O(N × M) repeated iterations over nodes;
- lots of near-identical "group by key" code;
- hard to test.

**Recommendation:** move aggregation into a separate `MenuDataAggregator` (or a set of
functions) that walks the nodes once and caches results (`functools.cached_property`).
This both simplifies [`MenuCraft`](../generate_menu/menucraft.py:17) and speeds up generation.

#### 🔴 A2. Dead / unreachable code
In [`managers/node_control_manager.py`](../generate_menu/managers/node_control_manager.py:172),
`all_function_infos` has an **unreachable continuation** after `return infos` — dead code
that never executes but confuses readers. Also:
- [`_apply_parent_navigation_rules`](../generate_menu/menu_flattener.py:62) — not called (duplicate of `_apply_branch_navigation_rules`);
- [`MenuValidator._validate_data_type`](../generate_menu/menu_validator.py:111) — returns an empty list (stub);
- many commented-out `print(f"DEBUG ...")` lines across managers.

**Recommendation:** remove unreachable blocks and stubs; clean up commented debug lines.

#### 🔴 A3. `print()` instead of logging
The whole code base relies on `print()` with emoji (including production paths).

**Recommendation:** switch to the `logging` module: `logger = logging.getLogger(__name__)`.
Output stays readable but becomes controllable (levels, files, disabling).

#### 🔴 A4. Config: inconsistent keys and typos
- `output_flattern` — a typo (`flatten`), mirrored in [`save_flattern_json`](../generate_menu/menucraft.py:50).
- The `menu_config` key points at `menu_data.json` — confusion between "menu config" and
  "type/role rules".
- `files.json` uses `templates_path` while some legacy files used `templates`.
- The `menu` key loads the menu tree while `menu_config` loads data rules.

**Recommendation:** unify key names (e.g. `menu_tree`, `data_rules`, `generation_files`,
`templates_path`), fix typos, align the schema with the rules.

#### 🔴 A5. Paths: absolute paths & portability
Some legacy JSON files (`menu.json`, `files_orig.json`, `files_test01.json`) contained
hard-coded absolute paths (`/home/yevst/...`).

**Recommendation:** keep `output_directory` in the menu config with a default of `./output/`
and resolve all config paths relative to the project root (done for YAML configs).

#### 🔴 A6. Side-effect constructors
- [`MenuCraft.__init__`](../generate_menu/menucraft.py:18) performs all loading/validation/flattening and throws exceptions.
- [`MenuGenerator.__init__`](../generate_menu/menu_generator.py:16) immediately calls `_generate_code()`.

**Recommendation:** constructors should only store dependencies; run methods explicitly
(`processor.run()`, `generator.generate()`). This simplifies testing and reuse.

### 4.2 Optimization & improvements

#### 🟡 B1. Single entry point (CLI)
Several modules have a `main()` + `if __name__ == "__main__":` block with a hard-coded
config path.

**Recommendation:** one `cli.py`/`__main__.py` with `argparse` (`--config`, `--output`,
`--flat-only`, `--debug`); library modules should not carry `main()`.

#### 🟡 B2. No tests
There are no tests (neither `pytest` nor `unittest`); debug `main()`s act as substitutes.

**Recommendation:** add `tests/` with `pytest`:
- unit: `MenuData` (type/role/control rules);
- unit: `MenuValidator` (valid/invalid trees);
- unit: `MenuFlattener` (links, cyclic navigation);
- e2e: full generation from a sample config → assert C files are produced.

#### 🟡 B3. Cache aggregations
Compute `MenuCraft` derived properties once; especially relevant for large menu trees.

#### ✅ B4. Validation duplication — consolidated into `MenuValidator`
Validation now lives in a single place: [`MenuValidator._validate_item`](../generate_menu/menu_validator.py:63),
which runs on the raw tree before flattening and is also what the GUI's Validate button
calls directly (without flattening). The flattened-tree pass
(`MenuCraft._validate_flat_data()`, `NodeDataManager.validate_numeric_range/validate_fixed_values`,
`BaseFlatNode.validate_data()`) has been removed as fully redundant, and the one check it
uniquely caught — `min > max` with no `default` present to key off of — was moved into
`MenuValidator` as `_validate_min_max`, so it now fires regardless of `default`.

#### 🟡 B5. `pathlib.Path` everywhere
Mixed `os.path`, strings and `Path`. Standardize on `pathlib.Path`.

#### 🟡 B6. `CallbackManager` temporal coupling
[`CallbackManager`](../generate_menu/managers/callback_manager.py:13) is initialized with empty `_auto_*`
and filled later via [`set_auto_functions`](../generate_menu/managers/callback_manager.py:35) from
`NodeControlManager` — fragile (easy to forget the call). **Recommendation:** pass the auto
functions at construction or compute them lazily.

#### 🟡 B7. Inconsistent typing
Mixed `Dict`/`dict`, `List`/`list` in annotations. Unify (preferably modern syntax
`dict[str, ...]`, Python 3.10+).

#### 🟡 B8. Unnecessary imports
- `menu_flattener.py` imports `MenuValidator` — unused.
- `menu_generator.py` imported `Environment` twice (fixed).

#### 🟡 B9. Schema for `menu_data.yaml`
Type/role/control rules are not validated at all. Add a schema/validation for this file.

---

## 5. Priority plan

| Priority | Task | Files |
|----------|------|-------|
| 🔴 P0 | Switch config to YAML (done) | `common.py`, `menu_config.py`, `config/*.yaml`, `menu/menu.yaml` |
| 🔴 P0 | Remove dead code & unreachable blocks | `node_control_manager.py`, `menu_flattener.py`, `menu_validator.py` |
| 🔴 P1 | `logging` instead of `print()` | all modules |
| 🔴 P1 | Fix typos & config keys | `menu_config.py`, `config/*` |
| 🟡 P2 | Extract aggregation from `MenuCraft` | new `aggregator.py` |
| 🟡 P2 | Single CLI with `argparse` | new `cli.py` |
| 🟡 P2 | `pytest` tests | `tests/` |
| 🟡 P3 | Unified validation, `pathlib`, typing | all modules |

> The YAML migration (P0) and the gettext/i18n integration are already implemented —
> see [changes.md](./changes.md) for details.
