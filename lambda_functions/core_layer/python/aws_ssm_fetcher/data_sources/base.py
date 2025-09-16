"""Base interface for data sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DataSource(ABC):
    """Abstract base class for all data sources."""

    def __init__(self, cache_manager=None):
        """Initialize data source with optional cache manager."""
        self.cache_manager = cache_manager

    @abstractmethod
    def fetch_data(self, **kwargs) -> Any:
        """Fetch data from the source.

        Args:
            **kwargs: Source-specific parameters

        Returns:
            Fetched data in source-specific format
        """
        pass

    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if available.

        Args:
            cache_key: Key to look up cached data

        Returns:
            Cached data if available and valid, None otherwise
        """
        if self.cache_manager:
            return self.cache_manager.get(cache_key)
        return None

    def cache_data(self, cache_key: str, data: Any) -> bool:
        """Cache data for future use.

        Args:
            cache_key: Key to store data under
            data: Data to cache

        Returns:
            True if cached successfully, False otherwise
        """
        if self.cache_manager:
            return self.cache_manager.set(cache_key, data)
        return False


class AWSDataSource(DataSource):
    """Base class for AWS-specific data sources."""

    def __init__(self, aws_session=None, cache_manager=None):
        """Initialize AWS data source.

        Args:
            aws_session: Boto3 session for AWS API calls
            cache_manager: Optional cache manager for data caching
        """
        super().__init__(cache_manager)
        self.aws_session = aws_session

    @abstractmethod
    def get_client(self):
        """Get the appropriate AWS service client."""
        pass
