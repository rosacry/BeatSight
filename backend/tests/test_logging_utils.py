"""Tests for logging utilities."""

import time
from unittest import mock

import pytest

from app.utils.logging_utils import (
    # Configuration
    LogConfig,
    get_logger,
    LoggerAdapter,
    # Context Managers
    log_context,
    request_context,
    timed_log,
    # Decorators
    log_call,
    log_execution_time,
    # Log Level Utilities
    should_log,
    level_to_int,
    # Formatters
    format_exception,
    format_request,
    format_sql_query,
    # Sampling and Rate Limiting
    SamplingLogger,
    RateLimitedLogger,
    # Audit Logging
    AuditEvent,
    AuditLogger,
    # Context Variables
    request_id_var,
    user_id_var,
)


class TestLogConfig:
    """Tests for LogConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = LogConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.add_timestamp is True
        assert "password" in config.redact_fields

    def test_custom_config(self):
        """Test custom configuration."""
        config = LogConfig(
            level="DEBUG",
            format="console",
            add_timestamp=False,
        )
        assert config.level == "DEBUG"
        assert config.format == "console"
        assert config.add_timestamp is False


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_basic(self):
        """Test basic logger creation."""
        logger = get_logger("test")
        assert logger is not None

    def test_get_logger_with_context(self):
        """Test logger with initial context."""
        logger = get_logger("test", service="api", version="1.0")
        assert logger is not None


class TestLoggerAdapter:
    """Tests for LoggerAdapter class."""

    def test_adapter_bind(self):
        """Test creating adapter with additional context."""
        base_logger = get_logger("test")
        adapter = LoggerAdapter(base_logger, service="api")
        new_adapter = adapter.bind(request_id="123")
        assert new_adapter is not None

    def test_adapter_log_methods(self):
        """Test all log methods exist."""
        base_logger = get_logger("test")
        adapter = LoggerAdapter(base_logger, service="api")

        # These should not raise
        with mock.patch.object(adapter._logger, "debug"):
            adapter.debug("test")
        with mock.patch.object(adapter._logger, "info"):
            adapter.info("test")
        with mock.patch.object(adapter._logger, "warning"):
            adapter.warning("test")
        with mock.patch.object(adapter._logger, "error"):
            adapter.error("test")
        with mock.patch.object(adapter._logger, "critical"):
            adapter.critical("test")


class TestLogContext:
    """Tests for log_context context manager."""

    def test_log_context_adds_context(self):
        """Test that context is added during block."""
        # This is difficult to test without capturing logs
        # Just verify it doesn't raise
        with log_context(request_id="123", user_id="456"):
            pass

    def test_log_context_cleanup(self):
        """Test that context is cleaned up after block."""
        with log_context(temp_key="temp_value"):
            pass
        # Context should be cleaned up (difficult to verify without log capture)


class TestRequestContext:
    """Tests for request_context context manager."""

    def test_request_context_sets_vars(self):
        """Test that context variables are set."""
        with request_context(request_id="req-123", user_id="user-456"):
            assert request_id_var.get() == "req-123"
            assert user_id_var.get() == "user-456"

    def test_request_context_partial(self):
        """Test with partial context."""
        with request_context(request_id="req-123"):
            assert request_id_var.get() == "req-123"


class TestTimedLog:
    """Tests for timed_log context manager."""

    def test_timed_log_captures_duration(self):
        """Test that duration is captured."""
        logger = get_logger("test")

        with mock.patch.object(logger, "info") as mock_info:
            with timed_log(logger, "test_operation"):
                time.sleep(0.01)

            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert "duration_ms" in call_kwargs
            assert call_kwargs["duration_ms"] >= 10

    def test_timed_log_extra_context(self):
        """Test adding extra context."""
        logger = get_logger("test")

        with mock.patch.object(logger, "info") as mock_info:
            with timed_log(logger, "test_operation") as ctx:
                ctx["rows"] = 100

            call_kwargs = mock_info.call_args[1]
            assert call_kwargs["rows"] == 100


class TestLogCall:
    """Tests for log_call decorator."""

    def test_log_call_sync(self):
        """Test logging sync function calls."""
        logger = get_logger("test")

        @log_call(logger=logger)
        def test_func(x, y):
            return x + y

        result = test_func(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_log_call_async(self):
        """Test logging async function calls."""
        logger = get_logger("test")

        @log_call(logger=logger)
        async def test_func(x, y):
            return x + y

        result = await test_func(1, 2)
        assert result == 3

    def test_log_call_exception(self):
        """Test logging exceptions."""
        logger = get_logger("test")

        @log_call(logger=logger, log_exceptions=True)
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_func()


class TestLogExecutionTime:
    """Tests for log_execution_time decorator."""

    def test_log_execution_time_sync(self):
        """Test execution time logging."""
        logger = get_logger("test")

        @log_execution_time(logger=logger)
        def slow_func():
            time.sleep(0.01)
            return "done"

        result = slow_func()
        assert result == "done"

    def test_log_execution_time_threshold(self):
        """Test execution time with threshold."""
        logger = get_logger("test")

        @log_execution_time(logger=logger, threshold_ms=1000)
        def fast_func():
            return "done"

        # Should not log because execution is below threshold
        result = fast_func()
        assert result == "done"


class TestLogLevelUtilities:
    """Tests for log level utilities."""

    def test_should_log_above_level(self):
        """Test should_log for levels above minimum."""
        assert should_log("ERROR", "INFO") is True
        assert should_log("WARNING", "DEBUG") is True

    def test_should_log_below_level(self):
        """Test should_log for levels below minimum."""
        assert should_log("DEBUG", "INFO") is False
        assert should_log("INFO", "ERROR") is False

    def test_should_log_equal_level(self):
        """Test should_log for equal levels."""
        assert should_log("INFO", "INFO") is True

    def test_level_to_int(self):
        """Test level to integer conversion."""
        assert level_to_int("DEBUG") == 10
        assert level_to_int("INFO") == 20
        assert level_to_int("WARNING") == 30
        assert level_to_int("ERROR") == 40
        assert level_to_int("CRITICAL") == 50

    def test_level_to_int_aliases(self):
        """Test level aliases."""
        assert level_to_int("WARN") == 30
        assert level_to_int("FATAL") == 50


class TestFormatters:
    """Tests for log formatters."""

    def test_format_exception(self):
        """Test exception formatting."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = format_exception(e)

        assert result["type"] == "ValueError"
        assert result["message"] == "test error"
        assert "traceback" in result

    def test_format_request(self):
        """Test request formatting."""
        result = format_request(
            method="GET",
            path="/api/users",
            status_code=200,
            duration_ms=45.678,
            user_id="123",
        )

        assert result["method"] == "GET"
        assert result["path"] == "/api/users"
        assert result["status_code"] == 200
        assert result["duration_ms"] == 45.68
        assert result["user_id"] == "123"

    def test_format_sql_query(self):
        """Test SQL query formatting."""
        result = format_sql_query(
            query="SELECT * FROM users WHERE id = %s",
            params=(123,),
            duration_ms=5.5,
        )

        assert "SELECT * FROM users" in result["query"]
        assert result["duration_ms"] == 5.5

    def test_format_sql_query_truncates(self):
        """Test SQL query truncation."""
        long_query = "SELECT " + "x, " * 1000
        result = format_sql_query(query=long_query)

        assert len(result["query"]) <= 500


