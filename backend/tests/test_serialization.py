"""Tests for serialization utilities."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from app.utils.serialization import (
    JSONEncoder,
    camel_to_snake,
    deep_dict,
    deserialize_value,
    dict_to_model,
    flatten_dict,
    from_json,
    json_serializer,
    merge_dicts,
    model_to_dict,
    omit_keys,
    pick_keys,
    safe_json_loads,
    serialize_value,
    snake_to_camel,
    to_dict,
    to_json,
    transform_keys,
    unflatten_dict,
)


# Test enums and models
class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Priority(Enum):
    LOW = 1
    HIGH = 2


class Address(BaseModel):
    city: str
    country: str = "USA"


class User(BaseModel):
    name: str
    age: int
    email: str | None = None


class UserWithAlias(BaseModel):
    user_name: str = Field(alias="userName")
    user_age: int = Field(alias="userAge")


class TestSerializeValue:
    """Tests for serialize_value function."""

    def test_serialize_none(self):
        """Test serializing None."""
        assert serialize_value(None) is None

    def test_serialize_primitives(self):
        """Test serializing primitive types."""
        assert serialize_value("hello") == "hello"
        assert serialize_value(42) == 42
        assert serialize_value(3.14) == 3.14
        assert serialize_value(True) is True
        assert serialize_value(False) is False

    def test_serialize_datetime(self):
        """Test serializing datetime."""
        dt = datetime(2024, 1, 15, 12, 30, 45)
        assert serialize_value(dt) == "2024-01-15T12:30:45"

    def test_serialize_datetime_with_timezone(self):
        """Test serializing datetime with timezone."""
        from datetime import timezone

        dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        assert serialize_value(dt) == "2024-01-15T12:30:45+00:00"

    def test_serialize_date(self):
        """Test serializing date."""
        d = date(2024, 1, 15)
        assert serialize_value(d) == "2024-01-15"

    def test_serialize_time(self):
        """Test serializing time."""
        t = time(12, 30, 45)
        assert serialize_value(t) == "12:30:45"

    def test_serialize_timedelta(self):
        """Test serializing timedelta."""
        td = timedelta(hours=2, minutes=30)
        assert serialize_value(td) == 9000.0  # 2.5 hours in seconds

    def test_serialize_decimal(self):
        """Test serializing Decimal."""
        assert serialize_value(Decimal("19.99")) == "19.99"
        assert serialize_value(Decimal("0.001")) == "0.001"

    def test_serialize_uuid(self):
        """Test serializing UUID."""
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert serialize_value(u) == "12345678-1234-5678-1234-567812345678"

    def test_serialize_enum(self):
        """Test serializing enum."""
        assert serialize_value(Status.ACTIVE) == "active"
        assert serialize_value(Priority.HIGH) == 2

    def test_serialize_set(self):
        """Test serializing set."""
        result = serialize_value({1, 2, 3})
        assert set(result) == {1, 2, 3}

    def test_serialize_frozenset(self):
        """Test serializing frozenset."""
        result = serialize_value(frozenset([1, 2, 3]))
        assert set(result) == {1, 2, 3}

    def test_serialize_bytes(self):
        """Test serializing bytes."""
        import base64

        data = b"hello world"
        result = serialize_value(data)
        assert base64.b64decode(result) == data

    def test_serialize_path(self):
        """Test serializing Path."""
        p = Path("/home/user/file.txt")
        # Path uses OS-specific separator
        assert serialize_value(p) == str(p)

    def test_serialize_list(self):
        """Test serializing list with mixed types."""
        data = [1, "two", datetime(2024, 1, 15)]
        result = serialize_value(data)
        assert result == [1, "two", "2024-01-15T00:00:00"]

    def test_serialize_tuple(self):
        """Test serializing tuple."""
        data = (1, 2, 3)
        result = serialize_value(data)
        assert result == [1, 2, 3]

    def test_serialize_dict(self):
        """Test serializing dict."""
        data = {"name": "test", "date": date(2024, 1, 15)}
        result = serialize_value(data)
        assert result == {"name": "test", "date": "2024-01-15"}

    def test_serialize_pydantic_model(self):
        """Test serializing Pydantic model."""
        user = User(name="Alice", age=30)
        result = serialize_value(user)
        assert result == {"name": "Alice", "age": 30, "email": None}

    def test_serialize_object_with_to_dict(self):
        """Test serializing object with to_dict method."""

        class Custom:
            def to_dict(self):
                return {"type": "custom"}

        result = serialize_value(Custom())
        assert result == {"type": "custom"}

    def test_serialize_object_with_dict(self):
        """Test serializing object with __dict__."""

        class Simple:
            def __init__(self):
                self.x = 1
                self.y = 2

        result = serialize_value(Simple())
        assert result == {"x": 1, "y": 2}


class TestDeserializeValue:
    """Tests for deserialize_value function."""

    def test_deserialize_none(self):
        """Test deserializing None."""
        assert deserialize_value(None) is None

    def test_deserialize_no_target_type(self):
        """Test deserializing without target type."""
        assert deserialize_value("hello") == "hello"
        assert deserialize_value(42) == 42

    def test_deserialize_datetime(self):
        """Test deserializing to datetime."""
        result = deserialize_value("2024-01-15T12:30:45", datetime)
        assert result == datetime(2024, 1, 15, 12, 30, 45)

    def test_deserialize_datetime_already_datetime(self):
        """Test deserializing datetime that's already datetime."""
        dt = datetime(2024, 1, 15)
        result = deserialize_value(dt, datetime)
        assert result == dt

    def test_deserialize_date(self):
        """Test deserializing to date."""
        result = deserialize_value("2024-01-15", date)
        assert result == date(2024, 1, 15)

    def test_deserialize_date_from_datetime(self):
        """Test deserializing date from datetime."""
        dt = datetime(2024, 1, 15, 12, 30)
        result = deserialize_value(dt, date)
        assert result == date(2024, 1, 15)

    def test_deserialize_time(self):
        """Test deserializing to time."""
        result = deserialize_value("12:30:45", time)
        assert result == time(12, 30, 45)

    def test_deserialize_timedelta(self):
        """Test deserializing to timedelta."""
        result = deserialize_value(9000, timedelta)
        assert result == timedelta(hours=2, minutes=30)

    def test_deserialize_decimal(self):
        """Test deserializing to Decimal."""
        result = deserialize_value("19.99", Decimal)
        assert result == Decimal("19.99")

    def test_deserialize_uuid(self):
        """Test deserializing to UUID."""
        result = deserialize_value("12345678-1234-5678-1234-567812345678", uuid.UUID)
        assert result == uuid.UUID("12345678-1234-5678-1234-567812345678")

    def test_deserialize_bytes(self):
        """Test deserializing to bytes."""
        import base64

        encoded = base64.b64encode(b"hello").decode()
        result = deserialize_value(encoded, bytes)
        assert result == b"hello"

    def test_deserialize_bool_from_string(self):
        """Test deserializing to bool from string."""
        assert deserialize_value("true", bool) is True
        assert deserialize_value("True", bool) is True
        assert deserialize_value("1", bool) is True
        assert deserialize_value("yes", bool) is True
        assert deserialize_value("on", bool) is True
        assert deserialize_value("false", bool) is False
        assert deserialize_value("no", bool) is False

    def test_deserialize_primitives(self):
        """Test deserializing to primitive types."""
        assert deserialize_value("42", int) == 42
        assert deserialize_value("3.14", float) == 3.14
        assert deserialize_value(42, str) == "42"


