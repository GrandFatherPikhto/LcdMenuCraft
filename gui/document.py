"""MenuDocument: the single seam between the Qt widgets and the backend.

Design notes (see the plan for the full rationale):

- ``MenuConfig.menu_data`` has a setter, but ``MenuConfig`` caches
  ``menu_tree``/``output_directory``/etc. once in ``__init__`` from the
  *original* loaded dict; the setter never refreshes them. So "opening a
  different file" always rebuilds a fresh ``MenuConfig`` instead of using
  that setter.
- ``MenuCraft``/``MenuGenerator`` only accept a config *path* and always
  reload from disk, so there is no way to feed them an in-memory tree
  directly. Generation therefore always: saves the current document to
  disk, points a GUI-owned *shadow* config file's ``menu:`` key at it, and
  runs the real pipeline against that shadow config -- the repo's own
  ``config/config.yaml`` is never written to.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from generate_menu.common import ConfigLoadError, load_config_file, save_json_data
from generate_menu.menu_config import ConfigError, MenuConfig
from generate_menu.menu_data import MenuData
from generate_menu.menu_flattener import FlattenerError
from generate_menu.menu_generator import MenuGenerator
from generate_menu.menu_validator import MenuValidator
from generate_menu.menucraft import MenuCraft, ProcessorError

logger = logging.getLogger("gui.document")

#: Keys copied verbatim from the real config into the GUI's shadow config.
#: ``menu`` is deliberately excluded -- the shadow config always points at
#: whichever file the GUI currently has open.
SHADOW_CONFIG_KEYS = ("menu_schema", "data_rules", "generation_files", "flatten")

#: Minimal, schema-valid document written by ``MenuDocument.new()``.
NEW_DOCUMENT_TEMPLATE = {
    "config": {
        "version": "1.0",
        "default_navigate": "limit",
        "default_control": "position",
        "default_branch_navigate": "cyclic",
        "root_navigate": "cyclic",
        "output_directory": "./output/",
    },
    "menu": [],
}


class DocumentError(Exception):
    """Raised for document-level problems (open/save/generate) meant for the GUI."""


class MenuDocument:
    def __init__(self, real_config_path: Path, shadow_config_path: Path):
        self._real_config_path = Path(real_config_path)
        self._shadow_config_path = Path(shadow_config_path)
        self._config = MenuConfig(str(self._real_config_path))
        self._menu_data_rules = MenuData(self._config)
        self._current_path: Optional[Path] = None
        self._dirty = False

    # -- accessors ---------------------------------------------------------
    @property
    def config(self) -> MenuConfig:
        return self._config

    @property
    def menu_data(self) -> MenuData:
        """Type/role/control/navigation rules (``config/menu_data.yaml``)."""
        return self._menu_data_rules

    @property
    def tree(self) -> List[dict]:
        return self._config.menu_tree or []

    @property
    def current_path(self) -> Optional[Path]:
        return self._current_path

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        self._dirty = True

    # -- open / save ---------------------------------------------------------
    def open(self, path: Path) -> None:
        """Loads ``path`` as the menu document, replacing the current one."""
        path = Path(path)
        try:
            load_config_file(path)  # validates it parses before we commit to it
        except ConfigLoadError as e:
            raise DocumentError(str(e)) from e

        self._write_shadow_config(path)
        try:
            self._config = MenuConfig(str(self._shadow_config_path))
        except ConfigError as e:
            raise DocumentError(str(e)) from e
        self._menu_data_rules = MenuData(self._config)
        self._current_path = path
        self._dirty = False

    def new(self) -> None:
        """Starts a fresh, minimal, unsaved menu document.

        There is no way to hand ``MenuConfig`` an in-memory tree (see the
        module docstring), so this writes ``NEW_DOCUMENT_TEMPLATE`` to a
        GUI-owned scratch file and opens that -- then clears ``current_path``
        so ``save()``/``generate()`` still treat this as unsaved and route
        through "Save As", instead of quietly overwriting the scratch file.
        """
        scratch_path = self._real_config_path.parent.parent / "menu" / ".new.yaml"
        scratch_path.parent.mkdir(parents=True, exist_ok=True)
        with open(scratch_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(NEW_DOCUMENT_TEMPLATE, f, allow_unicode=True, sort_keys=False)

        self.open(scratch_path)
        self._current_path = None
        self._dirty = False

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path is not None else self._current_path
        if target is None:
            raise DocumentError("No file path set -- use Save As")
        if target.suffix.lower() not in (".yaml", ".yml"):
            raise DocumentError("File must have a .yaml or .yml extension")

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._config.menu_data, f, allow_unicode=True, sort_keys=False)

        if target != self._current_path:
            self._write_shadow_config(target)
        self._current_path = target
        self._dirty = False
        return target

    def _write_shadow_config(self, menu_path: Path) -> None:
        main = load_config_file(self._real_config_path)
        shadow = {key: main[key] for key in SHADOW_CONFIG_KEYS if key in main}
        # Must be absolute: MenuConfig resolves this key relative to the
        # shadow config file's own directory (config/), not the CWD.
        shadow["menu"] = str(Path(menu_path).resolve())
        self._shadow_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._shadow_config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(shadow, f, allow_unicode=True, sort_keys=False)

    # -- output directory ----------------------------------------------------
    def set_output_directory(self, directory: str) -> None:
        """Writes ``directory`` into the *live* config block of the open document.

        Mutates the dict returned by ``MenuConfig.menu_data["config"]`` in
        place -- it is the same object ``MenuConfig`` privately cached as
        ``output_directory``'s source, so replacing it wholesale (instead of
        mutating it) would silently desync from that cache.
        """
        config_block = self._config.menu_data.get("config")
        if config_block is None:
            raise DocumentError("This menu file has no 'config:' block to set output_directory on")
        config_block["output_directory"] = directory
        self.mark_dirty()

    # -- validate / generate --------------------------------------------------
    def validate(self) -> Dict[str, List[str]]:
        """Validates the current in-memory tree; never requires a save first."""
        try:
            return MenuValidator(config=self._config).validate()
        except Exception:
            logger.exception("Validation failed unexpectedly")
            return {"internal": ["Validation raised an unexpected error -- see log"]}

    def generate(self) -> bool:
        """Replicates cli.py::_run's exact sequence against the shadow config."""
        if self._current_path is None:
            raise DocumentError("Save the menu file before generating")

        try:
            self.save(self._current_path)
            self._write_shadow_config(self._current_path)

            processor = MenuCraft(str(self._shadow_config_path))
            if not processor.validate_required_functions():
                logger.error("Generation aborted: required functions are missing")
                return False

            processor.save_flattern_json()
            save_json_data(processor.functions, "output/functions.json")

            MenuGenerator(str(self._shadow_config_path), processor=processor)
            logger.info("C code generated successfully")
            return True
        except (ConfigError, ProcessorError, FlattenerError) as e:
            logger.error("Generation failed: %s", e)
            return False
        except Exception:
            logger.exception("Unexpected error during generation")
            return False
