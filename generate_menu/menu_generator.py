"""Renders the Jinja2 templates into the generated C sources."""

import logging
import os
from pathlib import Path
from typing import Optional

from jinja2 import (
    Environment,
    FileSystemLoader,
    TemplateSyntaxError,
    UndefinedError,
    TemplateError,
)

from .i18n import _
from .menu_config import MenuConfig
from .menucraft import MenuCraft

logger = logging.getLogger(__name__)


class MenuGenerator:
    """Generates C source files from the Jinja2 templates."""

    def __init__(self, config_json, processor: Optional[MenuCraft] = None, menu_override: Optional[str] = None):
        self._processor = processor if processor is not None else MenuCraft(config_json, menu_override=menu_override)
        self._config: MenuConfig = self._processor.config
        self._env = Environment(
            loader=FileSystemLoader(str(self._config.templates_path)),
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=['jinja2.ext.debug'],
        )
        self._files = self._config.generation_files
        self._context = {}

        self._generate()

    def _generate(self):
        self._build_template_context()
        self._generate_code()

    def save_flatterned_menu(self, output_path: str | None = None):
        self._processor.save_flattern_json(output_path)

    def _build_template_context(self):
        self._context = {
            'menu': self._processor.menu,
            'first': self._processor.first,
            'leafs': self._processor.leafs,
            'categories': self._processor.categories,
            'functions': self._processor.functions,
            'wrap_by_name_functions': self._config.wrap_by_name_functions,
            'enable_node_names': self._config.enable_node_names,
            'include_files': self._config.include_files,
        }

    def _generate_code(self):
        if self._files is not None:
            for template, output in self._files.items():
                logger.info(_("Generate: {template} => {output}").format(
                    template=template, output=output))
                self._generate_file(template, output, self._context)

    def _generate_file(self, template_name: str, output_path: str | Path, template_data):
        """Generates a specific file."""
        logger.info(_("Generate from {template} to {output}").format(
            template=template_name, output=output_path))

        try:
            # Load the template
            template = self._env.get_template(str(template_name))

            # Render
            content = template.render(**template_data)

            # Save
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"✅ {_('Generated {path}').format(path=output_path)}")

        except TemplateSyntaxError as e:
            logger.error(f"❌ {_('Template Syntax Error: {error}').format(error=str(e))}")
        except UndefinedError as e:
            logger.error(f"❌ {_('Undefined Variable Error: {error}').format(error=str(e))}")
        except TemplateError as e:
            logger.error(f"❌ {_('General Template Error: {error}').format(error=str(e))}")
        except Exception as e:
            logger.error(f"❌ {_('Error generating {path} file: {error}').format(
                path=output_path, error=e)}")
