"""
Retry logic with exponential backoff for db-up.

This module provides retry functionality with configurable backoff strategies:
- Fixed: Same delay between retries
- Linear: Linearly increasing delay
- Exponential: Exponentially increasing delay (recommended)
- Jitter: Optional randomness to prevent thundering herd
"""

import time
import random
from typing import Any, Callable, Literal, Optional, TypeVar
from db_up.models import MonitorConfig

T = TypeVar("T")


def calculate_backoff(
    attempt: int, base_delay: int, strategy: str = "exponential", jitter: bool = True
) -> float:
    """
    Calculate backoff delay for a retry attempt.

    Args:
        attempt: Retry attempt number (1-based)
        base_delay: Base delay in seconds
        strategy: Backoff strategy: fixed, linear, exponential
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Delay in seconds

    Examples:
        >>> calculate_backoff(1, 5, 'fixed', jitter=False)
        5.0
        >>> calculate_backoff(2, 5, 'linear', jitter=False)
        10.0
        >>> calculate_backoff(2, 5, 'exponential', jitter=False)
        10.0
    """
    if strategy == "fixed":
        delay = float(base_delay)
    elif strategy == "linear":
        delay = float(base_delay * attempt)
    elif strategy == "exponential":
        delay = float(base_delay * (2 ** (attempt - 1)))
    else:
        raise ValueError(f"Invalid backoff strategy: {strategy}")

    # Add jitter if enabled
    if jitter:
        # Add random jitter of ±20%
        jitter_amount = delay * 0.2
        delay += random.uniform(-jitter_amount, jitter_amount)
        # Ensure delay is never negative
        delay = max(0.1, delay)

    return delay


def retry_with_backoff(
    func: Callable[[], T], config: MonitorConfig, logger: Optional[Any] = None
) -> T:
    """
    Execute a function with retry logic and backoff.

    This function will retry the given function up to max_retries times,
    with delays calculated according to the backoff strategy.

    Args:
        func: Function to execute (should return a result)
        config: Monitor configuration with retry settings
        logger: Optional logger for logging retry attempts

    Returns:
        Result from the function

    Raises:
        Exception: The last exception if all retries fail

    Example:
        >>> def check_db():
        ...     # Database check logic
        ...     return result
        >>> config = MonitorConfig(max_retries=3, retry_delay=5)
        >>> result = retry_with_backoff(check_db, config)
    """
    last_exception: Optional[Exception] = None

    # Try initial attempt + retries
    for attempt in range(config.max_retries + 1):
        try:
            result = func()

            # Log recovery if this was a retry
            if attempt > 0 and logger:
                logger.info(
                    f"Operation succeeded after {attempt} retries",
                    extra={"retry_attempt": attempt},
                )

            return result

        except Exception as e:
            last_exception = e

            # If this was the last attempt, don't retry
            if attempt >= config.max_retries:
                if logger:
                    logger.error(
                        f"Operation failed after {config.max_retries} retries",
                        extra={
                            "retry_attempt": attempt,
                            "max_retries": config.max_retries,
                        },
                    )
                break

            # Calculate backoff delay
            delay = calculate_backoff(
                attempt + 1,
                config.retry_delay,
                config.retry_backoff,
                config.retry_jitter,
            )

            # Log retry attempt
            if logger:
                logger.warning(
                    f"Operation failed, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{config.max_retries})",
                    extra={
                        "retry_attempt": attempt + 1,
                        "max_retries": config.max_retries,
                        "retry_delay": delay,
                    },
                )

            # Wait before retrying
            time.sleep(delay)

    # All retries exhausted, raise the last exception
    if last_exception:
        raise last_exception

    # This should never happen, but just in case
    raise RuntimeError("Retry logic failed unexpectedly")


class RetryContext:
    """
    Context manager for retry logic.

    This provides a more flexible way to use retry logic with
    custom error handling.

    Example:
        >>> config = MonitorConfig(max_retries=3)
        >>> with RetryContext(config) as retry:
        ...     while retry.should_retry():
        ...         try:
        ...             result = check_database()
        ...             retry.success()
        ...             break
        ...         except Exception as e:
        ...             retry.failure(e)
    """

    def __init__(self, config: MonitorConfig, logger: Optional[Any] = None):
        """
        Initialize retry context.

        Args:
            config: Monitor configuration with retry settings
            logger: Optional logger
        """
        self.config = config
        self.logger = logger
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._success = False

    def __enter__(self) -> "RetryContext":
        """Enter the context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """
        Exit the context.

        Returns:
            False to propagate exceptions
        """
        return False

    def should_retry(self) -> bool:
        """
        Check if should attempt/retry.

        Returns:
            True if should attempt, False if retries exhausted
        """
        if self._success:
            return False

        if self.attempt > self.config.max_retries:
            return False

        # If not the first attempt, wait before retrying
        if self.attempt > 0:
            delay = calculate_backoff(
                self.attempt,
                self.config.retry_delay,
                self.config.retry_backoff,
                self.config.retry_jitter,
            )

            if self.logger:
                self.logger.warning(
                    f"Retrying in {delay:.1f}s "
                    f"(attempt {self.attempt}/{self.config.max_retries})",
                    extra={
                        "retry_attempt": self.attempt,
                        "max_retries": self.config.max_retries,
                        "retry_delay": delay,
                    },
                )

            time.sleep(delay)

        self.attempt += 1
        return True

    def success(self) -> None:
        """Mark the operation as successful."""
        self._success = True

        if self.attempt > 1 and self.logger:
            self.logger.info(
                f"Operation succeeded after {self.attempt - 1} retries",
                extra={"retry_attempt": self.attempt - 1},
            )

    def failure(self, exception: Exception) -> None:
        """
        Record a failure.

        Args:
            exception: The exception that occurred
        """
        self.last_exception = exception

        if self.attempt > self.config.max_retries and self.logger:
            self.logger.error(
                f"Operation failed after {self.config.max_retries} retries",
                extra={
                    "retry_attempt": self.attempt,
                    "max_retries": self.config.max_retries,
                },
            )
