"""Tests for retry logic."""

import pytest
import time
from unittest.mock import Mock
from db_up.retry import (
    calculate_backoff,
    retry_with_backoff,
    RetryContext,
)
from db_up.models import MonitorConfig


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_fixed_backoff(self) -> None:
        """Test fixed backoff strategy."""
        assert calculate_backoff(1, 5, "fixed", jitter=False) == 5.0
        assert calculate_backoff(2, 5, "fixed", jitter=False) == 5.0
        assert calculate_backoff(3, 5, "fixed", jitter=False) == 5.0

    def test_linear_backoff(self) -> None:
        """Test linear backoff strategy."""
        assert calculate_backoff(1, 5, "linear", jitter=False) == 5.0
        assert calculate_backoff(2, 5, "linear", jitter=False) == 10.0
        assert calculate_backoff(3, 5, "linear", jitter=False) == 15.0

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff strategy."""
        assert calculate_backoff(1, 5, "exponential", jitter=False) == 5.0
        assert calculate_backoff(2, 5, "exponential", jitter=False) == 10.0
        assert calculate_backoff(3, 5, "exponential", jitter=False) == 20.0
        assert calculate_backoff(4, 5, "exponential", jitter=False) == 40.0

    def test_jitter_adds_randomness(self) -> None:
        """Test that jitter adds randomness to delays."""
        delays = [
            calculate_backoff(2, 5, "exponential", jitter=True) for _ in range(10)
        ]

        # All delays should be different (with high probability)
        assert len(set(delays)) > 5

        # All delays should be around 10s (5 * 2^1)
        for delay in delays:
            assert 8 <= delay <= 12

    def test_jitter_never_negative(self) -> None:
        """Test that jitter never produces negative delays."""
        for attempt in range(1, 10):
            delay = calculate_backoff(attempt, 1, "exponential", jitter=True)
            assert delay > 0

    def test_invalid_strategy_raises_error(self) -> None:
        """Test that invalid strategy raises ValueError."""
        with pytest.raises(ValueError) as exc:
            calculate_backoff(1, 5, "invalid")

        assert "Invalid backoff strategy" in str(exc.value)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_success_on_first_attempt(self) -> None:
        """Test that successful function returns immediately."""
        config = MonitorConfig(max_retries=3, retry_delay=1)
        mock_func = Mock(return_value="success")

        result = retry_with_backoff(mock_func, config)

        assert result == "success"
        assert mock_func.call_count == 1

    def test_success_after_retries(self) -> None:
        """Test that function succeeds after retries."""
        config = MonitorConfig(max_retries=3, retry_delay=1, retry_jitter=False)
        mock_func = Mock(
            side_effect=[Exception("fail 1"), Exception("fail 2"), "success"]
        )

        start_time = time.time()
        result = retry_with_backoff(mock_func, config)
        elapsed = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 3
        # Should have waited for 2 retries (1s + 2s with linear backoff)
        # Using exponential by default: 1s + 2s = 3s
        assert elapsed >= 2.0  # At least 2 retries with 1s base delay

    def test_all_retries_exhausted(self) -> None:
        """Test that exception is raised after all retries fail."""
        config = MonitorConfig(max_retries=2, retry_delay=1, retry_jitter=False)
        mock_func = Mock(side_effect=Exception("always fails"))

        with pytest.raises(Exception) as exc:
            retry_with_backoff(mock_func, config)

        assert "always fails" in str(exc.value)
        assert mock_func.call_count == 3  # Initial + 2 retries

    def test_zero_retries(self) -> None:
        """Test with zero retries (fail immediately)."""
        config = MonitorConfig(max_retries=0)
        mock_func = Mock(side_effect=Exception("fail"))

        with pytest.raises(Exception):
            retry_with_backoff(mock_func, config)

        assert mock_func.call_count == 1

    def test_logging_on_retry(self) -> None:
        """Test that retry attempts are logged."""
        config = MonitorConfig(max_retries=2, retry_delay=1, retry_jitter=False)
        mock_func = Mock(side_effect=[Exception("fail"), "success"])
        mock_logger = Mock()

        result = retry_with_backoff(mock_func, config, logger=mock_logger)

        assert result == "success"
        # Should log warning for retry and info for recovery
        assert mock_logger.warning.called
        assert mock_logger.info.called

    def test_logging_on_final_failure(self) -> None:
        """Test that final failure is logged."""
        config = MonitorConfig(max_retries=1, retry_delay=1, retry_jitter=False)
        mock_func = Mock(side_effect=Exception("fail"))
        mock_logger = Mock()

        with pytest.raises(Exception):
            retry_with_backoff(mock_func, config, logger=mock_logger)

        assert mock_logger.error.called

    def test_backoff_strategy_applied(self) -> None:
        """Test that backoff strategy is correctly applied."""
        config = MonitorConfig(
            max_retries=2, retry_delay=1, retry_backoff="fixed", retry_jitter=False
        )
        mock_func = Mock(
            side_effect=[Exception("fail 1"), Exception("fail 2"), "success"]
        )

        start_time = time.time()
        retry_with_backoff(mock_func, config)
        elapsed = time.time() - start_time

        # With fixed backoff, should wait 1s + 1s = 2s
        assert elapsed >= 2.0
        assert elapsed < 3.0


class TestRetryContext:
    """Tests for RetryContext class."""

    def test_success_on_first_attempt(self) -> None:
        """Test successful operation on first attempt."""
        config = MonitorConfig(max_retries=3)

        with RetryContext(config) as retry:
            assert retry.should_retry() is True
            retry.success()
            assert retry.should_retry() is False

    def test_success_after_retries(self) -> None:
        """Test successful operation after retries."""
        config = MonitorConfig(max_retries=3, retry_delay=1, retry_jitter=False)
        attempt_count = 0

        with RetryContext(config) as retry:
            while retry.should_retry():
                attempt_count += 1
                if attempt_count < 3:
                    retry.failure(Exception("fail"))
                else:
                    retry.success()
                    break

        assert attempt_count == 3

    def test_all_retries_exhausted(self) -> None:
        """Test that retries are exhausted."""
        config = MonitorConfig(max_retries=2, retry_delay=1, retry_jitter=False)
        attempt_count = 0

        with RetryContext(config) as retry:
            while retry.should_retry():
                attempt_count += 1
                retry.failure(Exception("fail"))

        assert attempt_count == 3  # Initial + 2 retries
        assert retry.last_exception is not None

    def test_logging_on_retry(self) -> None:
        """Test that retry attempts are logged."""
        config = MonitorConfig(max_retries=2, retry_delay=1, retry_jitter=False)
        mock_logger = Mock()

        with RetryContext(config, logger=mock_logger) as retry:
            assert retry.should_retry()
            retry.failure(Exception("fail"))
            assert retry.should_retry()
            retry.success()

        # Should log warning for retry and info for success
        assert mock_logger.warning.called
        assert mock_logger.info.called

    def test_logging_on_final_failure(self) -> None:
        """Test that final failure is logged."""
        config = MonitorConfig(max_retries=1, retry_delay=1, retry_jitter=False)
        mock_logger = Mock()

        with RetryContext(config, logger=mock_logger) as retry:
            while retry.should_retry():
                retry.failure(Exception("fail"))

        assert mock_logger.error.called

    def test_context_manager_protocol(self) -> None:
        """Test that context manager protocol works correctly."""
        config = MonitorConfig(max_retries=1)

        # Should not raise exception
        with RetryContext(config) as retry:
            pass

        assert retry is not None

    def test_no_retry_on_zero_max_retries(self) -> None:
        """Test with zero max retries."""
        config = MonitorConfig(max_retries=0)
        attempt_count = 0

        with RetryContext(config) as retry:
            while retry.should_retry():
                attempt_count += 1
                retry.failure(Exception("fail"))

        assert attempt_count == 1  # Only initial attempt


class TestIntegration:
    """Integration tests for retry logic."""

    def test_realistic_database_retry_scenario(self) -> None:
        """Test realistic scenario of database connection retry."""
        config = MonitorConfig(
            max_retries=3,
            retry_delay=1,
            retry_backoff="exponential",
            retry_jitter=False,
        )

        # Simulate database that fails twice then succeeds
        call_count = 0

        def check_database():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Database unavailable")
            return {"status": "success"}

        result = retry_with_backoff(check_database, config)

        assert result["status"] == "success"
        assert call_count == 3

    def test_exponential_backoff_timing(self) -> None:
        """Test that exponential backoff timing is correct."""
        config = MonitorConfig(
            max_retries=3,
            retry_delay=1,
            retry_backoff="exponential",
            retry_jitter=False,
        )

        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("fail")

        start_time = time.time()
        try:
            retry_with_backoff(always_fail, config)
        except Exception:
            pass
        elapsed = time.time() - start_time

        # Exponential backoff: 1s + 2s + 4s = 7s
        assert elapsed >= 7.0
        assert elapsed < 8.0
        assert call_count == 4  # Initial + 3 retries