class TestToJson:
    """Tests for to_json function."""

    def test_simple_dict(self):
        """Test converting simple dict to JSON."""
        data = {"name": "test", "count": 42}
        result = to_json(data)
        assert json.loads(result) == data

    def test_with_datetime(self):
        """Test converting dict with datetime."""
        data = {"created": datetime(2024, 1, 15, 12, 0, 0)}
        result = to_json(data)
        parsed = json.loads(result)
        assert parsed == {"created": "2024-01-15T12:00:00"}

    def test_with_indent(self):
        """Test pretty printing JSON."""
        data = {"a": 1, "b": 2}
        result = to_json(data, indent=2)
        assert "\n" in result

    def test_with_sort_keys(self):
        """Test sorting keys."""
        data = {"z": 1, "a": 2}
        result = to_json(data, sort_keys=True)
        assert result.index('"a"') < result.index('"z"')

    def test_with_nested_types(self):
        """Test with nested complex types."""
        data = {
            "user": User(name="Alice", age=30),
            "date": date(2024, 1, 15),
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
        }
        result = to_json(data)
        parsed = json.loads(result)
        assert parsed["user"]["name"] == "Alice"
        assert parsed["date"] == "2024-01-15"


class TestFromJson:
    """Tests for from_json function."""

    def test_simple_json(self):
        """Test parsing simple JSON."""
        result = from_json('{"name": "test", "count": 42}')
        assert result == {"name": "test", "count": 42}

    def test_json_array(self):
        """Test parsing JSON array."""
        result = from_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        with pytest.raises(json.JSONDecodeError):
            from_json("invalid json")


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        result = safe_json_loads('{"valid": true}')
        assert result == {"valid": True}

    def test_invalid_json_returns_default(self):
        """Test invalid JSON returns default."""
        result = safe_json_loads("invalid", default={})
        assert result == {}

    def test_none_input(self):
        """Test None input returns default."""
        result = safe_json_loads(None, default=[])
        assert result == []

    def test_bytes_input(self):
        """Test bytes input."""
        result = safe_json_loads(b'{"key": "value"}')
        assert result == {"key": "value"}


