"""AWS SSM Data Fetcher - Lambda Shared Layer

Lightweight shared core functionality for Lambda functions including:
- Configuration management
- Caching infrastructure
- Logging setup
- Error handling patterns

Heavy processing and output modules are included in individual function packages.
"""

__version__ = "2.0.0"
__author__ = "AWS SSM Data Fetcher"

# Import core shared functionality only
try:
    from .core.cache import CacheManager
    from .core.config import Config
    from .core.error_handling import (CacheError, CircuitBreakerError,
                                      RetryExhaustedError, ValidationError,
                                      circuit_breaker)
    from .core.logging import create_logger, setup_console_logging

    __all__ = [
        "Config",
        "CacheManager",
        "create_logger",
        "setup_console_logging",
        "CircuitBreakerError",
        "RetryExhaustedError",
        "ValidationError",
        "CacheError",
        "circuit_breaker",
    ]

except ImportError:
    # During development, core modules might not exist yet
    __all__ = []
