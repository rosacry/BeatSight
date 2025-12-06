"""Tests for background task utilities."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.background_tasks import (
    BackgroundTaskManager,
    TaskConfig,
    TaskInfo,
    TaskPriority,
    TaskStatus,
    background_tasks,
    fire_and_forget,
    gather_with_timeout,
    retry_async,
    run_async,
    run_in_background,
)


# =============================================================================
# TaskInfo Tests
# =============================================================================

class TestTaskInfo:
    """Tests for TaskInfo class."""
    
    def test_task_info_creation(self):
        """Test creating a task info."""
        task = TaskInfo(
            task_id="test-123",
            name="test_task",
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        
        assert task.task_id == "test-123"
        assert task.name == "test_task"
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None
        assert task.error is None
    
    def test_task_info_to_dict(self):
        """Test converting task info to dictionary."""
        now = datetime.now(timezone.utc)
        task = TaskInfo(
            task_id="test-123",
            name="test_task",
            status=TaskStatus.COMPLETED,
            created_at=now,
            started_at=now,
            completed_at=now,
            priority=TaskPriority.HIGH,
        )
        
        result = task.to_dict()
        
        assert result["task_id"] == "test-123"
        assert result["name"] == "test_task"
        assert result["status"] == "completed"
        assert result["priority"] == 10
        assert "created_at" in result
    
    def test_duration_seconds(self):
        """Test duration calculation."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        start = now
        end = now + timedelta(seconds=5)
        
        task = TaskInfo(
            task_id="test",
            name="test",
            status=TaskStatus.COMPLETED,
            created_at=now,
            started_at=start,
            completed_at=end,
        )
        
        assert task.duration_seconds == 5.0
    
    def test_duration_seconds_none_when_not_complete(self):
        """Test duration is None when task not complete."""
        task = TaskInfo(
            task_id="test",
            name="test",
            status=TaskStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
        )
        
        assert task.duration_seconds is None


# =============================================================================
# TaskConfig Tests
# =============================================================================

class TestTaskConfig:
    """Tests for TaskConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = TaskConfig()
        
        assert config.timeout is None
        assert config.max_retries == 0
        assert config.retry_delay == 1.0
        assert config.priority == TaskPriority.NORMAL
        assert config.track_result is False
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = TaskConfig(
            timeout=30,
            max_retries=3,
            retry_delay=2.0,
            priority=TaskPriority.HIGH,
            track_result=True,
        )
        
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.priority == TaskPriority.HIGH
        assert config.track_result is True


# =============================================================================
# TaskStatus Tests
# =============================================================================

class TestTaskStatus:
    """Tests for TaskStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"
    
    def test_status_count(self):
        """Test we have expected number of statuses."""
        assert len(TaskStatus) == 6


# =============================================================================
# TaskPriority Tests
# =============================================================================

class TestTaskPriority:
    """Tests for TaskPriority enum."""
    
    def test_priority_values(self):
        """Test priority values."""
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.NORMAL.value == 5
        assert TaskPriority.HIGH.value == 10
        assert TaskPriority.CRITICAL.value == 20
    
    def test_priority_ordering(self):
        """Test priorities are ordered correctly."""
        assert TaskPriority.LOW < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.CRITICAL


# =============================================================================
# BackgroundTaskManager Tests
# =============================================================================

