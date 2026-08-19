"""Integration tests: run the full menu generation pipeline in-process.

The generator resolves templates and the output directory relative to the
current working directory, so these tests change into the package directory
before constructing a ``MenuGenerator``.
"""

import json
from pathlib import Path

#: Files the generator must produce from the bundled templates.
EXPECTED_FILES = [
    "menu.c",
    "menu_context.c",
    "menu_name.c",
    "menu_draw.c",
    "menu_edit.c",
    "menu_navigate.c",
    "menu_data_tree.c",
    "menu_data_config.c",
    "menu_data_context.c",
    "menu_data_value.c",
    "menu_data_name.c",
    "include/menu.h",
    "include/menu_context.h",
    "include/menu_name.h",
    "include/menu_draw.h",
    "include/menu_edit.h",
    "include/menu_navigate.h",
    "include/menu_config.h",
    "include/menu_type.h",
]


def test_generator_creates_c_files(monkeypatch, project_root, config_path):
    """Running the generator from the project root produces the C sources."""
    monkeypatch.chdir(project_root)

    from generate_menu.menu_generator import MenuGenerator

    MenuGenerator(str(config_path))

    output = project_root / "output"
    for relative in EXPECTED_FILES:
        path = output / relative
        assert path.is_file(), f"Missing generated file: {path}"
        assert path.stat().st_size > 0, f"Generated file is empty: {path}"


def test_processor_exposes_flat_menu(monkeypatch, project_root, config_path):
    """The processor behind the generator exposes all menu nodes but root."""
    monkeypatch.chdir(project_root)

    from generate_menu.menu_generator import MenuGenerator

    generator = MenuGenerator(str(config_path))
    processor = generator._processor
    # 18 flat nodes total, minus the virtual root node.
    assert len(processor.menu) == 17


def test_processor_saves_flat_and_functions_json(monkeypatch, project_root, config_path):
    """save_flattern_json() and save_json_data() write the JSON artifacts."""
    monkeypatch.chdir(project_root)

    from generate_menu.menucraft import MenuCraft
    from generate_menu.common import save_json_data

    processor = MenuCraft(str(config_path))

    output = project_root / "output"
    flat_path = output / "flatterned.json"
    functions_path = output / "functions.json"

    processor.save_flattern_json(str(flat_path))
    save_json_data(processor.functions, str(functions_path))

    assert flat_path.is_file()
    assert functions_path.is_file()

    flat_data = json.loads(flat_path.read_text(encoding="utf-8"))
    assert "nodes" in flat_data
    # Same node set as processor.menu: 18 minus the virtual root node.
    assert len(flat_data["nodes"]) == 17

    functions_data = json.loads(functions_path.read_text(encoding="utf-8"))
    assert isinstance(functions_data, dict)
    assert len(functions_data) > 0


def test_generated_data_file_contains_node_titles(monkeypatch, project_root, config_path):
    """The generated data file embeds real menu node titles."""
    monkeypatch.chdir(project_root)

    from generate_menu.menu_generator import MenuGenerator

    MenuGenerator(str(config_path))

    data_c = project_root / "output" / "menu_data_config.c"
    content = data_c.read_text(encoding="utf-8")
    assert "s_values_str_start" in content
    assert '"Start"' in content
