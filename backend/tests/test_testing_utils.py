"""Tests for testing utilities."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.utils.testing import (
    CaptureOutput,
    DataBuilder,
    MockEnv,
    TempDirectory,
    TempFile,
    assert_almost_equal,
    assert_datetime_close,
    assert_dict_contains,
    assert_list_contains_all,
    assert_list_contains_any,
    assert_raises_with_message,
    async_raise,
    async_return,
    fake_bool,
    fake_choice,
    fake_datetime,
    fake_email,
    fake_float,
    fake_future_datetime,
    fake_int,
    fake_password,
    fake_past_datetime,
    fake_phone,
    fake_sample,
    fake_sentence,
    fake_text,
    fake_username,
    fake_uuid,
    fake_word,
    run_async,
)


class TestFakeUuid:
    """Tests for fake_uuid."""

    def test_valid_uuid_format(self):
        """Test generates valid UUID format."""
        result = fake_uuid()
        assert len(result) == 36
        assert result.count("-") == 4

    def test_unique(self):
        """Test generates unique values."""
        uuids = {fake_uuid() for _ in range(100)}
        assert len(uuids) == 100


class TestFakeEmail:
    """Tests for fake_email."""

    def test_valid_email_format(self):
        """Test generates valid email format."""
        result = fake_email()
        assert "@" in result
        assert result.endswith("@example.com")

    def test_custom_domain(self):
        """Test custom domain."""
        result = fake_email(domain="test.org")
        assert result.endswith("@test.org")


class TestFakeUsername:
    """Tests for fake_username."""

    def test_default_length(self):
        """Test default length."""
        result = fake_username()
        assert len(result) == 8

    def test_custom_length(self):
        """Test custom length."""
        result = fake_username(length=12)
        assert len(result) == 12

    def test_valid_characters(self):
        """Test contains only valid characters."""
        result = fake_username()
        assert result.isalnum()


class TestFakePassword:
    """Tests for fake_password."""

    def test_default_length(self):
        """Test default length."""
        result = fake_password()
        assert len(result) == 16

    def test_custom_length(self):
        """Test custom length."""
        result = fake_password(length=32)
        assert len(result) == 32


class TestFakePhone:
    """Tests for fake_phone."""

    def test_format(self):
        """Test phone number format."""
        result = fake_phone()
        assert result.startswith("+1")
        # +1 + 3 + 3 + 4 = 12 characters
        assert len(result) == 12


class TestFakeDatetime:
    """Tests for fake_datetime."""

    def test_returns_datetime(self):
        """Test returns datetime."""
        result = fake_datetime()
        assert isinstance(result, datetime)

    def test_tz_aware(self):
        """Test timezone aware."""
        result = fake_datetime(tz_aware=True)
        assert result.tzinfo is not None

    def test_tz_naive(self):
        """Test timezone naive."""
        result = fake_datetime(tz_aware=False)
        assert result.tzinfo is None

    def test_within_range(self):
        """Test within specified range."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        result = fake_datetime(start=start, end=end)
        assert start <= result <= end


class TestFakeFutureDatetime:
    """Tests for fake_future_datetime."""

    def test_is_future(self):
        """Test datetime is in future."""
        now = datetime.now(timezone.utc)
        result = fake_future_datetime()
        assert result > now


class TestFakePastDatetime:
    """Tests for fake_past_datetime."""

    def test_is_past(self):
        """Test datetime is in past."""
        now = datetime.now(timezone.utc)
        result = fake_past_datetime()
        assert result < now


class TestFakeText:
    """Tests for fake_text."""

    def test_approximate_length(self):
        """Test approximate length."""
        result = fake_text(length=100)
        assert len(result) <= 100

    def test_contains_spaces(self):
        """Test contains words."""
        result = fake_text(length=50)
        assert " " in result


class TestFakeSentence:
    """Tests for fake_sentence."""

    def test_ends_with_period(self):
        """Test ends with period."""
        result = fake_sentence()
        assert result.endswith(".")

    def test_starts_capitalized(self):
        """Test starts with capital letter."""
        result = fake_sentence()
        assert result[0].isupper()


class TestFakeWord:
    """Tests for fake_word."""

    def test_random_length(self):
        """Test random length."""
        result = fake_word()
        assert 3 <= len(result) <= 10

    def test_custom_length(self):
        """Test custom length."""
        result = fake_word(length=5)
        assert len(result) == 5


class TestFakeInt:
    """Tests for fake_int."""

    def test_within_range(self):
        """Test within range."""
        result = fake_int(min_val=10, max_val=20)
        assert 10 <= result <= 20


