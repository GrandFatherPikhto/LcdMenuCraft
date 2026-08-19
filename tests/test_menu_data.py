"""Unit tests for MenuData (data types, roles, controls, navigation rules)."""

from generate_menu.menu_data import ControlType, NavigationType


def test_control_type_enum_values():
    assert ControlType.CLICK.value == "click"
    assert ControlType.POSITION.value == "position"


def test_navigation_type_enum_values():
    assert NavigationType.LIMIT.value == "limit"
    assert NavigationType.CYCLIC.value == "cyclic"


def test_c_type_mapping(menu_data):
    assert menu_data.c_type("byte") == "int8_t"
    assert menu_data.c_type("ubyte") == "uint8_t"
    assert menu_data.c_type("word") == "int16_t"
    assert menu_data.c_type("uword") == "uint16_t"
    assert menu_data.c_type("dword") == "int32_t"
    assert menu_data.c_type("udword") == "uint32_t"
    assert menu_data.c_type("string") == "const char*"
    assert menu_data.c_type("callback") == "void*"
    assert menu_data.c_type("missing") is None


def test_roles_and_their_types(menu_data):
    assert "simple" in menu_data.roles
    assert "fixed" in menu_data.roles
    assert "factor" in menu_data.roles
    assert "callback" in menu_data.roles

    simple_types = menu_data.role_types("simple")
    assert simple_types is not None
    assert "ubyte" in simple_types
    assert menu_data.role_types("missing") is None


def test_roles_for_type(menu_data):
    # "ubyte" belongs to the simple, fixed and factor roles.
    assert {"simple", "fixed", "factor"} <= set(menu_data.get_roles_for_type("ubyte"))
    assert menu_data.get_roles_for_type("callback") == ["callback"]
    assert menu_data.get_roles_for_type("missing") == []


def test_controls_for_type(menu_data):
    assert menu_data.get_controls_for_type("ubyte") == {
        ControlType.CLICK,
        ControlType.POSITION,
    }
    # The callback role declares no controls.
    assert menu_data.get_controls_for_type("callback") == set()
    assert menu_data.get_controls_for_type("missing") == set()


def test_navigation_rules(menu_data):
    allowed, default = menu_data.get_navigation_rules(ControlType.CLICK)
    assert allowed == [NavigationType.CYCLIC]
    assert default == NavigationType.CYCLIC

    allowed, default = menu_data.get_navigation_rules(ControlType.POSITION)
    assert NavigationType.LIMIT in allowed
    assert NavigationType.CYCLIC in allowed
    assert default == NavigationType.LIMIT


def test_is_valid_navigation(menu_data):
    assert menu_data.is_valid_navigation(ControlType.CLICK, NavigationType.CYCLIC)
    assert not menu_data.is_valid_navigation(ControlType.CLICK, NavigationType.LIMIT)
    assert menu_data.is_valid_navigation(ControlType.POSITION, NavigationType.LIMIT)
    assert menu_data.is_valid_navigation(ControlType.POSITION, NavigationType.CYCLIC)


def test_get_default_navigation(menu_data):
    assert (
        menu_data.get_default_navigation(ControlType.CLICK) == NavigationType.CYCLIC
    )
    assert menu_data.get_default_navigation(ControlType.POSITION) == NavigationType.LIMIT


def test_get_control_config_factor_click(menu_data):
    cfg = menu_data.get_control_config("factor", ControlType.CLICK)
    assert cfg is not None
    assert cfg["purpose"] == "change_factor_index"
    assert cfg["navigate"] == NavigationType.CYCLIC
    assert cfg["required"] is True


def test_get_control_config_factor_position(menu_data):
    cfg = menu_data.get_control_config("factor", ControlType.POSITION)
    assert cfg is not None
    assert cfg["purpose"] == "change_value"
    assert cfg["navigate"] == NavigationType.LIMIT
    assert cfg["required"] is True


def test_get_control_config_honors_node_controls(menu_data):
    cfg = menu_data.get_control_config("factor", ControlType.CLICK, node_controls=["click"])
    assert cfg is not None

    cfg = menu_data.get_control_config("factor", ControlType.POSITION, node_controls=["click"])
    assert cfg is None


def test_get_control_config_unknown_role(menu_data):
    assert menu_data.get_control_config("missing", ControlType.CLICK) is None
