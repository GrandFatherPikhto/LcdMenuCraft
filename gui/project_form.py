"""Form for editing the menu document's own ``config:`` block.

This is the sibling of the whole tree (``output_directory``, navigation
defaults, ...), not a node -- so it lives in its own tab next to the node
form instead of being folded into it, and is rebuilt on open/new rather
than on tree selection.
"""

import logging

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .node_form import ListEditor

logger = logging.getLogger("gui.project_form")

NAVIGATE_OPTIONS = ["cyclic", "limit"]
CONTROL_OPTIONS = ["click", "position"]


class ProjectForm(QWidget):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self._document = document

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll)

        self.refresh()

    def _commit(self) -> None:
        self._document.mark_dirty()

    def _config_block(self) -> dict:
        menu_data = self._document.config.menu_data
        block = menu_data.get("config")
        if block is None:
            block = {}
            menu_data["config"] = block
        return block

    def refresh(self) -> None:
        content = QWidget()
        form = QFormLayout(content)
        block = self._config_block()

        self._text_row(form, block, "version", "Version")
        self._text_row(form, block, "author", "Author")
        self._combo_row(form, block, "default_navigate", "Default navigate", NAVIGATE_OPTIONS)
        self._combo_row(form, block, "default_control", "Default control", CONTROL_OPTIONS)
        self._combo_row(form, block, "default_branch_navigate", "Default branch navigate", NAVIGATE_OPTIONS)
        self._combo_row(form, block, "root_navigate", "Root navigate", NAVIGATE_OPTIONS)
        self._text_row(form, block, "output_directory", "Output directory")
        self._list_row(form, block, "include_files", "Include files")
        self._checkbox_row(form, block, "wrap_by_name_functions", "Wrap by-name functions")
        self._checkbox_row(form, block, "enable_node_names", "Enable node names")

        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._scroll.setWidget(content)

    # -- row builders -----------------------------------------------------
    def _text_row(self, form: QFormLayout, block: dict, key: str, label: str) -> None:
        edit = QLineEdit("" if block.get(key) is None else str(block.get(key)))

        def on_changed():
            text = edit.text().strip()
            if text == "":
                block.pop(key, None)
            else:
                block[key] = text
            self._commit()

        edit.editingFinished.connect(on_changed)
        form.addRow(label, edit)

    def _combo_row(self, form: QFormLayout, block: dict, key: str, label: str, options) -> None:
        combo = QComboBox()
        combo.addItems(options)
        current = block.get(key)
        if current in options:
            combo.setCurrentText(current)

        def on_changed(text):
            block[key] = text
            self._commit()

        combo.currentTextChanged.connect(on_changed)
        form.addRow(label, combo)

    def _checkbox_row(self, form: QFormLayout, block: dict, key: str, label: str) -> None:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(block.get(key, False)))

        def on_toggled(checked):
            block[key] = checked
            self._commit()

        checkbox.toggled.connect(on_toggled)
        form.addRow(label, checkbox)

    def _list_row(self, form: QFormLayout, block: dict, key: str, label: str) -> None:
        def on_change():
            values = editor.values()
            if values:
                block[key] = values
            else:
                block.pop(key, None)
            self._commit()

        editor = ListEditor(block.get(key, []), on_change)
        form.addRow(label, editor)
