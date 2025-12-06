"""Datetime utilities for timezone-aware date/time handling.

Provides utilities for:
- Timezone-aware datetime operations
- ISO 8601 parsing and formatting
- Relative time formatting (human-readable)
- Time range calculations
- Business day calculations

Usage:
    from app.utils.datetime import (
        utc_now,
        parse_datetime,
        format_relative,
        TimeRange,
    )

    # Get current UTC time
    now = utc_now()

    # Parse ISO 8601 datetime
    dt = parse_datetime("2024-01-15T10:30:00Z")

    # Format as relative time
    relative = format_relative(dt)  # "2 hours ago"
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Iterator

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

UTC = timezone.utc

# ISO 8601 format strings
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
ISO_FORMAT_TZ = "%Y-%m-%dT%H:%M:%S%z"
ISO_FORMAT_MS = "%Y-%m-%dT%H:%M:%S.%f"
ISO_FORMAT_MS_TZ = "%Y-%m-%dT%H:%M:%S.%f%z"

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

# Time intervals in seconds
MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY
MONTH = 30 * DAY  # Approximate
YEAR = 365 * DAY  # Approximate


# =============================================================================
# Current time functions
# =============================================================================


def utc_now() -> datetime:
    """Get current UTC datetime.

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.now(UTC)


def utc_today() -> date:
    """Get current UTC date.

    Returns:
        Current date in UTC
    """
    return utc_now().date()


def timestamp_now() -> int:
    """Get current Unix timestamp (seconds).

    Returns:
        Unix timestamp
    """
    return int(utc_now().timestamp())


def timestamp_ms_now() -> int:
    """Get current Unix timestamp (milliseconds).

    Returns:
        Unix timestamp in milliseconds
    """
    return int(utc_now().timestamp() * 1000)


# =============================================================================
# Parsing functions
# =============================================================================


