"""Tests for metrics utilities in app/utils/metrics.py."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest

from app.utils.metrics import (
    # Core classes
    MetricType,
    MetricValue,
    HealthStatus,
    HealthCheck,
    # Metrics
    Counter,
    CounterChild,
    Gauge,
    GaugeChild,
    Histogram,
    HistogramChild,
    Summary,
    # Timer
    Timer,
    # Health
    HealthChecker,
    # Registry
    MetricsRegistry,
    StatsCollector,
    # Decorators
    timed,
    counted,
    # Factory functions
    create_registry,
    create_health_checker,
    create_stats_collector,
    get_registry,
    reset_registry,
)


class TestMetricValue:
    """Tests for MetricValue class."""
    
    def test_metric_value_creation(self):
        """Test creating a metric value."""
        mv = MetricValue(
            name="test_metric",
            value=42.0,
            metric_type=MetricType.COUNTER,
            labels={"env": "test"},
            description="Test metric",
        )
        
        assert mv.name == "test_metric"
        assert mv.value == 42.0
        assert mv.metric_type == MetricType.COUNTER
        assert mv.labels == {"env": "test"}
    
    def test_metric_value_to_dict(self):
        """Test metric value serialization."""
        mv = MetricValue(
            name="test",
            value=10,
            metric_type=MetricType.GAUGE,
        )
        
        data = mv.to_dict()
        assert data["name"] == "test"
        assert data["value"] == 10
        assert data["type"] == "gauge"


class TestCounter:
    """Tests for Counter metric."""
    
    def test_counter_increment(self):
        """Test counter increment."""
        counter = Counter("requests_total")
        
        counter.inc()
        assert counter.get() == 1
        
        counter.inc(5)
        assert counter.get() == 6
    
    def test_counter_negative_raises(self):
        """Test counter rejects negative values."""
        counter = Counter("test")
        
        with pytest.raises(ValueError):
            counter.inc(-1)
    
    def test_counter_with_labels(self):
        """Test counter with labels."""
        counter = Counter("requests", labels=["method", "path"])
        
        counter.inc(method="GET", path="/api")
        counter.inc(2, method="POST", path="/api")
        
        assert counter.get(method="GET", path="/api") == 1
        assert counter.get(method="POST", path="/api") == 2
    
    def test_counter_child(self):
        """Test counter child with preset labels."""
        counter = Counter("requests")
        child = counter.labels(method="GET")
        
        child.inc()
        child.inc(2)
        
        assert child.get() == 3
        assert counter.get(method="GET") == 3
    
    def test_counter_collect(self):
        """Test counter collection."""
        counter = Counter("test", description="Test counter")
        counter.inc()
        counter.inc(method="POST")
        
        values = counter.collect()
        assert len(values) == 2


class TestGauge:
    """Tests for Gauge metric."""
    
    def test_gauge_set(self):
        """Test gauge set."""
        gauge = Gauge("temperature")
        
        gauge.set(72.5)
        assert gauge.get() == 72.5
        
        gauge.set(65.0)
        assert gauge.get() == 65.0
    
    def test_gauge_increment(self):
        """Test gauge increment."""
        gauge = Gauge("connections")
        
        gauge.inc()
        assert gauge.get() == 1
        
        gauge.inc(5)
        assert gauge.get() == 6
    
    def test_gauge_decrement(self):
        """Test gauge decrement."""
        gauge = Gauge("connections")
        gauge.set(10)
        
        gauge.dec()
        assert gauge.get() == 9
        
        gauge.dec(5)
        assert gauge.get() == 4
    
    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauge = Gauge("memory", labels=["server"])
        
        gauge.set(1024, server="server1")
        gauge.set(2048, server="server2")
        
        assert gauge.get(server="server1") == 1024
        assert gauge.get(server="server2") == 2048
    
    def test_gauge_child(self):
        """Test gauge child."""
        gauge = Gauge("connections")
        child = gauge.labels(service="web")
        
        child.set(100)
        child.inc(10)
        child.dec(5)
        
        assert child.get() == 105


class TestHistogram:
    """Tests for Histogram metric."""
    
    def test_histogram_observe(self):
        """Test histogram observation."""
        histogram = Histogram("latency")
        
        histogram.observe(0.15)
        histogram.observe(0.25)
        histogram.observe(0.35)
        
        stats = histogram.get_statistics()
        assert stats["count"] == 3
        assert stats["min"] == 0.15
        assert stats["max"] == 0.35
    
    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        histogram = Histogram(
            "response_time",
            buckets=(0.1, 0.5, 1.0),
        )
        
        histogram.observe(0.05)  # <= 0.1
        histogram.observe(0.3)   # <= 0.5
        histogram.observe(0.8)   # <= 1.0
        histogram.observe(2.0)   # > 1.0 (no bucket)
        
        stats = histogram.get_statistics()
        assert stats["count"] == 4
    
    def test_histogram_with_labels(self):
        """Test histogram with labels."""
        histogram = Histogram("duration", labels=["method"])
        
        histogram.observe(0.1, method="GET")
        histogram.observe(0.2, method="GET")
        histogram.observe(0.5, method="POST")
        
        get_stats = histogram.get_statistics(method="GET")
        assert get_stats["count"] == 2
        
        post_stats = histogram.get_statistics(method="POST")
        assert post_stats["count"] == 1
    
    def test_histogram_percentiles(self):
        """Test histogram percentile calculation."""
        histogram = Histogram("latency")
        
        for i in range(100):
            histogram.observe(i / 100.0)  # 0.0 to 0.99
        
        stats = histogram.get_statistics()
        assert stats["p95"] == 0.95
        assert stats["p99"] == 0.99
    
    def test_histogram_child(self):
        """Test histogram child."""
        histogram = Histogram("duration")
        child = histogram.labels(endpoint="/api")
        
        child.observe(0.1)
        child.observe(0.2)
        
        stats = child.get_statistics()
        assert stats["count"] == 2
    
    def test_histogram_collect(self):
        """Test histogram collection."""
        histogram = Histogram("test", buckets=(0.1, 0.5, 1.0))
        histogram.observe(0.2)
        
        values = histogram.collect()
        # Should have count, sum, and bucket metrics
        assert len(values) > 0


class TestSummary:
    """Tests for Summary metric."""
    
    def test_summary_observe(self):
        """Test summary observation."""
        summary = Summary("duration")
        
        summary.observe(0.1)
        summary.observe(0.2)
        
        stats = summary.get_statistics()
        assert stats["count"] == 2
        assert stats["sum"] == pytest.approx(0.3)
    
    def test_summary_expiration(self):
        """Test summary value expiration."""
        summary = Summary("test", max_age_seconds=0.1)
        
        summary.observe(1.0)
        
        stats = summary.get_statistics()
        assert stats["count"] == 1
        
        time.sleep(0.15)
        
        stats = summary.get_statistics()
        assert stats["count"] == 0
    
    def test_summary_collect(self):
        """Test summary collection."""
        summary = Summary("test")
        summary.observe(1.0)
        
        values = summary.collect()
        assert len(values) >= 2  # count and sum


class TestTimer:
    """Tests for Timer class."""
    
    def test_timer_context_manager(self):
        """Test timer as context manager."""
        histogram = Histogram("duration")
        
        with Timer(histogram) as timer:
            time.sleep(0.01)
        
        assert timer.duration is not None
        assert timer.duration >= 0.01
        
        stats = histogram.get_statistics()
        assert stats["count"] == 1
    
    @pytest.mark.asyncio
    async def test_timer_async_context_manager(self):
        """Test timer as async context manager."""
        histogram = Histogram("duration")
        
        async with Timer(histogram) as timer:
            await asyncio.sleep(0.01)
        
        assert timer.duration is not None
        assert timer.duration >= 0.01
    
    def test_timer_with_callback(self):
        """Test timer with callback."""
        durations = []
        
        with Timer(callback=lambda d: durations.append(d)):
            time.sleep(0.01)
        
        assert len(durations) == 1
        assert durations[0] >= 0.01
    
    def test_timer_decorator_sync(self):
        """Test timer decorator on sync function."""
        histogram = Histogram("duration")
        
        @Timer(histogram).decorator()
        def slow_func():
            time.sleep(0.01)
            return "done"
        
        result = slow_func()
        
        assert result == "done"
        stats = histogram.get_statistics()
        assert stats["count"] == 1
    
    @pytest.mark.asyncio
    async def test_timer_decorator_async(self):
        """Test timer decorator on async function."""
        histogram = Histogram("duration")
        
        @Timer(histogram).decorator()
        async def async_func():
            await asyncio.sleep(0.01)
            return "done"
        
        result = await async_func()
        
        assert result == "done"
        stats = histogram.get_statistics()
        assert stats["count"] == 1


class TestHealthCheck:
    """Tests for HealthCheck class."""
    
    def test_health_check_defaults(self):
        """Test health check defaults."""
        check = HealthCheck(name="test")
        
        assert check.name == "test"
        assert check.status == HealthStatus.UNKNOWN
        assert check.message == ""
    
    def test_health_check_to_dict(self):
        """Test health check serialization."""
        check = HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connected",
            details={"latency_ms": 5},
        )
        
        data = check.to_dict()
        assert data["name"] == "database"
        assert data["status"] == "healthy"
        assert data["details"]["latency_ms"] == 5


class TestHealthChecker:
    """Tests for HealthChecker class."""
    
    @pytest.mark.asyncio
    async def test_register_and_check(self):
        """Test registering and running health check."""
        checker = HealthChecker()
        
        @checker.register("test")
        async def check_test():
            return HealthStatus.HEALTHY
        
        result = await checker.check("test")
        
        assert result.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_check_with_message(self):
        """Test health check returning status and message."""
        checker = HealthChecker()
        
        @checker.register("database")
        def check_db():
            return (HealthStatus.DEGRADED, "High latency")
        
        result = await checker.check("database")
        
        assert result.status == HealthStatus.DEGRADED
        assert result.message == "High latency"
    
    @pytest.mark.asyncio
    async def test_check_failure(self):
        """Test health check failure."""
        checker = HealthChecker()
        
        @checker.register("failing")
        def check_failing():
            raise RuntimeError("Connection failed")
        
        result = await checker.check("failing")
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in result.message
    
    @pytest.mark.asyncio
    async def test_check_all(self):
        """Test checking all health checks."""
        checker = HealthChecker()
        
        @checker.register("service1")
        def check1():
            return HealthStatus.HEALTHY
        
        @checker.register("service2")
        def check2():
            return HealthStatus.DEGRADED
        
        results = await checker.check_all()
        
        assert len(results) == 2
        assert results["service1"].status == HealthStatus.HEALTHY
        assert results["service2"].status == HealthStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_overall_status(self):
        """Test overall status calculation."""
        checker = HealthChecker()
        
        @checker.register("healthy")
        def check_healthy():
            return HealthStatus.HEALTHY
        
        @checker.register("degraded")
        def check_degraded():
            return HealthStatus.DEGRADED
        
        await checker.check_all()
        
        assert checker.get_overall_status() == HealthStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_overall_unhealthy(self):
        """Test overall status with unhealthy check."""
        checker = HealthChecker()
        
        @checker.register("healthy")
        def check_healthy():
            return HealthStatus.HEALTHY
        
        @checker.register("unhealthy")
        def check_unhealthy():
            return HealthStatus.UNHEALTHY
        
        await checker.check_all()
        
        assert checker.get_overall_status() == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_check_not_found(self):
        """Test checking nonexistent check."""
        checker = HealthChecker()
        
        result = await checker.check("nonexistent")
        
        assert result.status == HealthStatus.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_to_dict(self):
        """Test health checker serialization."""
        checker = HealthChecker()
        
        @checker.register("test")
        def check():
            return HealthStatus.HEALTHY
        
        await checker.check_all()
        
        data = checker.to_dict()
        assert "status" in data
        assert "checks" in data


class TestMetricsRegistry:
    """Tests for MetricsRegistry class."""
    
    def test_create_counter(self):
        """Test creating counter through registry."""
        registry = MetricsRegistry()
        
        counter = registry.counter("requests_total", description="Total requests")
        counter.inc()
        
        # Same name returns same counter
        counter2 = registry.counter("requests_total")
        assert counter2.get() == 1
    
    def test_create_gauge(self):
        """Test creating gauge through registry."""
        registry = MetricsRegistry()
        
        gauge = registry.gauge("temperature")
        gauge.set(72.5)
        
        assert registry.gauge("temperature").get() == 72.5
    
    def test_create_histogram(self):
        """Test creating histogram through registry."""
        registry = MetricsRegistry()
        
        histogram = registry.histogram("latency", buckets=(0.1, 0.5, 1.0))
        histogram.observe(0.2)
        
        stats = registry.histogram("latency").get_statistics()
        assert stats["count"] == 1
    
    def test_create_summary(self):
        """Test creating summary through registry."""
        registry = MetricsRegistry()
        
        summary = registry.summary("duration", max_age_seconds=60)
        summary.observe(1.0)
        
        stats = registry.summary("duration").get_statistics()
        assert stats["count"] == 1
    
    def test_collect_all(self):
        """Test collecting all metrics."""
        registry = MetricsRegistry()
        
        registry.counter("requests").inc()
        registry.gauge("temp").set(70)
        registry.histogram("latency").observe(0.1)
        
        values = registry.collect()
        assert len(values) >= 3
    
    def test_to_prometheus(self):
        """Test Prometheus format export."""
        registry = MetricsRegistry()
        
        counter = registry.counter("http_requests_total", description="HTTP requests")
        counter.inc(method="GET")
        
        output = registry.to_prometheus()
        
        assert "# HELP http_requests_total HTTP requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET"}' in output
    
    def test_to_dict(self):
        """Test dict export."""
        registry = MetricsRegistry()
        
        registry.counter("requests").inc()
        
        data = registry.to_dict()
        assert "requests" in data


class TestStatsCollector:
    """Tests for StatsCollector class."""
    
    def test_record_and_get_stats(self):
        """Test recording values and getting stats."""
        stats = StatsCollector()
        
        stats.record("latency", 0.1)
        stats.record("latency", 0.2)
        stats.record("latency", 0.3)
        
        result = stats.get_stats("latency")
        
        assert result["count"] == 3
        assert result["min"] == 0.1
        assert result["max"] == 0.3
        assert result["mean"] == 0.2
    
    def test_max_samples(self):
        """Test max samples limit."""
        stats = StatsCollector(max_samples=5)
        
        for i in range(10):
            stats.record("test", float(i))
        
        result = stats.get_stats("test")
        assert result["count"] == 5
        assert result["min"] == 5.0  # First 5 were dropped
    
    def test_get_all_stats(self):
        """Test getting all stats."""
        stats = StatsCollector()
        
        stats.record("metric1", 1.0)
        stats.record("metric2", 2.0)
        
        all_stats = stats.get_all_stats()
        
        assert "metric1" in all_stats
        assert "metric2" in all_stats
    
    def test_clear(self):
        """Test clearing samples."""
        stats = StatsCollector()
        
        stats.record("metric1", 1.0)
        stats.record("metric2", 2.0)
        
        stats.clear("metric1")
        
        all_stats = stats.get_all_stats()
        assert "metric1" not in all_stats
        assert "metric2" in all_stats
        
        stats.clear()
        assert stats.get_all_stats() == {}
    
    def test_empty_stats(self):
        """Test stats for empty metric."""
        stats = StatsCollector()
        
        result = stats.get_stats("nonexistent")
        
        assert result["count"] == 0
        assert result["sum"] == 0


class TestDecorators:
    """Tests for decorator functions."""
    
    def test_timed_decorator(self):
        """Test timed decorator."""
        histogram = Histogram("duration")
        
        @timed(histogram, operation="test")
        def slow_func():
            time.sleep(0.01)
            return "done"
        
        result = slow_func()
        
        assert result == "done"
        stats = histogram.get_statistics(operation="test")
        assert stats["count"] == 1
    
    @pytest.mark.asyncio
    async def test_timed_decorator_async(self):
        """Test timed decorator on async function."""
        histogram = Histogram("duration")
        
        @timed(histogram)
        async def async_func():
            await asyncio.sleep(0.01)
            return "done"
        
        result = await async_func()
        assert result == "done"
    
    def test_counted_decorator(self):
        """Test counted decorator."""
        counter = Counter("calls")
        
        @counted(counter, function="test")
        def my_func():
            return "result"
        
        my_func()
        my_func()
        
        assert counter.get(function="test") == 2
    
    @pytest.mark.asyncio
    async def test_counted_decorator_async(self):
        """Test counted decorator on async function."""
        counter = Counter("calls")
        
        @counted(counter, function="async_test")
        async def async_func():
            return "result"
        
        await async_func()
        await async_func()
        
        assert counter.get(function="async_test") == 2


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_registry(self):
        """Test registry factory."""
        registry = create_registry()
        assert isinstance(registry, MetricsRegistry)
    
    def test_create_health_checker(self):
        """Test health checker factory."""
        checker = create_health_checker()
        assert isinstance(checker, HealthChecker)
    
    def test_create_stats_collector(self):
        """Test stats collector factory."""
        collector = create_stats_collector(max_samples=500)
        assert isinstance(collector, StatsCollector)
    
    def test_get_default_registry(self):
        """Test getting default registry."""
        reset_registry()
        
        registry1 = get_registry()
        registry2 = get_registry()
        
        assert registry1 is registry2
    
    def test_reset_registry(self):
        """Test resetting default registry."""
        registry1 = get_registry()
        registry1.counter("test").inc()
        
        reset_registry()
        
        registry2 = get_registry()
        assert registry2.counter("test").get() == 0


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_histogram_empty_stats(self):
        """Test histogram stats when empty."""
        histogram = Histogram("test")
        
        stats = histogram.get_statistics()
        
        assert stats["count"] == 0
        assert stats["mean"] == 0
    
    def test_gauge_negative_values(self):
        """Test gauge with negative values."""
        gauge = Gauge("temperature")
        
        gauge.set(-10)
        assert gauge.get() == -10
        
        gauge.dec(5)
        assert gauge.get() == -15
    
    def test_counter_large_values(self):
        """Test counter with large values."""
        counter = Counter("bytes")
        
        counter.inc(10**12)  # 1 TB
        counter.inc(10**12)
        
        assert counter.get() == 2 * 10**12
    
    def test_label_ordering(self):
        """Test label ordering is consistent."""
        counter = Counter("test")
        
        counter.inc(a="1", b="2")
        counter.inc(b="2", a="1")  # Same labels, different order
        
        assert counter.get(a="1", b="2") == 2
    
    def test_histogram_single_value_percentiles(self):
        """Test histogram percentiles with single value."""
        histogram = Histogram("test")
        histogram.observe(1.0)
        
        stats = histogram.get_statistics()
        assert stats["p95"] == 1.0
        assert stats["p99"] == 1.0
    
    @pytest.mark.asyncio
    async def test_health_check_boolean_return(self):
        """Test health check with boolean return."""
        checker = HealthChecker()
        
        @checker.register("bool_check")
        def check():
            return True
        
        result = await checker.check("bool_check")
        assert result.status == HealthStatus.HEALTHY
        
        @checker.register("false_check")
        def check_false():
            return False
        
        result = await checker.check("false_check")
        assert result.status == HealthStatus.UNHEALTHY
