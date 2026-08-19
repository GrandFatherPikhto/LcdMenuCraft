"""Unit tests for MenuValidator (schema + custom tree checks)."""

from generate_menu.menu_validator import MenuValidator


def _make_validator(menu_config):
    """Creates a fresh validator (it keeps internal state between calls)."""
    return MenuValidator(menu_config)


def _make_menu(items):
    """Wraps items in the expected top-level menu structure."""
    return {"config": {}, "menu": items}


def _item(node_id, **fields):
    """Builds a minimal menu item dict."""
    item = {"id": node_id}
    item.update(fields)
    return item


def test_real_config_valid(menu_config):
    assert _make_validator(menu_config).validate() == {}


def test_valid_custom_menu(menu_config):
    validator = _make_validator(menu_config)
    items = [
        _item("a", title="A", type="string", role="fixed",
              values=["Off", "On"], default_idx=0),
        _item("b", title="B", type="ubyte", role="simple",
              default=5, min=0, max=10),
    ]
    assert validator.validate(_make_menu(items)) == {}


def test_duplicate_id(menu_config):
    validator = _make_validator(menu_config)
    items = [
        _item("dup", title="A", type="string", role="fixed"),
        _item("dup", title="B", type="string", role="fixed"),
    ]
    errors = validator.validate(_make_menu(items))
    assert "dup" in errors
    assert any("not unique" in message for message in errors["dup"])


def test_branch_with_type_custom_check(menu_config):
    """
    The custom "branch cannot have 'type'" check.

    The JSON Schema ``oneOf`` already forbids branches carrying ``type``, so
    such input never reaches the custom tree walker through ``validate()``.
    The private ``_validate_tree`` is exercised directly to cover this rule.
    """
    validator = _make_validator(menu_config)
    items = [
        _item("branch", title="B", type="string",
              items=[_item("child", title="C", type="string", role="fixed")]),
    ]
    errors = {}
    validator._validate_tree(items, [], errors)
    assert "branch" in errors
    assert any("cannot have 'type'" in message for message in errors["branch"])


def test_leaf_without_type_custom_check(menu_config):
    """
    The custom "leaf must have 'type'" check.

    Same rationale as above: the schema requires ``type``/``role`` on leaves,
    so the custom rule is only reachable through the private tree walker.
    """
    validator = _make_validator(menu_config)
    items = [_item("leaf", title="L")]
    errors = {}
    validator._validate_tree(items, [], errors)
    assert "leaf" in errors
    assert any("must have 'type'" in message for message in errors["leaf"])


def test_default_out_of_range(menu_config):
    validator = _make_validator(menu_config)
    items = [_item("n", title="N", type="ubyte", role="simple",
                   default=200, min=0, max=100)]
    errors = validator.validate(_make_menu(items))
    assert "n" in errors
    assert any("out of range" in message for message in errors["n"])


def test_min_greater_than_max_without_default(menu_config):
    """min > max must be flagged even when no default is present to key off of."""
    validator = _make_validator(menu_config)
    items = [_item("n", title="N", type="ubyte", role="simple",
                   min=100, max=10)]
    errors = validator.validate(_make_menu(items))
    assert "n" in errors
    assert any("min (100) > max (10)" in message for message in errors["n"])


def test_default_not_in_allowed_values(menu_config):
    validator = _make_validator(menu_config)
    items = [_item("f", title="F", type="string", role="fixed",
                   values=["Off", "On"], default="Maybe")]
    errors = validator.validate(_make_menu(items))
    assert "f" in errors
    assert any("not in allowed values" in message for message in errors["f"])


def test_default_idx_out_of_bounds_for_factors(menu_config):
    validator = _make_validator(menu_config)
    items = [_item("x", title="X", type="udword", role="factor",
                   factors=[1, 10, 100], default_idx=5)]
    errors = validator.validate(_make_menu(items))
    assert "x" in errors
    assert any("out of bounds for factors" in message for message in errors["x"])


def test_default_idx_out_of_bounds_for_values(menu_config):
    validator = _make_validator(menu_config)
    items = [_item("y", title="Y", type="string", role="fixed",
                   values=["Off", "On"], default_idx=7)]
    errors = validator.validate(_make_menu(items))
    assert "y" in errors
    assert any("out of bounds for values" in message for message in errors["y"])


def test_nested_tree_path_in_errors(menu_config):
    validator = _make_validator(menu_config)
    items = [
        _item(
            "parent",
            title="Parent",
            items=[_item("child", title="Child", type="string", role="fixed",
                         values=["Off", "On"], default="Nope")],
        )
    ]
    errors = validator.validate(_make_menu(items))
    # The error is keyed by the full path 'parent->child'.
    assert "parent->child" in errors
    assert any(
        "not in allowed values" in message
        for message in errors["parent->child"]
    )


def test_validate_is_idempotent(menu_config):
    """Repeated validate() calls must not accumulate duplicate-id state."""
    validator = _make_validator(menu_config)
    items = [
        _item("a", title="A", type="string", role="fixed"),
        _item("b", title="B", type="string", role="fixed"),
    ]
    menu = _make_menu(items)
    assert validator.validate(menu) == {}
    assert validator.validate(menu) == {}
