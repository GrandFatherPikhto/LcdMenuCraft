from typing import Dict, List, Optional, Set, Any
from .menu_config import MenuConfig
from .menu_data import MenuData
from .managers.node_data_manager import NodeDataManager
from .managers.node_control_manager import NodeControlManager
from .managers.node_navigation_manager import NodeNavigationManager
from .managers.callback_manager import CallbackManager

class BaseFlatNode:
    """Base node class - composition of managers for various aspects."""
    
    def __init__(self, original_node: Dict[str, Any], config: MenuConfig, menu_data: MenuData):
        self._original_node = original_node
        self._menu_config = config
        self._menu_data = menu_data
        
        # Create the data manager
        self._data_manager = NodeDataManager(original_node, menu_data)
        
        # Create the CallbackManager
        self._callback_manager = CallbackManager(
            original_node, 
            self._data_manager.type, 
            self._data_manager.role, 
            self._data_manager.category,
            menu_data
        )
        
        # Basic navigation properties
        self._navigate = original_node.get("navigate", None)
        
        # Control configuration from JSON
        self._controls_config = original_node.get("controls")

        # Create the navigation manager
        self._navigation_manager = NodeNavigationManager(self)

        # Create the control manager (empty for now, initialized in subclasses)
        self._control_manager: Optional[NodeControlManager] = None

        # Navigation links (initialized later by the MenuFlattener)
        self.parent: Optional["BaseFlatNode"] = None
        self.children: List["BaseFlatNode"] = []
        self.first_child: Optional["BaseFlatNode"] = None
        self.last_child: Optional["BaseFlatNode"] = None

    # Initialize the control manager (called by subclasses)
    def _init_control_manager(self):
        """Initializes the control manager."""
        if self._data_manager.type is None or self._data_manager.role is None:
            return
            
        self._control_manager = NodeControlManager(
            node_id=self.id,
            node_type=self._data_manager.type,
            node_role=self._data_manager.role,
            node_c_type=self._data_manager.c_type,
            original_node=self._original_node,
            menu_data=self._menu_data,
            callback_manager=self._callback_manager,
            node_navigate=self._navigate
        )

    # Delegate data properties to the NodeDataManager
    @property
    def id(self) -> str:
        return self._original_node["id"]

    @property
    def name(self) -> str:
        return self._original_node["title"]

    @property
    def type(self) -> Optional[str]:
        return self._data_manager.type

    @property
    def role(self) -> Optional[str]:
        return self._data_manager.role

    @property
    def min(self):
        return self._data_manager.min

    @property
    def max(self):
        return self._data_manager.max

    @property
    def default(self):
        return self._data_manager.default

    @property
    def default_idx(self):
        return self._data_manager.default_idx

    @property
    def factors(self):
        return self._data_manager.factors

    @property
    def tag(self):
        return self._data_manager.tag

    @property
    def values(self):
        return self._data_manager.values

    @property
    def step(self) -> int:
        return self._data_manager.step

    @step.setter
    def step(self, step: int):
        self._data_manager.step = step

    @property
    def c_type(self) -> Optional[str]:
        return self._data_manager.c_type

    @property
    def category_name(self) -> Optional[str]:
        return self._data_manager.category_name

    @property
    def category(self) -> Optional[Dict[str, Any]]:
        return self._data_manager.category

    @property
    def fixed_count(self) -> Optional[int]:
        return self._data_manager.fixed_count

    @property
    def values_count(self) -> Optional[int]:
        return self._data_manager.values_count

    @property
    def values_default_idx(self) -> Optional[int]:
        return self._data_manager.values_default_idx

    @property
    def factors_default_idx(self) -> Optional[int]:
        return self._data_manager.factors_default_idx

    @property
    def c_str_factors(self) -> Optional[str]:
        return self._data_manager.c_str_factors

    @property
    def c_str_values(self) -> Optional[str]:
        return self._data_manager.c_str_values

    # Delegate control properties to the NodeControlManager
    @property
    def controls(self) -> List[Dict]:
        if self._control_manager is None:
            return []
        return self._control_manager.controls

    @property
    def controls_config(self) -> Optional[List[str]]:
        return self._controls_config

    @property
    def all_function_infos(self) -> List[Dict[str, Any]]:
        if self._control_manager is None:
            return []
        return self._control_manager.all_function_infos

    @property
    def detailed_function_infos(self) -> Dict[str, Dict[str, Any]]:
        if self._control_manager is None:
            return {}
        return self._control_manager.detailed_function_infos

    # Delegate navigation properties to the NodeNavigationManager
    @property
    def prev_sibling(self) -> Optional['BaseFlatNode']:
        return self._navigation_manager.effective_prev_sibling

    @property
    def next_sibling(self) -> Optional['BaseFlatNode']:
        return self._navigation_manager.effective_next_sibling

    @prev_sibling.setter
    def prev_sibling(self, value: Optional['BaseFlatNode']):
        self._navigation_manager.prev_sibling = value

    @next_sibling.setter
    def next_sibling(self, value: Optional['BaseFlatNode']):
        self._navigation_manager.next_sibling = value

    @property
    def has_cyclic_siblings(self) -> bool:
        return self._navigation_manager.has_cyclic_siblings

    @property
    def sibling_count(self) -> int:
        return self._navigation_manager.sibling_count

    @property
    def sibling_index(self) -> int:
        return self._navigation_manager.sibling_index

    @property
    def is_first_child(self) -> bool:
        return self._navigation_manager.is_first_child

    @property
    def is_last_child(self) -> bool:
        return self._navigation_manager.is_last_child

    @property
    def is_only_child(self) -> bool:
        return self._navigation_manager.is_only_child

    # Delegate properties to the CallbackManager
    @property
    def callback_manager(self) -> CallbackManager:
        return self._callback_manager

    def get_callback_info(self, callback_type: str) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_callback_info(callback_type)

    def get_draw_value_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_draw_value_info()

    def get_double_click_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_double_click_info()

    def get_long_click_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_long_click_info()

    def get_event_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_event_info()

    def get_click_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_click_info()

    def get_position_info(self) -> Optional[Dict[str, Any]]:
        return self._callback_manager.get_position_info()

    @property
    def all_callback_infos(self) -> Dict[str, Optional[Dict[str, Any]]]:
        return self._callback_manager.all_callback_infos

    @property
    def defined_callback_infos(self) -> Dict[str, Dict[str, Any]]:
        return self._callback_manager.defined_callback_infos

    @property
    def auto_generated_callbacks(self) -> Dict[str, Dict[str, Any]]:
        return self._callback_manager.auto_generated_callbacks

    @property
    def custom_callbacks(self) -> Dict[str, Dict[str, Any]]:
        return self._callback_manager.custom_callbacks

    @property
    def custom_callbacks_summary(self) -> Dict[str, Optional[str]]:
        return self._callback_manager.custom_callbacks_summary

    @property
    def has_custom_callbacks(self) -> bool:
        return self._callback_manager.has_custom_callbacks

    # Basic navigation properties
    @property
    def navigate(self) -> Optional[str]:
        return self._navigate

    @navigate.setter
    def navigate(self, value: str):
        self._navigate = value

    # Basic tree structure properties
    @property
    def is_leaf(self) -> bool:
        """Whether the node is a leaf (has no children)."""
        return not self.children

    @property
    def is_branch(self) -> bool:
        """Whether the node is a branch (has children)."""
        return bool(self.children)

    # Methods for accessing the managers
    @property
    def data_manager(self) -> NodeDataManager:
        """Access to the data manager."""
        return self._data_manager

    @property
    def control_manager(self) -> Optional[NodeControlManager]:
        """Access to the control manager."""
        return self._control_manager

    @property
    def navigation_manager(self) -> NodeNavigationManager:
        """Access to the navigation manager."""
        return self._navigation_manager

    def validate_data(self) -> List[str]:
        """Validates node data."""
        errors = []
        errors.extend(self._data_manager.validate_numeric_range())
        errors.extend(self._data_manager.validate_fixed_values())
        return errors

    def validate_required_functions(self) -> List[Dict[str, str]]:
        """Checks that all required functions are generated."""
        if self._control_manager is None:
            return []
        return self._control_manager.validate_required_functions()

    def get_data_summary(self) -> Dict[str, Any]:
        """Node data summary."""
        return self._data_manager.get_data_summary()

    def get_control_summary(self) -> Dict[str, Any]:
        """Control summary."""
        if self._control_manager is None:
            return {
                "node_id": self.id,
                "type": self.type,
                "role": self.role,
                "has_control_manager": False
            }
        return self._control_manager.get_control_summary()

    def get_navigation_info(self) -> Dict[str, Any]:
        """Node navigation information."""
        return self._navigation_manager.get_navigation_info()

    def print_control_info(self):
        """Prints control information."""
        if self._control_manager is not None:
            self._control_manager.print_control_info()

    def print_navigation_debug(self):
        """Prints debug navigation information."""
        self._navigation_manager.print_navigation_debug()

    # Basic utilities for debugging
    def __repr__(self):
        """Simplified string representation."""
        tree_flag = "📁"
        match self.role:
            case "simple":
                tree_flag = "🟦"
            case "factor":
                tree_flag = "🟢"
            case "fixed": 
                tree_flag = "⚫"
            case "callback":
                tree_flag = "⚪"
            case _:
                if self.role is not None:
                    tree_flag = "✨"
        
        controls_str = ""
        if self._control_manager and self._control_manager.controls:
            controls_str = " [" + ", ".join([c["type"].value for c in self._control_manager.controls]) + "]"
        
        config_info = ""
        if self._controls_config:
            config_info = f" (config: {self._controls_config})"
        
        callback_flag = "🎛️" if self.has_custom_callbacks else ""
        cyclic_flag = "🔁" if self.has_cyclic_siblings else "➡️"
        
        return f"BaseFlatNode({tree_flag} {cyclic_flag} {self.id}{controls_str}{config_info} {callback_flag}, {self.sibling_index + 1}/{self.sibling_count})"