class TestSamplingLogger:
    """Tests for SamplingLogger."""

    def test_sampling_full_rate(self):
        """Test sampling at full rate."""
        base_logger = get_logger("test")
        sampler = SamplingLogger(base_logger, sample_rate=1.0)

        with mock.patch.object(base_logger, "info") as mock_info:
            for _ in range(10):
                sampler.info("test")

            assert mock_info.call_count == 10

    def test_sampling_zero_rate(self):
        """Test sampling at zero rate."""
        base_logger = get_logger("test")
        sampler = SamplingLogger(base_logger, sample_rate=0.0)

        with mock.patch.object(base_logger, "info") as mock_info:
            for _ in range(10):
                sampler.info("test")

            assert mock_info.call_count == 0

    def test_sampling_always_logs_errors(self):
        """Test that errors are always logged."""
        base_logger = get_logger("test")
        sampler = SamplingLogger(
            base_logger,
            sample_rate=0.0,
            always_log_errors=True,
        )

        with mock.patch.object(base_logger, "error") as mock_error:
            sampler.error("test error")
            assert mock_error.call_count == 1


class TestRateLimitedLogger:
    """Tests for RateLimitedLogger."""

    def test_rate_limiting_basic(self):
        """Test basic rate limiting."""
        base_logger = get_logger("test")
        rate_limited = RateLimitedLogger(base_logger, max_per_minute=5)

        with mock.patch.object(base_logger, "info") as mock_info:
            for _ in range(10):
                rate_limited.info("test_event")

            # Should only log first 5
            assert mock_info.call_count == 5

    def test_rate_limiting_per_event(self):
        """Test rate limiting is per event."""
        base_logger = get_logger("test")
        rate_limited = RateLimitedLogger(base_logger, max_per_minute=2)

        with mock.patch.object(base_logger, "info") as mock_info:
            for _ in range(3):
                rate_limited.info("event_a")
            for _ in range(3):
                rate_limited.info("event_b")

            # 2 for event_a + 2 for event_b
            assert mock_info.call_count == 4


