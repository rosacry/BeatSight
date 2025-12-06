"""
Queue and task management utilities.

This module provides utilities for:
- In-memory task queues for background processing
- Priority queues with task scheduling
- Task state management and tracking
- Delayed task execution
- Simple worker patterns
"""

from __future__ import annotations

import asyncio
import heapq
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)


# Type variables
T = TypeVar("T")
R = TypeVar("R")
TaskFunc = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class TaskStatus(Enum):
    """Status of a task."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Priority levels for tasks."""

    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class Task(Generic[T]):
    """
    Represents a task to be executed.

    Attributes:
        id: Unique task identifier
        name: Human-readable task name
        func: Callable to execute
        args: Positional arguments
        kwargs: Keyword arguments
        priority: Task priority
        status: Current task status
        result: Task result when completed
        error: Error message if failed
        retries: Number of retry attempts
        max_retries: Maximum retry attempts allowed
        created_at: When task was created
        started_at: When task started running
        completed_at: When task completed
        scheduled_at: When task is scheduled to run
    """

    func: TaskFunc = field(repr=False)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[T] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set default name from function."""
        if not self.name and self.func:
            self.name = getattr(self.func, "__name__", "unknown")

    def __lt__(self, other: "Task") -> bool:
        """Compare by priority for heap ordering."""
        return self.priority.value < other.priority.value

    @property
    def is_complete(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retries < self.max_retries

    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.name,
            "result": self.result,
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "scheduled_at": self.scheduled_at.isoformat()
            if self.scheduled_at
            else None,
            "duration": self.duration,
            "metadata": self.metadata,
        }


@dataclass
class TaskResult(Generic[T]):
    """Result of task execution."""

    task_id: str
    success: bool
    result: Optional[T] = None
    error: Optional[str] = None
    duration: Optional[float] = None


class TaskQueue(Generic[T]):
    """
    Simple in-memory task queue with priority support.

    Example:
        queue = TaskQueue[str]()

        # Add tasks
        task = queue.enqueue(my_function, args=("arg1",))

        # Process tasks
        while task := await queue.dequeue():
            result = await queue.execute(task)
    """

    def __init__(
        self,
        max_size: int = 0,
        default_priority: TaskPriority = TaskPriority.NORMAL,
    ) -> None:
        """
        Initialize task queue.

        Args:
            max_size: Maximum queue size (0 = unlimited)
            default_priority: Default task priority
        """
        self._queue: List[Task[T]] = []
        self._tasks: Dict[str, Task[T]] = {}
        self._max_size = max_size
        self._default_priority = default_priority
        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._max_size > 0 and len(self._queue) >= self._max_size

    async def enqueue(
        self,
        func: TaskFunc,
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: Optional[TaskPriority] = None,
        name: str = "",
        max_retries: int = 0,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Task[T]:
        """
        Add a task to the queue.

        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            priority: Task priority
            name: Task name
            max_retries: Maximum retry attempts
            scheduled_at: When to execute task
            metadata: Additional task metadata

        Returns:
            Created task

        Raises:
            QueueFullError: If queue is at capacity
        """
        async with self._lock:
            if self.is_full:
                raise QueueFullError("Queue is at maximum capacity")

            task = Task[T](
                func=func,
                args=args,
                kwargs=kwargs or {},
                priority=priority or self._default_priority,
                name=name,
                max_retries=max_retries,
                scheduled_at=scheduled_at,
                status=TaskStatus.SCHEDULED if scheduled_at else TaskStatus.PENDING,
                metadata=metadata or {},
            )

            heapq.heappush(self._queue, task)
            self._tasks[task.id] = task

            return task

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[Task[T]]:
        """
        Get the next task from the queue.

        Args:
            timeout: Maximum seconds to wait (None = no wait)

        Returns:
            Next task or None if queue is empty
        """
        start = time.monotonic()

        while True:
            async with self._lock:
                if self._queue:
                    # Check for scheduled tasks
                    task = self._queue[0]
                    if task.scheduled_at and task.scheduled_at > datetime.now(
                        timezone.utc
                    ):
                        # Task is scheduled for future
                        if timeout is not None:
                            remaining = timeout - (time.monotonic() - start)
                            if remaining <= 0:
                                return None
                            # Task is scheduled for future, continue waiting
                        else:
                            return None
                    else:
                        return heapq.heappop(self._queue)
                elif timeout is not None and time.monotonic() - start < timeout:
                    pass  # Continue waiting
                else:
                    return None

            # Wait a bit before checking again
            await asyncio.sleep(0.01)

    async def execute(self, task: Task[T]) -> TaskResult[T]:
        """
        Execute a task.

        Args:
            task: Task to execute

        Returns:
            Task result
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        try:
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)

            return TaskResult(
                task_id=task.id,
                success=True,
                result=result,
                duration=task.duration,
            )
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)

            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=task.duration,
            )

    async def retry(self, task: Task[T]) -> bool:
        """
        Retry a failed task.

        Args:
            task: Task to retry

        Returns:
            True if task was re-queued
        """
        if not task.can_retry:
            return False

        async with self._lock:
            task.retries += 1
            task.status = TaskStatus.RETRYING
            task.error = None
            task.started_at = None
            task.completed_at = None

            heapq.heappush(self._queue, task)
            return True

    def get_task(self, task_id: str) -> Optional[Task[T]]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was cancelled
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and not task.is_complete:
                task.status = TaskStatus.CANCELLED
                return True
            return False

    async def clear(self) -> int:
        """
        Clear all pending tasks.

        Returns:
            Number of tasks cleared
        """
        async with self._lock:
            count = len(self._queue)
            for task in self._queue:
                task.status = TaskStatus.CANCELLED
            self._queue.clear()
            return count

    def get_pending_tasks(self) -> List[Task[T]]:
        """Get all pending tasks."""
        return [t for t in self._queue if t.status == TaskStatus.PENDING]

    def get_completed_tasks(self) -> List[Task[T]]:
        """Get all completed tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> List[Task[T]]:
        """Get all failed tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]


