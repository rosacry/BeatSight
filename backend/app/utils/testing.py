"""
Testing utilities for writing cleaner, more expressive tests.

Provides helpers for fixtures, assertions, and test data generation.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import string
import tempfile
import uuid
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

__all__ = [
    # Test data generators
    "fake_uuid",
    "fake_email",
    "fake_username",
    "fake_password",
    "fake_phone",
    "fake_datetime",
    "fake_future_datetime",
    "fake_past_datetime",
    "fake_text",
    "fake_sentence",
    "fake_word",
    "fake_int",
    "fake_float",
    "fake_bool",
    "fake_choice",
    "fake_sample",
    # Assertions
    "assert_raises_with_message",
    "assert_dict_contains",
    "assert_list_contains_all",
    "assert_list_contains_any",
    "assert_datetime_close",
    "assert_almost_equal",
    # Fixtures
    "TempDirectory",
    "TempFile",
    "MockEnv",
    "MockTime",
    "CaptureOutput",
    # Async helpers
    "async_return",
    "async_raise",
    "run_async",
    # Test data builder
    "DataBuilder",
]

T = TypeVar("T")


# =============================================================================
# Test Data Generators
# =============================================================================

def fake_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def fake_email(domain: str = "example.com") -> str:
    """
    Generate a random email address.
    
    Args:
        domain: Domain for the email
        
    Returns:
        Random email address
    """
    username = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"{username}@{domain}"


def fake_username(length: int = 8) -> str:
    """
    Generate a random username.
    
    Args:
        length: Length of username
        
    Returns:
        Random username
    """
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def fake_password(length: int = 16) -> str:
    """
    Generate a random password with mixed characters.
    
    Args:
        length: Length of password
        
    Returns:
        Random password
    """
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(random.choices(chars, k=length))


def fake_phone() -> str:
    """Generate a random phone number."""
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"


def fake_datetime(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    tz_aware: bool = True,
) -> datetime:
    """
    Generate a random datetime.
    
    Args:
        start: Minimum datetime (default: 1 year ago)
        end: Maximum datetime (default: now)
        tz_aware: Whether to return timezone-aware datetime
        
    Returns:
        Random datetime
    """
    now = datetime.now(timezone.utc) if tz_aware else datetime.now()
    
    if start is None:
        start = now - timedelta(days=365)
    if end is None:
        end = now
    
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    
    return start + timedelta(seconds=random_seconds)


def fake_future_datetime(
    *,
    max_days: int = 365,
    tz_aware: bool = True,
) -> datetime:
    """
    Generate a random datetime in the future.
    
    Args:
        max_days: Maximum days in the future
        tz_aware: Whether to return timezone-aware datetime
        
    Returns:
        Random future datetime
    """
    now = datetime.now(timezone.utc) if tz_aware else datetime.now()
    return fake_datetime(start=now, end=now + timedelta(days=max_days), tz_aware=tz_aware)


def fake_past_datetime(
    *,
    max_days: int = 365,
    tz_aware: bool = True,
) -> datetime:
    """
    Generate a random datetime in the past.
    
    Args:
        max_days: Maximum days in the past
        tz_aware: Whether to return timezone-aware datetime
        
    Returns:
        Random past datetime
    """
    now = datetime.now(timezone.utc) if tz_aware else datetime.now()
    return fake_datetime(start=now - timedelta(days=max_days), end=now, tz_aware=tz_aware)


def fake_text(length: int = 100) -> str:
    """
    Generate random text.
    
    Args:
        length: Approximate length of text
        
    Returns:
        Random text
    """
    words = [fake_word() for _ in range(length // 5)]
    return " ".join(words)[:length]


def fake_sentence(word_count: int = 10) -> str:
    """
    Generate a random sentence.
    
    Args:
        word_count: Number of words
        
    Returns:
        Random sentence
    """
    words = [fake_word() for _ in range(word_count)]
    sentence = " ".join(words)
    return sentence.capitalize() + "."


def fake_word(length: int | None = None) -> str:
    """
    Generate a random word.
    
    Args:
        length: Length of word (random 3-10 if None)
        
    Returns:
        Random word
    """
    if length is None:
        length = random.randint(3, 10)
    return "".join(random.choices(string.ascii_lowercase, k=length))


def fake_int(min_val: int = 0, max_val: int = 1000) -> int:
    """
    Generate a random integer.
    
    Args:
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Random integer
    """
    return random.randint(min_val, max_val)


def fake_float(min_val: float = 0.0, max_val: float = 1000.0, decimals: int = 2) -> float:
    """
    Generate a random float.
    
    Args:
        min_val: Minimum value
        max_val: Maximum value
        decimals: Number of decimal places
        
    Returns:
        Random float
    """
    return round(random.uniform(min_val, max_val), decimals)


def fake_bool() -> bool:
    """Generate a random boolean."""
    return random.choice([True, False])


def fake_choice(choices: list[T]) -> T:
    """
    Pick a random item from a list.
    
    Args:
        choices: List of choices
        
    Returns:
        Random choice
    """
    return random.choice(choices)


def fake_sample(choices: list[T], k: int) -> list[T]:
    """
    Pick k random items from a list without replacement.
    
    Args:
        choices: List of choices
        k: Number of items to pick
        
    Returns:
        List of random choices
    """
    return random.sample(choices, k)


# =============================================================================
# Assertions
# =============================================================================

def assert_raises_with_message(
    exception_type: type[BaseException],
    message_contains: str,
    callable_obj: Callable[[], Any],
) -> None:
    """
    Assert that a callable raises an exception with a specific message.
    
    Args:
        exception_type: Expected exception type
        message_contains: Substring that should be in error message
        callable_obj: Callable to test
        
    Raises:
        AssertionError: If exception not raised or message doesn't match
    """
    try:
        callable_obj()
        raise AssertionError(f"Expected {exception_type.__name__} to be raised")
    except exception_type as e:
        if message_contains not in str(e):
            raise AssertionError(
                f"Expected error message to contain '{message_contains}', "
                f"but got: {str(e)}"
            )


def assert_dict_contains(actual: dict, expected: dict) -> None:
    """
    Assert that a dict contains all key-value pairs from expected.
    
    Args:
        actual: Actual dictionary
        expected: Expected key-value pairs
        
    Raises:
        AssertionError: If any expected key-value pair is missing
    """
    for key, value in expected.items():
        if key not in actual:
            raise AssertionError(f"Key '{key}' not found in dict")
        if actual[key] != value:
            raise AssertionError(
                f"Value mismatch for key '{key}': "
                f"expected {value!r}, got {actual[key]!r}"
            )


def assert_list_contains_all(actual: list, expected: list) -> None:
    """
    Assert that a list contains all expected items.
    
    Args:
        actual: Actual list
        expected: Expected items
        
    Raises:
        AssertionError: If any expected item is missing
    """
    for item in expected:
        if item not in actual:
            raise AssertionError(f"Item {item!r} not found in list")


def assert_list_contains_any(actual: list, expected: list) -> None:
    """
    Assert that a list contains at least one expected item.
    
    Args:
        actual: Actual list
        expected: Expected items (at least one should be present)
        
    Raises:
        AssertionError: If no expected items are found
    """
    for item in expected:
        if item in actual:
            return
    raise AssertionError(f"None of {expected!r} found in list")


def assert_datetime_close(
    actual: datetime,
    expected: datetime,
    delta: timedelta | None = None,
) -> None:
    """
    Assert that two datetimes are close to each other.
    
    Args:
        actual: Actual datetime
        expected: Expected datetime
        delta: Maximum allowed difference (default: 1 second)
        
    Raises:
        AssertionError: If datetimes differ by more than delta
    """
    if delta is None:
        delta = timedelta(seconds=1)
    
    diff = abs(actual - expected)
    if diff > delta:
        raise AssertionError(
            f"Datetimes differ by {diff}, expected within {delta}. "
            f"Actual: {actual}, Expected: {expected}"
        )


def assert_almost_equal(
    actual: float,
    expected: float,
    places: int = 7,
) -> None:
    """
    Assert that two floats are almost equal.
    
    Args:
        actual: Actual value
        expected: Expected value
        places: Number of decimal places
        
    Raises:
        AssertionError: If values differ
    """
    if round(abs(expected - actual), places) != 0:
        raise AssertionError(
            f"Values not equal to {places} places: "
            f"actual={actual}, expected={expected}"
        )


# =============================================================================
# Fixtures
# =============================================================================

@dataclass
class TempDirectory:
    """
    Context manager for creating a temporary directory.
    
    Example:
        with TempDirectory() as temp_dir:
            file_path = temp_dir.path / "test.txt"
            file_path.write_text("hello")
    """
    
    prefix: str = "test_"
    path: Path = field(init=False)
    _cleanup: bool = field(default=True, init=False)
    
    def __enter__(self) -> TempDirectory:
        self._temp_dir = tempfile.mkdtemp(prefix=self.prefix)
        self.path = Path(self._temp_dir)
        return self
    
    def __exit__(self, *args: Any) -> None:
        if self._cleanup:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
    
    def create_file(self, name: str, content: str = "") -> Path:
        """Create a file in the temp directory."""
        file_path = self.path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path


@dataclass
class TempFile:
    """
    Context manager for creating a temporary file.
    
    Example:
        with TempFile(content="hello") as temp_file:
            assert temp_file.path.read_text() == "hello"
    """
    
    content: str = ""
    suffix: str = ".txt"
    path: Path = field(init=False)
    
    def __enter__(self) -> TempFile:
        fd, path = tempfile.mkstemp(suffix=self.suffix)
        self.path = Path(path)
        os.close(fd)
        if self.content:
            self.path.write_text(self.content)
        return self
    
    def __exit__(self, *args: Any) -> None:
        if self.path.exists():
            self.path.unlink()


class MockEnv:
    """
    Context manager for mocking environment variables.
    
    Example:
        with MockEnv(API_KEY="test"):
            assert os.environ["API_KEY"] == "test"
    """
    
    def __init__(self, **env_vars: str):
        self.env_vars = env_vars
        self._original: dict[str, str | None] = {}
    
    def __enter__(self) -> MockEnv:
        for key, value in self.env_vars.items():
            self._original[key] = os.environ.get(key)
            os.environ[key] = value
        return self
    
    def __exit__(self, *args: Any) -> None:
        for key, original_value in self._original.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


class MockTime:
    """
    Context manager for mocking time functions.
    
    Example:
        frozen_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with MockTime(frozen_time):
            from datetime import datetime
            # datetime.now() will return the frozen time
    """
    
    def __init__(self, frozen_time: datetime):
        self.frozen_time = frozen_time
        self._patches: list[Any] = []
    
    def __enter__(self) -> MockTime:
        self._patches.append(
            patch("datetime.datetime", wraps=datetime)
        )
        for p in self._patches:
            mock = p.start()
            mock.now.return_value = self.frozen_time
            mock.utcnow.return_value = self.frozen_time.replace(tzinfo=None)
        return self
    
    def __exit__(self, *args: Any) -> None:
        for p in self._patches:
            p.stop()


@dataclass
class CaptureOutput:
    """
    Context manager for capturing stdout/stderr.
    
    Example:
        with CaptureOutput() as output:
            print("hello")
        assert output.stdout == "hello\\n"
    """
    
    stdout: str = field(default="", init=False)
    stderr: str = field(default="", init=False)
    
    def __enter__(self) -> CaptureOutput:
        import io
        import sys
        
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self._stdout_buffer = io.StringIO()
        sys.stderr = self._stderr_buffer = io.StringIO()
        return self
    
    def __exit__(self, *args: Any) -> None:
        import sys
        
        self.stdout = self._stdout_buffer.getvalue()
        self.stderr = self._stderr_buffer.getvalue()
        sys.stdout = self._stdout
        sys.stderr = self._stderr


# =============================================================================
# Async Helpers
# =============================================================================

def async_return(value: T) -> AsyncMock:
    """
    Create an AsyncMock that returns a value.
    
    Args:
        value: Value to return
        
    Returns:
        AsyncMock configured to return the value
    """
    mock = AsyncMock()
    mock.return_value = value
    return mock


def async_raise(exception: BaseException) -> AsyncMock:
    """
    Create an AsyncMock that raises an exception.
    
    Args:
        exception: Exception to raise
        
    Returns:
        AsyncMock configured to raise the exception
    """
    mock = AsyncMock()
    mock.side_effect = exception
    return mock


def run_async(coro: Any) -> Any:
    """
    Run an async function synchronously.
    
    Useful for testing async code in sync contexts.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# =============================================================================
