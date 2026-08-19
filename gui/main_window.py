"""Main window: menu/toolbar, layout, and wiring between panels and the document."""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolBar,
)

from .document import DocumentError, MenuDocument
from .log_panel import LogPanel
from .node_form import NodeForm
from .project_form import ProjectForm
from .tree_panel import TreePanel

logger = logging.getLogger("gui.main_window")


class GenerateWorker(QThread):
    """Runs MenuDocument.generate() off the GUI thread (real file I/O + Jinja2 rendering)."""

    finished_ok = pyqtSignal(bool)

    def __init__(self, document: MenuDocument, parent=None):
        super().__init__(parent)
        self._document = document

    def run(self) -> None:
        try:
            ok = self._document.generate()
        except DocumentError as e:
            logger.error("Generation failed: %s", e)
            ok = False
        except Exception:
            logger.exception("Unexpected error during generation")
            ok = False
        self.finished_ok.emit(ok)


class MainWindow(QMainWindow):
    def __init__(self, document: MenuDocument, settings, parent=None):
        super().__init__(parent)
        self._document = document
        self._settings = settings
        self._worker = None

        self.setWindowTitle("MenuCraft GUI")

        self.tree_panel = TreePanel(document, self)
        self.node_form = NodeForm(document, self)
        self.project_form = ProjectForm(document, self)
        self.log_panel = LogPanel(self)
        self.tree_panel.nodeSelected.connect(self.node_form.set_node)

        right_tabs = QTabWidget(self)
        right_tabs.addTab(self.node_form, "Node")
        right_tabs.addTab(self.project_form, "Project")

        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.addWidget(self.tree_panel)
        top_splitter.addWidget(right_tabs)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.log_panel)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        self.setCentralWidget(main_splitter)

        self._build_actions()

        self._status_label = QLabel(self)
        self.statusBar().addWidget(self._status_label)
        self.refresh_status()

        self._restore_geometry()

    # -- menu/toolbar ---------------------------------------------------------
    def _build_actions(self) -> None:
        toolbar = QToolBar("Main", self)
        self.addToolBar(toolbar)
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        open_action = QAction("Open...", self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self.save_file_as)
        output_dir_action = QAction("Set output directory...", self)
        output_dir_action.triggered.connect(self.choose_output_directory)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        for action in (new_action, open_action, save_action, save_as_action, output_dir_action, quit_action):
            file_menu.addAction(action)
            toolbar.addAction(action)

        run_menu = menu_bar.addMenu("Run")
        validate_action = QAction("Validate", self)
        validate_action.triggered.connect(self.validate)
        self._generate_action = QAction("Generate C files", self)
        self._generate_action.triggered.connect(self.generate)
        for action in (validate_action, self._generate_action):
            run_menu.addAction(action)
            toolbar.addAction(action)

    # -- document actions -------------------------------------------------------
    def new_file(self) -> None:
        if not self._confirm_discard_changes():
            return
        try:
            self._document.new()
        except DocumentError as e:
            QMessageBox.critical(self, "New failed", str(e))
            return
        self.tree_panel.refresh()
        self.node_form.set_node(None)
        self.project_form.refresh()
        self.refresh_status()
        logger.info("Started a new menu document")

    def open_file(self) -> None:
        if not self._confirm_discard_changes():
            return
        start_dir = str(Path(self._document.current_path or ".").parent)
        path, _ = QFileDialog.getOpenFileName(
            self, "Open menu file", start_dir, "YAML files (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            self._document.open(Path(path))
        except DocumentError as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return
        self.tree_panel.refresh()
        self.node_form.set_node(None)
        self.project_form.refresh()
        self.refresh_status()
        logger.info("Opened %s", path)

    def save_file(self) -> None:
        if self._document.current_path is None:
            self.save_file_as()
            return
        try:
            self._document.save()
        except DocumentError as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.refresh_status()
        logger.info("Saved %s", self._document.current_path)

    def save_file_as(self) -> None:
        start_dir = str(Path(self._document.current_path or "menu/menu.yaml").parent)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save menu file as", start_dir, "YAML files (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            self._document.save(Path(path))
        except DocumentError as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.refresh_status()
        logger.info("Saved %s", path)

    def choose_output_directory(self) -> None:
        current = self._document.config.output_directory or "."
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", current)
        if not directory:
            return
        try:
            self._document.set_output_directory(directory)
        except DocumentError as e:
            QMessageBox.critical(self, "Could not set output directory", str(e))
            return
        self._settings.set("last_output_directory", directory)
        self.project_form.refresh()
        self.refresh_status()
        logger.info("Output directory set to %s", directory)

    def validate(self) -> None:
        errors = self._document.validate()
        if not errors:
            logger.info("Menu is valid")
            return
        logger.error("Validation failed:")
        for path, messages in errors.items():
            logger.error("  %s:", path)
            for message in messages:
                logger.error("    - %s", message)

    def generate(self) -> None:
        if self._document.current_path is None:
            QMessageBox.information(self, "Save required", "Save the menu file before generating.")
            return
        self._generate_action.setEnabled(False)
        logger.info("Generating C files...")
        self._worker = GenerateWorker(self._document, self)
        self._worker.finished_ok.connect(self._on_generate_finished)
        self._worker.start()

    def _on_generate_finished(self, ok: bool) -> None:
        self._generate_action.setEnabled(True)
        self.refresh_status()
        if ok:
            logger.info("Generation finished")
        else:
            logger.error("Generation failed -- see log above")

    # -- helpers ------------------------------------------------------------
    def refresh_status(self) -> None:
        path = self._document.current_path
        output_dir = self._document.config.output_directory or "(not set)"
        dirty = " *" if self._document.is_dirty else ""
        self._status_label.setText(f"{path or '(unsaved)'}{dirty}    |    output: {output_dir}")

    def _confirm_discard_changes(self) -> bool:
        if not self._document.is_dirty:
            return True
        answer = QMessageBox.question(
            self, "Unsaved changes", "You have unsaved changes. Discard them?"
        )
        return answer == QMessageBox.StandardButton.Yes

    def _restore_geometry(self) -> None:
        self.setGeometry(
            self._settings.get("window_x"),
            self._settings.get("window_y"),
            self._settings.get("window_width"),
            self._settings.get("window_height"),
        )

    # -- Qt overrides -----------------------------------------------------------
    def closeEvent(self, event) -> None:
        if self._document.is_dirty:
            answer = QMessageBox.question(
                self, "Unsaved changes", "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Yes:
                self.save_file()
                if self._document.is_dirty:
                    event.ignore()
                    return

        geometry = self.geometry()
        self._settings.set("window_x", geometry.x())
        self._settings.set("window_y", geometry.y())
        self._settings.set("window_width", geometry.width())
        self._settings.set("window_height", geometry.height())
        if self._document.current_path:
            self._settings.set("last_menu_file", str(self._document.current_path))
        self._settings.save()
        event.accept()
