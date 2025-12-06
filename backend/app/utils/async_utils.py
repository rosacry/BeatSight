"""
Async utilities for concurrent operations and task management.

Provides helpers for running async tasks concurrently, with timeouts,
rate limiting, and error handling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

__all__ = [
    "gather_with_concurrency",
    "gather_with_timeout",
    "run_with_timeout",
    "first_completed",
    "retry_async",
    "async_map",
    "async_filter",
    "chunk_async",
    "AsyncSemaphore",
    "AsyncBatcher",
    "AsyncThrottle",
    "timeout_context",
]

logger = structlog.get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


async def gather_with_concurrency(
    tasks: Sequence[Awaitable[T]],
    *,
    limit: int = 10,
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """
    Run tasks concurrently with a maximum concurrency limit.

    Args:
        tasks: Sequence of awaitables to run
        limit: Maximum number of concurrent tasks
        return_exceptions: If True, exceptions are returned; if False, raised

    Returns:
        List of results in the same order as input tasks

    Example:
        async def fetch(url):
            ...

        urls = ["http://a.com", "http://b.com", ...]
        results = await gather_with_concurrency(
            [fetch(url) for url in urls],
            limit=5,
        )
    """
    semaphore = asyncio.Semaphore(limit)

    async def limited_task(task: Awaitable[T]) -> T:
        async with semaphore:
            return await task

    return await asyncio.gather(
        *[limited_task(task) for task in tasks],
        return_exceptions=return_exceptions,
    )


async def gather_with_timeout(
    tasks: Sequence[Awaitable[T]],
    *,
    timeout: float,
    return_exceptions: bool = True,
) -> list[T | BaseException]:
    """
    Run tasks concurrently with a global timeout.

    Args:
        tasks: Sequence of awaitables to run
        timeout: Maximum time to wait for all tasks
        return_exceptions: If True, exceptions are returned; if False, raised

    Returns:
        List of results (may include TimeoutError for timed-out tasks)

    Raises:
        asyncio.TimeoutError: If timeout exceeded and return_exceptions=False

    Example:
        results = await gather_with_timeout(
            [fetch(url) for url in urls],
            timeout=30.0,
        )
    """
    try:
        return await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=return_exceptions),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        if return_exceptions:
            # Cancel remaining tasks and return timeout errors
            return [asyncio.TimeoutError("Task timed out") for _ in tasks]
        raise


async def run_with_timeout(
    coro: Awaitable[T],
    *,
    timeout: float,
    default: T | None = None,
) -> T | None:
    """
    Run a coroutine with a timeout, returning default if it times out.

    Args:
        coro: Coroutine to run
        timeout: Maximum time to wait
        default: Value to return on timeout

    Returns:
        Result of coroutine or default value

    Example:
        result = await run_with_timeout(
            slow_operation(),
            timeout=5.0,
            default=None,
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return default


async def first_completed(
    tasks: Sequence[Awaitable[T]],
    *,
    cancel_remaining: bool = True,
) -> T:
    """
    Return the result of the first task to complete.

    Args:
        tasks: Sequence of awaitables to run
        cancel_remaining: If True, cancel other tasks after first completes

    Returns:
        Result of first completed task

    Raises:
        ValueError: If no tasks provided
        Exception: If the first completed task raised an exception

    Example:
        # Race multiple data sources
        result = await first_completed([
            fetch_from_cache(key),
            fetch_from_db(key),
        ])
    """
    if not tasks:
        raise ValueError("No tasks provided")

    # Create task objects
    async_tasks = [asyncio.ensure_future(t) for t in tasks]

    try:
        done, pending = await asyncio.wait(
            async_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Get the first completed result
        first = done.pop()
        result = first.result()  # May raise if task failed

        return result

    finally:
        if cancel_remaining:
            for task in async_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to call (no arguments)
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to retry on

    Returns:
        Result of successful function call

    Raises:
        Exception: Last exception if all retries fail

    Example:
        result = await retry_async(
            lambda: fetch_data(url),
            max_attempts=3,
            delay=1.0,
        )
    """
    last_exception: BaseException | None = None
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                logger.warning(
                    "Retry attempt failed",
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    delay=current_delay,
                    error=str(e),
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(
                    "All retry attempts failed",
                    max_attempts=max_attempts,
                    error=str(e),
                )

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry failure")


async def async_map(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    concurrency: int = 10,
) -> list[R]:
    """
    Apply an async function to each item with concurrency limit.

    Args:
        func: Async function to apply
        items: Items to process
        concurrency: Maximum concurrent operations

    Returns:
        List of results in the same order as input

    Example:
        async def process(item):
            return item * 2

        results = await async_map(process, [1, 2, 3, 4, 5])
    """
    tasks = [func(item) for item in items]
    results = await gather_with_concurrency(tasks, limit=concurrency)
    return results  # type: ignore


async def async_filter(
    predicate: Callable[[T], Awaitable[bool]],
    items: Iterable[T],
    *,
    concurrency: int = 10,
) -> list[T]:
    """
    Filter items using an async predicate with concurrency limit.

    Args:
        predicate: Async function returning True to keep item
        items: Items to filter
        concurrency: Maximum concurrent operations

    Returns:
        List of items where predicate returned True

    Example:
        async def is_valid(item):
            return await validate(item)

        valid_items = await async_filter(is_valid, items)
    """
    items_list = list(items)
    tasks = [predicate(item) for item in items_list]
    results = await gather_with_concurrency(tasks, limit=concurrency)

    return [item for item, keep in zip(items_list, results) if keep is True]


async def chunk_async(
    items: Sequence[T],
    chunk_size: int,
    func: Callable[[list[T]], Awaitable[R]],
) -> list[R]:
    """
    Process items in chunks using an async function.

    Args:
        items: Sequence of items to process
        chunk_size: Number of items per chunk
        func: Async function to process each chunk

    Returns:
        List of results from each chunk

    Example:
        async def batch_insert(records):
            await db.insert_many(records)

        await chunk_async(records, chunk_size=100, func=batch_insert)
    """
    results: list[R] = []
    for i in range(0, len(items), chunk_size):
        chunk = list(items[i : i + chunk_size])
        result = await func(chunk)
        results.append(result)
    return results


@dataclass
class AsyncSemaphore:
    """
    Async semaphore wrapper with statistics tracking.

    Example:
        semaphore = AsyncSemaphore(limit=5)
        async with semaphore:
            await do_work()

        print(f"Total acquisitions: {semaphore.total_acquisitions}")
    """

    limit: int
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)
    _total_acquisitions: int = field(default=0, init=False)
    _current_count: int = field(default=0, init=False)
    _max_concurrent: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.limit)

    async def __aenter__(self) -> AsyncSemaphore:
        await self._semaphore.acquire()
        self._total_acquisitions += 1
        self._current_count += 1
        self._max_concurrent = max(self._max_concurrent, self._current_count)
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._current_count -= 1
        self._semaphore.release()

    @property
    def total_acquisitions(self) -> int:
        """Total number of times semaphore was acquired."""
        return self._total_acquisitions

    @property
    def current_count(self) -> int:
        """Current number of active acquisitions."""
        return self._current_count

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent acquisitions observed."""
        return self._max_concurrent

    @property
    def available(self) -> int:
        """Number of available slots."""
        return self.limit - self._current_count


@dataclass
class AsyncBatcher:
    """
    Batch items and process them when batch is full or timeout expires.

    Example:
        async def process_batch(items):
            await db.insert_many(items)

        batcher = AsyncBatcher(
            batch_size=100,
            timeout=5.0,
            processor=process_batch,
        )

        async with batcher:
            for item in items:
                await batcher.add(item)
    """

    batch_size: int
    timeout: float
    processor: Callable[[list[Any]], Awaitable[Any]]
    _items: list[Any] = field(default_factory=list, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _timer_task: asyncio.Task[None] | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    async def __aenter__(self) -> AsyncBatcher:
        self._closed = False
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def add(self, item: Any) -> None:
        """Add an item to the batch."""
        async with self._lock:
            self._items.append(item)

            if len(self._items) >= self.batch_size:
                await self._flush_locked()
            elif self._timer_task is None and self.timeout > 0:
                self._timer_task = asyncio.create_task(self._timeout_flush())

    async def flush(self) -> None:
        """Manually flush the current batch."""
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self) -> None:
        """Flush batch (must hold lock)."""
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None

        if self._items:
            items = self._items
            self._items = []
            await self.processor(items)

    async def _timeout_flush(self) -> None:
        """Flush batch after timeout."""
        await asyncio.sleep(self.timeout)
        async with self._lock:
            if self._items:
                await self._flush_locked()

    async def close(self) -> None:
        """Close the batcher and flush remaining items."""
        self._closed = True
        await self.flush()


@dataclass
class AsyncThrottle:
    """
    Rate limiter for async operations.

    Limits operations to a maximum rate per second.

    Example:
        throttle = AsyncThrottle(rate=10)  # 10 ops/second

        for item in items:
            async with throttle:
                await process(item)
    """

    rate: float  # Operations per second
    _last_call: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def interval(self) -> float:
        """Minimum interval between operations."""
        return 1.0 / self.rate

    async def __aenter__(self) -> AsyncThrottle:
        async with self._lock:
            import time

            now = time.monotonic()
            elapsed = now - self._last_call

            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)

            self._last_call = time.monotonic()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def wait(self) -> None:
        """Wait until next operation is allowed."""
        async with self:
            pass


class timeout_context:
    """
    Async context manager for timeouts.

    Example:
        async with timeout_context(5.0) as ctx:
            await slow_operation()

        if ctx.expired:
            print("Operation timed out")
    """

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.expired = False
        self._task: asyncio.Task[Any] | None = None

    async def __aenter__(self) -> timeout_context:
        self._task = asyncio.current_task()
        self._timeout_handle = asyncio.get_event_loop().call_later(
            self.timeout,
            self._on_timeout,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self._timeout_handle.cancel()

        if exc_type is asyncio.CancelledError and self.expired:
            # Convert cancellation due to timeout to TimeoutError
            raise asyncio.TimeoutError("Operation timed out")

        return False

    def _on_timeout(self) -> None:
        self.expired = True
        if self._task:
            self._task.cancel()
