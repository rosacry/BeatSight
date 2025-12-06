"""Tests for queue and task utilities."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List

import pytest

from app.utils.queue import (
    # Core classes
    Task,
    TaskStatus,
    TaskPriority,
    TaskResult,
    # Task queue
    TaskQueue,
    QueueFullError,
    Worker,
    # Specialized queues
    DelayedQueue,
    RateLimitedQueue,
    # Scheduler
    Scheduler,
    ScheduledJob,
    # Batch processor
    BatchProcessor,
    # Factory functions
    create_task_queue,
    create_delayed_queue,
    create_rate_limited_queue,
    create_scheduler,
    create_batch_processor,
    create_worker,
)


# Test functions


def sync_add(a: int, b: int) -> int:
    """Sync test function."""
    return a + b


async def async_add(a: int, b: int) -> int:
    """Async test function."""
    await asyncio.sleep(0.01)
    return a + b


def failing_func() -> None:
    """Function that always fails."""
    raise ValueError("Test error")


async def async_failing_func() -> None:
    """Async function that always fails."""
    raise ValueError("Async test error")


class TestTask:
    """Tests for Task class."""
    
    def test_task_defaults(self):
        """Test default task values."""
        task = Task(func=sync_add)
        
        assert task.id is not None
        assert task.name == "sync_add"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.retries == 0
        assert task.max_retries == 0
    
    def test_task_with_args(self):
        """Test task with arguments."""
        task = Task(
            func=sync_add,
            args=(1, 2),
            kwargs={"extra": "value"},
            name="addition",
        )
        
        assert task.args == (1, 2)
        assert task.kwargs == {"extra": "value"}
        assert task.name == "addition"
    
    def test_task_priority(self):
        """Test task priority comparison."""
        low = Task(func=sync_add, priority=TaskPriority.LOW)
        high = Task(func=sync_add, priority=TaskPriority.HIGH)
        critical = Task(func=sync_add, priority=TaskPriority.CRITICAL)
        
        assert critical < high
        assert high < low
    
    def test_task_is_complete(self):
        """Test is_complete property."""
        task = Task(func=sync_add)
        assert task.is_complete is False
        
        task.status = TaskStatus.COMPLETED
        assert task.is_complete is True
        
        task.status = TaskStatus.FAILED
        assert task.is_complete is True
        
        task.status = TaskStatus.CANCELLED
        assert task.is_complete is True
    
    def test_task_can_retry(self):
        """Test can_retry property."""
        task = Task(func=sync_add, max_retries=3)
        
        # Can't retry pending task
        assert task.can_retry is False
        
        # Can retry failed task
        task.status = TaskStatus.FAILED
        assert task.can_retry is True
        
        # Can't retry if max retries reached
        task.retries = 3
        assert task.can_retry is False
    
    def test_task_duration(self):
        """Test duration calculation."""
        task = Task(func=sync_add)
        assert task.duration is None
        
        task.started_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        task.completed_at = datetime(2024, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
        
        assert task.duration == 5.0
    
    def test_task_to_dict(self):
        """Test task serialization."""
        task = Task(
            func=sync_add,
            name="test_task",
            metadata={"key": "value"},
        )
        
        data = task.to_dict()
        assert data["name"] == "test_task"
        assert data["status"] == "pending"
        assert data["metadata"] == {"key": "value"}


class TestTaskResult:
    """Tests for TaskResult class."""
    
    def test_successful_result(self):
        """Test successful result."""
        result = TaskResult(
            task_id="123",
            success=True,
            result=42,
            duration=0.5,
        )
        
        assert result.success is True
        assert result.result == 42
        assert result.error is None
    
    def test_failed_result(self):
        """Test failed result."""
        result = TaskResult(
            task_id="123",
            success=False,
            error="Test error",
        )
        
        assert result.success is False
        assert result.error == "Test error"


class TestTaskQueue:
    """Tests for TaskQueue class."""
    
    @pytest.fixture
    def queue(self):
        """Create task queue for tests."""
        return TaskQueue()
    
    @pytest.mark.asyncio
    async def test_enqueue_task(self, queue):
        """Test adding task to queue."""
        task = await queue.enqueue(sync_add, args=(1, 2))
        
        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert queue.size == 1
    
    @pytest.mark.asyncio
    async def test_dequeue_task(self, queue):
        """Test getting task from queue."""
        await queue.enqueue(sync_add, args=(1, 2))
        
        task = await queue.dequeue()
        
        assert task is not None
        assert task.func == sync_add
        assert queue.size == 0
    
    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, queue):
        """Test dequeue from empty queue."""
        task = await queue.dequeue(timeout=0.01)
        assert task is None
    
    @pytest.mark.asyncio
    async def test_execute_sync_task(self, queue):
        """Test executing sync task."""
        task = await queue.enqueue(sync_add, args=(1, 2))
        task = await queue.dequeue()
        
        result = await queue.execute(task)
        
        assert result.success is True
        assert result.result == 3
        assert task.status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_execute_async_task(self, queue):
        """Test executing async task."""
        task = await queue.enqueue(async_add, args=(2, 3))
        task = await queue.dequeue()
        
        result = await queue.execute(task)
        
        assert result.success is True
        assert result.result == 5
    
    @pytest.mark.asyncio
    async def test_execute_failing_task(self, queue):
        """Test executing failing task."""
        task = await queue.enqueue(failing_func)
        task = await queue.dequeue()
        
        result = await queue.execute(task)
        
        assert result.success is False
        assert "Test error" in result.error
        assert task.status == TaskStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Test priority ordering."""
        await queue.enqueue(sync_add, args=(1,), priority=TaskPriority.LOW)
        await queue.enqueue(sync_add, args=(2,), priority=TaskPriority.HIGH)
        await queue.enqueue(sync_add, args=(3,), priority=TaskPriority.CRITICAL)
        
        # Should get critical first
        task1 = await queue.dequeue()
        task2 = await queue.dequeue()
        task3 = await queue.dequeue()
        
        assert task1.args == (3,)  # CRITICAL
        assert task2.args == (2,)  # HIGH
        assert task3.args == (1,)  # LOW
    
    @pytest.mark.asyncio
    async def test_retry_task(self, queue):
        """Test task retry."""
        task = await queue.enqueue(failing_func, max_retries=2)
        task = await queue.dequeue()
        
        await queue.execute(task)
        assert task.status == TaskStatus.FAILED
        
        result = await queue.retry(task)
        assert result is True
        assert task.retries == 1
        assert task.status == TaskStatus.RETRYING
        
        # Should be back in queue
        assert queue.size == 1
    
    @pytest.mark.asyncio
    async def test_retry_exceeds_max(self, queue):
        """Test retry when max exceeded."""
        task = await queue.enqueue(failing_func, max_retries=1)
        task = await queue.dequeue()
        
        await queue.execute(task)
        task.retries = 1  # Already retried once
        
        result = await queue.retry(task)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, queue):
        """Test cancelling task."""
        task = await queue.enqueue(sync_add)
        
        result = await queue.cancel(task.id)
        
        assert result is True
        assert task.status == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, queue):
        """Test clearing queue."""
        for i in range(5):
            await queue.enqueue(sync_add, args=(i,))
        
        count = await queue.clear()
        
        assert count == 5
        assert queue.size == 0
    
    @pytest.mark.asyncio
    async def test_max_size(self):
        """Test queue max size."""
        queue = TaskQueue(max_size=2)
        
        await queue.enqueue(sync_add)
        await queue.enqueue(sync_add)
        
        with pytest.raises(QueueFullError):
            await queue.enqueue(sync_add)
    
    @pytest.mark.asyncio
    async def test_get_task(self, queue):
        """Test getting task by ID."""
        task = await queue.enqueue(sync_add)
        
        found = queue.get_task(task.id)
        
        assert found is task
    
    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, queue):
        """Test getting pending tasks."""
        await queue.enqueue(sync_add)
        await queue.enqueue(sync_add)
        
        pending = queue.get_pending_tasks()
        
        assert len(pending) == 2
    
    @pytest.mark.asyncio
    async def test_scheduled_task(self, queue):
        """Test scheduled task."""
        future = datetime.now(timezone.utc) + timedelta(seconds=0.1)
        task = await queue.enqueue(sync_add, scheduled_at=future)
        
        assert task.status == TaskStatus.SCHEDULED
        
        # Should not be dequeued before scheduled time
        result = await queue.dequeue(timeout=0.01)
        assert result is None


