from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from ..menu_data import MenuData, ControlType
from .callback_manager import CallbackManager

@dataclass
class FunctionInfo:
    """Dataclass for storing function information."""
    name: str
    node_id: str
    event_type: str
    navigate: Optional[str]
    purpose: str
    source: str
    type: str
    role: str
    c_type: str
    category: str
    printf_format: Optional[str] = None
    printf_cast: Optional[str] = None

    @classmethod
    def create_auto(cls, node_id: str, node_type: str, node_role: str, node_c_type: str,
                   name: str, event_type: str, navigate: str, purpose: str,
                   node_printf_format: Optional[str] = None, node_printf_cast: Optional[str] = None):
        """Factory method for automatic functions."""
        return cls(
            name=name,
            node_id=node_id,
            event_type=event_type,
            navigate=navigate,
            purpose=purpose,
            source="auto_generated",
            type=node_type,
            role=node_role,
            c_type=node_c_type,
            category=f"{node_type}_{node_role}",
            printf_format=node_printf_format,
            printf_cast=node_printf_cast
        )

    @classmethod
    def create_custom(cls, node_id: str, node_type: str, node_role: str, node_c_type: str,
                     cb_info: Dict[str, Any],
                     node_printf_format: Optional[str] = None, node_printf_cast: Optional[str] = None):
        """Factory method for custom functions."""
        category = cls._extract_category(cb_info)
        return cls(
            name=cb_info["name"],
            node_id=node_id,
            event_type=cb_info["event_type"],
            navigate=cb_info.get("navigate"),
            purpose=cb_info.get("purpose", "user_defined"),
            source="custom",
            type=node_type,
            role=node_role,
            c_type=node_c_type,
            category=category or f"{node_type}_{node_role}",
            printf_format=node_printf_format,
            printf_cast=node_printf_cast
        )
    
    @staticmethod
    def _extract_category(cb_info: Dict[str, Any]) -> Optional[str]:
        """Safely extracts the category."""
        if not cb_info.get("category"):
            return None
        category_data = cb_info["category"]
        return category_data.get("name") if isinstance(category_data, dict) else category_data

