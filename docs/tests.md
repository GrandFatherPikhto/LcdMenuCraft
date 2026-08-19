# 🧪 Unit & Smoke Tests (`tests/`)

> This document covers the **unit and smoke tests** located in the
> [`tests/`](../tests) directory. For the end-to-end integration tests see
> [test.md](./test.md).

---

## 1. Overview

The `tests/` directory holds fast, dependency-free tests that exercise individual
components of the generator: configuration loading, validation, flattening,
i18n, data rules and aggregation. Together with the integration suite they make up
the full pytest run (currently **54 tests, all passing**).

The suite is split into:

- **smoke tests** — import sanity, real-config load/validate/flatten;
- **unit tests** — focused checks of `MenuData`, `MenuValidator`,
  `MenuFlattener`, `MenuDataAggregator` and the i18n module.

## 2. Shared fixtures

[`conftest.py`](../conftest.py) at the project root is loaded before any test and:

- inserts the project root into `sys.path` so `import generate_menu` works from any
  working directory;
- removes any stale `MENU_PROCESSOR_LANG` before the i18n module is imported (the
  translation is bound at import time), keeping tests deterministic in English;
- provides the fixtures used by every test module:

| Fixture | Scope | Provides |
|---------|-------|----------|
| `project_root` | session | Absolute path of the project root |
| `package_dir` | session | Absolute path of the `generate_menu` package |
| `config_path` | session | Absolute path of `config/test_config.yaml` (**not** the real `config/config.yaml`) |
| `menu_config` | session | `MenuConfig` built from `test_config.yaml` |
| `menu_data` | session | `MenuData` built from `test_config.yaml` |
| `menu_validator` | function | A fresh `MenuValidator` per test (it keeps internal state) |
| `menu_flattener` | function | A fresh `MenuFlattener` per test |

All of these read [`config/test_config.yaml`](../config/test_config.yaml), which
points at [`menu/test.yaml`](../menu/test.yaml) — a frozen copy of the original
sample menu tree — instead of the real [`config/config.yaml`](../config/config.yaml)
/ [`menu/menu.yaml`](../menu/menu.yaml). This keeps the suite (several tests assert
exact node counts and ids) stable while the real menu tree is being edited for an
actual device.

## 3. Test modules

| Module | What it verifies |
|--------|------------------|
| [`test_smoke.py`](../tests/test_smoke.py) | The package imports cleanly; the real config loads, validates and flattens into 18 nodes with `root` first. |
| [`test_validator.py`](../tests/test_validator.py) | Schema + custom validation: duplicate ids, branch/leaf rules, out-of-range defaults, values/factor index bounds, nested error paths (`parent->child`), idempotence of `validate()`. |
| [`test_flattener.py`](../tests/test_flattener.py) | Flattening and links: node count, root branch flags, `get_node_by_id`, leaf/branch flags, cyclic vs limit siblings, explicit vs default `navigate`, empty menu → root only. |
| [`test_menu_data.py`](../tests/test_menu_data.py) | Type/role/control/navigation rules: enums, `c_type()` mapping, roles, `get_controls_for_type`, navigation rules/defaults, `get_control_config`. |
| [`test_menu_data_aggregator.py`](../tests/test_menu_data_aggregator.py) | `MenuDataAggregator` (plan P2/A1): builds from flat nodes, `cached_property` memoization, `MenuCraft` delegation to a single aggregator, identical results. |
| [`test_i18n.py`](../tests/test_i18n.py) | gettext/Babel: default language English, `get_language()` from `MENU_PROCESSOR_LANG`, English identity, Russian catalog applied in a fresh subprocess. |

## 4. Running the unit suite

From the project root:

```bash
# unit + smoke tests only
python -m pytest tests -q

# the whole project suite (unit + integration)
python -m pytest -q
```

## 5. Notes

- The unit tests use the **real** bundled configuration and menu
  (`config/`, `menu/`), so no fixtures or sample files are required.
- `MenuValidator` keeps a list of seen ids between `validate()` calls, therefore the
  tests always build a fresh instance (see the `menu_validator` fixture).
- `MenuFlattener` is stateless and can be reused; a fresh instance per test is
  provided anyway for isolation.
- The i18n subprocess test forces `PYTHONIOENCODING=utf-8` so the Russian output is
  not garbled on Windows (default console encoding is cp1251).