class TestWorker:
    """Tests for Worker class."""
    
    @pytest.mark.asyncio
    async def test_worker_processes_tasks(self):
        """Test worker processes tasks."""
        queue = TaskQueue()
        completed = []
        
        async def on_complete(task, result):
            completed.append((task.id, result.result))
        
        worker = Worker(queue, num_workers=1, on_task_complete=on_complete)
        
        await worker.start()
        
        await queue.enqueue(sync_add, args=(1, 2))
        await queue.enqueue(sync_add, args=(3, 4))
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        await worker.stop()
        
        assert len(completed) == 2
        assert worker.processed_count == 2
    
    @pytest.mark.asyncio
    async def test_worker_handles_errors(self):
        """Test worker handles errors."""
        queue = TaskQueue()
        errors = []
        
        async def on_error(task, exc):
            errors.append(str(exc))
        
        worker = Worker(queue, on_task_error=on_error)
        
        await worker.start()
        await queue.enqueue(failing_func)
        
        await asyncio.sleep(0.2)
        await worker.stop()
        
        assert len(errors) == 1
        assert worker.error_count == 1
    
    @pytest.mark.asyncio
    async def test_worker_multiple_workers(self):
        """Test multiple concurrent workers."""
        queue = TaskQueue()
        results = []
        
        async def slow_task(n):
            await asyncio.sleep(0.1)
            return n
        
        async def on_complete(task, result):
            results.append(result.result)
        
        worker = Worker(queue, num_workers=3, on_task_complete=on_complete)
        
        await worker.start()
        
        for i in range(3):
            await queue.enqueue(slow_task, args=(i,))
        
        # With 3 workers, should complete in ~0.1s instead of ~0.3s
        await asyncio.sleep(0.2)
        await worker.stop()
        
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_worker_auto_retry(self):
        """Test worker auto-retries failed tasks."""
        queue = TaskQueue()
        attempt_count = [0]
        
        async def sometimes_fails():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Not yet")
            return "success"
        
        worker = Worker(queue)
        await worker.start()
        
        await queue.enqueue(sometimes_fails, max_retries=3)
        
        await asyncio.sleep(0.3)
        await worker.stop()
        
        assert attempt_count[0] == 3


