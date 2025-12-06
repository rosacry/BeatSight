"""
Metrics collection and monitoring utilities.

This module provides utilities for:
- Application metrics collection (counters, gauges, histograms)
- Timing measurements and performance tracking
- Health indicators and status reporting
- Metrics export and formatting
"""

from __future__ import annotations

import asyncio
import time
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)


# Type variables
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class MetricType(Enum):
    """Types of metrics."""
    
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMING = "timing"


class HealthStatus(Enum):
    """Health check status values."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class MetricValue:
    """A single metric value with metadata."""
    
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    unit: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "unit": self.unit,
            "description": self.description,
        }


class Counter:
    """
    A counter metric that can only increase.
    
    Example:
        requests = Counter("http_requests_total", description="Total HTTP requests")
        requests.inc()  # Increment by 1
        requests.inc(5)  # Increment by 5
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize counter.
        
        Args:
            name: Metric name
            description: Metric description
            labels: Label names for this metric
        """
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
    
    def inc(self, amount: float = 1, **labels: str) -> None:
        """
        Increment the counter.
        
        Args:
            amount: Amount to increment (must be positive)
            labels: Label values
        """
        if amount < 0:
            raise ValueError("Counter can only be incremented")
        
        label_key = self._make_label_key(labels)
        self._values[label_key] += amount
    
    def get(self, **labels: str) -> float:
        """Get current counter value."""
        label_key = self._make_label_key(labels)
        return self._values[label_key]
    
    def labels(self, **labels: str) -> "CounterChild":
        """Get a child counter with labels pre-set."""
        return CounterChild(self, labels)
    
    def _make_label_key(self, labels: Dict[str, str]) -> tuple:
        """Create a hashable key from labels."""
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        for label_key, value in self._values.items():
            labels = dict(label_key)
            results.append(MetricValue(
                name=self.name,
                value=value,
                metric_type=MetricType.COUNTER,
                labels=labels,
                description=self.description,
            ))
        return results


class CounterChild:
    """A counter with pre-set labels."""
    
    def __init__(self, parent: Counter, labels: Dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels
    
    def inc(self, amount: float = 1) -> None:
        """Increment the counter."""
        self._parent.inc(amount, **self._labels)
    
    def get(self) -> float:
        """Get current value."""
        return self._parent.get(**self._labels)


class Gauge:
    """
    A gauge metric that can increase or decrease.
    
    Example:
        temp = Gauge("temperature", description="Current temperature")
        temp.set(72.5)
        temp.inc(1)
        temp.dec(0.5)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> None:
        """Initialize gauge."""
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
    
    def set(self, value: float, **labels: str) -> None:
        """Set the gauge value."""
        label_key = self._make_label_key(labels)
        self._values[label_key] = value
    
    def inc(self, amount: float = 1, **labels: str) -> None:
        """Increment the gauge."""
        label_key = self._make_label_key(labels)
        self._values[label_key] += amount
    
    def dec(self, amount: float = 1, **labels: str) -> None:
        """Decrement the gauge."""
        label_key = self._make_label_key(labels)
        self._values[label_key] -= amount
    
    def get(self, **labels: str) -> float:
        """Get current gauge value."""
        label_key = self._make_label_key(labels)
        return self._values[label_key]
    
    def labels(self, **labels: str) -> "GaugeChild":
        """Get a child gauge with labels pre-set."""
        return GaugeChild(self, labels)
    
    def _make_label_key(self, labels: Dict[str, str]) -> tuple:
        """Create a hashable key from labels."""
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        for label_key, value in self._values.items():
            labels = dict(label_key)
            results.append(MetricValue(
                name=self.name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels,
                description=self.description,
            ))
        return results


