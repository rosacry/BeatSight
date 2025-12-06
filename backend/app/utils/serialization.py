"""
Serialization utilities for JSON, datetime, and model conversion.

Provides consistent serialization patterns across the application.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

__all__ = [
    "json_serializer",
    "serialize_value",
    "deserialize_value",
    "to_json",
    "from_json",
    "to_dict",
    "deep_dict",
    "model_to_dict",
    "dict_to_model",
    "camel_to_snake",
    "snake_to_camel",
    "transform_keys",
    "flatten_dict",
    "unflatten_dict",
    "merge_dicts",
    "pick_keys",
    "omit_keys",
    "safe_json_loads",
    "JSONEncoder",
]


T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles common Python types.
    
    Supports:
    - datetime, date, time objects -> ISO format strings
    - timedelta -> total seconds as float
    - Decimal -> string (preserves precision)
    - UUID -> string
    - Enum -> value
    - set, frozenset -> list
    - bytes -> base64 encoded string
    - Path -> string
    - Pydantic models -> dict
    - Objects with to_dict() method
    - Objects with __dict__ attribute
    """
    
    def default(self, obj: Any) -> Any:
        """Convert object to JSON-serializable type."""
        return serialize_value(obj)


def serialize_value(value: Any) -> Any:
    """
    Convert a value to a JSON-serializable type.
    
    Args:
        value: Any Python value
        
    Returns:
        JSON-serializable representation
        
    Examples:
        >>> serialize_value(datetime(2024, 1, 15, 12, 0, 0))
        '2024-01-15T12:00:00'
        >>> serialize_value(Decimal('19.99'))
        '19.99'
        >>> serialize_value(uuid.UUID('12345678-1234-5678-1234-567812345678'))
        '12345678-1234-5678-1234-567812345678'
    """
    import base64
    
    if value is None:
        return None
    
    if isinstance(value, (str, int, float, bool)):
        return value
    
    if isinstance(value, datetime):
        return value.isoformat()
    
    if isinstance(value, date):
        return value.isoformat()
    
    if isinstance(value, time):
        return value.isoformat()
    
    if isinstance(value, timedelta):
        return value.total_seconds()
    
    if isinstance(value, Decimal):
        return str(value)
    
    if isinstance(value, uuid.UUID):
        return str(value)
    
    if isinstance(value, Enum):
        return value.value
    
    if isinstance(value, (set, frozenset)):
        return [serialize_value(v) for v in value]
    
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("utf-8")
    
    if isinstance(value, Path):
        return str(value)
    
    if isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    
    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}
    
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    
    if hasattr(value, "to_dict"):
        return value.to_dict()
    
    if hasattr(value, "__dict__"):
        return serialize_value(value.__dict__)
    
    # Last resort: try str()
    return str(value)


def deserialize_value(
    value: Any,
    target_type: type[T] | None = None,
) -> T | Any:
    """
    Convert a serialized value back to Python type.
    
    Args:
        value: Serialized value
        target_type: Optional target type for conversion
        
    Returns:
        Deserialized Python value
        
    Examples:
        >>> deserialize_value('2024-01-15T12:00:00', datetime)
        datetime(2024, 1, 15, 12, 0, 0)
        >>> deserialize_value('19.99', Decimal)
        Decimal('19.99')
    """
    if value is None or target_type is None:
        return value
    
    if target_type is datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)
    
    if target_type is date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return date.fromisoformat(value)
    
    if target_type is time:
        if isinstance(value, time):
            return value
        return time.fromisoformat(value)
    
    if target_type is timedelta:
        if isinstance(value, timedelta):
            return value
        return timedelta(seconds=float(value))
    
    if target_type is Decimal:
        return Decimal(str(value))
    
    if target_type is uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
    
    if target_type is bytes:
        import base64
        if isinstance(value, bytes):
            return value
        return base64.b64decode(value.encode("utf-8"))
    
    if target_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    
    if target_type in (int, float, str):
        return target_type(value)
    
    return value


