"""AWS SSM Data Fetcher - Modular Package

A modular Python package for fetching AWS service availability data from Systems Manager
Parameter Store and generating comprehensive reports in multiple formats.

This package is designed for both standalone execution and AWS Lambda deployment.
"""

__version__ = "2.0.0"
__author__ = "AWS SSM Data Fetcher"

# Import main classes for easy access
try:
    from .core.config import Config

    __all__ = ["Config"]

    # Try to import cache manager if available
    try:
        from .core.cache import CacheManager

        __all__.append("CacheManager")
    except ImportError:
        pass

except ImportError:
    # During development, core modules might not exist yet
    __all__ = []
