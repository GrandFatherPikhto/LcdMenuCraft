# 🖥️ GUI (PyQt6)

> A thin PyQt6 wrapper around the same pipeline the CLI uses (`MenuConfig` →
> `MenuValidator` → `MenuFlattener` → `MenuCraft` → `MenuGenerator`): edit the
> menu tree visually, validate it, and generate the C files — without any
> changes to [`generate_menu/`](../generate_menu/).

---

## 1. Launching

```bash
# from the project root, with dependencies installed (PyQt6 is in requirements.txt)
python gui.py

# or as a module
python -m gui
```

Both entry points mirror [`generate_menu.py`](../generate_menu.py)'s bootstrap:
they add the project root to `sys.path` and change the working directory to it,
since config values such as `templates_path`, `output_directory` and `flatten`
are resolved relative to the CWD, not the config file's own location.

On startup the GUI opens the menu file wired into
[`config/config.yaml`](../config/config.yaml) (or the last file recorded in
[`gui_settings.json`](#6-settings), if it still exists).

## 2. Layout

```
┌───────────────────────────────┬─────────────────────────────────┐
│  Menu tree                    │  Node properties                │
│  Add child / Add sibling /    │  fields depend on the node's    │
│  Delete / Move up / Move down │  type / role                    │
├────────────────────────────────┴─────────────────────────────────┤
│  Log (search box, colored by level, Copy All)                    │
└────────────────────────────────────────────────────────────────────┘
```

- **Tree panel** (left, [`gui/tree_panel.py`](../gui/tree_panel.py)) — the live
  menu tree, backed directly by the same node dicts the backend uses. Structural
  edits mutate that list-of-dicts directly and the tree view is rebuilt from it —
  simpler and more robust than incremental item surgery for the tree sizes this
  project deals with (tens of nodes). New-node ids are checked for uniqueness
  across the **whole** tree, matching how `MenuValidator` checks duplicates.
- **Node form** (right, [`gui/node_form.py`](../gui/node_form.py)) — rebuilt on
  every selection. Which fields appear (`type`, `role`, `min`/`max`/`step`,
  `values`/`default_idx`, `factors`, `controls`, `navigate`, the six optional
  callback overrides) is driven by the same rules the backend uses, read
  straight from [`config/menu_data.yaml`](../config/menu_data.yaml) via
  `MenuData`. A role's controls that are marked `required: true` (e.g. `factor`'s
  `click`/`position`) show up pre-checked and disabled — informational only;
  merely viewing a node never writes anything into it. Two fields aren't
  role-driven: an optional **Tag** (any leaf) and an optional **Raw values**
  list shown only for `role: fixed`, parallel to **Values** — see
  [`tag`/`raw_values`](./jinja_templates.md#33-node-config-menuconfighoutputincludemenuconfigh)
  in the generated-code reference. Emptying the Raw values list removes the
  key entirely rather than leaving `[]` behind.
- **Log panel** (bottom, [`gui/log_panel.py`](../gui/log_panel.py)) — every
  `logger.error/info/debug(...)` call already made throughout
  `menucraft.py`/`menu_generator.py`/`menu_flattener.py`/`common.py` shows up
  here in real time, because a single `logging.Handler` is attached to the root
  logger — no backend changes needed for this. Lines are colored by level
  (error/warning/debug), with a search box (`QTextEdit.find`) and a "Copy All"
  button.

## 3. Menu / toolbar actions

| Action | Effect |
|--------|--------|
| Open... | Loads a different menu YAML file, replacing the current document |
| Save / Save As... | Writes the current tree back to YAML (`Ctrl+S` for Save). See [§5](#5-known-limitations) for what is not preserved. |
| Set output directory... | Writes into `config.output_directory` **inside the open menu file itself** — the same field `generate_menu.py` reads |
| Validate | Runs `MenuValidator` against the current in-memory tree — no save required first |
| Generate C files | Replicates `cli.py`'s exact sequence (`MenuCraft` → `validate_required_functions()` gate → `MenuGenerator`) on a background `QThread`, so real Jinja2 rendering + file I/O never freezes the window |

Closing the window with unsaved edits prompts Save / Discard / Cancel.

## 4. How Generate stays safe for `config/config.yaml`

`MenuCraft(config_path: str)` and `MenuGenerator(config_path, processor=None)`
only ever accept a config **path** and always reload from disk — there is no
public way to hand them an in-memory tree directly. Rewriting the repository's
own `config/config.yaml` on every click would produce an unexpected diff in a
shared, git-tracked file every time someone uses the GUI.

Instead, [`MenuDocument`](../gui/document.py) maintains its own shadow config,
`config/.gui_config.yaml` (git-ignored). It copies the four fixed pipeline keys
— `menu_schema`, `data_rules`, `generation_files`, `flatten` — verbatim from the
real `config/config.yaml`, and points its own `menu:` key at an **absolute**
path to whichever file is currently open (`MenuConfig` resolves that key
relative to the shadow config's own directory, so a relative path would
resolve wrong).

*Generate* always: saves the open document to disk, refreshes the shadow
config's `menu:` key, then runs `MenuCraft(shadow_config)` →
`validate_required_functions()` (aborting cleanly, matching the CLI, if a
required callback is missing) → `MenuGenerator(shadow_config, processor=...)`.
`config/config.yaml` is never opened for writing.

## 5. Known limitations

- Saving uses `yaml.safe_dump`, so **comments and formatting in the YAML file
  are not preserved** across a save. Nothing in the current feature set needs
  round-trip formatting, so this wasn't solved with a comment-preserving YAML
  library (e.g. `ruamel.yaml`) — worth revisiting if that becomes a problem.
- There is no "New menu" flow — the GUI always opens an existing YAML file (by
  default, the one wired into `config/config.yaml`).

## 6. Settings

Window geometry, the last opened menu file and the last output directory are
persisted to `gui_settings.json` at the project root (git-ignored,
[`gui/settings.py`](../gui/settings.py)). The file is read tolerantly — a
missing or corrupted settings file falls back to defaults rather than crashing
the app.

## 7. Source layout

```
gui.py                    # root entry point (mirrors generate_menu.py)
gui/
  __init__.py              # docstring + __version__ only, no re-exports
  __main__.py               # enables `python -m gui`
  app.py                     # QApplication bootstrap, attaches the log handler
  document.py                 # MenuDocument -- the only module that imports generate_menu
  main_window.py                # menu/toolbar, splitter layout, wiring, close handling
  tree_panel.py                  # tree view + structural edits (add/delete/move)
  node_form.py                    # dynamic per-node property form
  log_panel.py                     # log view + Qt logging handler
  settings.py                       # JSON settings persistence
```

No file inside [`generate_menu/`](../generate_menu/) is modified by the GUI;
[`tests/`](../tests/)/[`test/`](../test/) and `python -m pytest -q` are
unaffected.
