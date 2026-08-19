import json
import logging
from typing import Any, Dict, List, Optional

from .flat_node import FlatNode
from .menu_validator import MenuValidator
from .menu_config import MenuConfig, ConfigError
from .menu_flattener import MenuFlattener, FlattenerError
from .menu_data import ControlType
from .menu_data_aggregator import MenuDataAggregator
from .i18n import _

logger = logging.getLogger(__name__)


class ProcessorError(Exception):
    """Exception raised for configuration errors."""

    def __init__(self, message: str):
        super().__init__(message)


class MenuCraft:
    """Orchestrates the menu pipeline: load → validate → flatten.

    Derived menu data (functions, categories, leaves, callbacks, ...) is
    delegated to :class:`MenuDataAggregator`, which memoizes every result;
    the processor itself keeps the configuration, the flattened nodes and
    the artifact-saving/validation/debug helpers.
    """

    def __init__(self, config_name: str, menu_override: Optional[str] = None):
        self._config_name = config_name
        self._config = MenuConfig(self._config_name, menu_override=menu_override)
        logger.info("✅ " + _("Configuration {path} loaded successfully").format(path=self._config_name))
        self._validator = MenuValidator(config=self._config)
        errors = self._validator.validate()
        if errors:
            logger.error("❌ " + _("Configuration contains errors:"))
            for id, items in errors.items():
                logger.error("❌ " + _("{id}:").format(id=id))
                for item in items:
                    logger.error("\t➤ " + str(item))
            raise ProcessorError("❌ " + _("Configuration error"))
        else:
            logger.info("✅ " + _("and validated"))
            self._flattener = MenuFlattener(self._config)
            self._flat_nodes = self._flattener.flatten()
            self._aggregator = MenuDataAggregator(self._flat_nodes)

            # Debug information about controls
            self._print_control_summary()

    def _print_control_summary(self):
        """Prints a control summary for debugging."""
        logger.debug("\n📊 " + _("Control summary:"))
        for node in self._flat_nodes:
            if node.id == 'root':
                continue
            logger.debug("- " + str(node))
            if hasattr(node, 'print_control_info'):
                node.print_control_info()
        logger.debug("")

    def save_flattern_json(self, file_name: str | None = None):
        """Saves the flat menu representation to JSON (optional)."""
        if file_name is None and self._config.flatten:
            file_name = self._config.flatten

        if file_name:
            flat_data = {
                "nodes": [
                    {
                        "id": node.id,
                        "name": node.name,
                        "type": node.type,
                        "role": node.role,
                        "parent": node.parent.id if node.parent else None,
                        "prev_sibling": node.prev_sibling.id if node.prev_sibling else None,
                        "next_sibling": node.next_sibling.id if node.next_sibling else None,
                        "children": [child.id for child in node.children],
                        "is_leaf": node.is_leaf,
                        "is_branch": node.is_branch,
                        "controls": [
                            {
                                "type": control["type"].value,
                                "purpose": control["purpose"],
                                "navigate": control["navigate"].value,
                                "required": control["required"]
                            }
                            for control in getattr(node, '_controls', [])
                        ]
                    }
                    for node in self._flat_nodes if node.id != 'root'
                ]
            }

            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(flat_data, f, indent=2, ensure_ascii=False)
                logger.info("✅ " + _("Flat menu saved to {path}").format(path=file_name))
            except Exception as e:
                logger.error("❌ " + _("Error saving flat menu: {error}").format(error=e))

    @property
    def config(self) -> MenuConfig:
        return self._config

    @property
    def data(self) -> MenuDataAggregator:
        """Access to the aggregated menu data."""
        return self._aggregator

    # ------------------------------------------------------------------
    # Aggregation API (delegated to MenuDataAggregator, memoized there).
    # These accessors keep the public interface used by the CLI, the
    # generator templates and the tests unchanged.
    # ------------------------------------------------------------------

    @property
    def menu(self) -> Dict[str, FlatNode]:
        """All menu nodes (excluding root)."""
        return self._aggregator.menu

    @property
    def functions(self) -> Dict[str, Dict[str, Any]]:
        """All handler functions grouped by name with full information."""
        return self._aggregator.functions

    @property
    def categories(self) -> Dict[str, Dict[str, Any]]:
        """All menu categories (type + role)."""
        return self._aggregator.categories

    @property
    def leafs(self) -> Dict[str, FlatNode]:
        """All leaf nodes (final menu items)."""
        return self._aggregator.leafs

    @property
    def branches(self) -> Dict[str, FlatNode]:
        """All menu branches (nodes with children)."""
        return self._aggregator.branches

    @property
    def first(self) -> Optional[FlatNode]:
        """The first menu node (after root)."""
        return self._aggregator.first

    @property
    def callback_nodes(self) -> Dict[str, FlatNode]:
        """All nodes with the callback role."""
        return self._aggregator.callback_nodes

    @property
    def required_functions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by category, marking the required ones."""
        return self._aggregator.required_functions

    @property
    def custom_callbacks(self) -> Dict[str, Dict[str, Any]]:
        """All custom callback functions."""
        return self._aggregator.custom_callbacks

    @property
    def auto_generated_functions(self) -> Dict[str, Dict[str, Any]]:
        """All automatically generated functions with full information."""
        return self._aggregator.auto_generated_functions

    @property
    def functions_by_event_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by event type."""
        return self._aggregator.functions_by_event_type

    @property
    def functions_by_navigation(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by navigation type."""
        return self._aggregator.functions_by_navigation

    @property
    def nodes_with_custom_callbacks(self) -> Dict[str, FlatNode]:
        """All nodes with custom callbacks."""
        return self._aggregator.nodes_with_custom_callbacks

    def get_callbacks_by_type(self, callback_type: str) -> Dict[str, str]:
        """Get callbacks of a specific type."""
        return self._aggregator.get_callbacks_by_type(callback_type)

    def get_functions_by_category(self, category_name: str) -> List[Dict[str, Any]]:
        """All functions for the given category."""
        return self._aggregator.get_functions_by_category(category_name)

    def get_callbacks_by_category(self, category_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """All callback functions for the given category."""
        return self._aggregator.get_callbacks_by_category(category_name)

    @property
    def detailed_callback_infos(self) -> Dict[str, List[Dict[str, Any]]]:
        """Detailed information about all callback functions, grouped by type."""
        return self._aggregator.detailed_callback_infos

    @property
    def callback_summary_by_category(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Callback function summary by category."""
        return self._aggregator.callback_summary_by_category

    @property
    def functions_by_type_role(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by the type_role combination."""
        return self._aggregator.functions_by_type_role

    @property
    def functions_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by data type."""
        return self._aggregator.functions_by_type

    @property
    def functions_by_role(self) -> Dict[str, List[Dict[str, Any]]]:
        """Functions grouped by role."""
        return self._aggregator.functions_by_role

    # ------------------------------------------------------------------
    # Summaries, validation and debug output (processor-level concerns).
    # ------------------------------------------------------------------

    def print_callback_summary(self):
        """Prints a callback summary."""
        logger.debug("\n🎛️ " + _("Callback functions summary:"))

        custom_callbacks = self.custom_callbacks
        if custom_callbacks:
            logger.debug(_("Custom callbacks:"))
            for cb_name, cb_info in custom_callbacks.items():
                logger.debug("  - " + _("{name} ({type}) -> {node_id}").format(
                    name=cb_name, type=cb_info['callback_type'], node_id=cb_info['node_id']))
        else:
            logger.debug(_("Custom callbacks: none"))

        auto_funcs = self.auto_generated_functions
        if auto_funcs:
            logger.debug(_("Automatically generated functions:"))
            for func_name, func_info in auto_funcs.items():
                logger.debug("  - " + _("{name} ({source}) -> {node_id}").format(
                    name=func_name, source=func_info['source'], node_id=func_info['node_id']))

        nodes_with_callbacks = self.nodes_with_custom_callbacks
        if nodes_with_callbacks:
            logger.debug(_("Nodes with custom callbacks: {count}").format(count=len(nodes_with_callbacks)))
        else:
            logger.debug(_("Nodes with custom callbacks: none"))

    def validate_required_functions(self) -> bool:
        """Checks that all required functions are generated."""
        missing_functions = []

        for node in self._flat_nodes:
            if node.id == 'root':
                continue

            for control in getattr(node, '_controls', []):
                if control.get("required", False):
                    function_name = None
                    if control["type"] == ControlType.CLICK:
                        function_name = node.callback_manager._auto_click_function
                    elif control["type"] == ControlType.POSITION:
                        function_name = node.callback_manager._auto_position_function

                    if not function_name:
                        missing_functions.append({
                            "node": node.id,
                            "control": control["type"].value,
                            "purpose": control["purpose"]
                        })

        if missing_functions:
            logger.error("❌ " + _("Missing required functions:"))
            for missing in missing_functions:
                logger.error("   - " + _("{node}: {control} ({purpose})").format(
                    node=missing['node'], control=missing['control'], purpose=missing['purpose']))
            return False

        logger.info("✅ " + _("All required functions are present"))
        return True

    def print_detailed_callback_summary(self):
        """Prints a detailed summary of all callback functions."""
        logger.debug("\n📋 " + _("Detailed callback functions summary:"))

        # Summary by callback type
        detailed_infos = self.detailed_callback_infos
        for cb_type, infos in detailed_infos.items():
            if infos:
                custom_count = sum(1 for info in infos if info["custom"])
                auto_count = len(infos) - custom_count
                logger.debug("\n" + _("{type}:").format(type=cb_type.upper()))
                logger.debug("  " + _("Total: {total} (🎛️ {custom} custom, ⚙️ {auto} automatic)").format(
                    total=len(infos), custom=custom_count, auto=auto_count))

                for info in infos[:3]:  # Show the first 3 as examples
                    custom_flag = "🎛️" if info["custom"] else "⚙️"
                    logger.debug("    - " + _("{name} {flag} -> {node_id} ({category})").format(
                        name=info['name'], flag=custom_flag, node_id=info['node_id'], category=info['category']))

                if len(infos) > 3:
                    logger.debug("    " + _("... and {count} more").format(count=len(infos) - 3))

        # Summary by category
        logger.debug("\n📊 " + _("Categories summary:"))
        category_summary = self.callback_summary_by_category
        for category, callbacks in category_summary.items():
            total = sum(len(cb_list) for cb_list in callbacks.values())
            if total > 0:
                logger.debug("\n  " + _("{category}:").format(category=category))
                for cb_type, cb_list in callbacks.items():
                    custom_count = sum(1 for cb in cb_list if cb["custom"])
                    auto_count = len(cb_list) - custom_count
                    logger.debug("    " + _("{type}: {count} (🎛️ {custom}, ⚙️ {auto})").format(
                        type=cb_type, count=len(cb_list), custom=custom_count, auto=auto_count))

    def print_detailed_function_summary(self):
        """Prints a detailed summary of all functions with type and role."""
        logger.debug("\n📋 " + _("Detailed functions summary:"))

        # Summary by event type
        by_event = self.functions_by_event_type
        for event_type, functions in by_event.items():
            logger.debug("\n🎯 " + _("{event} functions ({count}):").format(
                event=event_type.upper(), count=len(functions)))
            for func in functions[:3]:  # Show the first 3 as examples
                source_flag = "🎛️" if func.get("custom") else "⚙️"
                navigate_info = f" [navigate: {func.get('navigate', 'N/A')}]" if func.get("navigate") else ""
                type_role_info = f" ({func.get('type', 'N/A')}_{func.get('role', 'N/A')})"
                logger.debug(f"    - {func['name']} {source_flag}{navigate_info}{type_role_info} -> {func['node_id']}")

            if len(functions) > 3:
                logger.debug("    " + _("... and {count} more").format(count=len(functions) - 3))

        # Summary by type and role
        logger.debug("\n🏷️ " + _("Types and roles summary:"))
        by_type_role = self.functions_by_type_role
        for type_role, functions in by_type_role.items():
            if type_role and type_role != "N/A_N/A":
                logger.debug("  " + _("{type_role}: {count} functions").format(
                    type_role=type_role, count=len(functions)))

    def print_debug_factor_nodes(self):
        """Debug information about factor nodes and their functions."""
        logger.debug("\n🔍 " + _("DEBUG INFO ABOUT FACTOR NODES:"))

        factor_nodes = [n for n in self._flat_nodes if n.role == "factor" and n.id != 'root']
        logger.debug(_("Factor nodes: {ids}").format(ids=[n.id for n in factor_nodes]))

        for node in factor_nodes:
            logger.debug(f"\n--- {node.id} ---")
            logger.debug(_("Controls: {value}").format(value=node.controls))
            logger.debug(_("Navigate: {value}").format(value=node.navigate))

            # Check the CallbackManager
            logger.debug(_("Auto click function: {name}").format(name=node.callback_manager._auto_click_function))
            logger.debug(_("Auto position function: {name}").format(name=node.callback_manager._auto_position_function))
            logger.debug(_("Auto click info: {value}").format(value=node.callback_manager._auto_click_info))
            logger.debug(_("Auto position info: {value}").format(value=node.callback_manager._auto_position_info))

            logger.debug(_("Auto functions info: {value}").format(value=node.callback_manager.auto_functions_info))
            logger.debug(_("All function infos: {value}").format(value=node.all_function_infos))

            # Check required functions
            for control in getattr(node, '_controls', []):
                if control.get("required", False):
                    function_name = None
                    if control["type"] == ControlType.CLICK:
                        function_name = node.callback_manager._auto_click_function
                    elif control["type"] == ControlType.POSITION:
                        function_name = node.callback_manager._auto_position_function
                    logger.debug(_("Required {type}: {name} (purpose: {purpose})").format(
                        type=control['type'].value, name=function_name, purpose=control['purpose']))