class TestFakeFloat:
    """Tests for fake_float."""

    def test_within_range(self):
        """Test within range."""
        result = fake_float(min_val=1.0, max_val=2.0)
        assert 1.0 <= result <= 2.0

    def test_decimal_places(self):
        """Test decimal places."""
        result = fake_float(decimals=3)
        str_result = str(result)
        if "." in str_result:
            decimals = len(str_result.split(".")[1])
            assert decimals <= 3


class TestFakeBool:
    """Tests for fake_bool."""

    def test_returns_bool(self):
        """Test returns boolean."""
        result = fake_bool()
        assert isinstance(result, bool)


class TestFakeChoice:
    """Tests for fake_choice."""

    def test_returns_from_choices(self):
        """Test returns item from choices."""
        choices = ["a", "b", "c"]
        result = fake_choice(choices)
        assert result in choices


class TestFakeSample:
    """Tests for fake_sample."""

    def test_returns_k_items(self):
        """Test returns k items."""
        choices = [1, 2, 3, 4, 5]
        result = fake_sample(choices, k=3)
        assert len(result) == 3

    def test_unique_items(self):
        """Test items are unique."""
        choices = [1, 2, 3, 4, 5]
        result = fake_sample(choices, k=3)
        assert len(set(result)) == 3


class TestAssertRaisesWithMessage:
    """Tests for assert_raises_with_message."""

    def test_passes_on_match(self):
        """Test passes when exception and message match."""
        def raises():
            raise ValueError("Invalid value")
        
        # Should not raise
        assert_raises_with_message(ValueError, "Invalid", raises)

    def test_fails_on_no_exception(self):
        """Test fails when no exception raised."""
        def no_raise():
            pass
        
        with pytest.raises(AssertionError):
            assert_raises_with_message(ValueError, "error", no_raise)

    def test_fails_on_wrong_message(self):
        """Test fails when message doesn't match."""
        def raises():
            raise ValueError("Wrong message")
        
        with pytest.raises(AssertionError):
            assert_raises_with_message(ValueError, "different", raises)


class TestAssertDictContains:
    """Tests for assert_dict_contains."""

    def test_passes_on_match(self):
        """Test passes when dict contains expected."""
        actual = {"a": 1, "b": 2, "c": 3}
        expected = {"a": 1, "c": 3}
        assert_dict_contains(actual, expected)

    def test_fails_on_missing_key(self):
        """Test fails when key missing."""
        actual = {"a": 1}
        expected = {"b": 2}
        with pytest.raises(AssertionError):
            assert_dict_contains(actual, expected)

    def test_fails_on_wrong_value(self):
        """Test fails when value wrong."""
        actual = {"a": 1}
        expected = {"a": 2}
        with pytest.raises(AssertionError):
            assert_dict_contains(actual, expected)


class TestAssertListContainsAll:
    """Tests for assert_list_contains_all."""

    def test_passes_on_match(self):
        """Test passes when list contains all."""
        actual = [1, 2, 3, 4, 5]
        expected = [2, 4]
        assert_list_contains_all(actual, expected)

    def test_fails_on_missing(self):
        """Test fails when item missing."""
        actual = [1, 2, 3]
        expected = [2, 4]
        with pytest.raises(AssertionError):
            assert_list_contains_all(actual, expected)


class TestAssertListContainsAny:
    """Tests for assert_list_contains_any."""

    def test_passes_on_match(self):
        """Test passes when at least one found."""
        actual = [1, 2, 3]
        expected = [4, 2, 5]
        assert_list_contains_any(actual, expected)

    def test_fails_on_none_found(self):
        """Test fails when none found."""
        actual = [1, 2, 3]
        expected = [4, 5, 6]
        with pytest.raises(AssertionError):
            assert_list_contains_any(actual, expected)


class TestAssertDatetimeClose:
    """Tests for assert_datetime_close."""

    def test_passes_on_close(self):
        """Test passes when datetimes close."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 15, 12, 0, 0, 500000, tzinfo=timezone.utc)
        assert_datetime_close(dt1, dt2)

    def test_fails_on_far(self):
        """Test fails when datetimes far apart."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 15, 12, 1, 0, tzinfo=timezone.utc)
        with pytest.raises(AssertionError):
            assert_datetime_close(dt1, dt2)

    def test_custom_delta(self):
        """Test with custom delta."""
        dt1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 15, 12, 5, 0, tzinfo=timezone.utc)
        assert_datetime_close(dt1, dt2, delta=timedelta(minutes=10))


class TestAssertAlmostEqual:
    """Tests for assert_almost_equal."""

    def test_passes_on_equal(self):
        """Test passes when almost equal."""
        assert_almost_equal(1.0000001, 1.0, places=5)

    def test_fails_on_not_equal(self):
        """Test fails when not equal."""
        with pytest.raises(AssertionError):
            assert_almost_equal(1.1, 1.0, places=2)