class TestDelayedQueue:
    """Tests for DelayedQueue class."""
    
    @pytest.mark.asyncio
    async def test_immediate_item(self):
        """Test item with no delay."""
        queue = DelayedQueue()
        await queue.put("item", delay=0)
        
        result = await queue.get()
        
        assert result == "item"
    
    @pytest.mark.asyncio
    async def test_delayed_item(self):
        """Test item with delay."""
        queue = DelayedQueue()
        await queue.put("item", delay=0.1)
        
        # Should not be available immediately
        result = await queue.get(timeout=0.01)
        assert result is None
        
        # Should be available after delay
        await asyncio.sleep(0.15)
        result = await queue.get()
        assert result == "item"
    
    @pytest.mark.asyncio
    async def test_ordering_by_time(self):
        """Test items ordered by run time."""
        queue = DelayedQueue()
        
        await queue.put("second", delay=0.1)
        await queue.put("first", delay=0.01)
        await queue.put("third", delay=0.2)
        
        await asyncio.sleep(0.25)
        
        assert await queue.get() == "first"
        assert await queue.get() == "second"
        assert await queue.get() == "third"
    
    @pytest.mark.asyncio
    async def test_scheduled_at(self):
        """Test item with specific run time."""
        queue = DelayedQueue()
        run_at = datetime.now(timezone.utc) + timedelta(seconds=0.1)
        
        await queue.put("item", run_at=run_at)
        
        # Wait for scheduled time
        await asyncio.sleep(0.15)
        result = await queue.get()
        
        assert result == "item"
    
    def test_peek(self):
        """Test peeking at next item."""
        queue = DelayedQueue()
        
        assert queue.peek() is None
        
        # Add item synchronously for testing
        import time
        import heapq
        heapq.heappush(queue._heap, (time.time() + 1, 1, "item"))
        
        result = queue.peek()
        assert result is not None
        assert result[1] == "item"


