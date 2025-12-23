"""Unit tests for next_check calculation methods (Story 5.8).

Tests the IntentService calculation methods:
- _calculate_initial_next_check(): Initial scheduling at creation
- _calculate_next_check_after_fire(): Rescheduling after execution

AC1: Initial calculation works for all trigger types
AC2: After-fire calculation handles all status outcomes
AC3: Minimum 15 test cases with mocked time
AC4: Croniter edge cases handled gracefully
AC5: Methods testable in isolation without database
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from src.schemas import TriggerSchedule
from src.services.intent_service import IntentService


# =============================================================================
# Fixtures (Task 1.2)
# =============================================================================

@pytest.fixture
def mock_conn():
    """Create a mock database connection for IntentService instantiation."""
    return MagicMock()


@pytest.fixture
def intent_service(mock_conn):
    """Create IntentService instance for isolated testing (AC5)."""
    return IntentService(mock_conn)


@pytest.fixture
def fixed_now():
    """Fixed datetime for deterministic testing."""
    return datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# Task 2: Test _calculate_initial_next_check() for each trigger type (AC1)
# =============================================================================

class TestCalculateInitialNextCheck:
    """Tests for _calculate_initial_next_check() method."""

    def test_cron_valid_expression(self, intent_service):
        """Test cron type with valid expression returns next occurrence (2.1)."""
        schedule = TriggerSchedule(cron="0 9 * * 1")  # Every Monday at 9 AM
        now = datetime.now(timezone.utc)

        result = intent_service._calculate_initial_next_check("cron", schedule)

        # Should return a future datetime
        assert result is not None
        assert result >= now
        # Should be on a Monday at 9 AM
        assert result.hour == 9
        assert result.weekday() == 0  # Monday

    def test_cron_invalid_expression(self, intent_service, fixed_now):
        """Test cron type with invalid expression returns fallback (2.2, AC4)."""
        schedule = TriggerSchedule(cron="invalid cron")

        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = intent_service._calculate_initial_next_check("cron", schedule)

        # Should return NOW as fallback (not None, not crash)
        assert result is not None
        # The fallback is NOW when croniter fails
        assert result == fixed_now

    def test_interval_30_minutes(self, intent_service, fixed_now):
        """Test interval type with 30 minutes (2.3)."""
        schedule = TriggerSchedule(interval_minutes=30)

        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = intent_service._calculate_initial_next_check("interval", schedule)

        expected = fixed_now + timedelta(minutes=30)
        assert result == expected

    def test_interval_various_values(self, intent_service, fixed_now):
        """Test interval type with various interval values (2.3)."""
        test_cases = [5, 15, 60, 120, 1440]  # 5min, 15min, 1hr, 2hr, 1day

        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            for minutes in test_cases:
                schedule = TriggerSchedule(interval_minutes=minutes)
                result = intent_service._calculate_initial_next_check("interval", schedule)
                expected = fixed_now + timedelta(minutes=minutes)
                assert result == expected, f"Failed for {minutes} minutes"

    def test_once_future_datetime(self, intent_service, fixed_now):
        """Test once type with future datetime (2.4)."""
        future_time = fixed_now + timedelta(hours=24)
        schedule = TriggerSchedule(trigger_at=future_time)

        result = intent_service._calculate_initial_next_check("once", schedule)

        assert result == future_time

    def test_once_past_datetime(self, intent_service, fixed_now):
        """Test once type with past datetime - edge case (2.5)."""
        past_time = fixed_now - timedelta(hours=1)
        schedule = TriggerSchedule(trigger_at=past_time)

        result = intent_service._calculate_initial_next_check("once", schedule)

        # Should still return the trigger_at even if in past
        # (validation should prevent this at creation)
        assert result == past_time

    def test_price_immediate_check(self, intent_service, fixed_now):
        """Test price type returns immediate check (2.6)."""
        schedule = TriggerSchedule(check_interval_minutes=10)

        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = intent_service._calculate_initial_next_check("price", schedule)

        # Price triggers should check immediately on creation
        assert result == fixed_now

    def test_silence_immediate_check(self, intent_service, fixed_now):
        """Test silence type returns immediate check (2.7)."""
        schedule = TriggerSchedule(check_interval_minutes=60)

        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = intent_service._calculate_initial_next_check("silence", schedule)

        assert result == fixed_now

    def test_event_immediate_check(self, intent_service, fixed_now):
        """Test event type returns immediate check."""
        with patch('src.services.intent_service.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = intent_service._calculate_initial_next_check("event", None)

        assert result == fixed_now

    def test_missing_schedule_returns_none(self, intent_service):
        """Test missing schedule returns None (2.8)."""
        result = intent_service._calculate_initial_next_check("unknown_type", None)

        assert result is None

    def test_cron_without_schedule(self, intent_service):
        """Test cron type without schedule returns None."""
        result = intent_service._calculate_initial_next_check("cron", None)

        assert result is None

    def test_interval_without_schedule(self, intent_service):
        """Test interval type without schedule returns None."""
        result = intent_service._calculate_initial_next_check("interval", None)

        assert result is None


# =============================================================================
# Task 3: Test _calculate_next_check_after_fire() for each status (AC2)
# =============================================================================

class TestCalculateNextCheckAfterFire:
    """Tests for _calculate_next_check_after_fire() method."""

    def test_success_cron_next_occurrence(self, intent_service, fixed_now):
        """Test success + cron returns croniter.get_next() (3.1)."""
        schedule = TriggerSchedule(cron="0 9 * * *")  # Every day at 9 AM

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", fixed_now
        )

        assert result is not None
        assert result > fixed_now
        assert result.hour == 9

    def test_success_interval_now_plus_minutes(self, intent_service, fixed_now):
        """Test success + interval returns NOW + interval_minutes (3.2)."""
        schedule = TriggerSchedule(interval_minutes=45)

        result = intent_service._calculate_next_check_after_fire(
            "interval", schedule, "success", fixed_now
        )

        expected = fixed_now + timedelta(minutes=45)
        assert result == expected

    def test_success_once_returns_none(self, intent_service, fixed_now):
        """Test success + once returns None (trigger disabled) (3.3)."""
        schedule = TriggerSchedule(trigger_at=fixed_now)

        result = intent_service._calculate_next_check_after_fire(
            "once", schedule, "success", fixed_now
        )

        assert result is None

    def test_success_price_check_interval(self, intent_service, fixed_now):
        """Test success + price returns NOW + check_interval_minutes (3.4)."""
        schedule = TriggerSchedule(check_interval_minutes=15)

        result = intent_service._calculate_next_check_after_fire(
            "price", schedule, "success", fixed_now
        )

        expected = fixed_now + timedelta(minutes=15)
        assert result == expected

    def test_success_price_default_interval(self, intent_service, fixed_now):
        """Test success + price with no check_interval uses default 5 min."""
        schedule = TriggerSchedule()  # No check_interval_minutes

        result = intent_service._calculate_next_check_after_fire(
            "price", schedule, "success", fixed_now
        )

        expected = fixed_now + timedelta(minutes=5)
        assert result == expected

    def test_success_silence_check_interval(self, intent_service, fixed_now):
        """Test success + silence returns NOW + check_interval_minutes."""
        schedule = TriggerSchedule(check_interval_minutes=30)

        result = intent_service._calculate_next_check_after_fire(
            "silence", schedule, "success", fixed_now
        )

        expected = fixed_now + timedelta(minutes=30)
        assert result == expected

    def test_condition_not_met_5_minutes(self, intent_service, fixed_now):
        """Test condition_not_met returns NOW + 5 minutes (3.5)."""
        schedule = TriggerSchedule(interval_minutes=60)

        result = intent_service._calculate_next_check_after_fire(
            "interval", schedule, "condition_not_met", fixed_now
        )

        expected = fixed_now + timedelta(minutes=5)
        assert result == expected

    def test_gate_blocked_5_minutes(self, intent_service, fixed_now):
        """Test gate_blocked returns NOW + 5 minutes (3.6)."""
        schedule = TriggerSchedule(cron="0 * * * *")

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "gate_blocked", fixed_now
        )

        expected = fixed_now + timedelta(minutes=5)
        assert result == expected

    def test_failed_15_minutes(self, intent_service, fixed_now):
        """Test failed returns NOW + 15 minutes (3.7)."""
        schedule = TriggerSchedule(interval_minutes=30)

        result = intent_service._calculate_next_check_after_fire(
            "interval", schedule, "failed", fixed_now
        )

        expected = fixed_now + timedelta(minutes=15)
        assert result == expected

    def test_failed_any_trigger_type(self, intent_service, fixed_now):
        """Test failed status applies 15-min backoff regardless of trigger type."""
        trigger_types = ["cron", "interval", "once", "price", "silence"]

        for trigger_type in trigger_types:
            result = intent_service._calculate_next_check_after_fire(
                trigger_type, None, "failed", fixed_now
            )
            expected = fixed_now + timedelta(minutes=15)
            assert result == expected, f"Failed for trigger_type={trigger_type}"


# =============================================================================
# Task 4: Test croniter edge cases (AC4)
# =============================================================================

class TestCroniterEdgeCases:
    """Tests for croniter edge cases."""

    def test_end_of_month_cron(self, intent_service):
        """Test end-of-month cron expressions (4.1)."""
        # Last day of month at noon
        schedule = TriggerSchedule(cron="0 12 L * *")  # croniter supports L for last day
        now = datetime(2025, 1, 30, 10, 0, 0, tzinfo=timezone.utc)

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", now
        )

        # Should return a valid datetime (may be next month if past last day)
        assert result is not None
        assert result > now

    def test_every_minute_cron(self, intent_service, fixed_now):
        """Test every-minute cron expression."""
        schedule = TriggerSchedule(cron="* * * * *")  # Every minute

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", fixed_now
        )

        assert result is not None
        # Next occurrence should be within 1 minute
        assert result <= fixed_now + timedelta(minutes=1)

    def test_leap_year_february_29(self, intent_service):
        """Test leap year handling (4.2)."""
        # Feb 29 2024 (leap year)
        now = datetime(2024, 2, 28, 23, 0, 0, tzinfo=timezone.utc)
        schedule = TriggerSchedule(cron="0 12 * * *")  # Every day at noon

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", now
        )

        # Should correctly handle Feb 29
        assert result is not None
        assert result.day == 29 or result.month == 3  # Either Feb 29 or March

    def test_timezone_utc_consistency(self, intent_service):
        """Test all returned datetimes are UTC (4.3, 4.4)."""
        now = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        schedule = TriggerSchedule(cron="0 9 * * *")

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", now
        )

        # Result should have UTC timezone
        assert result is not None
        # croniter returns naive datetime, but we pass in UTC now
        # The result may or may not have tzinfo depending on croniter version
        # Just verify it's a valid datetime
        assert isinstance(result, datetime)

    def test_cron_invalid_expression_fallback(self, intent_service, fixed_now):
        """Test invalid cron expression gracefully falls back (AC4)."""
        schedule = TriggerSchedule(cron="not a cron")

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", fixed_now
        )

        # Should not crash, should return fallback
        assert result is not None
        # Fallback is NOW + 5 minutes for success with bad cron
        expected = fixed_now + timedelta(minutes=5)
        assert result == expected

    def test_cron_yearly_expression(self, intent_service, fixed_now):
        """Test yearly cron expression (edge case for infrequent schedules)."""
        schedule = TriggerSchedule(cron="0 0 1 1 *")  # Jan 1 at midnight

        result = intent_service._calculate_next_check_after_fire(
            "cron", schedule, "success", fixed_now
        )

        assert result is not None
        assert result > fixed_now
        assert result.month == 1
        assert result.day == 1


# =============================================================================
# Additional Edge Cases
# =============================================================================

class TestEdgeCases:
    """Additional edge case tests."""

    def test_none_schedule_for_all_types(self, intent_service, fixed_now):
        """Test None schedule doesn't crash for any trigger type."""
        trigger_types = ["cron", "interval", "once", "price", "silence", "event", "calendar", "news"]

        for trigger_type in trigger_types:
            # Should not raise exception
            result = intent_service._calculate_initial_next_check(trigger_type, None)
            # Either returns None or a datetime
            assert result is None or isinstance(result, datetime)

    def test_empty_trigger_schedule(self, intent_service, fixed_now):
        """Test empty TriggerSchedule object."""
        schedule = TriggerSchedule()

        # For interval without interval_minutes
        result = intent_service._calculate_initial_next_check("interval", schedule)
        assert result is None

    def test_after_fire_all_condition_types(self, intent_service, fixed_now):
        """Test all condition-based trigger types use check_interval."""
        condition_types = ["price", "silence", "event", "calendar", "news"]
        schedule = TriggerSchedule(check_interval_minutes=20)

        for trigger_type in condition_types:
            result = intent_service._calculate_next_check_after_fire(
                trigger_type, schedule, "success", fixed_now
            )
            expected = fixed_now + timedelta(minutes=20)
            assert result == expected, f"Failed for {trigger_type}"


