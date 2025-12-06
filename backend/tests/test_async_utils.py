"""Tests for async utilities."""

from __future__ import annotations

import asyncio

import pytest

from app.utils.async_utils import (
    AsyncBatcher,
    AsyncSemaphore,
    AsyncThrottle,
    async_filter,
    async_map,
    chunk_async,
    first_completed,
    gather_with_concurrency,
    gather_with_timeout,
    retry_async,
    run_with_timeout,
    timeout_context,
)


class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency."""

    @pytest.mark.asyncio
    async def test_basic_concurrency(self):
        """Test basic concurrent execution."""
        results = []

        async def task(n: int) -> int:
            results.append(n)
            await asyncio.sleep(0.01)
            return n * 2

        output = await gather_with_concurrency(
            [task(i) for i in range(5)],
            limit=3,
        )

        assert output == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        """Test that concurrency limit is respected."""
        concurrent_count = 0
        max_concurrent = 0

        async def task() -> int:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return 1

        await gather_with_concurrency(
            [task() for _ in range(10)],
            limit=3,
        )

        assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_return_exceptions(self):
        """Test returning exceptions."""

        async def failing_task(n: int) -> int:
            if n == 2:
                raise ValueError("Task 2 failed")
            return n

        results = await gather_with_concurrency(
            [failing_task(i) for i in range(5)],
            limit=3,
            return_exceptions=True,
        )

        assert results[0] == 0
        assert results[1] == 1
        assert isinstance(results[2], ValueError)
        assert results[3] == 3
        assert results[4] == 4

    @pytest.mark.asyncio
    async def test_raise_exceptions(self):
        """Test raising exceptions."""

        async def failing_task(n: int) -> int:
            if n == 2:
                raise ValueError("Task 2 failed")
            return n

        with pytest.raises(ValueError):
            await gather_with_concurrency(
                [failing_task(i) for i in range(5)],
                limit=3,
                return_exceptions=False,
            )


class TestGatherWithTimeout:
    """Tests for gather_with_timeout."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """Test tasks complete within timeout."""

        async def quick_task(n: int) -> int:
            await asyncio.sleep(0.01)
            return n

        results = await gather_with_timeout(
            [quick_task(i) for i in range(3)],
            timeout=1.0,
        )

        assert results == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_timeout_returns_errors(self):
        """Test timeout returns errors when return_exceptions=True."""

        async def slow_task() -> int:
            await asyncio.sleep(10.0)
            return 1

        results = await gather_with_timeout(
            [slow_task() for _ in range(3)],
            timeout=0.05,
            return_exceptions=True,
        )

        assert all(isinstance(r, asyncio.TimeoutError) for r in results)

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """Test timeout raises when return_exceptions=False."""

        async def slow_task() -> int:
            await asyncio.sleep(10.0)
            return 1

        with pytest.raises(asyncio.TimeoutError):
            await gather_with_timeout(
                [slow_task()],
                timeout=0.05,
                return_exceptions=False,
            )


class TestRunWithTimeout:
    """Tests for run_with_timeout."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """Test coroutine completes within timeout."""

        async def quick():
            await asyncio.sleep(0.01)
            return "done"

        result = await run_with_timeout(quick(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_returns_default(self):
        """Test timeout returns default value."""

        async def slow():
            await asyncio.sleep(10.0)
            return "done"

        result = await run_with_timeout(slow(), timeout=0.05, default="timeout")
        assert result == "timeout"

    @pytest.mark.asyncio
    async def test_timeout_returns_none_by_default(self):
        """Test timeout returns None by default."""

        async def slow():
            await asyncio.sleep(10.0)
            return "done"

        result = await run_with_timeout(slow(), timeout=0.05)
        assert result is None


class TestFirstCompleted:
    """Tests for first_completed."""

    @pytest.mark.asyncio
    async def test_returns_fastest(self):
        """Test returns result of fastest task."""

        async def fast():
            await asyncio.sleep(0.01)
            return "fast"

        async def slow():
            await asyncio.sleep(1.0)
            return "slow"

        result = await first_completed([fast(), slow()])
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_cancels_remaining(self):
        """Test cancels remaining tasks."""
        slow_completed = False

        async def fast():
            return "fast"

        async def slow():
            nonlocal slow_completed
            await asyncio.sleep(1.0)
            slow_completed = True
            return "slow"

        result = await first_completed([fast(), slow()], cancel_remaining=True)

        assert result == "fast"
        await asyncio.sleep(0.1)  # Give time for cancellation
        assert not slow_completed

    @pytest.mark.asyncio
    async def test_empty_tasks_raises(self):
        """Test empty tasks raises ValueError."""
        with pytest.raises(ValueError):
            await first_completed([])

    @pytest.mark.asyncio
    async def test_exception_propagates(self):
        """Test exception from first task propagates."""

        async def failing():
            raise ValueError("Failed")

        async def slow():
            await asyncio.sleep(1.0)
            return "slow"

        with pytest.raises(ValueError):
            await first_completed([failing(), slow()])


class TestRetryAsync:
    """Tests for retry_async."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful first attempt."""
        attempts = 0

        async def succeeds():
            nonlocal attempts
            attempts += 1
            return "success"

        result = await retry_async(succeeds)
        assert result == "success"
        assert attempts == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_retry(self):
        """Test succeeds after retry."""
        attempts = 0

        async def eventually_succeeds():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("Not yet")
            return "success"

        result = await retry_async(
            eventually_succeeds,
            max_attempts=3,
            delay=0.01,
        )
        assert result == "success"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_attempts(self):
        """Test fails after max attempts."""
        attempts = 0

        async def always_fails():
            nonlocal attempts
            attempts += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            await retry_async(
                always_fails,
                max_attempts=3,
                delay=0.01,
            )
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_only_retries_specified_exceptions(self):
        """Test only retries specified exceptions."""
        attempts = 0

        async def type_error():
            nonlocal attempts
            attempts += 1
            raise TypeError("Type error")

        with pytest.raises(TypeError):
            await retry_async(
                type_error,
                max_attempts=3,
                delay=0.01,
                exceptions=(ValueError,),
            )
        assert attempts == 1  # No retries for TypeError