class TestToDict:
    """Tests for to_dict function."""

    def test_dict_passthrough(self):
        """Test dict passes through."""
        data = {"a": 1}
        assert to_dict(data) == data

    def test_pydantic_model(self):
        """Test Pydantic model conversion."""
        user = User(name="Alice", age=30)
        result = to_dict(user)
        assert result == {"name": "Alice", "age": 30, "email": None}

    def test_object_with_to_dict(self):
        """Test object with to_dict method."""

        class Custom:
            def to_dict(self):
                return {"custom": True}

        result = to_dict(Custom())
        assert result == {"custom": True}

    def test_object_with_dict(self):
        """Test object with __dict__."""

        class Simple:
            def __init__(self):
                self.value = 42

        result = to_dict(Simple())
        assert result == {"value": 42}

    def test_unsupported_type(self):
        """Test unsupported type raises error."""
        with pytest.raises(TypeError):
            to_dict("not a dict")


class TestDeepDict:
    """Tests for deep_dict function."""

    def test_nested_dict(self):
        """Test nested dict conversion."""
        data = {"outer": {"inner": {"date": datetime(2024, 1, 15)}}}
        result = deep_dict(data)
        assert result == {"outer": {"inner": {"date": "2024-01-15T00:00:00"}}}

    def test_list_of_dicts(self):
        """Test list of dicts."""
        data = [{"date": date(2024, 1, 15)}, {"date": date(2024, 1, 16)}]
        result = deep_dict(data)
        assert result == [{"date": "2024-01-15"}, {"date": "2024-01-16"}]

    def test_pydantic_model(self):
        """Test Pydantic model deep conversion."""
        user = User(name="Alice", age=30)
        result = deep_dict(user)
        assert result == {"name": "Alice", "age": 30, "email": None}

    def test_primitives(self):
        """Test primitives pass through."""
        assert deep_dict(None) is None
        assert deep_dict("hello") == "hello"
        assert deep_dict(42) == 42
        assert deep_dict(True) is True


class TestModelToDict:
    """Tests for model_to_dict function."""

    def test_basic_conversion(self):
        """Test basic model conversion."""
        user = User(name="Alice", age=30)
        result = model_to_dict(user)
        assert result == {"name": "Alice", "age": 30, "email": None}

    def test_exclude_none(self):
        """Test excluding None values."""
        user = User(name="Alice", age=30)
        result = model_to_dict(user, exclude_none=True)
        assert result == {"name": "Alice", "age": 30}

    def test_by_alias(self):
        """Test using aliases."""
        user = UserWithAlias(userName="Alice", userAge=30)
        result = model_to_dict(user, by_alias=True)
        assert result == {"userName": "Alice", "userAge": 30}


class TestDictToModel:
    """Tests for dict_to_model function."""

    def test_basic_conversion(self):
        """Test basic dict to model."""
        data = {"name": "Alice", "age": 30}
        result = dict_to_model(data, User)
        assert result.name == "Alice"
        assert result.age == 30

    def test_with_alias(self):
        """Test dict with alias."""
        data = {"userName": "Alice", "userAge": 30}
        result = dict_to_model(data, UserWithAlias)
        assert result.user_name == "Alice"
        assert result.user_age == 30

    def test_strict_mode(self):
        """Test strict validation mode."""
        data = {"name": "Alice", "age": "30"}  # age is string
        # In strict mode, this should fail for non-coercible types
        # But "30" can be coerced to int, so it should work
        result = dict_to_model(data, User, strict=False)
        assert result.age == 30


