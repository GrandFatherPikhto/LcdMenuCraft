"""QApplication bootstrap for the MenuCraft GUI."""

import logging
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .document import MenuDocument
from .log_panel import QtLogHandler
from .main_window import MainWindow
from .settings import AppSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
SHADOW_CONFIG_PATH = PROJECT_ROOT / "config" / ".gui_config.yaml"
SETTINGS_PATH = PROJECT_ROOT / "gui_settings.json"
DEFAULT_MENU_FILE = PROJECT_ROOT / "menu" / "menu.yaml"

logger = logging.getLogger("gui.app")


def _configure_logging(log_panel) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = QtLogHandler()
    handler.emitter.logRecord.connect(log_panel.append_record)
    root.addHandler(handler)


def main(argv=None) -> int:
    app = QApplication(list(argv) if argv is not None else sys.argv)

    settings = AppSettings(SETTINGS_PATH).load()
    document = MenuDocument(REAL_CONFIG_PATH, SHADOW_CONFIG_PATH)

    window = MainWindow(document, settings)
    _configure_logging(window.log_panel)

    last_menu_file = settings.get("last_menu_file")
    menu_path = Path(last_menu_file) if last_menu_file and Path(last_menu_file).exists() else DEFAULT_MENU_FILE
    try:
        document.open(menu_path)
        window.tree_panel.refresh()
        window.project_form.refresh()
    except Exception:
        logger.exception("Could not open %s", menu_path)

    window.refresh_status()
    window.show()
    return app.exec()