class TestAsyncMap:
    """Tests for async_map."""

    @pytest.mark.asyncio
    async def test_basic_map(self):
        """Test basic async map."""

        async def double(x: int) -> int:
            return x * 2

        results = await async_map(double, [1, 2, 3, 4, 5])
        assert results == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_preserves_order(self):
        """Test preserves order despite different completion times."""

        async def variable_time(x: int) -> int:
            await asyncio.sleep((5 - x) * 0.01)
            return x

        results = await async_map(variable_time, [1, 2, 3, 4, 5])
        assert results == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_respects_concurrency(self):
        """Test respects concurrency limit."""
        concurrent = 0
        max_concurrent = 0

        async def track(x: int) -> int:
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.01)
            concurrent -= 1
            return x

        await async_map(track, range(10), concurrency=3)
        assert max_concurrent <= 3


class TestAsyncFilter:
    """Tests for async_filter."""

    @pytest.mark.asyncio
    async def test_basic_filter(self):
        """Test basic async filter."""

        async def is_even(x: int) -> bool:
            return x % 2 == 0

        results = await async_filter(is_even, [1, 2, 3, 4, 5, 6])
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """Test filter returning empty result."""

        async def always_false(x: int) -> bool:
            return False

        results = await async_filter(always_false, [1, 2, 3])
        assert results == []

    @pytest.mark.asyncio
    async def test_all_pass(self):
        """Test all items pass filter."""

        async def always_true(x: int) -> bool:
            return True

        items = [1, 2, 3]
        results = await async_filter(always_true, items)
        assert results == items


