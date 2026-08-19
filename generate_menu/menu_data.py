from typing import Dict, Any, Set, List, Tuple, Optional
from enum import Enum

from .i18n import _
from .menu_config import MenuConfig

class ControlType(Enum):
    CLICK = "click"
    POSITION = "position"

class NavigationType(Enum):
    LIMIT = "limit"
    CYCLIC = "cyclic"

class MenuData:
    def __init__(self, config: MenuConfig):
        self._config = config
        self._data_config = config.data_config
        self._roles: Dict[str, List] = self._data_config.get("roles") or {}
        self._types: Dict[str, Dict[str, str]] = self._data_config.get("types") or {}
        self._controls: Dict[str, List[str]] = self._data_config.get("controls", {}) or {}
        self._navigation_rules: Dict[str, Dict[str, Any]] = self._data_config.get("navigation_rules", {}) or {}
        self._role_rules: Dict[str, Any] = self._data_config.get("role_rules", {}) or {}
        
        # Build a reverse mapping: type -> roles
        self._type_to_roles: Dict[str, List[str]] = self._build_type_to_role_mapping()

    def _build_type_to_role_mapping(self) -> Dict[str, List[str]]:
        """Builds a mapping from a type to its list of roles."""
        mapping = {}
        for role, types in self._roles.items():
            for type_name in types:
                if type_name not in mapping:
                    mapping[type_name] = []
                mapping[type_name].append(role)
        return mapping

    def get_controls_for_type(self, type_name: str) -> Set[ControlType]:
        """Returns the available controls for a type."""
        roles = self.get_roles_for_type(type_name)
        if not roles:
            return set()
            
        # Collect controls from all roles of the type
        all_controls = set()
        for role in roles:
            control_names = self._controls.get(role, [])
            all_controls.update({ControlType(name) for name in control_names})
                
        return all_controls

    def get_roles_for_type(self, type_name: str) -> List[str]:
        return self._type_to_roles.get(type_name, [])

    def get_navigation_rules(self, control: ControlType) -> Tuple[List[NavigationType], NavigationType]:
        """Returns the navigation rules for a control."""
        rules = self._navigation_rules.get(control.value, {})
        allowed_navigate = [NavigationType(nav) for nav in rules.get("allowed_navigate", [])]
        default_navigate = NavigationType(rules.get("default", "cyclic"))
        return allowed_navigate, default_navigate

    def is_valid_navigation(self, control: ControlType, navigate: NavigationType) -> bool:
        """Checks whether a control + navigate combination is allowed."""
        allowed_navigate, _ = self.get_navigation_rules(control)
        return navigate in allowed_navigate

    def get_default_navigation(self, control: ControlType) -> NavigationType:
        """Returns the default navigation for a control."""
        _, default_navigate = self.get_navigation_rules(control)
        return default_navigate
    
    def type(self, name: str) -> Dict[str, str] | None:
        return self._types.get(name)
    
    def c_type(self, name: str) -> str | None:
        type_data = self._types.get(name)
        if type_data is None:
            return None
        return type_data.get("c_type")

    def printf_format(self, name: str) -> str | None:
        type_data = self._types.get(name)
        if type_data is None:
            return None
        return type_data.get("printf_format")

    def printf_cast(self, name: str) -> str | None:
        type_data = self._types.get(name)
        if type_data is None:
            return None
        return type_data.get("printf_cast")


    def role(self, name: str) -> List | None:
        return self._roles.get(name)

    def role_types(self, name: str) -> List | None:
        if self._roles.get(name) is None:
            return None
        return self._roles[name]

    def get_role_rules(self, role: str) -> Optional[Dict[str, Any]]:
        """Returns the rules for the given role."""
        return self._role_rules.get(role)

    def get_control_config(self, role: str, control: ControlType, 
                        node_controls: Optional[List[str]] = None,
                        node_navigate: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns the control configuration for a role, honoring overrides."""
        rules = self.get_role_rules(role)
        if not rules:
            return None
        
        # Check whether the control is allowed for the role
        allowed_controls = rules.get("allowed_controls", [])
        
        # If the node lists explicit controls, validate against them
        if node_controls is not None:
            if control.value not in node_controls:
                return None
        # Otherwise validate against the role rules by default
        elif control.value not in allowed_controls:
            return None
        
        # Get the rules for the specific control
        control_rules = rules.get(control.value, {})
        if not control_rules:
            return None
        
        # For click always use cyclic; for position it can be overridden
        if control == ControlType.CLICK:
            navigate = NavigationType.CYCLIC
        else:
            navigate_str = node_navigate if node_navigate else control_rules.get("navigate", "limit")
            navigate = NavigationType(navigate_str)
        
        return {
            "purpose": control_rules.get("purpose"),
            "navigate": navigate,
            "required": control_rules.get("required", False)
        }

    @property
    def roles(self) -> Set[str]:
        return {role for role in self._roles}
    
    @property
    def types(self) -> Set[str]:
        return {type for type in self._types}
    
    def navigation_rule(self, name: str) -> Dict[str, List[str]] | None:
        return self._navigation_rules.get(name, None)

    @property
    def navigation_rules(self) -> Dict[str, Dict[str, List[str]]] | None:
        return self._navigation_rules