# Test Data Builder
# =============================================================================

class DataBuilder:
    """
    Fluent builder for creating test data objects.
    
    Example:
        user = (
            DataBuilder()
            .with_field("name", "Alice")
            .with_field("email", fake_email())
            .with_field("age", 30)
            .build()
        )
    """
    
    def __init__(self, base: dict[str, Any] | None = None):
        self._data: dict[str, Any] = base.copy() if base else {}
    
    def with_field(self, key: str, value: Any) -> DataBuilder:
        """
        Add a field to the data.
        
        Args:
            key: Field name
            value: Field value
            
        Returns:
            Self for chaining
        """
        self._data[key] = value
        return self
    
    def without_field(self, key: str) -> DataBuilder:
        """
        Remove a field from the data.
        
        Args:
            key: Field name to remove
            
        Returns:
            Self for chaining
        """
        self._data.pop(key, None)
        return self
    
    def with_fields(self, **fields: Any) -> DataBuilder:
        """
        Add multiple fields.
        
        Args:
            **fields: Field key-value pairs
            
        Returns:
            Self for chaining
        """
        self._data.update(fields)
        return self
    
    def build(self) -> dict[str, Any]:
        """
        Build the final dictionary.
        
        Returns:
            Built dictionary
        """
        return self._data.copy()
    
    def build_list(self, count: int, vary_field: str | None = None) -> list[dict[str, Any]]:
        """
        Build a list of dictionaries.
        
        Args:
            count: Number of items to create
            vary_field: Field to vary (append index)
            
        Returns:
            List of dictionaries
        """
        result = []
        for i in range(count):
            item = self._data.copy()
            if vary_field and vary_field in item:
                item[vary_field] = f"{item[vary_field]}_{i}"
            result.append(item)
        return result
