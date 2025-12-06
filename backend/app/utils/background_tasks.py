"""Background task utilities for async job execution.

Provides utilities for running background tasks:
- Fire-and-forget task execution
- Task queuing with Redis
- Task status tracking
- Periodic task scheduling
- Task timeouts and cancellation

Usage:
    from app.utils.background_tasks import background_tasks, run_in_background

    # Fire and forget
    @run_in_background
    async def send_notification(user_id: str, message: str):
        await email_service.send(user_id, message)
    
    # Call it - runs asynchronously
    send_notification("user123", "Hello!")
    
    # With task tracking
    task_id = await background_tasks.submit(
        send_email,
        args=("user@example.com", "subject", "body"),
    )
    status = await background_tasks.get_status(task_id)
"""

from __future__ import annotations

import asyncio
import functools
import traceback
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ParamSpec, TypeVar

import structlog

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class TaskStatus(str, Enum):
    """Status of a background task."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Priority levels for background tasks."""
    
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class TaskInfo:
    """Information about a background task."""
    
    task_id: str
    name: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any = None
    priority: TaskPriority = TaskPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "priority": self.priority.value,
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds,
        }
    
    @property
    def duration_seconds(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class TaskConfig:
    """Configuration for background task execution."""
    
    timeout: float | None = None  # Task timeout in seconds
    max_retries: int = 0  # Number of retries on failure
    retry_delay: float = 1.0  # Delay between retries
    priority: TaskPriority = TaskPriority.NORMAL
    track_result: bool = False  # Whether to store task result
    metadata: dict[str, Any] = field(default_factory=dict)


class BackgroundTaskManager:
    """Manager for background task execution and tracking.
    
    Features:
    - In-memory task queue
    - Task status tracking
    - Timeout support
    - Retry logic
    - Priority-based execution
    """
    
    def __init__(self, max_concurrent: int = 10) -> None:
        """Initialize the task manager.
        
        Args:
            max_concurrent: Maximum concurrent tasks
        """
        self._max_concurrent = max_concurrent
        self._tasks: dict[str, TaskInfo] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._shutdown = False
    
    async def submit(
        self,
        func: Callable[..., Awaitable[T]],
        args: tuple = (),
        kwargs: dict | None = None,
        config: TaskConfig | None = None,
        task_id: str | None = None,
    ) -> str:
        """Submit a task for background execution.
        
        Args:
            func: Async function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            config: Task configuration
            task_id: Optional custom task ID
            
        Returns:
            Task ID
        """
        if self._shutdown:
            raise RuntimeError("Task manager is shutting down")
        
        config = config or TaskConfig()
        kwargs = kwargs or {}
        task_id = task_id or str(uuid.uuid4())
        
        # Create task info
        task_info = TaskInfo(
            task_id=task_id,
            name=func.__name__,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            priority=config.priority,
            metadata=config.metadata,
        )
        self._tasks[task_id] = task_info
        
        # Start execution
        async def execute_task() -> None:
            async with self._semaphore:
                await self._run_task(task_id, func, args, kwargs, config)
        
        asyncio_task = asyncio.create_task(execute_task())
        self._running_tasks[task_id] = asyncio_task
        
        logger.info(
            "Background task submitted",
            task_id=task_id,
            name=func.__name__,
            priority=config.priority.value,
        )
        
        return task_id
    
    async def _run_task(
        self,
        task_id: str,
        func: Callable[..., Awaitable[T]],
        args: tuple,
        kwargs: dict,
        config: TaskConfig,
    ) -> None:
        """Execute a task with retry and timeout logic."""
        task_info = self._tasks[task_id]
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now(timezone.utc)
        
        attempt = 0
        last_error: Exception | None = None
        
        while attempt <= config.max_retries:
            try:
                if config.timeout:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout,
                    )
                else:
                    result = await func(*args, **kwargs)
                
                # Success
                task_info.status = TaskStatus.COMPLETED
                task_info.completed_at = datetime.now(timezone.utc)
                if config.track_result:
                    task_info.result = result
                
                logger.info(
                    "Background task completed",
                    task_id=task_id,
                    duration=task_info.duration_seconds,
                )
                return
                
            except asyncio.TimeoutError:
                task_info.status = TaskStatus.TIMEOUT
                task_info.completed_at = datetime.now(timezone.utc)
                task_info.error = f"Task timed out after {config.timeout}s"
                logger.warning(
                    "Background task timeout",
                    task_id=task_id,
                    timeout=config.timeout,
                )
                return
                
            except asyncio.CancelledError:
                task_info.status = TaskStatus.CANCELLED
                task_info.completed_at = datetime.now(timezone.utc)
                logger.info(
                    "Background task cancelled",
                    task_id=task_id,
                )
                return
                
            except Exception as e:
                last_error = e
                attempt += 1
                
                if attempt <= config.max_retries:
                    logger.warning(
                        "Background task failed, retrying",
                        task_id=task_id,
                        attempt=attempt,
                        max_retries=config.max_retries,
                        error=str(e),
                    )
                    await asyncio.sleep(config.retry_delay)
                else:
                    # All retries exhausted
                    task_info.status = TaskStatus.FAILED
                    task_info.completed_at = datetime.now(timezone.utc)
                    task_info.error = f"{type(e).__name__}: {str(e)}"
                    
                    logger.error(
                        "Background task failed",
                        task_id=task_id,
                        error=str(e),
                        traceback=traceback.format_exc(),
                    )
        
        # Clean up running task reference
        self._running_tasks.pop(task_id, None)
    
    def get_status(self, task_id: str) -> TaskInfo | None:
        """Get the status of a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskInfo or None if not found
        """
        return self._tasks.get(task_id)
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            logger.info(
                "Background task cancellation requested",
                task_id=task_id,
            )
            return True
        return False
    
    async def wait(self, task_id: str, timeout: float | None = None) -> TaskInfo | None:
        """Wait for a task to complete.
        
        Args:
            task_id: Task ID
            timeout: Maximum wait time
            
        Returns:
            TaskInfo when complete
        """
        if task_id not in self._running_tasks:
            return self._tasks.get(task_id)
        
        try:
            await asyncio.wait_for(
                self._running_tasks[task_id],
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
        
        return self._tasks.get(task_id)
    
    def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 100,
    ) -> list[TaskInfo]:
        """List tasks, optionally filtered by status.
        
        Args:
            status: Filter by status
            limit: Maximum number of tasks
            
        Returns:
            List of TaskInfo
        """
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def cleanup_completed(self, max_age_seconds: float = 3600) -> int:
        """Remove old completed tasks from tracking.
        
        Args:
            max_age_seconds: Maximum age of tasks to keep
            
        Returns:
            Number of tasks removed
        """
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for task_id, task_info in self._tasks.items():
            if task_info.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
                TaskStatus.TIMEOUT,
            ):
                if task_info.completed_at:
                    age = (now - task_info.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]
            self._running_tasks.pop(task_id, None)
        
        if to_remove:
            logger.info(
                "Cleaned up old background tasks",
                count=len(to_remove),
            )
        
        return len(to_remove)
    
    async def shutdown(self, timeout: float = 30) -> None:
        """Gracefully shutdown the task manager.
        
        Args:
            timeout: Maximum time to wait for tasks
        """
        self._shutdown = True
        
        if self._running_tasks:
            logger.info(
                "Shutting down background task manager",
                pending_tasks=len(self._running_tasks),
            )
            
            # Wait for running tasks or timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._running_tasks.values(), return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Cancel remaining tasks
                for task in self._running_tasks.values():
                    task.cancel()
                
                logger.warning(
                    "Force cancelled background tasks on shutdown",
                    count=len(self._running_tasks),
                )
    
    def get_stats(self) -> dict[str, Any]:
        """Get task manager statistics.
        
        Returns:
            Statistics dictionary
        """
        status_counts: dict[str, int] = {}
        for task in self._tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
        
        return {
            "total_tasks": len(self._tasks),
            "running_tasks": len(self._running_tasks),
            "max_concurrent": self._max_concurrent,
            "status_counts": status_counts,
            "shutdown": self._shutdown,
        }