class TestCamelToSnake:
    """Tests for camel_to_snake function."""

    def test_simple_camel(self):
        """Test simple camelCase."""
        assert camel_to_snake("camelCase") == "camel_case"

    def test_pascal_case(self):
        """Test PascalCase."""
        assert camel_to_snake("PascalCase") == "pascal_case"

    def test_acronym(self):
        """Test with acronyms."""
        assert camel_to_snake("getHTTPResponse") == "get_http_response"
        assert camel_to_snake("XMLParser") == "xml_parser"

    def test_single_word(self):
        """Test single word."""
        assert camel_to_snake("word") == "word"

    def test_already_snake(self):
        """Test already snake_case."""
        assert camel_to_snake("already_snake") == "already_snake"


class TestSnakeToCamel:
    """Tests for snake_to_camel function."""

    def test_simple_snake(self):
        """Test simple snake_case."""
        assert snake_to_camel("snake_case") == "snakeCase"

    def test_pascal_mode(self):
        """Test PascalCase mode."""
        assert snake_to_camel("snake_case", pascal=True) == "SnakeCase"

    def test_single_word(self):
        """Test single word."""
        assert snake_to_camel("word") == "word"

    def test_multiple_underscores(self):
        """Test multiple underscores."""
        assert snake_to_camel("one_two_three") == "oneTwoThree"


class TestTransformKeys:
    """Tests for transform_keys function."""

    def test_camel_to_snake(self):
        """Test transforming keys to snake_case."""
        data = {"firstName": "Alice", "lastName": "Smith"}
        result = transform_keys(data, camel_to_snake)
        assert result == {"first_name": "Alice", "last_name": "Smith"}

    def test_snake_to_camel(self):
        """Test transforming keys to camelCase."""
        data = {"first_name": "Alice", "last_name": "Smith"}
        result = transform_keys(data, snake_to_camel)
        assert result == {"firstName": "Alice", "lastName": "Smith"}

    def test_deep_transform(self):
        """Test deep transformation."""
        data = {"userName": {"firstName": "Alice"}}
        result = transform_keys(data, camel_to_snake, deep=True)
        assert result == {"user_name": {"first_name": "Alice"}}

    def test_shallow_transform(self):
        """Test shallow transformation."""
        data = {"userName": {"firstName": "Alice"}}
        result = transform_keys(data, camel_to_snake, deep=False)
        assert result == {"user_name": {"firstName": "Alice"}}

    def test_list_of_dicts(self):
        """Test transforming list of dicts."""
        data = {"users": [{"firstName": "Alice"}, {"firstName": "Bob"}]}
        result = transform_keys(data, camel_to_snake, deep=True)
        assert result == {"users": [{"first_name": "Alice"}, {"first_name": "Bob"}]}


class TestFlattenDict:
    """Tests for flatten_dict function."""

    def test_simple_nested(self):
        """Test flattening simple nested dict."""
        data = {"user": {"name": "Alice"}}
        result = flatten_dict(data)
        assert result == {"user.name": "Alice"}

    def test_deep_nested(self):
        """Test flattening deeply nested dict."""
        data = {"a": {"b": {"c": {"d": 1}}}}
        result = flatten_dict(data)
        assert result == {"a.b.c.d": 1}

    def test_custom_separator(self):
        """Test with custom separator."""
        data = {"user": {"name": "Alice"}}
        result = flatten_dict(data, separator="_")
        assert result == {"user_name": "Alice"}

    def test_mixed_depth(self):
        """Test with mixed depth values."""
        data = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        result = flatten_dict(data)
        assert result == {"a": 1, "b.c": 2, "b.d.e": 3}

    def test_flat_dict(self):
        """Test already flat dict."""
        data = {"a": 1, "b": 2}
        result = flatten_dict(data)
        assert result == {"a": 1, "b": 2}


class TestUnflattenDict:
    """Tests for unflatten_dict function."""

    def test_simple_unflatten(self):
        """Test unflattening simple dict."""
        data = {"user.name": "Alice"}
        result = unflatten_dict(data)
        assert result == {"user": {"name": "Alice"}}

    def test_deep_unflatten(self):
        """Test unflattening deeply nested keys."""
        data = {"a.b.c.d": 1}
        result = unflatten_dict(data)
        assert result == {"a": {"b": {"c": {"d": 1}}}}

    def test_custom_separator(self):
        """Test with custom separator."""
        data = {"user_name": "Alice"}
        result = unflatten_dict(data, separator="_")
        assert result == {"user": {"name": "Alice"}}

    def test_mixed_depth(self):
        """Test with mixed depth."""
        data = {"a": 1, "b.c": 2, "b.d.e": 3}
        result = unflatten_dict(data)
        assert result == {"a": 1, "b": {"c": 2, "d": {"e": 3}}}

    def test_roundtrip(self):
        """Test flatten/unflatten roundtrip."""
        original = {"user": {"name": "Alice", "address": {"city": "NYC"}}}
        flattened = flatten_dict(original)
        unflattened = unflatten_dict(flattened)
        assert unflattened == original