def parse_datetime(
    value: str | datetime,
    *,
    default_tz: timezone = UTC,
) -> datetime:
    """Parse datetime string or return datetime.

    Supports ISO 8601 formats and common variants.

    Args:
        value: Datetime string or datetime object
        default_tz: Default timezone for naive datetimes

    Returns:
        Timezone-aware datetime

    Raises:
        ValueError: If string cannot be parsed
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=default_tz)
        return value

    value = value.strip()

    # Handle Z suffix
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    # Try various formats
    formats = [
        ISO_FORMAT_MS_TZ,
        ISO_FORMAT_TZ,
        ISO_FORMAT_MS,
        ISO_FORMAT,
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=default_tz)
            return dt
        except ValueError:
            continue

    # Try fromisoformat as fallback
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt
    except ValueError:
        pass

    raise ValueError(f"Cannot parse datetime: {value}")


def parse_date(value: str | date) -> date:
    """Parse date string or return date.

    Args:
        value: Date string or date object

    Returns:
        Date object

    Raises:
        ValueError: If string cannot be parsed
    """
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = value.strip()

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date: {value}")


def from_timestamp(
    ts: int | float,
    *,
    milliseconds: bool = False,
) -> datetime:
    """Create datetime from Unix timestamp.

    Args:
        ts: Unix timestamp
        milliseconds: Whether timestamp is in milliseconds

    Returns:
        Timezone-aware datetime in UTC
    """
    if milliseconds:
        ts = ts / 1000
    return datetime.fromtimestamp(ts, tz=UTC)


# =============================================================================
# Formatting functions
# =============================================================================


def format_iso(
    dt: datetime,
    *,
    include_ms: bool = False,
    include_tz: bool = True,
) -> str:
    """Format datetime as ISO 8601 string.

    Args:
        dt: Datetime to format
        include_ms: Include milliseconds
        include_tz: Include timezone

    Returns:
        ISO 8601 formatted string
    """
    if include_ms:
        result = dt.strftime(ISO_FORMAT_MS)
        # Truncate microseconds to milliseconds
        result = result[:-3]
    else:
        result = dt.strftime(ISO_FORMAT)

    if include_tz and dt.tzinfo:
        offset = dt.strftime("%z")
        if offset:
            # Format as +HH:MM
            result += offset[:3] + ":" + offset[3:]
        else:
            result += "Z"
    elif include_tz:
        result += "Z"

    return result


def format_date(dt: datetime | date) -> str:
    """Format as date string (YYYY-MM-DD).

    Args:
        dt: Date or datetime

    Returns:
        Formatted date string
    """
    if isinstance(dt, datetime):
        return dt.strftime(DATE_FORMAT)
    return dt.strftime(DATE_FORMAT)


def format_time(dt: datetime | time) -> str:
    """Format as time string (HH:MM:SS).

    Args:
        dt: Time or datetime

    Returns:
        Formatted time string
    """
    return dt.strftime(TIME_FORMAT)


def format_relative(
    dt: datetime,
    *,
    reference: datetime | None = None,
    short: bool = False,
) -> str:
    """Format datetime as relative string (e.g., "2 hours ago").

    Args:
        dt: Datetime to format
        reference: Reference datetime (default: now)
        short: Use short format (e.g., "2h" instead of "2 hours ago")

    Returns:
        Relative time string
    """
    if reference is None:
        reference = utc_now()

    # Ensure both are timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)

    diff = reference - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return _format_future(-seconds, short)
    return _format_past(seconds, short)


def _format_past(seconds: int, short: bool) -> str:
    """Format past time."""
    if seconds < MINUTE:
        return "now" if short else "just now"

    if seconds < HOUR:
        minutes = seconds // MINUTE
        if short:
            return f"{minutes}m"
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    if seconds < DAY:
        hours = seconds // HOUR
        if short:
            return f"{hours}h"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    if seconds < WEEK:
        days = seconds // DAY
        if short:
            return f"{days}d"
        return f"{days} day{'s' if days != 1 else ''} ago"

    if seconds < MONTH:
        weeks = seconds // WEEK
        if short:
            return f"{weeks}w"
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    if seconds < YEAR:
        months = seconds // MONTH
        if short:
            return f"{months}mo"
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = seconds // YEAR
    if short:
        return f"{years}y"
    return f"{years} year{'s' if years != 1 else ''} ago"


def _format_future(seconds: int, short: bool) -> str:
    """Format future time."""
    if seconds < MINUTE:
        return "soon" if short else "in a moment"

    if seconds < HOUR:
        minutes = seconds // MINUTE
        if short:
            return f"+{minutes}m"
        return f"in {minutes} minute{'s' if minutes != 1 else ''}"

    if seconds < DAY:
        hours = seconds // HOUR
        if short:
            return f"+{hours}h"
        return f"in {hours} hour{'s' if hours != 1 else ''}"

    if seconds < WEEK:
        days = seconds // DAY
        if short:
            return f"+{days}d"
        return f"in {days} day{'s' if days != 1 else ''}"

    if seconds < MONTH:
        weeks = seconds // WEEK
        if short:
            return f"+{weeks}w"
        return f"in {weeks} week{'s' if weeks != 1 else ''}"

    if seconds < YEAR:
        months = seconds // MONTH
        if short:
            return f"+{months}mo"
        return f"in {months} month{'s' if months != 1 else ''}"

    years = seconds // YEAR
    if short:
        return f"+{years}y"
    return f"in {years} year{'s' if years != 1 else ''}"


# =============================================================================
# Time range operations
# =============================================================================


class TimeUnit(str, Enum):
    """Time unit for calculations."""

    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


@dataclass
class TimeRange:
    """A time range with start and end."""

    start: datetime
    end: datetime

    def __post_init__(self):
        """Ensure timezone-aware datetimes."""
        if self.start.tzinfo is None:
            self.start = self.start.replace(tzinfo=UTC)
        if self.end.tzinfo is None:
            self.end = self.end.replace(tzinfo=UTC)

    @property
    def duration(self) -> timedelta:
        """Duration of the range."""
        return self.end - self.start

    @property
    def total_seconds(self) -> float:
        """Total seconds in range."""
        return self.duration.total_seconds()

    @property
    def total_hours(self) -> float:
        """Total hours in range."""
        return self.total_seconds / HOUR

    @property
    def total_days(self) -> float:
        """Total days in range."""
        return self.total_seconds / DAY

    def contains(self, dt: datetime) -> bool:
        """Check if datetime is within range.

        Args:
            dt: Datetime to check

        Returns:
            True if within range
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return self.start <= dt <= self.end

    def overlaps(self, other: "TimeRange") -> bool:
        """Check if ranges overlap.

        Args:
            other: Other time range

        Returns:
            True if ranges overlap
        """
        return self.start <= other.end and other.start <= self.end

    def intersection(self, other: "TimeRange") -> "TimeRange | None":
        """Get intersection of two ranges.

        Args:
            other: Other time range

        Returns:
            Intersection or None if no overlap
        """
        if not self.overlaps(other):
            return None

        return TimeRange(
            start=max(self.start, other.start),
            end=min(self.end, other.end),
        )

    def iterate_days(self) -> Iterator[date]:
        """Iterate over days in range.

        Yields:
            Each date in range
        """
        current = self.start.date()
        end_date = self.end.date()

        while current <= end_date:
            yield current
            current += timedelta(days=1)

    @classmethod
    def today(cls) -> "TimeRange":
        """Get range for today (UTC)."""
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return cls(start=start, end=end)

    @classmethod
    def this_week(cls) -> "TimeRange":
        """Get range for this week (Monday to Sunday, UTC)."""
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start -= timedelta(days=now.weekday())  # Back to Monday
        end = start + timedelta(weeks=1) - timedelta(microseconds=1)
        return cls(start=start, end=end)

    @classmethod
    def this_month(cls) -> "TimeRange":
        """Get range for this month (UTC)."""
        now = utc_now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get last day of month
        _, last_day = calendar.monthrange(now.year, now.month)
        end = start.replace(
            day=last_day, hour=23, minute=59, second=59, microsecond=999999
        )

        return cls(start=start, end=end)

    @classmethod
    def last_n_days(cls, days: int) -> "TimeRange":
        """Get range for last N days (UTC).

        Args:
            days: Number of days

        Returns:
            TimeRange
        """
        now = utc_now()
        end = now
        start = now - timedelta(days=days)
        return cls(start=start, end=end)

    @classmethod
    def last_n_hours(cls, hours: int) -> "TimeRange":
        """Get range for last N hours (UTC).

        Args:
            hours: Number of hours

        Returns:
            TimeRange
        """
        now = utc_now()
        end = now
        start = now - timedelta(hours=hours)
        return cls(start=start, end=end)