class TestChunkAsync:
    """Tests for chunk_async."""

    @pytest.mark.asyncio
    async def test_basic_chunking(self):
        """Test basic chunking."""
        chunks_processed = []

        async def process(chunk: list[int]) -> int:
            chunks_processed.append(chunk)
            return sum(chunk)

        results = await chunk_async([1, 2, 3, 4, 5], chunk_size=2, func=process)

        assert chunks_processed == [[1, 2], [3, 4], [5]]
        assert results == [3, 7, 5]

    @pytest.mark.asyncio
    async def test_exact_chunks(self):
        """Test when items divide evenly."""
        chunks = []

        async def process(chunk: list[int]) -> int:
            chunks.append(chunk)
            return len(chunk)

        await chunk_async([1, 2, 3, 4], chunk_size=2, func=process)
        assert chunks == [[1, 2], [3, 4]]


class TestAsyncSemaphore:
    """Tests for AsyncSemaphore."""

    @pytest.mark.asyncio
    async def test_limits_concurrency(self):
        """Test semaphore limits concurrency."""
        semaphore = AsyncSemaphore(limit=2)

        async def task():
            async with semaphore:
                await asyncio.sleep(0.05)

        await asyncio.gather(*[task() for _ in range(5)])

        assert semaphore.max_concurrent <= 2
        assert semaphore.total_acquisitions == 5

    @pytest.mark.asyncio
    async def test_statistics(self):
        """Test semaphore statistics."""
        semaphore = AsyncSemaphore(limit=3)

        async with semaphore:
            assert semaphore.current_count == 1
            assert semaphore.available == 2

        assert semaphore.current_count == 0
        assert semaphore.total_acquisitions == 1


class TestAsyncBatcher:
    """Tests for AsyncBatcher."""

    @pytest.mark.asyncio
    async def test_flushes_on_size(self):
        """Test flushes when batch size reached."""
        batches = []

        async def process(items):
            batches.append(items)

        async with AsyncBatcher(
            batch_size=3, timeout=10.0, processor=process
        ) as batcher:
            for i in range(5):
                await batcher.add(i)

        assert batches == [[0, 1, 2], [3, 4]]

    @pytest.mark.asyncio
    async def test_flushes_on_close(self):
        """Test flushes remaining on close."""
        batches = []

        async def process(items):
            batches.append(items)

        async with AsyncBatcher(
            batch_size=10, timeout=10.0, processor=process
        ) as batcher:
            await batcher.add(1)
            await batcher.add(2)

        assert batches == [[1, 2]]

    @pytest.mark.asyncio
    async def test_manual_flush(self):
        """Test manual flush."""
        batches = []

        async def process(items):
            batches.append(items)

        async with AsyncBatcher(
            batch_size=10, timeout=10.0, processor=process
        ) as batcher:
            await batcher.add(1)
            await batcher.flush()
            await batcher.add(2)

        assert batches == [[1], [2]]


class TestAsyncThrottle:
    """Tests for AsyncThrottle."""

    @pytest.mark.asyncio
    async def test_throttles_rate(self):
        """Test throttles to specified rate."""
        throttle = AsyncThrottle(rate=100)  # 100 ops/sec = 10ms interval

        import time

        start = time.monotonic()

        for _ in range(5):
            async with throttle:
                pass

        elapsed = time.monotonic() - start
        # Should take at least 4 intervals (5 ops, first is immediate)
        assert elapsed >= 0.035  # ~4 * 10ms with some tolerance

    @pytest.mark.asyncio
    async def test_interval_property(self):
        """Test interval calculation."""
        throttle = AsyncThrottle(rate=10)
        assert throttle.interval == 0.1

    @pytest.mark.asyncio
    async def test_wait_method(self):
        """Test wait method."""
        throttle = AsyncThrottle(rate=100)

        await throttle.wait()
        await throttle.wait()
        # Should complete without error


class TestTimeoutContext:
    """Tests for timeout_context."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """Test operation completes within timeout."""
        async with timeout_context(1.0) as ctx:
            await asyncio.sleep(0.01)

        assert not ctx.expired

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        """Test raises TimeoutError on timeout."""
        with pytest.raises(asyncio.TimeoutError):
            async with timeout_context(0.05):
                await asyncio.sleep(1.0)
