"""Pytest configuration for the whole project.

This file is loaded before any test module, so it:
- inserts the project root into ``sys.path`` so that ``import generate_menu``
  works regardless of the current working directory;
- makes the default language deterministic (English) by removing any stale
  ``MENU_PROCESSOR_LANG`` environment variable BEFORE the i18n module is
  imported (the translation is bound at import time);
- provides reusable fixtures shared by the ``tests/`` (unit/smoke) and
  ``test/integration/`` (integration) suites.
"""

import os
import sys
from pathlib import Path

import pytest

# Project root directory (the parent of this file).
PROJECT_ROOT = Path(__file__).resolve().parent

# Ensure the project root is importable regardless of the CWD.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The i18n module binds its translation at import time, so remove any stale
# environment variable before test modules import generate_menu.i18n.
os.environ.pop("MENU_PROCESSOR_LANG", None)

#: Absolute path to the generate_menu package directory.
PACKAGE_DIR = PROJECT_ROOT / "generate_menu"

#: Absolute path to the main YAML configuration file used by the test suite.
#: Deliberately points at config/test_config.yaml -> menu/test.yaml (a frozen
#: copy of the sample tree), not the real config/config.yaml -> menu/menu.yaml,
#: so tests stay stable while the real menu tree is being edited for a device.
CONFIG_PATH = PROJECT_ROOT / "config" / "test_config.yaml"


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path of the project root directory.

    The non-code asset directories (config/, menu/, templates/, output/)
    live here, one level above the ``generate_menu`` package.
    """
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Absolute path to the ``generate_menu`` package directory."""
    return PACKAGE_DIR


@pytest.fixture(scope="session")
def config_path() -> Path:
    """Absolute path to the main YAML configuration file."""
    return CONFIG_PATH


@pytest.fixture(scope="session")
def menu_config(config_path):
    """A session-scoped ``MenuConfig`` built from the real configuration."""
    from generate_menu.menu_config import MenuConfig

    return MenuConfig(str(config_path))


@pytest.fixture(scope="session")
def menu_data(menu_config):
    """A session-scoped ``MenuData`` built from the real configuration."""
    from generate_menu.menu_data import MenuData

    return MenuData(menu_config)


@pytest.fixture()
def menu_validator(menu_config):
    """
    A fresh ``MenuValidator`` per test.

    The validator keeps internal state (the list of seen ids) between
    ``validate()`` calls, so a fresh instance guarantees isolation.
    """
    from generate_menu.menu_validator import MenuValidator

    return MenuValidator(menu_config)


@pytest.fixture()
def menu_flattener(menu_config):
    """A fresh ``MenuFlattener`` per test."""
    from generate_menu.menu_flattener import MenuFlattener

    return MenuFlattener(menu_config)
