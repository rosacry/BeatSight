"""Tests for datetime utilities."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.utils.datetime_utils import (
    HOUR,
    UTC,
    TimeRange,
    add_business_days,
    add_time,
    age_in_years,
    business_days_between,
    end_of_day,
    end_of_month,
    format_date,
    format_iso,
    format_relative,
    format_time,
    from_timestamp,
    is_weekday,
    is_weekend,
    next_weekday,
    parse_date,
    parse_datetime,
    start_of_day,
    start_of_month,
    start_of_week,
    time_since,
    time_until,
    timestamp_ms_now,
    timestamp_now,
    utc_now,
    utc_today,
)


# =============================================================================
# Current Time Tests
# =============================================================================


class TestUtcNow:
    """Tests for utc_now function."""

    def test_returns_datetime(self):
        """Test returns datetime."""
        result = utc_now()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self):
        """Test result is timezone-aware."""
        result = utc_now()
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_is_current_time(self):
        """Test returns current time."""
        before = datetime.now(UTC)
        result = utc_now()
        after = datetime.now(UTC)

        assert before <= result <= after


class TestUtcToday:
    """Tests for utc_today function."""

    def test_returns_date(self):
        """Test returns date."""
        result = utc_today()
        assert isinstance(result, date)

    def test_is_current_date(self):
        """Test returns current date."""
        expected = datetime.now(UTC).date()
        assert utc_today() == expected


class TestTimestampNow:
    """Tests for timestamp functions."""

    def test_timestamp_now(self):
        """Test Unix timestamp."""
        result = timestamp_now()
        assert isinstance(result, int)
        assert result > 0

    def test_timestamp_ms_now(self):
        """Test millisecond timestamp."""
        result = timestamp_ms_now()
        assert isinstance(result, int)
        assert result > timestamp_now() * 1000 - 1000
        assert result < timestamp_now() * 1000 + 1000


# =============================================================================
# Parsing Tests
# =============================================================================


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_parse_iso_format(self):
        """Test parsing ISO format."""
        result = parse_datetime("2024-01-15T10:30:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_iso_with_offset(self):
        """Test parsing ISO with offset."""
        result = parse_datetime("2024-01-15T10:30:00+05:00")
        assert result.tzinfo is not None

    def test_parse_iso_with_ms(self):
        """Test parsing ISO with milliseconds."""
        result = parse_datetime("2024-01-15T10:30:00.123Z")
        assert result.microsecond == 123000

    def test_parse_date_only(self):
        """Test parsing date only."""
        result = parse_datetime("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0

    def test_parse_space_separator(self):
        """Test parsing with space separator."""
        result = parse_datetime("2024-01-15 10:30:00")
        assert result.hour == 10

    def test_datetime_passthrough(self):
        """Test datetime passed through."""
        dt = datetime(2024, 1, 15, tzinfo=UTC)
        result = parse_datetime(dt)
        assert result == dt

    def test_adds_default_tz(self):
        """Test adds default timezone to naive datetime."""
        dt = datetime(2024, 1, 15)
        result = parse_datetime(dt)
        assert result.tzinfo == UTC

    def test_invalid_format(self):
        """Test invalid format raises error."""
        with pytest.raises(ValueError):
            parse_datetime("not a date")


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_iso_date(self):
        """Test parsing ISO date."""
        result = parse_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_slash_format(self):
        """Test parsing slash format."""
        result = parse_date("2024/01/15")
        assert result == date(2024, 1, 15)

    def test_date_passthrough(self):
        """Test date passed through."""
        d = date(2024, 1, 15)
        result = parse_date(d)
        assert result == d

    def test_datetime_to_date(self):
        """Test datetime converted to date."""
        dt = datetime(2024, 1, 15, 10, 30)
        result = parse_date(dt)
        assert result == date(2024, 1, 15)


class TestFromTimestamp:
    """Tests for from_timestamp function."""

    def test_from_seconds(self):
        """Test from seconds timestamp."""
        ts = 1705312200  # 2024-01-15T10:30:00Z
        result = from_timestamp(ts)
        assert result.year == 2024
        assert result.tzinfo == UTC

    def test_from_milliseconds(self):
        """Test from milliseconds timestamp."""
        ts = 1705312200000
        result = from_timestamp(ts, milliseconds=True)
        assert result.year == 2024


# =============================================================================
# Formatting Tests
# =============================================================================


class TestFormatIso:
    """Tests for format_iso function."""

    def test_basic_format(self):
        """Test basic ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = format_iso(dt)
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_with_ms(self):
        """Test format with milliseconds."""
        dt = datetime(2024, 1, 15, 10, 30, 0, 123456, tzinfo=UTC)
        result = format_iso(dt, include_ms=True)
        assert ".123" in result

    def test_without_tz(self):
        """Test format without timezone."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = format_iso(dt, include_tz=False)
        assert "Z" not in result
        assert "+" not in result


class TestFormatDate:
    """Tests for format_date function."""

    def test_format_date(self):
        """Test date formatting."""
        d = date(2024, 1, 15)
        assert format_date(d) == "2024-01-15"

    def test_format_datetime_as_date(self):
        """Test datetime formatted as date."""
        dt = datetime(2024, 1, 15, 10, 30)
        assert format_date(dt) == "2024-01-15"


class TestFormatTime:
    """Tests for format_time function."""

    def test_format_time(self):
        """Test time formatting."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        assert format_time(dt) == "10:30:45"