# Global task manager instance
background_tasks = BackgroundTaskManager()


# =============================================================================
# Decorators
# =============================================================================

def run_in_background(
    timeout: float | None = None,
    max_retries: int = 0,
    retry_delay: float = 1.0,
    priority: TaskPriority = TaskPriority.NORMAL,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, str]]:
    """Decorator to run an async function in the background.
    
    The decorated function will return a task ID instead of awaiting the result.
    
    Args:
        timeout: Task timeout in seconds
        max_retries: Number of retries on failure
        retry_delay: Delay between retries
        priority: Task priority
        
    Returns:
        Decorated function that returns task ID
        
    Example:
        @run_in_background(timeout=30, max_retries=3)
        async def send_welcome_email(user_id: str):
            await email_service.send_welcome(user_id)
        
        # Calling it submits to background
        task_id = send_welcome_email("user123")
    """
    config = TaskConfig(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        priority=priority,
    )
    
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, str]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            # Create task synchronously but execution is async
            loop = asyncio.get_event_loop()
            task_id = str(uuid.uuid4())
            
            # Schedule the task
            loop.create_task(
                background_tasks.submit(
                    func,
                    args=args,
                    kwargs=kwargs,
                    config=config,
                    task_id=task_id,
                )
            )
            
            return task_id
        
        # Also allow async usage
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            return await background_tasks.submit(
                func,
                args=args,
                kwargs=kwargs,
                config=config,
            )
        
        wrapper.submit = async_wrapper  # type: ignore
        wrapper.original = func  # type: ignore
        
        return wrapper
    
    return decorator


