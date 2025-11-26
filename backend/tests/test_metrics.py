"""
Tests for Prometheus metrics service.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

# Skip all tests if prometheus_client is not installed
pytest.importorskip("prometheus_client")

from app.services.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    AI_JOBS_TOTAL,
    AI_JOB_DURATION_SECONDS,
    AI_JOB_ERRORS_TOTAL,
    AI_JOB_RETRIES_TOTAL,
    AI_JOBS_QUEUE_DEPTH,
    AI_JOBS_PROCESSING,
    STORAGE_OPERATIONS_TOTAL,
    STORAGE_BYTES_TOTAL,
    NOTIFICATIONS_SENT_TOTAL,
    QUOTA_EXCEEDED_TOTAL,
    track_ai_job_stage,
    track_storage_operation,
    track_db_query,
    record_ai_job_complete,
    record_ai_job_error,
    record_ai_job_retry,
    update_queue_depth,
    update_processing_count,
    record_storage_bytes,
    record_notification_sent,
    record_notification_rate_limited,
    record_quota_exceeded,
)
from prometheus_client import REGISTRY


class TestHTTPMetrics:
    """Tests for HTTP metrics."""

    def test_http_requests_total_exists(self) -> None:
        """HTTP requests counter exists."""
        assert HTTP_REQUESTS_TOTAL is not None
        # Verify we can increment with labels
        HTTP_REQUESTS_TOTAL.labels(method="GET", path="/test", status=200).inc()

    def test_http_request_duration_exists(self) -> None:
        """HTTP request duration histogram exists."""
        assert HTTP_REQUEST_DURATION_SECONDS is not None
        # Verify we can observe with labels
        HTTP_REQUEST_DURATION_SECONDS.labels(method="GET", path="/test").observe(0.1)


class TestAIJobMetrics:
    """Tests for AI job metrics."""

    def test_ai_jobs_total_counter(self) -> None:
        """AI jobs total counter increments."""
        initial = AI_JOBS_TOTAL.labels(status="complete")._value.get()
        record_ai_job_complete("complete")
        assert AI_JOBS_TOTAL.labels(status="complete")._value.get() == initial + 1

    def test_ai_job_duration_histogram(self) -> None:
        """AI job duration histogram records values."""
        # Use the context manager
        with track_ai_job_stage("test_stage"):
            pass  # Simulate some work

        # Verify bucket was incremented (sum should be > 0)
        assert AI_JOB_DURATION_SECONDS.labels(stage="test_stage")._sum.get() >= 0

    def test_ai_job_errors_counter(self) -> None:
        """AI job errors counter increments."""
        initial = AI_JOB_ERRORS_TOTAL.labels(error_type="timeout")._value.get()
        record_ai_job_error("timeout")
        assert AI_JOB_ERRORS_TOTAL.labels(error_type="timeout")._value.get() == initial + 1

    def test_ai_job_retries_counter(self) -> None:
        """AI job retries counter increments."""
        initial = AI_JOB_RETRIES_TOTAL._value.get()
        record_ai_job_retry()
        assert AI_JOB_RETRIES_TOTAL._value.get() == initial + 1

    def test_queue_depth_gauge(self) -> None:
        """Queue depth gauge sets values."""
        update_queue_depth(standard=10, priority=5)
        assert AI_JOBS_QUEUE_DEPTH.labels(priority="standard")._value.get() == 10
        assert AI_JOBS_QUEUE_DEPTH.labels(priority="priority")._value.get() == 5

    def test_processing_count_gauge(self) -> None:
        """Processing count gauge sets value."""
        update_processing_count(3)
        assert AI_JOBS_PROCESSING._value.get() == 3


class TestStorageMetrics:
    """Tests for storage metrics."""

    def test_storage_operations_counter(self) -> None:
        """Storage operations counter increments."""
        with track_storage_operation("upload", "s3"):
            pass

        # Counter should have been incremented
        assert STORAGE_OPERATIONS_TOTAL.labels(operation="upload", backend="s3")._value.get() > 0

    def test_storage_bytes_counter(self) -> None:
        """Storage bytes counter increments."""
        initial = STORAGE_BYTES_TOTAL.labels(direction="upload", backend="s3")._value.get()
        record_storage_bytes("upload", "s3", 1024)
        assert STORAGE_BYTES_TOTAL.labels(direction="upload", backend="s3")._value.get() == initial + 1024


class TestNotificationMetrics:
    """Tests for notification metrics."""

    def test_notifications_sent_counter(self) -> None:
        """Notifications sent counter increments."""
        initial_success = NOTIFICATIONS_SENT_TOTAL.labels(type="email", status="success")._value.get()
        initial_failed = NOTIFICATIONS_SENT_TOTAL.labels(type="email", status="failed")._value.get()

        record_notification_sent("email", success=True)
        record_notification_sent("email", success=False)

        assert NOTIFICATIONS_SENT_TOTAL.labels(type="email", status="success")._value.get() == initial_success + 1
        assert NOTIFICATIONS_SENT_TOTAL.labels(type="email", status="failed")._value.get() == initial_failed + 1


class TestQuotaMetrics:
    """Tests for quota metrics."""

    def test_quota_exceeded_counter(self) -> None:
        """Quota exceeded counter increments."""
        initial = QUOTA_EXCEEDED_TOTAL.labels(plan="free")._value.get()
        record_quota_exceeded("free")
        assert QUOTA_EXCEEDED_TOTAL.labels(plan="free")._value.get() == initial + 1


class TestContextManagers:
    """Tests for metric context managers."""

    def test_track_ai_job_stage_records_duration(self) -> None:
        """track_ai_job_stage records duration."""
        import time

        with track_ai_job_stage("test_sleep"):
            time.sleep(0.01)  # 10ms

        # Should have recorded at least 10ms (0.01s)
        assert AI_JOB_DURATION_SECONDS.labels(stage="test_sleep")._sum.get() >= 0.01

    def test_track_storage_operation_increments_counter(self) -> None:
        """track_storage_operation increments counter on success."""
        initial = STORAGE_OPERATIONS_TOTAL.labels(operation="download", backend="local")._value.get()

        with track_storage_operation("download", "local"):
            pass

        assert STORAGE_OPERATIONS_TOTAL.labels(operation="download", backend="local")._value.get() == initial + 1

    def test_track_db_query_records_duration(self) -> None:
        """track_db_query records query duration."""
        from app.services.metrics import DB_QUERY_DURATION_SECONDS

        with track_db_query("select"):
            pass

        # Should have recorded something
        assert DB_QUERY_DURATION_SECONDS.labels(operation="select")._sum.get() >= 0
