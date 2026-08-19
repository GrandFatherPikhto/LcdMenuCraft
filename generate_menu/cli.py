"""Command-line interface for the Menu Processor.

Provides a single ``argparse``-based entry point for the whole pipeline:
load configuration → validate → flatten → generate C sources → save debug
artifacts (flattened menu and functions JSON).

The CLI is designed to be run in either of these ways::

    python generate_menu.py     # root convenience script
    python -m generate_menu     # module execution

Both forms change the current working directory into the project root
because configuration paths (templates, menu definitions, output directory
and the flattened menu file) are resolved relative to the current working
directory.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from .i18n import _

logger = logging.getLogger(__name__)

#: Default main configuration file, resolved relative to the project root.
DEFAULT_CONFIG = "config/config.yaml"


def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="generate_menu",
        description=_(
            "Generates C source files for an embedded LCD1602 menu system "
            "from a declarative YAML/JSON menu definition."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=_(
            "Path to the main configuration file "
            "(default: config/config.yaml relative to the project root)."
        ),
    )
    parser.add_argument(
        "--menu",
        default=None,
        metavar="PATH",
        help=_(
            "Path to a menu tree YAML/JSON file. Overrides just the 'menu' key "
            "from --config, while schema/data-rules/templates still come from "
            "there -- lets you generate a different device's menu without "
            "writing a new main config file for it."
        ),
    )
    parser.add_argument(
        "--flat-only",
        action="store_true",
        help=_(
            "Validate, flatten and save the flattened menu JSON, "
            "but skip C-code generation."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=_("Enable DEBUG logging and detailed summaries."),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=_("Only log errors (suppress informational output)."),
    )
    return parser


def _resolve_project_root() -> Path:
    """Returns the absolute path of the project root directory.

    The non-code asset directories (``config/``, ``menu/``, ``templates/``,
    ``output/``) live at the project root, one level above this package.
    """
    return Path(__file__).resolve().parent.parent


def _setup_logging(level: int) -> None:
    """Configures the root logger to write human-readable messages to stdout.

    The formatter emits only the message itself (no level prefixes), keeping
    the emoji-styled output readable while making the verbosity configurable
    through the logging level. Messages go to stdout so that the generated
    artifacts and console output stay consistent with previous behaviour.
    """
    # Ensure emoji and other non-ASCII characters can be written even when the
    # console uses a legacy code page (e.g. cp1251 on Windows). ``errors`` is
    # set to "replace" so that genuinely unrepresentable output degrades
    # gracefully instead of raising ``UnicodeEncodeError`` from the handler.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    root = logging.getLogger()
    root.setLevel(level)

    already_configured = any(
        isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout
        for handler in root.handlers
    )
    if not already_configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)


def _run(config_path: str, flat_only: bool, debug: bool, menu_override: str | None = None) -> int:
    """Runs the pipeline: load → validate → flatten → generate → save JSON."""
    from .common import save_json_data
    from .menu_generator import MenuGenerator
    from .menucraft import MenuCraft

    processor = MenuCraft(config_path, menu_override=menu_override)

    if not processor.validate_required_functions():
        return 1

    # Debug artifacts: the flattened menu and the functions summary.
    processor.save_flattern_json()
    save_json_data(processor.functions, "output/functions.json")

    if flat_only:
        logger.info("✅ " + _("Flat-only mode: C-code generation skipped"))
        return 0

    # Constructing the generator renders all C sources.
    MenuGenerator(config_path, processor=processor)

    if debug:
        processor.print_detailed_function_summary()
        processor.print_callback_summary()

    return 0


def main(argv: list[str] | None = None) -> int:
    """Parses arguments, runs the pipeline and returns the exit code."""
    args = build_parser().parse_args(argv)

    # Configuration paths (templates, output directory, flattened menu) are
    # resolved relative to the CWD, so change into the project root.
    os.chdir(_resolve_project_root())

    if args.quiet:
        level = logging.WARNING
    elif args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    _setup_logging(level)

    config_path = args.config or DEFAULT_CONFIG

    try:
        return _run(config_path, args.flat_only, args.debug, args.menu)
    except Exception as e:
        logger.error("❌ " + _("Error: {error}").format(error=e))
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