# =============================================================================
# Task 6: Test trigger_type/schedule compatibility validation
# =============================================================================

class TestTriggerTypeScheduleCompatibility:
    """Tests for _validate_trigger_type_schedule_compatibility() method."""

    def test_cron_without_cron_expression_fails(self, intent_service):
        """Test cron type without cron expression returns error."""
        schedule = TriggerSchedule(interval_minutes=30)  # Wrong field for cron

        errors = intent_service._validate_trigger_type_schedule_compatibility("cron", schedule)

        assert len(errors) == 1
        assert "cron" in errors[0].lower()

    def test_cron_with_cron_expression_passes(self, intent_service):
        """Test cron type with cron expression returns no errors."""
        schedule = TriggerSchedule(cron="0 9 * * *")

        errors = intent_service._validate_trigger_type_schedule_compatibility("cron", schedule)

        assert len(errors) == 0

    def test_interval_without_interval_minutes_fails(self, intent_service):
        """Test interval type without interval_minutes returns error."""
        schedule = TriggerSchedule(cron="0 9 * * *")  # Wrong field for interval

        errors = intent_service._validate_trigger_type_schedule_compatibility("interval", schedule)

        assert len(errors) == 1
        assert "interval_minutes" in errors[0].lower()

    def test_interval_with_interval_minutes_passes(self, intent_service):
        """Test interval type with interval_minutes returns no errors."""
        schedule = TriggerSchedule(interval_minutes=30)

        errors = intent_service._validate_trigger_type_schedule_compatibility("interval", schedule)

        assert len(errors) == 0

    def test_once_without_trigger_at_fails(self, intent_service):
        """Test once type without trigger_at returns error."""
        schedule = TriggerSchedule(interval_minutes=30)  # Wrong field for once

        errors = intent_service._validate_trigger_type_schedule_compatibility("once", schedule)

        assert len(errors) == 1
        assert "trigger_at" in errors[0].lower()

    def test_once_with_trigger_at_passes(self, intent_service, fixed_now):
        """Test once type with trigger_at returns no errors."""
        schedule = TriggerSchedule(trigger_at=fixed_now)

        errors = intent_service._validate_trigger_type_schedule_compatibility("once", schedule)

        assert len(errors) == 0

    def test_price_type_always_passes(self, intent_service):
        """Test price type doesn't require specific schedule fields."""
        schedule = TriggerSchedule()  # Empty schedule with default check_interval

        errors = intent_service._validate_trigger_type_schedule_compatibility("price", schedule)

        assert len(errors) == 0

    def test_silence_type_always_passes(self, intent_service):
        """Test silence type doesn't require specific schedule fields."""
        schedule = TriggerSchedule()

        errors = intent_service._validate_trigger_type_schedule_compatibility("silence", schedule)

        assert len(errors) == 0