class TestAuditEvent:
    """Tests for AuditEvent."""

    def test_audit_event_to_dict(self):
        """Test converting audit event to dictionary."""
        event = AuditEvent(
            action="user.login",
            actor_id="user-123",
            actor_type="user",
            resource_type="session",
            resource_id="sess-456",
            details={"method": "password"},
            ip_address="1.2.3.4",
        )

        result = event.to_dict()

        assert result["audit"] is True
        assert result["action"] == "user.login"
        assert result["actor_id"] == "user-123"
        assert result["actor_type"] == "user"
        assert result["resource_type"] == "session"
        assert result["resource_id"] == "sess-456"
        assert result["details"] == {"method": "password"}
        assert result["ip_address"] == "1.2.3.4"
        assert "timestamp" in result

    def test_audit_event_defaults(self):
        """Test audit event with defaults."""
        event = AuditEvent(
            action="test.action",
            actor_id="actor-123",
        )

        result = event.to_dict()
        assert result["actor_type"] == "user"
        assert result["resource_type"] == ""
        assert result["details"] == {}


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_log_event(self):
        """Test logging audit event."""
        base_logger = get_logger("audit")
        audit_logger = AuditLogger(base_logger)

        event = AuditEvent(
            action="user.login",
            actor_id="user-123",
        )

        with mock.patch.object(base_logger, "info") as mock_info:
            audit_logger.log_event(event)

            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert call_kwargs["audit"] is True
            assert call_kwargs["action"] == "user.login"

    def test_log_action(self):
        """Test logging audit action."""
        base_logger = get_logger("audit")
        audit_logger = AuditLogger(base_logger)

        with mock.patch.object(base_logger, "info") as mock_info:
            audit_logger.log_action(
                action="document.delete",
                actor_id="user-123",
                resource_type="document",
                resource_id="doc-456",
                ip_address="1.2.3.4",
            )

            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert call_kwargs["action"] == "document.delete"
            assert call_kwargs["actor_id"] == "user-123"
            assert call_kwargs["resource_type"] == "document"
            assert call_kwargs["resource_id"] == "doc-456"


class TestAsyncTimedLog:
    """Tests for async_timed_log."""

    @pytest.mark.asyncio
    async def test_async_timed_log(self):
        """Test async timed logging."""
        import asyncio
        from app.utils.logging_utils import async_timed_log

        logger = get_logger("test")

        with mock.patch.object(logger, "info") as mock_info:
            async with async_timed_log(logger, "async_operation"):
                await asyncio.sleep(0.01)

            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert "duration_ms" in call_kwargs
            assert call_kwargs["duration_ms"] >= 10
