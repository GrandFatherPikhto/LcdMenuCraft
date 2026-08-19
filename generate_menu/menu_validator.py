from jsonschema import Draft7Validator, ValidationError
from typing import Dict, List, Optional, Any

from .i18n import _
from .menu_config import MenuConfig

class ParserError(Exception):
    """Raised when menu validation fails."""
    def __init__(self, errors: List[str]):
        super().__init__("Menu validation failed")
        self.errors = errors

class MenuValidator:
    def __init__(self, config: MenuConfig, raise_exception = False):
        self._config = config
        self._raise_exception = raise_exception
        self._validator = Draft7Validator(self._config.menu_schema)
        self._ids = []
        self._errors = {}

    def validate(self, menu_data: Dict = None) -> Dict[str, List[str]]:
        """
        Full validation of the menu tree.

        Returns:
            Dict[str, List[str]]: errors grouped by element ID.
        """
        # Reset per-call state so that repeated validate() calls are idempotent.
        self._ids = []

        menu = self._config.menu_data if menu_data is None else menu_data

        errors = {}

        # JSON Schema validation
        try:
            self._validator.validate(menu)
        except ValidationError as e:
            errors["schema"] = [_("Schema validation failed: {message}").format(message=e.message)]
            return errors
        
        # Recursive validation of the elements
        self._validate_tree(menu.get("menu", []), [], errors)
        
        return errors

    def _validate_tree(self, items: List[Dict], path: List[str], errors: Dict[str, List[str]]):
        """Recursively validates the menu tree."""
        for item in items:
            current_path = path + [item['id']]
            item_errors = []
            
            # Validate the element
            item_errors.extend(self._validate_item(item))
            
            # Recursively validate children
            if 'items' in item:
                self._validate_tree(item['items'], current_path, errors)
            
            if item_errors:
                errors['->'.join(current_path)] = item_errors

    def _validate_item(self, item: Dict) -> List[str]:
        """Validates a single menu item."""
        errors = []

        if item.get("id") not in self._ids:
            self._ids.append(item.get("id"))
        else:
            errors.append(_("Id {id} not unique").format(id=item.get('id')))
        
        # Check: a branch must not have 'type'
        if 'items' in item and 'type' in item:
            errors.append(_("Branch element cannot have 'type'"))
        
        # Check: a leaf must have 'type'
        if 'items' not in item and 'type' not in item:
            errors.append(_("Leaf element must have 'type'"))
        
        # Validate the default value
        if 'default' in item:
            errors.extend(self._validate_default_value(item))
        
        # Validate the min/max range (independent of 'default')
        if 'min' in item or 'max' in item:
            errors.extend(self._validate_min_max(item))
        
        # Validate factors and values
        if 'factors' in item:
            errors.extend(self._validate_factors(item))
        if 'values' in item:
            errors.extend(self._validate_values(item))
        if 'raw_values' in item:
            errors.extend(self._validate_raw_values(item))

        return errors

    def _validate_default_value(self, item: Dict) -> List[str]:
        """Validates the default value."""
        errors = []
        
        # Check for numeric types
        if 'min' in item and 'max' in item:
            if not (item['min'] <= item['default'] <= item['max']):
                errors.append(_("default value {default} out of range [{min}, {max}]").format(
                    default=item['default'], min=item['min'], max=item['max']))
        
        # Check for fixed types
        if 'values' in item and 'default' in item:
            if item['default'] not in item['values']:
                errors.append(_("default value {default} not in allowed values").format(
                    default=item['default']))
        
        return errors

    def _validate_min_max(self, item: Dict) -> List[str]:
        """Validates that min is not greater than max (independent of default)."""
        errors = []

        if 'min' in item and 'max' in item:
            if item['min'] > item['max']:
                errors.append(_("min ({min}) > max ({max})").format(
                    min=item['min'], max=item['max']))

        return errors

    def _validate_factors(self, item: Dict) -> List[str]:
        """Validates factors."""
        errors = []
        
        if 'default_idx' in item and item['default_idx'] >= len(item['factors']):
            errors.append(_("default_idx {idx} out of bounds for factors array").format(
                idx=item['default_idx']))
        
        return errors
    
    def _validate_values(self, item: Dict) -> List[str]:
        """Validates values."""
        errors = []
        
        if 'default_idx' in item and item['default_idx'] >= len(item['values']):
            errors.append(_("default_idx {idx} out of bounds for values array").format(
                idx=item['default_idx']))

        return errors

    def _validate_raw_values(self, item: Dict) -> List[str]:
        """Validates raw_values."""
        errors = []

        if 'values' not in item:
            errors.append(_("raw_values is set but values is not"))
        elif len(item['raw_values']) != len(item['values']):
            errors.append(_("raw_values length ({raw_len}) != values length ({values_len})").format(
                raw_len=len(item['raw_values']), values_len=len(item['values'])))

        return errors