class TestMergeDicts:
    """Tests for merge_dicts function."""

    def test_simple_merge(self):
        """Test simple merge."""
        result = merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override_value(self):
        """Test later values override."""
        result = merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_deep_merge(self):
        """Test deep merge."""
        result = merge_dicts(
            {"a": 1, "b": {"c": 2}},
            {"b": {"d": 3}},
        )
        assert result == {"a": 1, "b": {"c": 2, "d": 3}}

    def test_shallow_merge(self):
        """Test shallow merge (no deep merging)."""
        result = merge_dicts(
            {"a": 1, "b": {"c": 2}},
            {"b": {"d": 3}},
            deep=False,
        )
        assert result == {"a": 1, "b": {"d": 3}}

    def test_multiple_dicts(self):
        """Test merging multiple dicts."""
        result = merge_dicts({"a": 1}, {"b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_empty_dict(self):
        """Test merging with empty dict."""
        result = merge_dicts({"a": 1}, {})
        assert result == {"a": 1}


class TestPickKeys:
    """Tests for pick_keys function."""

    def test_pick_existing_keys(self):
        """Test picking existing keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = pick_keys(data, ["a", "c"])
        assert result == {"a": 1, "c": 3}

    def test_pick_with_missing_keys(self):
        """Test picking with some missing keys."""
        data = {"a": 1, "b": 2}
        result = pick_keys(data, ["a", "x"])
        assert result == {"a": 1}

    def test_pick_with_set(self):
        """Test picking with set of keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = pick_keys(data, {"a", "c"})
        assert result == {"a": 1, "c": 3}

    def test_pick_empty(self):
        """Test picking no keys."""
        data = {"a": 1, "b": 2}
        result = pick_keys(data, [])
        assert result == {}


class TestOmitKeys:
    """Tests for omit_keys function."""

    def test_omit_existing_keys(self):
        """Test omitting existing keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = omit_keys(data, ["b"])
        assert result == {"a": 1, "c": 3}

    def test_omit_with_missing_keys(self):
        """Test omitting with missing keys."""
        data = {"a": 1, "b": 2}
        result = omit_keys(data, ["x", "y"])
        assert result == {"a": 1, "b": 2}

    def test_omit_with_set(self):
        """Test omitting with set of keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = omit_keys(data, {"a", "b"})
        assert result == {"c": 3}

    def test_omit_all(self):
        """Test omitting all keys."""
        data = {"a": 1, "b": 2}
        result = omit_keys(data, ["a", "b"])
        assert result == {}


class TestJSONEncoder:
    """Tests for JSONEncoder class."""

    def test_encode_datetime(self):
        """Test encoding datetime."""
        result = json.dumps(
            {"dt": datetime(2024, 1, 15)},
            cls=JSONEncoder,
        )
        assert json.loads(result) == {"dt": "2024-01-15T00:00:00"}

    def test_encode_complex_types(self):
        """Test encoding complex types."""
        data = {
            "decimal": Decimal("19.99"),
            "uuid": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "status": Status.ACTIVE,
        }
        result = json.dumps(data, cls=JSONEncoder)
        parsed = json.loads(result)
        assert parsed["decimal"] == "19.99"
        assert parsed["uuid"] == "12345678-1234-5678-1234-567812345678"
        assert parsed["status"] == "active"


class TestJsonSerializer:
    """Tests for json_serializer function."""

    def test_with_json_dumps(self):
        """Test using json_serializer with json.dumps."""
        data = {"date": datetime(2024, 1, 15)}
        result = json.dumps(data, default=json_serializer)
        assert json.loads(result) == {"date": "2024-01-15T00:00:00"}

    def test_unsupported_type(self):
        """Test unsupported type behavior."""

        class Custom:
            pass

        # Objects with __dict__ get serialized
        result = json_serializer(Custom())
        assert result == {}
