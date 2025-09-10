"""Core functionality for AWS SSM Data Fetcher.

This module contains the foundational utilities used across all other modules:
- Configuration management
- Caching system
- Logging utilities
- AWS session management
"""

try:
    from .config import Config

    __all__ = ["Config"]

    # Try to import cache manager if available
    try:
        from .cache import CacheManager

        __all__.append("CacheManager")
    except ImportError:
        pass

except ImportError:
    # During development, modules might not exist yet
    __all__ = []