class TestBackgroundTaskManager:
    """Tests for BackgroundTaskManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh task manager."""
        return BackgroundTaskManager(max_concurrent=5)
    
    @pytest.mark.asyncio
    async def test_submit_task(self, manager):
        """Test submitting a task."""
        async def simple_task() -> str:
            return "done"
        
        task_id = await manager.submit(simple_task)
        
        assert task_id is not None
        assert task_id in manager._tasks
        assert manager._tasks[task_id].name == "simple_task"
    
    @pytest.mark.asyncio
    async def test_task_completes_successfully(self, manager):
        """Test task completes with success status."""
        completed = asyncio.Event()
        
        async def simple_task() -> str:
            completed.set()
            return "done"
        
        task_id = await manager.submit(simple_task)
        await completed.wait()
        await asyncio.sleep(0.1)  # Allow status update
        
        task_info = manager.get_status(task_id)
        assert task_info is not None
        assert task_info.status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_task_with_args(self, manager):
        """Test task with arguments."""
        result_holder = []
        
        async def task_with_args(a: int, b: str) -> None:
            result_holder.append(f"{a}-{b}")
        
        task_id = await manager.submit(
            task_with_args,
            args=(42, "test"),
        )
        await asyncio.sleep(0.1)
        
        assert result_holder == ["42-test"]
    
    @pytest.mark.asyncio
    async def test_task_with_kwargs(self, manager):
        """Test task with keyword arguments."""
        result_holder = []
        
        async def task_with_kwargs(name: str = "default") -> None:
            result_holder.append(name)
        
        task_id = await manager.submit(
            task_with_kwargs,
            kwargs={"name": "custom"},
        )
        await asyncio.sleep(0.1)
        
        assert result_holder == ["custom"]
    
    @pytest.mark.asyncio
    async def test_task_timeout(self, manager):
        """Test task timeout."""
        async def slow_task() -> None:
            await asyncio.sleep(10)
        
        config = TaskConfig(timeout=0.1)
        task_id = await manager.submit(slow_task, config=config)
        await asyncio.sleep(0.3)
        
        task_info = manager.get_status(task_id)
        assert task_info is not None
        assert task_info.status == TaskStatus.TIMEOUT
    
    @pytest.mark.asyncio
    async def test_task_failure(self, manager):
        """Test task failure handling."""
        async def failing_task() -> None:
            raise ValueError("Test error")
        
        task_id = await manager.submit(failing_task)
        await asyncio.sleep(0.1)
        
        task_info = manager.get_status(task_id)
        assert task_info is not None
        assert task_info.status == TaskStatus.FAILED
        assert "ValueError" in task_info.error
    
    @pytest.mark.asyncio
    async def test_task_retry(self, manager):
        """Test task retry on failure."""
        attempt_count = 0
        
        async def retry_task() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Not yet")
            return "success"
        
        config = TaskConfig(max_retries=3, retry_delay=0.1)
        task_id = await manager.submit(retry_task, config=config)
        await asyncio.sleep(0.5)
        
        task_info = manager.get_status(task_id)
        assert attempt_count == 3
        assert task_info.status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, manager):
        """Test cancelling a task."""
        cancel_started = asyncio.Event()
        
        async def cancellable_task() -> None:
            cancel_started.set()
            await asyncio.sleep(10)
        
        task_id = await manager.submit(cancellable_task)
        await cancel_started.wait()
        
        result = await manager.cancel(task_id)
        assert result is True
        
        await asyncio.sleep(0.1)
        task_info = manager.get_status(task_id)
        assert task_info.status == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_wait_for_task(self, manager):
        """Test waiting for task completion."""
        async def quick_task() -> str:
            return "done"
        
        task_id = await manager.submit(quick_task)
        task_info = await manager.wait(task_id, timeout=1.0)
        
        assert task_info is not None
        assert task_info.status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, manager):
        """Test listing tasks."""
        async def task1() -> None:
            pass
        
        async def task2() -> None:
            pass
        
        await manager.submit(task1)
        await manager.submit(task2)
        await asyncio.sleep(0.1)
        
        tasks = manager.list_tasks()
        assert len(tasks) == 2
    
    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, manager):
        """Test listing tasks filtered by status."""
        async def success_task() -> None:
            pass
        
        async def fail_task() -> None:
            raise ValueError("fail")
        
        await manager.submit(success_task)
        await manager.submit(fail_task)
        await asyncio.sleep(0.1)
        
        completed = manager.list_tasks(status=TaskStatus.COMPLETED)
        failed = manager.list_tasks(status=TaskStatus.FAILED)
        
        assert len(completed) == 1
        assert len(failed) == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_completed(self, manager):
        """Test cleanup of old completed tasks."""
        async def quick_task() -> None:
            pass
        
        await manager.submit(quick_task)
        await asyncio.sleep(0.1)
        
        # Should not remove recent tasks
        removed = manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 0
        
        # Force cleanup by using very short max age
        removed = manager.cleanup_completed(max_age_seconds=0)
        assert removed == 1
    
    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """Test getting task manager stats."""
        stats = manager.get_stats()
        
        assert "total_tasks" in stats
        assert "running_tasks" in stats
        assert "max_concurrent" in stats
        assert stats["max_concurrent"] == 5
    
    @pytest.mark.asyncio
    async def test_shutdown(self, manager):
        """Test graceful shutdown."""
        running = asyncio.Event()
        
        async def long_task() -> None:
            running.set()
            await asyncio.sleep(0.2)
        
        await manager.submit(long_task)
        await running.wait()
        
        await manager.shutdown(timeout=1.0)
        
        assert manager._shutdown is True
    
    @pytest.mark.asyncio
    async def test_submit_after_shutdown_fails(self, manager):
        """Test submitting task after shutdown raises error."""
        await manager.shutdown()
        
        async def task() -> None:
            pass
        
        with pytest.raises(RuntimeError, match="shutting down"):
            await manager.submit(task)
    
    @pytest.mark.asyncio
    async def test_concurrent_limit(self, manager):
        """Test concurrent task limit is respected."""
        running_count = 0
        max_running = 0
        
        async def tracked_task() -> None:
            nonlocal running_count, max_running
            running_count += 1
            max_running = max(max_running, running_count)
            await asyncio.sleep(0.1)
            running_count -= 1
        
        # Submit more tasks than concurrent limit
        for _ in range(10):
            await manager.submit(tracked_task)
        
        await asyncio.sleep(0.5)
        
        assert max_running <= 5  # Should respect limit