def to_json(
    obj: Any,
    *,
    indent: int | None = None,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> str:
    """
    Serialize object to JSON string with custom type handling.
    
    Args:
        obj: Object to serialize
        indent: Indentation level for pretty printing
        ensure_ascii: If True, escape non-ASCII characters
        sort_keys: If True, sort dictionary keys
        
    Returns:
        JSON string
        
    Examples:
        >>> to_json({"name": "test", "created": datetime(2024, 1, 15)})
        '{"name": "test", "created": "2024-01-15T00:00:00"}'
    """
    return json.dumps(
        obj,
        cls=JSONEncoder,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
    )


def from_json(
    json_str: str,
    *,
    strict: bool = True,
) -> Any:
    """
    Parse JSON string to Python object.
    
    Args:
        json_str: JSON string to parse
        strict: If False, allow NaN and Infinity
        
    Returns:
        Parsed Python object
        
    Raises:
        json.JSONDecodeError: If string is not valid JSON
        
    Examples:
        >>> from_json('{"name": "test", "count": 42}')
        {'name': 'test', 'count': 42}
    """
    return json.loads(json_str, strict=strict)


def safe_json_loads(
    json_str: str | bytes | None,
    *,
    default: T = None,
) -> Any | T:
    """
    Safely parse JSON string, returning default on error.
    
    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed object or default value
        
    Examples:
        >>> safe_json_loads('{"valid": true}')
        {'valid': True}
        >>> safe_json_loads('invalid json', default={})
        {}
    """
    if json_str is None:
        return default
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def to_dict(obj: Any) -> dict[str, Any]:
    """
    Convert object to dictionary.
    
    Args:
        obj: Object to convert
        
    Returns:
        Dictionary representation
        
    Examples:
        >>> class Person:
        ...     def __init__(self, name, age):
        ...         self.name = name
        ...         self.age = age
        >>> to_dict(Person("Alice", 30))
        {'name': 'Alice', 'age': 30}
    """
    if isinstance(obj, dict):
        return obj
    
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    
    raise TypeError(f"Cannot convert {type(obj).__name__} to dict")


def deep_dict(obj: Any) -> dict[str, Any] | list | Any:
    """
    Recursively convert object to dictionary with all nested values serialized.
    
    Args:
        obj: Object to convert
        
    Returns:
        Deep dictionary representation with all values JSON-serializable
        
    Examples:
        >>> deep_dict({"nested": {"date": datetime(2024, 1, 15)}})
        {'nested': {'date': '2024-01-15T00:00:00'}}
    """
    if obj is None:
        return None
    
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    if isinstance(obj, dict):
        return {str(k): deep_dict(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [deep_dict(v) for v in obj]
    
    # Try to convert to dict first
    if isinstance(obj, BaseModel):
        return deep_dict(obj.model_dump())
    
    if hasattr(obj, "to_dict"):
        return deep_dict(obj.to_dict())
    
    if hasattr(obj, "__dict__"):
        return deep_dict(obj.__dict__)
    
    # Fallback to serialization
    return serialize_value(obj)


def model_to_dict(
    model: BaseModel,
    *,
    exclude_unset: bool = False,
    exclude_none: bool = False,
    by_alias: bool = False,
) -> dict[str, Any]:
    """
    Convert Pydantic model to dictionary with options.
    
    Args:
        model: Pydantic model instance
        exclude_unset: Exclude fields that were not explicitly set
        exclude_none: Exclude fields with None value
        by_alias: Use field aliases instead of names
        
    Returns:
        Dictionary representation
        
    Examples:
        >>> from pydantic import BaseModel, Field
        >>> class User(BaseModel):
        ...     user_name: str = Field(alias='userName')
        ...     age: int | None = None
        >>> model_to_dict(User(userName='alice'), exclude_none=True, by_alias=True)
        {'userName': 'alice'}
    """
    return model.model_dump(
        exclude_unset=exclude_unset,
        exclude_none=exclude_none,
        by_alias=by_alias,
    )


def dict_to_model(
    data: dict[str, Any],
    model_class: type[ModelT],
    *,
    strict: bool = False,
) -> ModelT:
    """
    Convert dictionary to Pydantic model instance.
    
    Args:
        data: Dictionary data
        model_class: Target Pydantic model class
        strict: If True, use strict validation mode
        
    Returns:
        Model instance
        
    Raises:
        ValidationError: If data doesn't match model schema
        
    Examples:
        >>> from pydantic import BaseModel
        >>> class User(BaseModel):
        ...     name: str
        ...     age: int
        >>> dict_to_model({'name': 'alice', 'age': 30}, User)
        User(name='alice', age=30)
    """
    if strict:
        return model_class.model_validate(data, strict=True)
    return model_class.model_validate(data)


def camel_to_snake(name: str) -> str:
    """
    Convert camelCase or PascalCase to snake_case.
    
    Args:
        name: String in camelCase or PascalCase
        
    Returns:
        String in snake_case
        
    Examples:
        >>> camel_to_snake('camelCase')
        'camel_case'
        >>> camel_to_snake('PascalCase')
        'pascal_case'
        >>> camel_to_snake('getHTTPResponse')
        'get_http_response'
    """
    import re
    
    # Handle acronyms (HTTP -> http)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # Handle normal camelCase
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


def snake_to_camel(name: str, *, pascal: bool = False) -> str:
    """
    Convert snake_case to camelCase or PascalCase.
    
    Args:
        name: String in snake_case
        pascal: If True, return PascalCase instead of camelCase
        
    Returns:
        String in camelCase or PascalCase
        
    Examples:
        >>> snake_to_camel('snake_case')
        'snakeCase'
        >>> snake_to_camel('snake_case', pascal=True)
        'SnakeCase'
    """
    components = name.split("_")
    if pascal:
        return "".join(c.title() for c in components)
    return components[0] + "".join(c.title() for c in components[1:])


def transform_keys(
    data: dict[str, Any],
    transform: Callable[[str], str],
    *,
    deep: bool = True,
) -> dict[str, Any]:
    """
    Transform all keys in a dictionary using a function.
    
    Args:
        data: Dictionary to transform
        transform: Function to apply to each key
        deep: If True, recursively transform nested dicts
        
    Returns:
        New dictionary with transformed keys
        
    Examples:
        >>> transform_keys({'firstName': 'Alice'}, camel_to_snake)
        {'first_name': 'Alice'}
    """
    result = {}
    for key, value in data.items():
        new_key = transform(key)
        if deep and isinstance(value, dict):
            value = transform_keys(value, transform, deep=True)
        elif deep and isinstance(value, list):
            value = [
                transform_keys(v, transform, deep=True) if isinstance(v, dict) else v
                for v in value
            ]
        result[new_key] = value
    return result


def flatten_dict(
    data: dict[str, Any],
    *,
    separator: str = ".",
    parent_key: str = "",
) -> dict[str, Any]:
    """
    Flatten a nested dictionary into a single-level dictionary.
    
    Args:
        data: Nested dictionary to flatten
        separator: Separator to use between key parts
        parent_key: Prefix for all keys (internal use)
        
    Returns:
        Flattened dictionary
        
    Examples:
        >>> flatten_dict({'user': {'name': 'Alice', 'address': {'city': 'NYC'}}})
        {'user.name': 'Alice', 'user.address.city': 'NYC'}
    """
    items: list[tuple[str, Any]] = []
    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(
                flatten_dict(value, separator=separator, parent_key=new_key).items()
            )
        else:
            items.append((new_key, value))
    return dict(items)


def unflatten_dict(
    data: dict[str, Any],
    *,
    separator: str = ".",
) -> dict[str, Any]:
    """
    Unflatten a flat dictionary into a nested structure.
    
    Args:
        data: Flat dictionary with dot-notation keys
        separator: Separator used between key parts
        
    Returns:
        Nested dictionary
        
    Examples:
        >>> unflatten_dict({'user.name': 'Alice', 'user.address.city': 'NYC'})
        {'user': {'name': 'Alice', 'address': {'city': 'NYC'}}}
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        parts = key.split(separator)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def merge_dicts(
    *dicts: dict[str, Any],
    deep: bool = True,
) -> dict[str, Any]:
    """
    Merge multiple dictionaries, with later values overwriting earlier ones.
    
    Args:
        *dicts: Dictionaries to merge
        deep: If True, recursively merge nested dicts
        
    Returns:
        Merged dictionary
        
    Examples:
        >>> merge_dicts({'a': 1, 'b': {'c': 2}}, {'b': {'d': 3}})
        {'a': 1, 'b': {'c': 2, 'd': 3}}
    """
    result: dict[str, Any] = {}
    for d in dicts:
        for key, value in d.items():
            if (
                deep
                and key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value
    return result


def pick_keys(
    data: dict[str, Any],
    keys: list[str] | set[str] | tuple[str, ...],
) -> dict[str, Any]:
    """
    Create a dictionary with only the specified keys.
    
    Args:
        data: Source dictionary
        keys: Keys to include
        
    Returns:
        Dictionary with only specified keys
        
    Examples:
        >>> pick_keys({'a': 1, 'b': 2, 'c': 3}, ['a', 'c'])
        {'a': 1, 'c': 3}
    """
    key_set = set(keys)
    return {k: v for k, v in data.items() if k in key_set}


def omit_keys(
    data: dict[str, Any],
    keys: list[str] | set[str] | tuple[str, ...],
) -> dict[str, Any]:
    """
    Create a dictionary without the specified keys.
    
    Args:
        data: Source dictionary
        keys: Keys to exclude
        
    Returns:
        Dictionary without specified keys
        
    Examples:
        >>> omit_keys({'a': 1, 'b': 2, 'c': 3}, ['b'])
        {'a': 1, 'c': 3}
    """
    key_set = set(keys)
    return {k: v for k, v in data.items() if k not in key_set}


def json_serializer(obj: Any) -> Any:
    """
    Default JSON serializer function for use with json.dumps.
    
    This function is designed to be passed to json.dumps(default=...)
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-serializable representation
        
    Raises:
        TypeError: If object cannot be serialized
        
    Examples:
        >>> import json
        >>> json.dumps({'date': datetime(2024, 1, 15)}, default=json_serializer)
        '{"date": "2024-01-15T00:00:00"}'
    """
    result = serialize_value(obj)
    # If serialize_value returned the same object (via str()), check if it's valid
    if result is obj and not isinstance(obj, (str, int, float, bool, type(None))):
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    return result