class QueueFullError(Exception):
    """Raised when queue is at capacity."""

    pass


class Worker:
    """
    Background worker that processes tasks from a queue.

    Example:
        queue = TaskQueue()
        worker = Worker(queue, num_workers=4)

        await worker.start()
        # ... enqueue tasks ...
        await worker.stop()
    """

    def __init__(
        self,
        queue: TaskQueue,
        num_workers: int = 1,
        name: str = "worker",
        on_task_complete: Optional[
            Callable[[Task, TaskResult], Awaitable[None]]
        ] = None,
        on_task_error: Optional[Callable[[Task, Exception], Awaitable[None]]] = None,
    ) -> None:
        """
        Initialize worker.

        Args:
            queue: Task queue to process
            num_workers: Number of concurrent workers
            name: Worker name for logging
            on_task_complete: Callback for completed tasks
            on_task_error: Callback for failed tasks
        """
        self._queue = queue
        self._num_workers = num_workers
        self._name = name
        self._on_complete = on_task_complete
        self._on_error = on_task_error
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._processed = 0
        self._errors = 0

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    @property
    def processed_count(self) -> int:
        """Get number of processed tasks."""
        return self._processed

    @property
    def error_count(self) -> int:
        """Get number of failed tasks."""
        return self._errors

    async def start(self) -> None:
        """Start the worker."""
        if self._running:
            return

        self._running = True
        self._tasks = [
            asyncio.create_task(self._worker_loop(i)) for i in range(self._num_workers)
        ]

    async def stop(self, wait: bool = True) -> None:
        """
        Stop the worker.

        Args:
            wait: Whether to wait for current tasks to finish
        """
        self._running = False

        if wait and self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        else:
            for task in self._tasks:
                task.cancel()

        self._tasks.clear()

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes tasks."""
        while self._running:
            try:
                task = await self._queue.dequeue(timeout=0.1)
                if task is None:
                    continue

                if task.status == TaskStatus.CANCELLED:
                    continue

                result = await self._queue.execute(task)
                self._processed += 1

                if result.success:
                    if self._on_complete:
                        await self._on_complete(task, result)
                else:
                    self._errors += 1

                    # Auto-retry if configured
                    if task.can_retry:
                        await self._queue.retry(task)
                    elif self._on_error:
                        await self._on_error(
                            task, Exception(result.error or "Unknown error")
                        )
            except asyncio.CancelledError:
                break
            except Exception:
                self._errors += 1


class DelayedQueue(Generic[T]):
    """
    Queue that supports delayed task execution.

    Example:
        queue = DelayedQueue()

        # Add task to run in 5 seconds
        await queue.put("message", delay=5.0)

        # Get task when ready
        item = await queue.get()
    """

    def __init__(self) -> None:
        """Initialize delayed queue."""
        self._heap: List[Tuple[float, int, T]] = []
        self._counter = 0
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    @property
    def size(self) -> int:
        """Get queue size."""
        return len(self._heap)

    async def put(
        self,
        item: T,
        delay: float = 0.0,
        run_at: Optional[datetime] = None,
    ) -> None:
        """
        Add an item to the queue.

        Args:
            item: Item to add
            delay: Delay in seconds from now
            run_at: Specific time to run
        """
        if run_at:
            run_time = run_at.timestamp()
        else:
            run_time = time.time() + delay

        async with self._lock:
            self._counter += 1
            heapq.heappush(self._heap, (run_time, self._counter, item))
            self._not_empty.set()

    async def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get the next ready item.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Item or None if timeout
        """
        deadline = time.time() + timeout if timeout else None

        while True:
            wait_time: Optional[float] = None
            async with self._lock:
                if not self._heap:
                    self._not_empty.clear()
                    if timeout is None:
                        return None
                    wait_time = 0.01  # Short wait for empty queue
                else:
                    run_time, _, item = self._heap[0]
                    now = time.time()

                    if run_time <= now:
                        heapq.heappop(self._heap)
                        return item

                    # Wait until item is ready or timeout
                    wait_time = run_time - now
                    if deadline:
                        wait_time = min(wait_time, deadline - now)
                        if wait_time <= 0:
                            return None

            # Check deadline
            if deadline and time.time() >= deadline:
                return None

            # Wait outside the lock
            try:
                await asyncio.wait_for(
                    self._not_empty.wait(),
                    timeout=wait_time,
                )
            except asyncio.TimeoutError:
                if deadline and time.time() >= deadline:
                    return None

    def peek(self) -> Optional[Tuple[datetime, T]]:
        """
        Peek at the next item without removing.

        Returns:
            Tuple of (run_time, item) or None
        """
        if self._heap:
            run_time, _, item = self._heap[0]
            return (datetime.fromtimestamp(run_time, tz=timezone.utc), item)
        return None