# =============================================================================
# Decorator Tests
# =============================================================================

class TestRunInBackgroundDecorator:
    """Tests for @run_in_background decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_returns_task_id(self):
        """Test decorator returns task ID."""
        @run_in_background()
        async def my_task() -> str:
            return "done"
        
        # Use submit method for async context
        task_id = await my_task.submit()
        
        assert isinstance(task_id, str)
        assert len(task_id) > 0
    
    @pytest.mark.asyncio
    async def test_decorator_with_timeout(self):
        """Test decorator with timeout configuration."""
        @run_in_background(timeout=1.0)
        async def my_task() -> str:
            return "done"
        
        task_id = await my_task.submit()
        assert task_id is not None
    
    @pytest.mark.asyncio
    async def test_decorator_preserves_original(self):
        """Test decorator preserves original function."""
        @run_in_background()
        async def my_task() -> str:
            return "done"
        
        assert hasattr(my_task, "original")
        assert asyncio.iscoroutinefunction(my_task.original)


class TestFireAndForgetDecorator:
    """Tests for @fire_and_forget decorator."""
    
    @pytest.mark.asyncio
    async def test_fire_and_forget_executes(self):
        """Test fire and forget actually executes."""
        executed = asyncio.Event()
        
        @fire_and_forget
        async def my_task() -> None:
            executed.set()
        
        my_task()
        await asyncio.sleep(0.1)
        
        assert executed.is_set()
    
    @pytest.mark.asyncio
    async def test_fire_and_forget_handles_error(self):
        """Test fire and forget handles errors gracefully."""
        @fire_and_forget
        async def failing_task() -> None:
            raise ValueError("test error")
        
        # Should not raise
        failing_task()
        await asyncio.sleep(0.1)


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestRunAsync:
    """Tests for run_async utility."""
    
    @pytest.mark.asyncio
    async def test_runs_sync_function(self):
        """Test running sync function in thread pool."""
        def sync_func(x: int) -> int:
            return x * 2
        
        result = await run_async(sync_func, 5)
        
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_runs_with_kwargs(self):
        """Test running with keyword arguments."""
        def sync_func(a: int, b: int = 10) -> int:
            return a + b
        
        result = await run_async(sync_func, 5, b=20)
        
        assert result == 25


class TestGatherWithTimeout:
    """Tests for gather_with_timeout utility."""
    
    @pytest.mark.asyncio
    async def test_gathers_results(self):
        """Test gathering multiple coroutines."""
        async def task1() -> int:
            return 1
        
        async def task2() -> int:
            return 2
        
        results = await gather_with_timeout(task1(), task2(), timeout=1.0)
        
        assert results == [1, 2]
    
    @pytest.mark.asyncio
    async def test_times_out(self):
        """Test timeout when tasks take too long."""
        async def slow_task() -> None:
            await asyncio.sleep(10)
        
        with pytest.raises(asyncio.TimeoutError):
            await gather_with_timeout(slow_task(), timeout=0.1)


class TestRetryAsync:
    """Tests for retry_async utility."""
    
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        """Test success on first attempt."""
        async def success_func() -> str:
            return "done"
        
        result = await retry_async(success_func)
        
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Test retry on failure."""
        attempt = 0
        
        async def retry_func() -> str:
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError("not yet")
            return "done"
        
        result = await retry_async(retry_func, max_attempts=3, delay=0.01)
        
        assert result == "done"
        assert attempt == 3
    
    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        """Test raises exception after max attempts."""
        async def always_fail() -> None:
            raise ValueError("always")
        
        with pytest.raises(ValueError, match="always"):
            await retry_async(always_fail, max_attempts=2, delay=0.01)
    
    @pytest.mark.asyncio
    async def test_respects_exception_filter(self):
        """Test only retries on specified exceptions."""
        attempt = 0
        
        async def specific_fail() -> None:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise TypeError("wrong type")
            raise ValueError("value error")
        
        # Should not retry on TypeError
        with pytest.raises(TypeError):
            await retry_async(
                specific_fail,
                max_attempts=3,
                exceptions=(ValueError,),
            )
        
        assert attempt == 1