class TestFormatRelative:
    """Tests for format_relative function."""

    def test_just_now(self):
        """Test just now."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 15, 11, 59, 45, tzinfo=UTC)

        result = format_relative(dt, reference=reference)
        assert "just now" in result.lower()

    def test_minutes_ago(self):
        """Test minutes ago."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 15, 11, 55, 0, tzinfo=UTC)

        result = format_relative(dt, reference=reference)
        assert "5 minute" in result

    def test_hours_ago(self):
        """Test hours ago."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        result = format_relative(dt, reference=reference)
        assert "2 hour" in result

    def test_days_ago(self):
        """Test days ago."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 12, 12, 0, 0, tzinfo=UTC)

        result = format_relative(dt, reference=reference)
        assert "3 day" in result

    def test_short_format(self):
        """Test short format."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        result = format_relative(dt, reference=reference, short=True)
        assert result == "2h"

    def test_future_time(self):
        """Test future time."""
        reference = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        dt = datetime(2024, 1, 15, 14, 0, 0, tzinfo=UTC)

        result = format_relative(dt, reference=reference)
        assert "in 2 hour" in result


# =============================================================================
# TimeRange Tests
# =============================================================================


class TestTimeRange:
    """Tests for TimeRange class."""

    def test_duration(self):
        """Test duration calculation."""
        range_ = TimeRange(
            start=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        )
        assert range_.total_hours == 2.0

    def test_contains(self):
        """Test contains check."""
        range_ = TimeRange(
            start=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        )

        inside = datetime(2024, 1, 15, 11, 0, tzinfo=UTC)
        outside = datetime(2024, 1, 15, 13, 0, tzinfo=UTC)

        assert range_.contains(inside) is True
        assert range_.contains(outside) is False

    def test_overlaps(self):
        """Test overlap detection."""
        range1 = TimeRange(
            start=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
        )
        range2 = TimeRange(
            start=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
        )
        range3 = TimeRange(
            start=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 18, 0, tzinfo=UTC),
        )

        assert range1.overlaps(range2) is True
        assert range1.overlaps(range3) is False

    def test_intersection(self):
        """Test intersection."""
        range1 = TimeRange(
            start=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
        )
        range2 = TimeRange(
            start=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            end=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
        )

        intersection = range1.intersection(range2)

        assert intersection is not None
        assert intersection.start.hour == 12
        assert intersection.end.hour == 14

    def test_iterate_days(self):
        """Test day iteration."""
        range_ = TimeRange(
            start=datetime(2024, 1, 15, tzinfo=UTC),
            end=datetime(2024, 1, 17, tzinfo=UTC),
        )

        days = list(range_.iterate_days())
        assert len(days) == 3
        assert days[0] == date(2024, 1, 15)
        assert days[2] == date(2024, 1, 17)

    def test_last_n_days(self):
        """Test last N days factory."""
        range_ = TimeRange.last_n_days(7)
        assert range_.total_days == pytest.approx(7, abs=0.01)

    def test_last_n_hours(self):
        """Test last N hours factory."""
        range_ = TimeRange.last_n_hours(24)
        assert range_.total_hours == pytest.approx(24, abs=0.01)


# =============================================================================
# Date Arithmetic Tests
# =============================================================================


class TestAddTime:
    """Tests for add_time function."""

    def test_add_days(self):
        """Test adding days."""
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        result = add_time(dt, days=5)
        assert result.day == 20

    def test_add_months(self):
        """Test adding months."""
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        result = add_time(dt, months=2)
        assert result.month == 3

    def test_add_months_overflow(self):
        """Test month addition with day overflow."""
        dt = datetime(2024, 1, 31, 12, 0, tzinfo=UTC)
        result = add_time(dt, months=1)
        # Feb doesn't have 31 days, should be last day
        assert result.month == 2
        assert result.day == 29  # 2024 is leap year

    def test_add_years(self):
        """Test adding years."""
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        result = add_time(dt, years=1)
        assert result.year == 2025

    def test_add_years_leap_day(self):
        """Test adding years from leap day."""
        dt = datetime(2024, 2, 29, 12, 0, tzinfo=UTC)
        result = add_time(dt, years=1)
        # 2025 is not a leap year
        assert result.month == 2
        assert result.day == 28


class TestStartEndOfDay:
    """Tests for start/end of day functions."""

    def test_start_of_day(self):
        """Test start of day."""
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=UTC)
        result = start_of_day(dt)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_end_of_day(self):
        """Test end of day."""
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=UTC)
        result = end_of_day(dt)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59


class TestStartOfWeek:
    """Tests for start_of_week function."""

    def test_start_of_week(self):
        """Test start of week."""
        # Wednesday
        dt = datetime(2024, 1, 17, 14, 30, tzinfo=UTC)
        result = start_of_week(dt)
        # Should be Monday
        assert result.weekday() == 0
        assert result.day == 15


class TestStartEndOfMonth:
    """Tests for start/end of month functions."""

    def test_start_of_month(self):
        """Test start of month."""
        dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        result = start_of_month(dt)
        assert result.day == 1
        assert result.hour == 0

    def test_end_of_month(self):
        """Test end of month."""
        dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        result = end_of_month(dt)
        assert result.day == 31
        assert result.hour == 23

    def test_end_of_feb_leap_year(self):
        """Test end of February in leap year."""
        dt = datetime(2024, 2, 15, tzinfo=UTC)
        result = end_of_month(dt)
        assert result.day == 29


# =============================================================================
# Business Day Tests
# =============================================================================


class TestIsWeekend:
    """Tests for weekend/weekday functions."""

    def test_is_weekend_saturday(self):
        """Test Saturday is weekend."""
        assert is_weekend(date(2024, 1, 13)) is True

    def test_is_weekend_sunday(self):
        """Test Sunday is weekend."""
        assert is_weekend(date(2024, 1, 14)) is True

    def test_is_weekday(self):
        """Test weekday."""
        assert is_weekday(date(2024, 1, 15)) is True  # Monday
        assert is_weekday(date(2024, 1, 13)) is False  # Saturday


class TestNextWeekday:
    """Tests for next_weekday function."""

    def test_already_weekday(self):
        """Test already on weekday."""
        d = date(2024, 1, 15)  # Monday
        assert next_weekday(d) == d

    def test_from_saturday(self):
        """Test from Saturday."""
        d = date(2024, 1, 13)  # Saturday
        result = next_weekday(d)
        assert result == date(2024, 1, 15)  # Monday


class TestAddBusinessDays:
    """Tests for add_business_days function."""

    def test_add_business_days(self):
        """Test adding business days."""
        start = date(2024, 1, 15)  # Monday
        result = add_business_days(start, 5)
        # Mon + 5 business days = Mon
        assert result == date(2024, 1, 22)

    def test_add_business_days_over_weekend(self):
        """Test adding business days over weekend."""
        start = date(2024, 1, 18)  # Thursday
        result = add_business_days(start, 2)
        # Thu + 2 = Mon (skips weekend)
        assert result == date(2024, 1, 22)

    def test_subtract_business_days(self):
        """Test subtracting business days."""
        start = date(2024, 1, 22)  # Monday
        result = add_business_days(start, -5)
        assert result == date(2024, 1, 15)

    def test_with_holidays(self):
        """Test with holidays."""
        start = date(2024, 1, 15)  # Monday
        holidays = {date(2024, 1, 16)}  # Tuesday holiday
        result = add_business_days(start, 1, holidays)
        # Should skip Tuesday
        assert result == date(2024, 1, 17)


class TestBusinessDaysBetween:
    """Tests for business_days_between function."""

    def test_same_week(self):
        """Test business days in same week."""
        start = date(2024, 1, 15)  # Monday
        end = date(2024, 1, 19)  # Friday
        assert business_days_between(start, end) == 4

    def test_across_weekend(self):
        """Test business days across weekend."""
        start = date(2024, 1, 15)  # Monday
        end = date(2024, 1, 22)  # Next Monday
        assert business_days_between(start, end) == 5

    def test_reverse_order(self):
        """Test reverse date order."""
        start = date(2024, 1, 22)
        end = date(2024, 1, 15)
        assert business_days_between(start, end) == -5


# =============================================================================
# Age Calculation Tests
# =============================================================================


class TestAgeInYears:
    """Tests for age_in_years function."""

    def test_simple_age(self):
        """Test simple age calculation."""
        birth = date(2000, 1, 15)
        reference = date(2024, 6, 1)
        assert age_in_years(birth, reference) == 24

    def test_birthday_not_yet(self):
        """Test birthday hasn't occurred yet this year."""
        birth = date(2000, 6, 15)
        reference = date(2024, 1, 1)
        assert age_in_years(birth, reference) == 23


class TestTimeUntilSince:
    """Tests for time_until and time_since functions."""

    def test_time_until_future(self):
        """Test time until future datetime."""
        reference = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        target = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)

        result = time_until(target, reference)
        assert result.total_seconds() == 2 * HOUR

    def test_time_since_past(self):
        """Test time since past datetime."""
        reference = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        past = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

        result = time_since(past, reference)
        assert result.total_seconds() == 2 * HOUR