class GaugeChild:
    """A gauge with pre-set labels."""
    
    def __init__(self, parent: Gauge, labels: Dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels
    
    def set(self, value: float) -> None:
        """Set the gauge value."""
        self._parent.set(value, **self._labels)
    
    def inc(self, amount: float = 1) -> None:
        """Increment the gauge."""
        self._parent.inc(amount, **self._labels)
    
    def dec(self, amount: float = 1) -> None:
        """Decrement the gauge."""
        self._parent.dec(amount, **self._labels)
    
    def get(self) -> float:
        """Get current value."""
        return self._parent.get(**self._labels)


class Histogram:
    """
    A histogram metric for measuring distributions.
    
    Example:
        latency = Histogram(
            "request_latency",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        )
        latency.observe(0.15)
    """
    
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    
    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize histogram.
        
        Args:
            name: Metric name
            description: Metric description
            buckets: Upper bounds for histogram buckets
            labels: Label names
        """
        self.name = name
        self.description = description
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._labels = labels or []
        self._values: Dict[tuple, List[float]] = defaultdict(list)
        self._bucket_counts: Dict[tuple, Dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets}
        )
    
    def observe(self, value: float, **labels: str) -> None:
        """
        Observe a value.
        
        Args:
            value: Value to observe
            labels: Label values
        """
        label_key = self._make_label_key(labels)
        self._values[label_key].append(value)
        
        # Update bucket counts
        for bucket in self.buckets:
            if value <= bucket:
                self._bucket_counts[label_key][bucket] += 1
    
    def get_statistics(self, **labels: str) -> Dict[str, float]:
        """
        Get statistical summary.
        
        Returns:
            Dict with count, sum, mean, min, max, median, p95, p99
        """
        label_key = self._make_label_key(labels)
        values = self._values[label_key]
        
        if not values:
            return {
                "count": 0,
                "sum": 0,
                "mean": 0,
                "min": 0,
                "max": 0,
                "median": 0,
                "p95": 0,
                "p99": 0,
            }
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "sum": sum(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "median": statistics.median(values),
            "p95": sorted_values[int(n * 0.95)] if n > 0 else 0,
            "p99": sorted_values[int(n * 0.99)] if n > 0 else 0,
        }
    
    def labels(self, **labels: str) -> "HistogramChild":
        """Get a child histogram with labels pre-set."""
        return HistogramChild(self, labels)
    
    def _make_label_key(self, labels: Dict[str, str]) -> tuple:
        """Create a hashable key from labels."""
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        for label_key in self._values:
            labels = dict(label_key)
            stats = self.get_statistics(**labels)
            
            # Add summary metric
            results.append(MetricValue(
                name=f"{self.name}_count",
                value=stats["count"],
                metric_type=MetricType.HISTOGRAM,
                labels=labels,
                description=f"{self.description} (count)",
            ))
            results.append(MetricValue(
                name=f"{self.name}_sum",
                value=stats["sum"],
                metric_type=MetricType.HISTOGRAM,
                labels=labels,
                description=f"{self.description} (sum)",
            ))
            
            # Add bucket metrics
            for bucket, count in self._bucket_counts[label_key].items():
                bucket_labels = {**labels, "le": str(bucket)}
                results.append(MetricValue(
                    name=f"{self.name}_bucket",
                    value=count,
                    metric_type=MetricType.HISTOGRAM,
                    labels=bucket_labels,
                    description=f"{self.description} (bucket)",
                ))
        
        return results


class HistogramChild:
    """A histogram with pre-set labels."""
    
    def __init__(self, parent: Histogram, labels: Dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels
    
    def observe(self, value: float) -> None:
        """Observe a value."""
        self._parent.observe(value, **self._labels)
    
    def get_statistics(self) -> Dict[str, float]:
        """Get statistics."""
        return self._parent.get_statistics(**self._labels)


class Summary:
    """
    A summary metric for tracking values over a time window.
    
    Example:
        summary = Summary("request_duration", max_age_seconds=60)
        summary.observe(0.5)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        max_age_seconds: float = 60.0,
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize summary.
        
        Args:
            name: Metric name
            description: Metric description
            max_age_seconds: How long to keep values
            labels: Label names
        """
        self.name = name
        self.description = description
        self.max_age_seconds = max_age_seconds
        self._labels = labels or []
        self._values: Dict[tuple, Deque[tuple]] = defaultdict(deque)
    
    def observe(self, value: float, **labels: str) -> None:
        """Observe a value."""
        label_key = self._make_label_key(labels)
        now = time.time()
        self._values[label_key].append((now, value))
        self._cleanup(label_key)
    
    def _cleanup(self, label_key: tuple) -> None:
        """Remove old values."""
        cutoff = time.time() - self.max_age_seconds
        values = self._values[label_key]
        while values and values[0][0] < cutoff:
            values.popleft()
    
    def get_statistics(self, **labels: str) -> Dict[str, float]:
        """Get statistical summary."""
        label_key = self._make_label_key(labels)
        self._cleanup(label_key)
        
        values = [v for _, v in self._values[label_key]]
        
        if not values:
            return {
                "count": 0,
                "sum": 0,
                "mean": 0,
                "min": 0,
                "max": 0,
            }
        
        return {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
        }
    
    def _make_label_key(self, labels: Dict[str, str]) -> tuple:
        """Create a hashable key from labels."""
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        for label_key in list(self._values.keys()):
            labels = dict(label_key)
            stats = self.get_statistics(**labels)
            
            results.append(MetricValue(
                name=f"{self.name}_count",
                value=stats["count"],
                metric_type=MetricType.SUMMARY,
                labels=labels,
                description=f"{self.description} (count)",
            ))
            results.append(MetricValue(
                name=f"{self.name}_sum",
                value=stats["sum"],
                metric_type=MetricType.SUMMARY,
                labels=labels,
                description=f"{self.description} (sum)",
            ))
        
        return results


class Timer:
    """
    A context manager for timing operations.
    
    Example:
        histogram = Histogram("operation_duration")
        
        with Timer(histogram):
            do_something()
        
        # Or as decorator
        @Timer(histogram).decorator()
        def my_function():
            pass
    """
    
    def __init__(
        self,
        metric: Optional[Union[Histogram, Summary]] = None,
        callback: Optional[Callable[[float], None]] = None,
        **labels: str,
    ) -> None:
        """
        Initialize timer.
        
        Args:
            metric: Metric to record to
            callback: Optional callback with duration
            labels: Labels to apply
        """
        self.metric = metric
        self.callback = callback
        self.labels = labels
        self._start: Optional[float] = None
        self.duration: Optional[float] = None
    
    def __enter__(self) -> "Timer":
        """Start timing."""
        self._start = time.perf_counter()
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Stop timing and record."""
        if self._start is not None:
            self.duration = time.perf_counter() - self._start
            
            if self.metric:
                self.metric.observe(self.duration, **self.labels)
            
            if self.callback:
                self.callback(self.duration)
    
    async def __aenter__(self) -> "Timer":
        """Async context entry."""
        return self.__enter__()
    
    async def __aexit__(self, *args: Any) -> None:
        """Async context exit."""
        self.__exit__(*args)
    
    def decorator(self) -> Callable[[F], F]:
        """Get a decorator that times functions."""
        def decorator(func: F) -> F:
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    async with Timer(self.metric, self.callback, **self.labels):
                        return await func(*args, **kwargs)
                return async_wrapper  # type: ignore
            else:
                @wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    with Timer(self.metric, self.callback, **self.labels):
                        return func(*args, **kwargs)
                return sync_wrapper  # type: ignore
        return decorator


@dataclass
class HealthCheck:
    """
    A health check definition.
    
    Attributes:
        name: Check name
        status: Current status
        message: Status message
        details: Additional details
        last_check: When last checked
    """
    
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


class HealthChecker:
    """
    Manager for health checks.
    
    Example:
        health = HealthChecker()
        
        @health.register("database")
        async def check_database():
            # Check database connection
            return HealthStatus.HEALTHY
        
        status = await health.check_all()
    """
    
    def __init__(self) -> None:
        """Initialize health checker."""
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, HealthCheck] = {}
    
    def register(
        self,
        name: str,
        check: Optional[Callable[[], Awaitable[HealthStatus]]] = None,
    ) -> Callable:
        """
        Register a health check.
        
        Args:
            name: Check name
            check: Check function (optional for decorator use)
            
        Returns:
            Decorator or original function
        """
        def decorator(fn: Callable) -> Callable:
            self._checks[name] = fn
            self._results[name] = HealthCheck(name=name)
            return fn
        
        if check is not None:
            return decorator(check)
        return decorator
    
    async def check(self, name: str) -> HealthCheck:
        """
        Run a specific health check.
        
        Args:
            name: Check name
            
        Returns:
            Health check result
        """
        if name not in self._checks:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not found",
            )
        
        check_fn = self._checks[name]
        result = self._results[name]
        
        try:
            if asyncio.iscoroutinefunction(check_fn):
                status = await check_fn()
            else:
                status = check_fn()
            
            if isinstance(status, tuple):
                result.status, result.message = status[0], status[1] if len(status) > 1 else ""
                if len(status) > 2:
                    result.details = status[2]
            elif isinstance(status, HealthStatus):
                result.status = status
                result.message = ""
            else:
                result.status = HealthStatus.HEALTHY if status else HealthStatus.UNHEALTHY
                result.message = ""
        except Exception as e:
            result.status = HealthStatus.UNHEALTHY
            result.message = str(e)
        
        result.last_check = datetime.now(timezone.utc)
        return result
    
    async def check_all(self) -> Dict[str, HealthCheck]:
        """Run all health checks."""
        results = {}
        for name in self._checks:
            results[name] = await self.check(name)
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """
        Get overall health status.
        
        Returns UNHEALTHY if any check is unhealthy,
        DEGRADED if any check is degraded,
        otherwise HEALTHY.
        """
        statuses = [r.status for r in self._results.values()]
        
        if not statuses:
            return HealthStatus.UNKNOWN
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        
        if HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        
        return HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Get health status as dictionary."""
        return {
            "status": self.get_overall_status().value,
            "checks": {name: check.to_dict() for name, check in self._results.items()},
        }


class MetricsRegistry:
    """
    Central registry for all metrics.
    
    Example:
        registry = MetricsRegistry()
        
        requests = registry.counter("http_requests_total")
        requests.inc()
        
        all_metrics = registry.collect()
    """
    
    def __init__(self) -> None:
        """Initialize registry."""
        self._metrics: Dict[str, Any] = {}
    
    def counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> Counter:
        """Create or get a counter."""
        if name not in self._metrics:
            self._metrics[name] = Counter(name, description, labels)
        return self._metrics[name]
    
    def gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> Gauge:
        """Create or get a gauge."""
        if name not in self._metrics:
            self._metrics[name] = Gauge(name, description, labels)
        return self._metrics[name]
    
    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
        labels: Optional[List[str]] = None,
    ) -> Histogram:
        """Create or get a histogram."""
        if name not in self._metrics:
            self._metrics[name] = Histogram(name, description, buckets, labels)
        return self._metrics[name]
    
    def summary(
        self,
        name: str,
        description: str = "",
        max_age_seconds: float = 60.0,
        labels: Optional[List[str]] = None,
    ) -> Summary:
        """Create or get a summary."""
        if name not in self._metrics:
            self._metrics[name] = Summary(name, description, max_age_seconds, labels)
        return self._metrics[name]
    
    def collect(self) -> List[MetricValue]:
        """Collect all metrics."""
        results = []
        for metric in self._metrics.values():
            results.extend(metric.collect())
        return results
    
    def to_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric in self._metrics.values():
            if metric.description:
                lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric.__class__.__name__.lower()}")
            
            for value in metric.collect():
                label_str = ""
                if value.labels:
                    label_parts = [f'{k}="{v}"' for k, v in value.labels.items()]
                    label_str = "{" + ",".join(label_parts) + "}"
                
                lines.append(f"{value.name}{label_str} {value.value}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export metrics as dictionary."""
        result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for value in self.collect():
            result[value.name].append(value.to_dict())
        
        return dict(result)


