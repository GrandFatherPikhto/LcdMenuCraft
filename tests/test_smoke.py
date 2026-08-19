"""Smoke tests: minimal end-to-end sanity checks of the package.

These tests verify that the package imports, the real configuration loads
and validates, and the real menu flattens into the expected structure.
"""


def test_package_imports():
    """All public modules of the package import without errors."""
    from generate_menu.menu_config import ConfigError, MenuConfig
    from generate_menu.menu_data import ControlType, MenuData, NavigationType
    from generate_menu.menu_flattener import FlattenerError, MenuFlattener
    from generate_menu.menu_generator import MenuGenerator
    from generate_menu.menucraft import MenuCraft
    from generate_menu.menu_validator import MenuValidator, ParserError
    from generate_menu.flat_node import FlatNode

    assert all(
        cls is not None
        for cls in (
            ConfigError,
            MenuConfig,
            ControlType,
            MenuData,
            NavigationType,
            FlattenerError,
            MenuFlattener,
            MenuGenerator,
            MenuCraft,
            MenuValidator,
            ParserError,
            FlatNode,
        )
    )


def test_config_loads_from_absolute_path(config_path):
    """The real YAML configuration loads from any working directory."""
    from generate_menu.menu_config import MenuConfig

    config = MenuConfig(str(config_path))
    assert config.menu_schema is not None
    assert config.menu_data is not None
    assert config.data_config is not None
    assert config.menu_tree is not None


def test_config_navigation_defaults(menu_config):
    """Configuration defaults read from menu.yaml."""
    assert menu_config.default_navigate == "limit"
    assert menu_config.default_control == "position"
    assert menu_config.default_branch_navigate == "cyclic"
    assert menu_config.root_navigate == "cyclic"


def test_real_config_validates(menu_validator):
    """The bundled menu passes validation without errors."""
    assert menu_validator.validate() == {}


def test_real_menu_flattens(menu_flattener):
    """The bundled menu flattens into the expected number of nodes."""
    flat = menu_flattener.flatten()
    assert len(flat) == 18
    assert flat[0].id == "root"


def test_menu_override_replaces_only_the_tree(config_path, tmp_path):
    """menu_override swaps the tree while schema/data_rules still come from config_path."""
    from generate_menu.menu_config import MenuConfig

    override_path = tmp_path / "override.yaml"
    override_path.write_text(
        "config: {}\n"
        "menu:\n"
        "  - id: only_node\n"
        "    title: Only\n"
        "    type: string\n"
        "    role: fixed\n"
        "    values: [A]\n"
        "    default_idx: 0\n",
        encoding="utf-8",
    )

    base = MenuConfig(str(config_path))
    overridden = MenuConfig(str(config_path), menu_override=str(override_path))

    assert len(overridden.menu_tree) == 1
    assert overridden.menu_tree[0]["id"] == "only_node"
    # Not affected by the override: still sourced from the base config.
    assert overridden.menu_schema == base.menu_schema
    assert overridden.data_config == base.data_config


def test_menu_override_tree_still_validates(config_path, tmp_path):
    """A menu_override tree is validated with the same schema/rules as usual."""
    from generate_menu.menu_config import MenuConfig
    from generate_menu.menu_validator import MenuValidator

    override_path = tmp_path / "override.yaml"
    override_path.write_text(
        "config: {}\n"
        "menu:\n"
        "  - id: only_node\n"
        "    title: Only\n"
        "    type: string\n"
        "    role: fixed\n"
        "    values: [A]\n"
        "    default_idx: 0\n",
        encoding="utf-8",
    )

    config = MenuConfig(str(config_path), menu_override=str(override_path))
    assert MenuValidator(config=config).validate() == {}


def test_menucraft_accepts_menu_override(config_path, tmp_path):
    """MenuCraft threads menu_override through to MenuConfig end to end."""
    from generate_menu.menucraft import MenuCraft

    override_path = tmp_path / "override.yaml"
    override_path.write_text(
        "config: {}\n"
        "menu:\n"
        "  - id: only_node\n"
        "    title: Only\n"
        "    type: string\n"
        "    role: fixed\n"
        "    values: [A]\n"
        "    default_idx: 0\n",
        encoding="utf-8",
    )

    processor = MenuCraft(str(config_path), menu_override=str(override_path))
    assert list(processor.menu.keys()) == ["only_node"]
