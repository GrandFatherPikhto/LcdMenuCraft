"""Dynamic property-editing form for the currently selected menu node.

Fields shown depend on the node's ``type``/``role`` via the rules in
``config/menu_data.yaml`` (accessed through ``document.menu_data`` /
``document.config.data_config``) -- the same rules the backend itself
uses to build controls and validate the tree. Every field commit writes
directly into the same node dict already linked into ``document.tree``
(no intermediate DTO).
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from generate_menu.menu_data import ControlType

from .tree_panel import is_branch

logger = logging.getLogger("gui.node_form")

CALLBACK_FIELDS = (
    ("click_cb", "Click callback"),
    ("position_cb", "Position callback"),
    ("double_click_cb", "Double-click callback"),
    ("long_click_cb", "Long-click callback"),
    ("event_cb", "Event callback"),
    ("draw_value_cb", "Draw-value callback"),
)

#: Value-field keys owned by each role; used to strip stale fields on role change.
ROLE_VALUE_KEYS = {
    "simple": ("default", "min", "max", "step"),
    "fixed": ("values", "default_idx", "raw_values"),
    "factor": ("default", "min", "max", "factors", "default_idx"),
    "callback": (),
}


class ListEditor(QWidget):
    """Small editable list of scalar values (used for ``values`` and ``factors``)."""

    def __init__(self, values, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._list = QListWidget(self)
        self._list.addItems([str(v) for v in values])

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)
        layout.addLayout(buttons)

    def values(self):
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _add(self):
        text, ok = QInputDialog.getText(self, "Add value", "Value:")
        if ok and text:
            self._list.addItem(text)
            self._on_change()

    def _remove(self):
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._on_change()


class NodeForm(QWidget):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self._document = document
        self._node: Optional[dict] = None

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll)

        self.set_node(None)

    # -- entry point ------------------------------------------------------
    def set_node(self, node: Optional[dict]) -> None:
        self._node = node or None
        content = QWidget()
        form = QFormLayout(content)
        if self._node is None:
            form.addRow(QLabel("No node selected."))
        elif is_branch(self._node):
            self._build_branch_fields(form)
        else:
            self._build_leaf_fields(form)

        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._scroll.setWidget(content)

    def _commit(self) -> None:
        self._document.mark_dirty()

    # -- shared rows ------------------------------------------------------
    def _id_title_rows(self, form: QFormLayout) -> None:
        node = self._node

        id_edit = QLineEdit(node.get("id", ""))

        def on_id_changed():
            text = id_edit.text().strip()
            if text:
                node["id"] = text
                self._commit()

        id_edit.editingFinished.connect(on_id_changed)
        form.addRow("Id", id_edit)

        title_edit = QLineEdit(node.get("title", ""))

        def on_title_changed():
            node["title"] = title_edit.text()
            self._commit()

        title_edit.editingFinished.connect(on_title_changed)
        form.addRow("Title", title_edit)

    def _navigate_row(self, form: QFormLayout, options) -> None:
        node = self._node
        options = list(options) or ["cyclic", "limit"]
        combo = QComboBox()
        combo.addItems(options)
        current = node.get("navigate")
        if current in options:
            combo.setCurrentText(current)

        def on_changed(text):
            node["navigate"] = text
            self._commit()

        combo.currentTextChanged.connect(on_changed)
        form.addRow("Navigate", combo)

    # -- branch -------------------------------------------------------------
    def _build_branch_fields(self, form: QFormLayout) -> None:
        self._id_title_rows(form)
        self._navigate_row(form, ["cyclic", "limit"])

    # -- leaf -----------------------------------------------------------------
    def _build_leaf_fields(self, form: QFormLayout) -> None:
        node = self._node
        self._id_title_rows(form)

        menu_data = self._document.menu_data
        type_names = sorted(menu_data.types)
        type_combo = QComboBox()
        type_combo.addItems(type_names)
        if node.get("type") in type_names:
            type_combo.setCurrentText(node["type"])
        type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type", type_combo)

        roles = menu_data.get_roles_for_type(node.get("type", "")) or sorted(menu_data.roles)
        role_combo = QComboBox()
        role_combo.addItems(roles)
        if node.get("role") in roles:
            role_combo.setCurrentText(node["role"])
        role_combo.currentTextChanged.connect(self._on_role_changed)
        form.addRow("Role", role_combo)

        role = node.get("role", "")
        self._build_value_fields(form, role)
        self._build_controls_fields(form, role)
        self._build_callback_fields(form)
        self._number_row(form, "Tag (optional)", "tag")

    def _on_type_changed(self, type_name: str) -> None:
        node = self._node
        node["type"] = type_name
        roles = self._document.menu_data.get_roles_for_type(type_name)
        if node.get("role") not in roles and roles:
            self._apply_role(roles[0])
        self._commit()
        self.set_node(node)

    def _on_role_changed(self, role_name: str) -> None:
        self._apply_role(role_name)
        self._commit()
        self.set_node(self._node)

    def _apply_role(self, role_name: str) -> None:
        node = self._node
        old_role = node.get("role")
        node["role"] = role_name
        if old_role == role_name:
            return

        keep = set(ROLE_VALUE_KEYS.get(role_name, ()))
        for keys in ROLE_VALUE_KEYS.values():
            for key in keys:
                if key not in keep:
                    node.pop(key, None)

        if role_name == "simple":
            node.setdefault("default", 0)
            node.setdefault("min", 0)
            node.setdefault("max", 100)
            node.setdefault("step", 1)
        elif role_name == "fixed":
            node.setdefault("values", ["Value"])
            node.setdefault("default_idx", 0)
        elif role_name == "factor":
            node.setdefault("default", 0)
            node.setdefault("min", 0)
            node.setdefault("max", 100)
            node.setdefault("factors", [1, 10, 100])

        if role_name == "callback":
            node.pop("controls", None)
            node.pop("navigate", None)
        else:
            node.setdefault("controls", ["position"])
            node.setdefault("navigate", "limit")

    # -- value fields ---------------------------------------------------------
    def _build_value_fields(self, form: QFormLayout, role: str) -> None:
        if role == "simple":
            self._number_row(form, "Default", "default")
            self._number_row(form, "Min", "min")
            self._number_row(form, "Max", "max")
            self._number_row(form, "Step", "step")
        elif role == "factor":
            self._number_row(form, "Default", "default")
            self._number_row(form, "Min", "min")
            self._number_row(form, "Max", "max")
            self._list_row(form, "Factors", "factors", numeric=True)
        elif role == "fixed":
            self._list_row(form, "Values", "values", numeric=False)
            self._default_idx_row(form)
            self._list_row(form, "Raw values (optional)", "raw_values", numeric=True, pop_if_empty=True)

    def _number_row(self, form: QFormLayout, label: str, key: str) -> None:
        node = self._node
        edit = QLineEdit("" if node.get(key) is None else str(node.get(key)))

        def on_changed():
            text = edit.text().strip()
            if text == "":
                node.pop(key, None)
            else:
                try:
                    node[key] = int(text)
                except ValueError:
                    try:
                        node[key] = float(text)
                    except ValueError:
                        node[key] = text
            self._commit()

        edit.editingFinished.connect(on_changed)
        form.addRow(label, edit)

    def _list_row(self, form: QFormLayout, label: str, key: str, numeric: bool, pop_if_empty: bool = False) -> None:
        node = self._node

        def on_change():
            raw = editor.values()
            if numeric:
                converted = []
                for value in raw:
                    try:
                        converted.append(int(value))
                    except ValueError:
                        try:
                            converted.append(float(value))
                        except ValueError:
                            continue
            else:
                converted = raw
            if not converted and pop_if_empty:
                node.pop(key, None)
            else:
                node[key] = converted
            self._commit()

        editor = ListEditor(node.get(key, []), on_change)
        form.addRow(label, editor)

    def _default_idx_row(self, form: QFormLayout) -> None:
        node = self._node
        values = node.get("values", [])
        spin = QSpinBox()
        spin.setRange(0, max(len(values) - 1, 0))
        spin.setValue(min(node.get("default_idx", 0), spin.maximum()))

        def on_changed(value):
            node["default_idx"] = value
            self._commit()

        spin.valueChanged.connect(on_changed)
        form.addRow("Default index", spin)

    # -- controls / navigate --------------------------------------------------
    def _build_controls_fields(self, form: QFormLayout, role: str) -> None:
        node = self._node
        data_config = self._document.config.data_config
        role_rules = data_config.get("role_rules", {}).get(role, {})
        allowed = data_config.get("controls", {}).get(role, [])
        if not allowed:
            return  # e.g. callback role: no controls, no navigate

        current_controls = set(node.get("controls", []))
        checkboxes = {}
        box = QGroupBox("Controls")
        box_layout = QVBoxLayout(box)
        for control in allowed:
            required = bool(role_rules.get(control, {}).get("required", False))
            # Required controls show pre-checked and disabled purely for display --
            # the backend already treats them as active via role_rules even when
            # `controls:` is absent from the node, so merely viewing the form must
            # not write them into the node dict (that would falsely dirty the
            # document on a plain click-through with no actual edit).
            checkbox = _make_checkbox(control, control in current_controls or required, not required)
            box_layout.addWidget(checkbox)
            checkboxes[control] = checkbox

        def on_toggled():
            # Only reachable via a real user click, since required checkboxes are
            # disabled -- safe to always commit here.
            selected = [name for name, cb in checkboxes.items() if cb.isChecked()]
            if selected:
                node["controls"] = selected
            else:
                node.pop("controls", None)
            self._commit()

        for checkbox in checkboxes.values():
            checkbox.toggled.connect(on_toggled)
        form.addRow(box)

        active_controls = {name for name, cb in checkboxes.items() if cb.isChecked()}
        if "position" in active_controls:
            allowed_nav, _default = self._document.menu_data.get_navigation_rules(ControlType.POSITION)
            navigate_options = [nav.value for nav in allowed_nav]
        else:
            navigate_options = ["cyclic"]
        self._navigate_row(form, navigate_options)

    def _build_callback_fields(self, form: QFormLayout) -> None:
        node = self._node
        box = QGroupBox("Callbacks (optional)")
        box_layout = QFormLayout(box)
        for key, label in CALLBACK_FIELDS:
            edit = QLineEdit(node.get(key, ""))
            edit.editingFinished.connect(_make_callback_handler(node, key, edit, self._commit))
            box_layout.addRow(label, edit)
        form.addRow(box)


def _make_checkbox(text, checked, enabled):
    checkbox = QCheckBox(text)
    checkbox.setChecked(checked)
    checkbox.setEnabled(enabled)
    return checkbox


def _make_callback_handler(node, key, edit, commit):
    def handler():
        text = edit.text().strip()
        if text:
            node[key] = text
        else:
            node.pop(key, None)
        commit()

    return handler