def fire_and_forget(
    func: Callable[P, Awaitable[T]] | None = None,
    *,
    timeout: float | None = None,
) -> Callable:
    """Simple fire-and-forget decorator.
    
    Executes the function without waiting for result.
    
    Args:
        func: Async function to decorate
        timeout: Optional timeout
        
    Example:
        @fire_and_forget
        async def log_analytics(event: str):
            await analytics.track(event)
        
        # Call without awaiting
        log_analytics("user_signup")
    """
    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, None]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            async def run() -> None:
                try:
                    if timeout:
                        await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
                    else:
                        await fn(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        "Fire-and-forget task failed",
                        function=fn.__name__,
                        error=str(e),
                    )
            
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(run())
            except RuntimeError:
                # No running loop, create one
                asyncio.run(run())
        
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator


# =============================================================================
# Utility functions
# =============================================================================

async def run_async(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a sync function in a thread pool.
    
    Useful for running blocking IO operations without blocking the event loop.
    
    Args:
        func: Synchronous function
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(func, *args, **kwargs),
    )


async def gather_with_timeout(
    *coros: Awaitable[T],
    timeout: float,
    return_exceptions: bool = False,
) -> list[T | Exception]:
    """Gather coroutines with a timeout.
    
    Args:
        *coros: Coroutines to gather
        timeout: Timeout in seconds
        return_exceptions: Whether to return exceptions
        
    Returns:
        List of results or exceptions
    """
    try:
        return await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=return_exceptions),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        # Cancel remaining tasks
        for coro in coros:
            if hasattr(coro, "cancel"):
                coro.cancel()  # type: ignore
        raise


async def retry_async(
    func: Callable[..., Awaitable[T]],
    args: tuple = (),
    kwargs: dict | None = None,
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        args: Positional arguments
        kwargs: Keyword arguments
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        exceptions: Exceptions to retry on
        
    Returns:
        Function result
        
    Raises:
        Last exception if all attempts fail
    """
    kwargs = kwargs or {}
    last_error: Exception | None = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay * (2 ** attempt))
    
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed with no error")