class TestRateLimitedQueue:
    """Tests for RateLimitedQueue class."""
    
    @pytest.mark.asyncio
    async def test_basic_put_get(self):
        """Test basic put and get."""
        queue = RateLimitedQueue(rate=10)
        
        await queue.put("item")
        result = await queue.get()
        
        assert result == "item"
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting."""
        queue = RateLimitedQueue(rate=2, per_seconds=0.1)  # 2 per 100ms
        
        for i in range(4):
            await queue.put(f"item{i}")
        
        start = asyncio.get_event_loop().time()
        results = []
        
        for _ in range(4):
            result = await queue.get(timeout=1.0)
            if result:
                results.append(result)
        
        elapsed = asyncio.get_event_loop().time() - start
        
        assert len(results) == 4
        # Should take at least 100ms to get all 4 items
        assert elapsed >= 0.05  # Some margin for timing
    
    @pytest.mark.asyncio
    async def test_timeout_on_empty(self):
        """Test timeout on empty queue."""
        queue = RateLimitedQueue(rate=10)
        
        result = await queue.get(timeout=0.01)
        assert result is None


class TestScheduler:
    """Tests for Scheduler class."""
    
    @pytest.mark.asyncio
    async def test_schedule_recurring(self):
        """Test recurring task."""
        scheduler = Scheduler()
        call_count = [0]
        
        def task():
            call_count[0] += 1
        
        scheduler.schedule(
            task,
            interval=timedelta(milliseconds=50),
            run_immediately=True,
        )
        
        await scheduler.start()
        await asyncio.sleep(0.15)
        await scheduler.stop()
        
        assert call_count[0] >= 2
    
    @pytest.mark.asyncio
    async def test_schedule_one_time(self):
        """Test one-time scheduled task."""
        scheduler = Scheduler()
        result = []
        
        def task():
            result.append("done")
        
        # Schedule for immediate execution (no delay)
        run_at = datetime.now(timezone.utc)
        scheduler.schedule_at(task, run_at)
        
        await scheduler.start()
        await asyncio.sleep(0.2)  # Give more time for execution
        await scheduler.stop()
        
        assert result == ["done"]
    
    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test cancelling scheduled job."""
        scheduler = Scheduler()
        call_count = [0]
        
        def task():
            call_count[0] += 1
        
        job_id = scheduler.schedule(
            task,
            interval=timedelta(milliseconds=50),
        )
        
        result = scheduler.cancel(job_id)
        
        assert result is True
        
        await scheduler.start()
        await asyncio.sleep(0.1)
        await scheduler.stop()
        
        assert call_count[0] == 0
    
    @pytest.mark.asyncio
    async def test_async_task(self):
        """Test async scheduled task."""
        scheduler = Scheduler()
        result = []
        
        async def task():
            result.append("done")
        
        scheduler.schedule(
            task,
            interval=timedelta(milliseconds=50),
            run_immediately=True,
        )
        
        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()
        
        assert "done" in result
    
    @pytest.mark.asyncio
    async def test_get_jobs(self):
        """Test getting job info."""
        scheduler = Scheduler()
        
        scheduler.schedule(
            lambda: None,
            interval=timedelta(seconds=60),
            name="test_job",
        )
        
        jobs = scheduler.get_jobs()
        
        assert len(jobs) == 1
        assert jobs[0]["name"] == "test_job"
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test scheduler handles errors gracefully."""
        scheduler = Scheduler()
        
        def failing_task():
            raise ValueError("Error")
        
        scheduler.schedule(
            failing_task,
            interval=timedelta(milliseconds=50),
            run_immediately=True,
        )
        
        await scheduler.start()
        await asyncio.sleep(0.1)
        await scheduler.stop()
        
        jobs = scheduler.get_jobs()
        assert jobs[0]["error_count"] >= 1


class TestBatchProcessor:
    """Tests for BatchProcessor class."""
    
    @pytest.mark.asyncio
    async def test_batch_on_size(self):
        """Test batch processing when size reached."""
        processed = []
        
        async def processor(items):
            processed.extend(items)
            return items
        
        bp = BatchProcessor(processor, batch_size=3)
        
        await bp.add(1)
        await bp.add(2)
        result = await bp.add(3)  # Should trigger batch
        
        assert result == [1, 2, 3]
        assert processed == [1, 2, 3]
    
    @pytest.mark.asyncio
    async def test_flush_partial_batch(self):
        """Test flushing partial batch."""
        processed = []
        
        async def processor(items):
            processed.extend(items)
            return items
        
        bp = BatchProcessor(processor, batch_size=10)
        
        await bp.add(1)
        await bp.add(2)
        
        result = await bp.flush()
        
        assert result == [1, 2]
        assert bp.pending_count == 0
    
    @pytest.mark.asyncio
    async def test_all_results(self):
        """Test getting all results."""
        async def processor(items):
            return [i * 2 for i in items]
        
        bp = BatchProcessor(processor, batch_size=2)
        
        await bp.add(1)
        await bp.add(2)  # First batch
        await bp.add(3)
        await bp.add(4)  # Second batch
        
        results = bp.all_results
        assert results == [2, 4, 6, 8]
    
    @pytest.mark.asyncio
    async def test_empty_flush(self):
        """Test flushing empty buffer."""
        async def processor(items):
            return items
        
        bp = BatchProcessor(processor, batch_size=10)
        
        result = await bp.flush()
        assert result == []


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_task_queue(self):
        """Test task queue factory."""
        queue = create_task_queue(max_size=100)
        assert isinstance(queue, TaskQueue)
        assert queue._max_size == 100
    
    def test_create_delayed_queue(self):
        """Test delayed queue factory."""
        queue = create_delayed_queue()
        assert isinstance(queue, DelayedQueue)
    
    def test_create_rate_limited_queue(self):
        """Test rate-limited queue factory."""
        queue = create_rate_limited_queue(rate=100, per_seconds=1.0)
        assert isinstance(queue, RateLimitedQueue)
    
    def test_create_scheduler(self):
        """Test scheduler factory."""
        scheduler = create_scheduler()
        assert isinstance(scheduler, Scheduler)
    
    @pytest.mark.asyncio
    async def test_create_batch_processor(self):
        """Test batch processor factory."""
        async def proc(items):
            return items
        
        bp = create_batch_processor(proc, batch_size=50)
        assert isinstance(bp, BatchProcessor)
    
    def test_create_worker(self):
        """Test worker factory."""
        queue = TaskQueue()
        worker = create_worker(queue, num_workers=2)
        assert isinstance(worker, Worker)


class TestEdgeCases:
    """Tests for edge cases."""
    
    @pytest.mark.asyncio
    async def test_queue_concurrent_access(self):
        """Test concurrent queue access."""
        queue = TaskQueue()
        
        async def enqueuer():
            for i in range(10):
                await queue.enqueue(sync_add, args=(i, i))
        
        await asyncio.gather(
            enqueuer(),
            enqueuer(),
            enqueuer(),
        )
        
        assert queue.size == 30
    
    @pytest.mark.asyncio
    async def test_worker_stop_during_processing(self):
        """Test stopping worker during task processing."""
        queue = TaskQueue()
        
        async def slow_task():
            await asyncio.sleep(0.5)
            return "done"
        
        worker = Worker(queue)
        await worker.start()
        
        await queue.enqueue(slow_task)
        await asyncio.sleep(0.05)  # Let worker start task
        
        # Stop should work even during processing
        await worker.stop(wait=False)
        
        assert not worker.is_running
    
    @pytest.mark.asyncio
    async def test_scheduler_stop_start(self):
        """Test stopping and starting scheduler."""
        scheduler = Scheduler()
        
        await scheduler.start()
        await scheduler.stop()
        await scheduler.start()
        await scheduler.stop()
        
        assert not scheduler._running
    
    @pytest.mark.asyncio
    async def test_task_metadata(self):
        """Test task metadata."""
        queue = TaskQueue()
        
        task = await queue.enqueue(
            sync_add,
            args=(1, 2),
            metadata={"user_id": "123", "priority": "high"},
        )
        
        assert task.metadata["user_id"] == "123"
        assert task.metadata["priority"] == "high"
    
    @pytest.mark.asyncio
    async def test_delayed_queue_empty(self):
        """Test delayed queue timeout on empty."""
        queue = DelayedQueue()
        
        result = await queue.get(timeout=0.05)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_batch_processor_transform(self):
        """Test batch processor with transformation."""
        async def uppercase(items: List[str]) -> List[str]:
            return [item.upper() for item in items]
        
        bp = BatchProcessor(uppercase, batch_size=2)
        
        await bp.add("hello")
        results = await bp.add("world")
        
        assert results == ["HELLO", "WORLD"]
