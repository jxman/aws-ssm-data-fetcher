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
    from .core.config import Config
    from .core.cache import CacheManager
    from .core.logging import create_logger, setup_console_logging
    from .core.error_handling import (
        CircuitBreakerError, 
        RetryExhaustedError,
        ValidationError,
        CacheError,
        circuit_breaker
    )
    
    __all__ = [
        'Config', 
        'CacheManager', 
        'create_logger', 
        'setup_console_logging',
        'CircuitBreakerError',
        'RetryExhaustedError', 
        'ValidationError',
        'CacheError',
        'circuit_breaker'
    ]
        
except ImportError:
    # During development, core modules might not exist yet
    __all__ = []