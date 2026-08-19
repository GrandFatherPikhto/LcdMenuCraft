"""Integration tests: the command-line entry point end-to-end.

The root ``generate_menu.py`` script is executed in a subprocess exactly as
a user would run it, so the tests verify the real entry point, its exit code,
the generated artifacts and i18n localization.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Project root (two levels up from this file).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_entrypoint(env_extra=None, extra_args=None):
    """Runs the root generate_menu.py entry point in a subprocess."""
    env = dict(os.environ)
    # Force UTF-8 stdout/stderr in the subprocess: on Windows the console
    # encoding (cp1251) cannot represent the emoji used in the program output.
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "generate_menu.py", *(extra_args or [])],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_entrypoint_runs_successfully():
    """The root script runs end-to-end and exits with code 0."""
    result = _run_entrypoint()
    assert result.returncode == 0, result.stderr
    assert "Configuration" in result.stdout


def test_entrypoint_generates_output_files():
    """Running the entry point produces the C sources and JSON artifacts."""
    result = _run_entrypoint()
    assert result.returncode == 0, result.stderr

    output = PROJECT_ROOT / "output"
    assert (output / "menu.c").is_file()
    assert (output / "include" / "menu.h").is_file()
    assert (output / "flatterned.json").is_file()
    assert (output / "functions.json").is_file()


def test_entrypoint_writes_output_at_project_root():
    """
    Generation writes into the root output/ directory and leaves no stray
    output directory inside the generate_menu package.
    """
    result = _run_entrypoint()
    assert result.returncode == 0, result.stderr
    assert (PROJECT_ROOT / "output").is_dir()
    assert not (PROJECT_ROOT / "generate_menu" / "output").exists()


def test_russian_entrypoint_output():
    """With MENU_PROCESSOR_LANG=ru the console output is localized."""
    result = _run_entrypoint(env_extra={"MENU_PROCESSOR_LANG": "ru"})
    assert result.returncode == 0, result.stderr
    assert "Конфигурация" in result.stdout
    assert "успешно загружена" in result.stdout


def test_menu_flag_overrides_the_tree():
    """--menu swaps the tree while --config's own schema/rules still apply.

    Uses the frozen menu/test.yaml (17 nodes) against the *default* main
    config (config/config.yaml, whose own `menu:` key points at the real,
    separately-edited menu/menu.yaml) -- proving the override actually wins
    over the default config's own menu path.
    """
    result = _run_entrypoint(extra_args=["--menu", "menu/test.yaml", "--flat-only"])
    assert result.returncode == 0, result.stderr

    flat_path = PROJECT_ROOT / "output" / "flatterned.json"
    assert flat_path.is_file()
    flat_data = json.loads(flat_path.read_text(encoding="utf-8"))
    assert len(flat_data["nodes"]) == 17
