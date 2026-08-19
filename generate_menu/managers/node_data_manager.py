from typing import Dict, List, Optional, Set, Any
from ..menu_data import MenuData

class NodeDataManager:
    """Manager for node data: values, factors, data types and categories."""
    
    def __init__(self, original_node: Dict[str, Any], menu_data: MenuData):
        self._original_node = original_node
        self._menu_data = menu_data
        
        # Value data from JSON
        self.min = original_node.get("min")
        self.max = original_node.get("max")
        self.default = original_node.get("default")
        self.default_idx = original_node.get("default_idx")
        self.factors = original_node.get("factors")
        self.values = original_node.get("values")
        self.raw_values = original_node.get("raw_values")
        self.tag = original_node.get("tag")
        self._step = original_node.get("step")
        
        # Basic type and role properties
        self._node_type = original_node.get("type")
        self._node_role = original_node.get("role")

    # Data type properties
    @property
    def type(self) -> Optional[str]:
        """Node data type."""
        return self._node_type

    @property
    def role(self) -> Optional[str]:
        """Node role."""
        return self._node_role

    @property
    def c_type(self) -> Optional[str]:
        """C data type for code generation."""
        if self._node_type is None:
            return None
        return self._menu_data.c_type(self._node_type)

    @property
    def category_name(self) -> Optional[str]:
        """Category name (type_role)."""
        if self._node_type is None or self._node_role is None:
            return None
        return f"{self._node_type}_{self._node_role}"

    @property
    def category(self) -> Optional[Dict[str, Any]]:
        """Full category information."""
        if self._node_type is None or self._node_role is None:
            return None
        return {
            "name": self.category_name,
            "type": self._node_type,
            "role": self._node_role,
            "c_type": self.c_type
        }

    # Value and factor properties
    @property
    def step(self) -> int:
        """Value change step."""
        if self._step is None:
            return 1
        return self._step

    @step.setter
    def step(self, step: int):
        """Sets the value change step."""
        self._step = step

    @property
    def fixed_count(self) -> Optional[int]:
        """Number of factors (for fixed types)."""
        if self.factors is None:
            return None
        return len(self.factors)

    @property
    def values_count(self) -> Optional[int]:
        """Number of values (for fixed types)."""
        if self.values is None:
            return None
        return len(self.values)

    @property
    def values_default_idx(self) -> Optional[int]:
        """Default value index."""
        if self.values is None:
            return None
        if self.default_idx is None:
            return 0
        return self.default_idx

    @property
    def factors_default_idx(self) -> Optional[int]:
        """Default factor index."""
        if self.factors is None:
            return None
        if self.default_idx is None:
            return 0
        return self.default_idx

    # Methods for C code generation
    def c_str_array(self, values: List) -> Optional[str]:
        """Converts values to a C array string."""
        if not values:
            return None
        
        str_values = []
        for value in values:
            if isinstance(value, str):
                str_values.append(f'"{value}"')
            else:
                str_values.append(str(value))
        return ', '.join(str_values)

    @property
    def c_str_factors(self) -> Optional[str]:
        """C representation of the factors."""
        if self.factors is None:
            return None
        return self.c_str_array(self.factors)

    @property
    def c_str_values(self) -> Optional[str]:
        """C representation of the values."""
        if self.values is None:
            return None
        return self.c_str_array(self.values)

    @property
    def c_str_raw_values(self) -> Optional[str]:
        """C representation of raw_values."""
        if self.raw_values is None:
            return None
        return self.c_str_array(self.raw_values)

    # Data validation
    def validate_numeric_range(self) -> List[str]:
        """Validates the numeric range."""
        errors = []
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                errors.append(f"min ({self.min}) > max ({self.max})")
            if self.default is not None and not (self.min <= self.default <= self.max):
                errors.append(f"default ({self.default}) outside range [{self.min}, {self.max}]")
        return errors

    def validate_fixed_values(self) -> List[str]:
        """Validates fixed values."""
        errors = []
        if self.values is not None and self.default_idx is not None:
            if self.default_idx >= len(self.values):
                errors.append(f"default_idx ({self.default_idx}) out of bounds for values array (size: {len(self.values)})")
        if self.factors is not None and self.default_idx is not None:
            if self.default_idx >= len(self.factors):
                errors.append(f"default_idx ({self.default_idx}) out of bounds for factors array (size: {len(self.factors)})")
        if self.raw_values is not None:
            if self.values is None:
                errors.append("raw_values is set but values is not")
            elif len(self.raw_values) != len(self.values):
                errors.append(f"raw_values length ({len(self.raw_values)}) != values length ({len(self.values)})")
        return errors

    def get_data_summary(self) -> Dict[str, Any]:
        """Node data summary for debugging."""
        return {
            "id": self._original_node.get("id"),
            "type": self._node_type,
            "role": self._node_role,
            "category": self.category_name,
            "c_type": self.c_type,
            "min": self.min,
            "max": self.max,
            "default": self.default,
            "default_idx": self.default_idx,
            "step": self.step,
            "factors_count": self.fixed_count,
            "values_count": self.values_count,
            "has_factors": self.factors is not None,
            "has_values": self.values is not None
        }

    def __repr__(self):
        """String representation for debugging."""
        summary = self.get_data_summary()
        return (f"NodeDataManager({summary['id']}, type={summary['type']}, "
                f"role={summary['role']}, c_type={summary['c_type']})")