# =============================================================================
# Date arithmetic
# =============================================================================


def add_time(
    dt: datetime,
    *,
    years: int = 0,
    months: int = 0,
    weeks: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
) -> datetime:
    """Add time to datetime.

    Args:
        dt: Base datetime
        years: Years to add
        months: Months to add
        weeks: Weeks to add
        days: Days to add
        hours: Hours to add
        minutes: Minutes to add
        seconds: Seconds to add

    Returns:
        New datetime
    """
    # Handle simple time additions first
    result = dt + timedelta(
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )

    # Handle month additions
    if months:
        new_month = result.month + months
        new_year = result.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1

        # Handle day overflow (e.g., Jan 31 + 1 month)
        _, max_day = calendar.monthrange(new_year, new_month)
        new_day = min(result.day, max_day)

        result = result.replace(year=new_year, month=new_month, day=new_day)

    # Handle year additions
    if years:
        new_year = result.year + years

        # Handle Feb 29 on non-leap years
        if result.month == 2 and result.day == 29:
            if not calendar.isleap(new_year):
                result = result.replace(year=new_year, day=28)
            else:
                result = result.replace(year=new_year)
        else:
            result = result.replace(year=new_year)

    return result


def start_of_day(dt: datetime) -> datetime:
    """Get start of day for datetime.

    Args:
        dt: Datetime

    Returns:
        Datetime at 00:00:00
    """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """Get end of day for datetime.

    Args:
        dt: Datetime

    Returns:
        Datetime at 23:59:59.999999
    """
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_week(dt: datetime) -> datetime:
    """Get start of week (Monday) for datetime.

    Args:
        dt: Datetime

    Returns:
        Datetime at start of Monday
    """
    start = start_of_day(dt)
    return start - timedelta(days=dt.weekday())