class RateLimitedQueue(Generic[T]):
    """
    Queue with rate limiting.

    Example:
        # 10 items per second
        queue = RateLimitedQueue(rate=10, per_seconds=1)

        await queue.put("item1")
        await queue.put("item2")

        # Items are returned respecting rate limit
        item = await queue.get()
    """

    def __init__(
        self,
        rate: int,
        per_seconds: float = 1.0,
    ) -> None:
        """
        Initialize rate-limited queue.

        Args:
            rate: Maximum items per time period
            per_seconds: Time period in seconds
        """
        self._queue: Deque[T] = deque()
        self._rate = rate
        self._per_seconds = per_seconds
        self._tokens = float(rate)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        """Get queue size."""
        return len(self._queue)

    async def put(self, item: T) -> None:
        """Add an item to the queue."""
        async with self._lock:
            self._queue.append(item)

    async def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get the next item, respecting rate limit.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Item or None if timeout/empty
        """
        deadline = time.time() + timeout if timeout else None

        while True:
            async with self._lock:
                if not self._queue:
                    return None

                # Update tokens
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(
                    float(self._rate),
                    self._tokens + (elapsed * self._rate / self._per_seconds),
                )
                self._last_update = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return self._queue.popleft()

                # Calculate wait time
                wait_time = (1.0 - self._tokens) * self._per_seconds / self._rate

            if deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                wait_time = min(wait_time, remaining)

            await asyncio.sleep(wait_time)


class Scheduler:
    """
    Simple task scheduler for recurring tasks.

    Example:
        scheduler = Scheduler()

        # Run every 5 minutes
        scheduler.schedule(my_task, interval=timedelta(minutes=5))

        # Run at specific time
        scheduler.schedule_at(my_task, datetime(2024, 1, 1, 12, 0))

        await scheduler.start()
    """

    def __init__(self) -> None:
        """Initialize scheduler."""
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def schedule(
        self,
        func: TaskFunc,
        interval: timedelta,
        name: str = "",
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        run_immediately: bool = False,
    ) -> str:
        """
        Schedule a recurring task.

        Args:
            func: Function to run
            interval: Time between runs
            name: Job name
            args: Function arguments
            kwargs: Function keyword arguments
            run_immediately: Run once immediately

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        job = ScheduledJob(
            id=job_id,
            func=func,
            interval=interval,
            name=name or getattr(func, "__name__", "unknown"),
            args=args,
            kwargs=kwargs or {},
            next_run=datetime.now(timezone.utc)
            if run_immediately
            else datetime.now(timezone.utc) + interval,
        )
        self._jobs[job_id] = job
        return job_id

    def schedule_at(
        self,
        func: TaskFunc,
        run_at: datetime,
        name: str = "",
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Schedule a one-time task at specific time.

        Args:
            func: Function to run
            run_at: When to run
            name: Job name
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        job = ScheduledJob(
            id=job_id,
            func=func,
            name=name or getattr(func, "__name__", "unknown"),
            args=args,
            kwargs=kwargs or {},
            next_run=run_at,
            one_time=True,
        )
        self._jobs[job_id] = job
        return job_id

    def cancel(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now(timezone.utc)
            jobs_to_run = []

            for job in list(self._jobs.values()):
                if job.next_run and job.next_run <= now:
                    jobs_to_run.append(job)

            for job in jobs_to_run:
                try:
                    if asyncio.iscoroutinefunction(job.func):
                        await job.func(*job.args, **job.kwargs)
                    else:
                        job.func(*job.args, **job.kwargs)

                    job.last_run = now
                    job.run_count += 1

                    if job.one_time:
                        del self._jobs[job.id]
                    elif job.interval:
                        job.next_run = now + job.interval
                except Exception:
                    job.error_count += 1

            await asyncio.sleep(0.1)

    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled jobs."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "run_count": job.run_count,
                "error_count": job.error_count,
                "interval": job.interval.total_seconds() if job.interval else None,
            }
            for job in self._jobs.values()
        ]