class TestTempDirectory:
    """Tests for TempDirectory."""

    def test_creates_directory(self):
        """Test creates temporary directory."""
        with TempDirectory() as temp:
            assert temp.path.exists()
            assert temp.path.is_dir()

    def test_cleanup(self):
        """Test cleans up on exit."""
        with TempDirectory() as temp:
            path = temp.path
        assert not path.exists()

    def test_create_file(self):
        """Test creating file in temp directory."""
        with TempDirectory() as temp:
            file_path = temp.create_file("test.txt", "content")
            assert file_path.exists()
            assert file_path.read_text() == "content"


class TestTempFile:
    """Tests for TempFile."""

    def test_creates_file(self):
        """Test creates temporary file."""
        with TempFile() as temp:
            assert temp.path.exists()

    def test_with_content(self):
        """Test creates file with content."""
        with TempFile(content="hello") as temp:
            assert temp.path.read_text() == "hello"

    def test_cleanup(self):
        """Test cleans up on exit."""
        with TempFile() as temp:
            path = temp.path
        assert not path.exists()

    def test_custom_suffix(self):
        """Test custom suffix."""
        with TempFile(suffix=".json") as temp:
            assert temp.path.suffix == ".json"


class TestMockEnv:
    """Tests for MockEnv."""

    def test_sets_env_var(self):
        """Test sets environment variable."""
        with MockEnv(TEST_VAR="test_value"):
            assert os.environ["TEST_VAR"] == "test_value"

    def test_restores_on_exit(self):
        """Test restores original value."""
        original = os.environ.get("TEST_VAR")
        with MockEnv(TEST_VAR="test_value"):
            pass
        assert os.environ.get("TEST_VAR") == original

    def test_multiple_vars(self):
        """Test multiple variables."""
        with MockEnv(VAR1="val1", VAR2="val2"):
            assert os.environ["VAR1"] == "val1"
            assert os.environ["VAR2"] == "val2"


class TestCaptureOutput:
    """Tests for CaptureOutput."""

    def test_captures_stdout(self):
        """Test captures stdout."""
        with CaptureOutput() as output:
            print("hello")
        assert output.stdout == "hello\n"

    def test_captures_stderr(self):
        """Test captures stderr."""
        import sys
        with CaptureOutput() as output:
            print("error", file=sys.stderr)
        assert output.stderr == "error\n"


class TestAsyncReturn:
    """Tests for async_return."""

    @pytest.mark.asyncio
    async def test_returns_value(self):
        """Test returns configured value."""
        mock = async_return("result")
        result = await mock()
        assert result == "result"


class TestAsyncRaise:
    """Tests for async_raise."""

    @pytest.mark.asyncio
    async def test_raises_exception(self):
        """Test raises configured exception."""
        mock = async_raise(ValueError("test error"))
        with pytest.raises(ValueError):
            await mock()


class TestRunAsync:
    """Tests for run_async."""

    def test_runs_coroutine(self):
        """Test runs coroutine synchronously."""
        async def async_func():
            return "result"
        
        result = run_async(async_func())
        assert result == "result"


class TestDataBuilder:
    """Tests for DataBuilder."""

    def test_with_field(self):
        """Test adding single field."""
        data = DataBuilder().with_field("name", "Alice").build()
        assert data == {"name": "Alice"}

    def test_with_fields(self):
        """Test adding multiple fields."""
        data = DataBuilder().with_fields(name="Alice", age=30).build()
        assert data == {"name": "Alice", "age": 30}

    def test_without_field(self):
        """Test removing field."""
        data = (
            DataBuilder()
            .with_fields(name="Alice", age=30)
            .without_field("age")
            .build()
        )
        assert data == {"name": "Alice"}

    def test_chaining(self):
        """Test method chaining."""
        data = (
            DataBuilder()
            .with_field("a", 1)
            .with_field("b", 2)
            .with_field("c", 3)
            .build()
        )
        assert data == {"a": 1, "b": 2, "c": 3}

    def test_build_list(self):
        """Test building list of items."""
        items = (
            DataBuilder()
            .with_field("name", "item")
            .build_list(3, vary_field="name")
        )
        assert len(items) == 3
        assert items[0]["name"] == "item_0"
        assert items[1]["name"] == "item_1"
        assert items[2]["name"] == "item_2"

    def test_base_dict(self):
        """Test initialization with base dict."""
        data = DataBuilder({"a": 1}).with_field("b", 2).build()
        assert data == {"a": 1, "b": 2}