class StatsCollector:
    """
    Simple stats collector for tracking values over time.
    
    Example:
        stats = StatsCollector()
        stats.record("response_time", 0.15)
        stats.record("response_time", 0.20)
        
        print(stats.get_stats("response_time"))
    """
    
    def __init__(self, max_samples: int = 1000) -> None:
        """Initialize stats collector."""
        self._samples: Dict[str, Deque[float]] = defaultdict(deque)
        self._max_samples = max_samples
    
    def record(self, name: str, value: float) -> None:
        """Record a value."""
        samples = self._samples[name]
        samples.append(value)
        
        while len(samples) > self._max_samples:
            samples.popleft()
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        samples = list(self._samples.get(name, []))
        
        if not samples:
            return {
                "count": 0,
                "sum": 0,
                "mean": 0,
                "min": 0,
                "max": 0,
                "stddev": 0,
            }
        
        return {
            "count": len(samples),
            "sum": sum(samples),
            "mean": statistics.mean(samples),
            "min": min(samples),
            "max": max(samples),
            "stddev": statistics.stdev(samples) if len(samples) > 1 else 0,
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get stats for all metrics."""
        return {name: self.get_stats(name) for name in self._samples}
    
    def clear(self, name: Optional[str] = None) -> None:
        """Clear samples."""
        if name:
            self._samples.pop(name, None)
        else:
            self._samples.clear()


# Convenience decorators


def timed(
    metric: Optional[Union[Histogram, Summary]] = None,
    callback: Optional[Callable[[float], None]] = None,
    **labels: str,
) -> Callable[[F], F]:
    """
    Decorator to time function execution.
    
    Example:
        @timed(latency_histogram, method="GET")
        def handle_request():
            pass
    """
    return Timer(metric, callback, **labels).decorator()


def counted(
    counter: Counter,
    **labels: str,
) -> Callable[[F], F]:
    """
    Decorator to count function calls.
    
    Example:
        @counted(request_counter, endpoint="/api")
        def handle_request():
            pass
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                counter.inc(**labels)
                return await func(*args, **kwargs)
            return async_wrapper  # type: ignore
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                counter.inc(**labels)
                return func(*args, **kwargs)
            return sync_wrapper  # type: ignore
    return decorator


# Factory functions


def create_registry() -> MetricsRegistry:
    """Create a metrics registry."""
    return MetricsRegistry()


def create_health_checker() -> HealthChecker:
    """Create a health checker."""
    return HealthChecker()


def create_stats_collector(max_samples: int = 1000) -> StatsCollector:
    """Create a stats collector."""
    return StatsCollector(max_samples=max_samples)


# Default global registry
_default_registry: Optional[MetricsRegistry] = None


def get_registry() -> MetricsRegistry:
    """Get the default metrics registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = MetricsRegistry()
    return _default_registry


def reset_registry() -> None:
    """Reset the default registry."""
    global _default_registry
    _default_registry = None