def start_of_month(dt: datetime) -> datetime:
    """Get start of month for datetime.

    Args:
        dt: Datetime

    Returns:
        Datetime at start of first day of month
    """
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def end_of_month(dt: datetime) -> datetime:
    """Get end of month for datetime.

    Args:
        dt: Datetime

    Returns:
        Datetime at end of last day of month
    """
    _, last_day = calendar.monthrange(dt.year, dt.month)
    return dt.replace(
        day=last_day,
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
    )


# =============================================================================
# Business day calculations
# =============================================================================


def is_weekend(dt: datetime | date) -> bool:
    """Check if date is a weekend.

    Args:
        dt: Date or datetime

    Returns:
        True if Saturday or Sunday
    """
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt.weekday() >= 5


def is_weekday(dt: datetime | date) -> bool:
    """Check if date is a weekday.

    Args:
        dt: Date or datetime

    Returns:
        True if Monday through Friday
    """
    return not is_weekend(dt)


def next_weekday(dt: datetime | date) -> date:
    """Get next weekday (or same if already weekday).

    Args:
        dt: Date or datetime

    Returns:
        Next weekday date
    """
    if isinstance(dt, datetime):
        dt = dt.date()

    while is_weekend(dt):
        dt += timedelta(days=1)

    return dt


def add_business_days(
    dt: datetime | date,
    days: int,
    holidays: set[date] | None = None,
) -> date:
    """Add business days to date.

    Args:
        dt: Start date
        days: Number of business days to add (can be negative)
        holidays: Set of holiday dates to skip

    Returns:
        Resulting date
    """
    if isinstance(dt, datetime):
        dt = dt.date()

    holidays = holidays or set()
    direction = 1 if days >= 0 else -1
    days = abs(days)

    current = dt
    added = 0

    while added < days:
        current += timedelta(days=direction)
        if is_weekday(current) and current not in holidays:
            added += 1

    return current


def business_days_between(
    start: datetime | date,
    end: datetime | date,
    holidays: set[date] | None = None,
) -> int:
    """Count business days between two dates.

    Args:
        start: Start date (exclusive)
        end: End date (inclusive)
        holidays: Set of holiday dates

    Returns:
        Number of business days
    """
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()

    holidays = holidays or set()

    if start > end:
        return -business_days_between(end, start, holidays)

    count = 0
    current = start + timedelta(days=1)

    while current <= end:
        if is_weekday(current) and current not in holidays:
            count += 1
        current += timedelta(days=1)

    return count


# =============================================================================
# Age calculations
# =============================================================================


def age_in_years(birth_date: date, reference: date | None = None) -> int:
    """Calculate age in years.

    Args:
        birth_date: Birth date
        reference: Reference date (default: today)

    Returns:
        Age in complete years
    """
    if reference is None:
        reference = utc_today()

    age = reference.year - birth_date.year

    # Check if birthday has occurred this year
    if (reference.month, reference.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


def time_until(
    target: datetime,
    reference: datetime | None = None,
) -> timedelta:
    """Calculate time until target datetime.

    Args:
        target: Target datetime
        reference: Reference datetime (default: now)

    Returns:
        Timedelta until target (negative if past)
    """
    if reference is None:
        reference = utc_now()

    return target - reference


def time_since(
    past: datetime,
    reference: datetime | None = None,
) -> timedelta:
    """Calculate time since past datetime.

    Args:
        past: Past datetime
        reference: Reference datetime (default: now)

    Returns:
        Timedelta since past (negative if future)
    """
    if reference is None:
        reference = utc_now()

    return reference - past