@dataclass
class ScheduledJob:
    """A scheduled job."""

    func: TaskFunc = field(repr=False)
    id: str = ""
    name: str = ""
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    interval: Optional[timedelta] = None
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    one_time: bool = False
    run_count: int = 0
    error_count: int = 0


class BatchProcessor(Generic[T, R]):
    """
    Process items in batches.

    Example:
        async def process_batch(items):
            return [item * 2 for item in items]

        processor = BatchProcessor(process_batch, batch_size=10)

        for i in range(100):
            await processor.add(i)

        results = await processor.flush()
    """

    def __init__(
        self,
        processor: Callable[[List[T]], Awaitable[List[R]]],
        batch_size: int = 100,
        max_wait: float = 1.0,
    ) -> None:
        """
        Initialize batch processor.

        Args:
            processor: Async function to process batches
            batch_size: Maximum batch size
            max_wait: Maximum seconds to wait before processing
        """
        self._processor = processor
        self._batch_size = batch_size
        self._max_wait = max_wait
        self._buffer: List[T] = []
        self._results: List[R] = []
        self._last_add = time.monotonic()
        self._lock = asyncio.Lock()

    async def add(self, item: T) -> Optional[List[R]]:
        """
        Add an item to the batch.

        Args:
            item: Item to add

        Returns:
            Results if batch was processed, None otherwise
        """
        async with self._lock:
            self._buffer.append(item)
            self._last_add = time.monotonic()

            if len(self._buffer) >= self._batch_size:
                return await self._process_batch()

            return None

    async def flush(self) -> List[R]:
        """
        Process any remaining items.

        Returns:
            Results from final batch
        """
        async with self._lock:
            if self._buffer:
                return await self._process_batch()
            return []

    async def _process_batch(self) -> List[R]:
        """Process the current batch."""
        if not self._buffer:
            return []

        items = self._buffer
        self._buffer = []

        results = await self._processor(items)
        self._results.extend(results)

        return results

    @property
    def pending_count(self) -> int:
        """Get number of pending items."""
        return len(self._buffer)

    @property
    def all_results(self) -> List[R]:
        """Get all results."""
        return self._results.copy()


# Factory functions


def create_task_queue(
    max_size: int = 0,
    default_priority: TaskPriority = TaskPriority.NORMAL,
) -> TaskQueue:
    """Create a task queue."""
    return TaskQueue(max_size=max_size, default_priority=default_priority)


def create_delayed_queue() -> DelayedQueue:
    """Create a delayed queue."""
    return DelayedQueue()


def create_rate_limited_queue(
    rate: int,
    per_seconds: float = 1.0,
) -> RateLimitedQueue:
    """Create a rate-limited queue."""
    return RateLimitedQueue(rate=rate, per_seconds=per_seconds)


def create_scheduler() -> Scheduler:
    """Create a scheduler."""
    return Scheduler()


def create_batch_processor(
    processor: Callable[[List[T]], Awaitable[List[R]]],
    batch_size: int = 100,
    max_wait: float = 1.0,
) -> BatchProcessor[T, R]:
    """Create a batch processor."""
    return BatchProcessor(processor, batch_size=batch_size, max_wait=max_wait)


def create_worker(
    queue: TaskQueue,
    num_workers: int = 1,
    name: str = "worker",
) -> Worker:
    """Create a worker."""
    return Worker(queue, num_workers=num_workers, name=name)
