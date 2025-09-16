"""Advanced error handling utilities for AWS data fetching operations."""

import functools
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from .logging import get_logger


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    EXPONENTIAL_BACKOFF_WITH_JITTER = "exponential_backoff_with_jitter"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class RetryableError(Exception):
    """Exception for errors that should trigger retries."""

    pass


class NonRetryableError(Exception):
    """Exception for errors that should not be retried."""

    pass


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        non_retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        jitter_factor: float = 0.1,
    ):
        """Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            strategy: Retry strategy to use
            retryable_exceptions: Exception types that should trigger retries
            non_retryable_exceptions: Exception types that should not be retried
            jitter_factor: Jitter factor for randomizing delays (0.0-1.0)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.jitter_factor = jitter_factor

        # Default retryable exceptions (network/service errors)
        if retryable_exceptions is None:
            import requests
            from botocore.exceptions import ClientError

            self.retryable_exceptions = (
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                ClientError,  # AWS service errors
                RetryableError,
                ConnectionError,
                TimeoutError,
            )
        else:
            self.retryable_exceptions = retryable_exceptions

        # Default non-retryable exceptions
        if non_retryable_exceptions is None:
            self.non_retryable_exceptions = (
                NonRetryableError,
                KeyboardInterrupt,
                SystemExit,
                MemoryError,
            )
        else:
            self.non_retryable_exceptions = non_retryable_exceptions


class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: Type[Exception] = Exception,
        half_open_max_calls: int = 3,
    ):
        """Initialize circuit breaker configuration.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery (seconds)
            expected_exception: Exception type that triggers circuit breaker
            half_open_max_calls: Max calls allowed in half-open state for testing
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(self, config: CircuitBreakerConfig):
        """Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.logger = get_logger(f"circuit_breaker")

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.circuit_opens = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        self.total_calls += 1

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("Circuit breaker: Attempting reset (HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                self.logger.warning("Circuit breaker: OPEN - failing fast")
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.config.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.successful_calls += 1
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.config.half_open_max_calls:
                self.logger.info("Circuit breaker: Recovery successful (CLOSED)")
                self.state = CircuitState.CLOSED
                self.half_open_calls = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            self.logger.warning("Circuit breaker: Half-open test failed (OPEN)")
            self.state = CircuitState.OPEN
            self.circuit_opens += 1
        elif self.failure_count >= self.config.failure_threshold:
            self.logger.warning(f"Circuit breaker: Failure threshold reached (OPEN)")
            self.state = CircuitState.OPEN
            self.circuit_opens += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "failure_count": self.failure_count,
            "circuit_opens": self.circuit_opens,
            "success_rate": self.successful_calls / max(self.total_calls, 1),
            "failure_rate": self.failed_calls / max(self.total_calls, 1),
        }


def with_retry(retry_config: Optional[RetryConfig] = None):
    """Decorator for adding retry logic to functions.

    Args:
        retry_config: Retry configuration (uses defaults if None)

    Returns:
        Decorated function with retry logic
    """
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(f"retry.{func.__name__}")

            for attempt in range(retry_config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"Succeeded on attempt {attempt + 1}")
                    return result

                except retry_config.non_retryable_exceptions as e:
                    logger.error(f"Non-retryable error on attempt {attempt + 1}: {e}")
                    raise e

                except retry_config.retryable_exceptions as e:
                    if attempt == retry_config.max_attempts - 1:
                        logger.error(
                            f"All {retry_config.max_attempts} attempts failed. Last error: {e}"
                        )
                        raise e

                    # Calculate delay
                    delay = _calculate_delay(
                        attempt,
                        retry_config.base_delay,
                        retry_config.max_delay,
                        retry_config.strategy,
                        retry_config.jitter_factor,
                    )

                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

                except Exception as e:
                    # Unknown exception - check if it should be retried
                    if any(
                        isinstance(e, exc_type)
                        for exc_type in retry_config.retryable_exceptions
                    ):
                        if attempt == retry_config.max_attempts - 1:
                            logger.error(
                                f"All {retry_config.max_attempts} attempts failed. Last error: {e}"
                            )
                            raise e

                        delay = _calculate_delay(
                            attempt,
                            retry_config.base_delay,
                            retry_config.max_delay,
                            retry_config.strategy,
                            retry_config.jitter_factor,
                        )

                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"Unknown error on attempt {attempt + 1}: {e}")
                        raise e

            # This should never be reached
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator


def with_circuit_breaker(circuit_config: Optional[CircuitBreakerConfig] = None):
    """Decorator for adding circuit breaker protection to functions.

    Args:
        circuit_config: Circuit breaker configuration

    Returns:
        Decorated function with circuit breaker protection
    """
    if circuit_config is None:
        circuit_config = CircuitBreakerConfig()

    # Create circuit breaker instance per function
    circuit_breaker = CircuitBreaker(circuit_config)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)

        # Add circuit breaker stats access
        wrapper.get_circuit_stats = circuit_breaker.get_stats
        return wrapper

    return decorator


def with_retry_and_circuit_breaker(
    retry_config: Optional[RetryConfig] = None,
    circuit_config: Optional[CircuitBreakerConfig] = None,
):
    """Decorator combining retry and circuit breaker functionality.

    Args:
        retry_config: Retry configuration
        circuit_config: Circuit breaker configuration

    Returns:
        Decorated function with both retry and circuit breaker protection
    """

    def decorator(func: Callable) -> Callable:
        # Apply circuit breaker first, then retry
        circuit_protected = with_circuit_breaker(circuit_config)(func)
        retry_protected = with_retry(retry_config)(circuit_protected)

        # Preserve circuit breaker stats access
        if hasattr(circuit_protected, "get_circuit_stats"):
            retry_protected.get_circuit_stats = circuit_protected.get_circuit_stats

        return retry_protected

    return decorator


def _calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    strategy: RetryStrategy,
    jitter_factor: float,
) -> float:
    """Calculate delay for retry attempt.

    Args:
        attempt: Attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        strategy: Retry strategy
        jitter_factor: Jitter factor for randomization

    Returns:
        Delay in seconds
    """
    if strategy == RetryStrategy.FIXED_INTERVAL:
        delay = base_delay

    elif strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = base_delay * (attempt + 1)

    elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = base_delay * (2**attempt)

    elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER:
        delay = base_delay * (2**attempt)
        # Add jitter to prevent thundering herd
        jitter = delay * jitter_factor * random.random()
        delay += jitter

    else:
        delay = base_delay

    # Apply maximum delay limit
    return min(delay, max_delay)


class ErrorHandler:
    """Centralized error handler for AWS operations."""

    def __init__(self):
        """Initialize error handler."""
        self.logger = get_logger("error_handler")

    def classify_aws_error(self, error: Exception) -> Tuple[bool, str]:
        """Classify AWS error for retry decision.

        Args:
            error: Exception to classify

        Returns:
            Tuple of (should_retry: bool, error_category: str)
        """
        error_str = str(error).lower()

        # Throttling errors - always retry
        if any(
            keyword in error_str
            for keyword in ["throttling", "throttled", "rate exceeded"]
        ):
            return True, "throttling"

        # Network/connection errors - retry
        if any(
            keyword in error_str
            for keyword in ["timeout", "connection", "network", "dns"]
        ):
            return True, "network"

        # Service unavailable - retry
        if any(
            keyword in error_str
            for keyword in ["service unavailable", "503", "502", "504"]
        ):
            return True, "service_unavailable"

        # Authentication errors - don't retry
        if any(
            keyword in error_str
            for keyword in ["access denied", "unauthorized", "401", "403"]
        ):
            return False, "authentication"

        # Not found errors - don't retry
        if any(
            keyword in error_str for keyword in ["not found", "404", "does not exist"]
        ):
            return False, "not_found"

        # Parameter validation errors - don't retry
        if any(
            keyword in error_str
            for keyword in ["validation", "invalid parameter", "bad request", "400"]
        ):
            return False, "validation"

        # Unknown errors - conservative approach, retry
        return True, "unknown"

    def get_aws_retry_config(self) -> RetryConfig:
        """Get AWS-optimized retry configuration."""
        import requests
        from botocore.exceptions import BotoCoreError, ClientError

        return RetryConfig(
            max_attempts=5,  # More attempts for AWS operations
            base_delay=1.0,
            max_delay=30.0,  # Reasonable max for AWS operations
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
            retryable_exceptions=(
                ClientError,
                BotoCoreError,
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                ConnectionError,
                TimeoutError,
                RetryableError,
            ),
            non_retryable_exceptions=(
                NonRetryableError,
                KeyboardInterrupt,
                SystemExit,
                MemoryError,
            ),
            jitter_factor=0.1,
        )

    def get_aws_circuit_breaker_config(self) -> CircuitBreakerConfig:
        """Get AWS-optimized circuit breaker configuration."""
        return CircuitBreakerConfig(
            failure_threshold=3,  # Open after 3 failures
            recovery_timeout=60.0,  # Wait 1 minute before testing
            expected_exception=Exception,
            half_open_max_calls=2,  # Test with 2 calls
        )
