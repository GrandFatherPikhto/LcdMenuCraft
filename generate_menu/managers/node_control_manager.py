import logging
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from ..i18n import _
from ..menu_data import MenuData, ControlType
from .callback_manager import CallbackManager
from .function_info import FunctionInfo

logger = logging.getLogger(__name__)

class NodeControlManager:
    """Manager for node controls and automatic function generation."""
    
    def __init__(self, node_id: str, node_type: str, node_role: str, node_c_type: str, 
                 original_node: Dict[str, Any], menu_data: MenuData, 
                 callback_manager: CallbackManager, node_navigate: Optional[str] = None):
        self._node_id = node_id
        self._node_type = node_type
        self._node_role = node_role
        self._node_c_type = node_c_type
        self._original_node = original_node
        self._menu_data = menu_data
        self._callback_manager = callback_manager
        self._node_navigate = node_navigate
        
        # Control configuration from JSON
        self._controls_config = original_node.get("controls")
        self._controls = []
        
        # Initialize controls
        self._init_controls()

    def _init_controls(self):
        """Initializes controls based on the role, MenuData rules and node configuration."""
        if self._node_type is None or self._node_role is None:
            return
            
        self._controls = []
        
        # If custom callbacks are set, skip automatic controls for them
        use_auto_click = self._callback_manager.click_cb is None
        use_auto_position = self._callback_manager.position_cb is None
        
        # For the factor role always use both controls, unless custom callbacks are set
        if self._node_role == "factor":
            controls_to_check = []
            if use_auto_click:
                controls_to_check.append(ControlType.CLICK)
            if use_auto_position:
                controls_to_check.append(ControlType.POSITION)
        else:
            # For other roles: if controls are specified in the node, use them, otherwise both
            if self._controls_config:
                controls_to_check = [ControlType(ctrl) for ctrl in self._controls_config]
            else:
                controls_to_check = [ControlType.CLICK, ControlType.POSITION]
            
            # Filter controls according to custom callbacks
            if not use_auto_click and ControlType.CLICK in controls_to_check:
                controls_to_check.remove(ControlType.CLICK)
            if not use_auto_position and ControlType.POSITION in controls_to_check:
                controls_to_check.remove(ControlType.POSITION)
        
        # Process each control
        auto_click_info = None
        auto_position_info = None
        
        for control_type in controls_to_check:
            control_config = self._menu_data.get_control_config(
                self._node_role, control_type, self._controls_config, self._node_navigate
            )
            
            if control_config:
                self._controls.append({
                    "type": control_type,
                    "purpose": control_config["purpose"],
                    "navigate": control_config["navigate"],
                    "required": control_config["required"]
                })
                
                # Generate the function name and store the information
                function_name = self._generate_function_name(control_type, control_config)
                auto_info = {
                    "name": function_name,
                    "navigate": control_config["navigate"].value,  # 'cyclic' or 'limit'
                    "purpose": control_config["purpose"],
                    "control_type": control_type.value
                }
                
                if control_type == ControlType.CLICK:
                    auto_click_info = auto_info
                elif control_type == ControlType.POSITION:
                    auto_position_info = auto_info
        
        # Set automatic functions in the CallbackManager with additional information
        self._callback_manager.set_auto_functions(auto_click_info, auto_position_info)

    def _generate_function_name(self, control: ControlType, control_config: Dict) -> str:
        """Generates the function name according to the rules."""
        base_name = f"{self._node_type}_{self._node_role}"
        
        # Special case for the factor role when changing the index
        if self._node_role == "factor" and control_config["purpose"] == "change_factor_index":
            name = f"{base_name}_{control.value}_{control_config['navigate'].value}_factor"
        else:
            name = f"{base_name}_{control.value}_{control_config['navigate'].value}"
        
        # Add the _cb suffix for automatic functions
        return name + "_cb"

    # Properties for accessing controls
    @property
    def controls(self) -> List[Dict]:
        """List of node controls."""
        return self._controls

    @property
    def controls_config(self) -> Optional[List[str]]:
        """Control configuration from JSON."""
        return self._controls_config

    @property
    def has_controls(self) -> bool:
        """Whether the node has controls."""
        return len(self._controls) > 0

    @property
    def required_controls(self) -> List[Dict]:
        """Required controls."""
        return [control for control in self._controls if control.get("required", False)]

    @property
    def has_required_controls(self) -> bool:
        """Whether the node has required controls."""
        return any(control.get("required", False) for control in self._controls)

    # Properties for accessing functions
    @property
    def all_function_infos(self) -> List[Dict[str, Any]]:
        """All possible handler functions for this node with full information."""
        infos = []
        
        # Automatic functions via dataclass
        for auto_func in self._callback_manager.auto_functions_info:
            function_info = FunctionInfo.create_auto(
                self._node_id, self._node_type, self._node_role, self._node_c_type,
                auto_func["name"], auto_func["event_type"],
                auto_func["navigate"], auto_func["purpose"],
                self._menu_data.printf_format(self._node_type),
                self._menu_data.printf_cast(self._node_type)
            )
            infos.append(asdict(function_info))
        
        # Custom functions via dataclass
        for cb_type, cb_info in self._callback_manager.defined_callback_infos.items():
            if cb_info and cb_info["custom"]:
                # Check whether it duplicates automatic functions
                if not any(info["name"] == cb_info["name"] for info in infos):
                    function_info = FunctionInfo.create_custom(
                        self._node_id, self._node_type, self._node_role, self._node_c_type,
                        cb_info,
                        self._menu_data.printf_format(self._node_type),
                        self._menu_data.printf_cast(self._node_type)
                    )
                    infos.append(asdict(function_info))
        
        return infos

    @property
    def detailed_function_infos(self) -> Dict[str, Dict[str, Any]]:
        """Detailed information about all functions, grouped by name."""
        return {info["name"]: info for info in self.all_function_infos}

    # Methods for checking required functions
    def validate_required_functions(self) -> List[Dict[str, str]]:
        """Checks that all required functions are generated."""
        missing_functions = []
        
        for control in self._controls:
            if control.get("required", False):
                function_name = None
                if control["type"] == ControlType.CLICK:
                    function_name = self._callback_manager._auto_click_function
                elif control["type"] == ControlType.POSITION:
                    function_name = self._callback_manager._auto_position_function
                
                if not function_name:
                    missing_functions.append({
                        "node": self._node_id,
                        "control": control["type"].value,
                        "purpose": control["purpose"]
                    })
        
        return missing_functions

    def get_control_summary(self) -> Dict[str, Any]:
        """Control summary for debugging."""
        return {
            "node_id": self._node_id,
            "type": self._node_type,
            "role": self._node_role,
            "navigate": self._node_navigate,
            "controls_config": self._controls_config,
            "controls": [
                {
                    "type": control["type"].value,
                    "purpose": control["purpose"],
                    "navigate": control["navigate"].value,
                    "required": control["required"]
                }
                for control in self._controls
            ],
            "has_required_controls": self.has_required_controls,
            "required_controls_count": len(self.required_controls),
            "all_functions_count": len(self.all_function_infos),
            "auto_click_function": self._callback_manager._auto_click_function,
            "auto_position_function": self._callback_manager._auto_position_function
        }

    def print_control_info(self):
        """Prints control information for debugging."""
        summary = self.get_control_summary()
        logger.debug(_("Control info for {id} (role: {role}):").format(id=self._node_id, role=self._node_role))
        
        if summary["controls_config"]:
            logger.debug(_("  Config from JSON: {config}").format(config=summary['controls_config']))
        
        if summary["controls"]:
            logger.debug(_("  Active controls: {controls}").format(controls=[ctrl['type'] for ctrl in summary['controls']]))
        
        # Show custom callbacks
        if self._callback_manager.has_custom_callbacks:
            logger.debug(_("  Custom callbacks:"))
            for cb_name, cb_value in self._callback_manager.custom_callbacks_summary.items():
                if cb_value and cb_name != "auto_draw_value_cb":
                    logger.debug(f"    - {cb_name}: {cb_value}")
        
        # Show automatic functions
        if self._callback_manager._auto_click_function:
            logger.debug(_("  Auto click function: {name}").format(name=self._callback_manager._auto_click_function))
        if self._callback_manager._auto_position_function:
            logger.debug(_("  Auto position function: {name}").format(name=self._callback_manager._auto_position_function))
        
        # Show the draw function
        if self._callback_manager.effective_draw_value_cb:
            source = "custom" if self._callback_manager.draw_value_cb else "auto"
            logger.debug(_("  Draw value function: {name} ({source})").format(
                name=self._callback_manager.effective_draw_value_cb, source=source))

    def __repr__(self):
        """String representation for debugging."""
        return (f"NodeControlManager({self._node_id}, controls={len(self._controls)}, "
                f"functions={len(self.all_function_infos)})")