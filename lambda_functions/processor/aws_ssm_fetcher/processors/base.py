"""Base processor interfaces and shared processing context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from ..core.cache import CacheManager
from ..core.config import Config
from ..core.logging import get_logger


@dataclass
class ProcessingContext:
    """Shared context for all processors."""

    config: Config
    cache_manager: Optional[CacheManager] = None
    logger_name: str = "processor"
    start_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize context after creation."""
        if self.start_time is None:
            self.start_time = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class ProcessingError(Exception):
    """Exception raised during processing operations."""

    pass


class ProcessingValidationError(ProcessingError):
    """Exception raised when input data validation fails."""

    pass


class BaseProcessor(ABC):
    """Abstract base class for all data processors.

    Provides common functionality for:
    - Logging with context
    - Performance timing
    - Error handling
    - Data validation
    - Results caching
    """

    def __init__(self, context: ProcessingContext):
        """Initialize processor with context.

        Args:
            context: Processing context with config, cache, etc.
        """
        self.context = context
        self.logger = get_logger(
            f"{context.logger_name}.{self.__class__.__name__.lower()}"
        )
        self._processing_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    @abstractmethod
    def process(self, input_data: Any, **kwargs) -> Any:
        """Process input data and return results.

        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters

        Returns:
            Processed data

        Raises:
            ProcessingError: If processing fails
            ProcessingValidationError: If input validation fails
        """
        pass

    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """Validate input data before processing.

        Args:
            input_data: Data to validate

        Returns:
            True if valid, False otherwise

        Raises:
            ProcessingValidationError: If validation fails with details
        """
        pass

    def get_cache_key(self, input_data: Any, **kwargs) -> str:
        """Generate cache key for input data and parameters.

        Args:
            input_data: Input data
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        import hashlib

        # Create a deterministic cache key from input data and kwargs
        key_components = [
            self.__class__.__name__,
            str(hash(str(input_data))),
            str(sorted(kwargs.items())),
        ]

        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached processing result.

        Args:
            cache_key: Cache key to look up

        Returns:
            Cached result or None if not found/invalid
        """
        if not self.context.cache_manager:
            return None

        try:
            result = self.context.cache_manager.get(cache_key)
            if result is not None:
                self._processing_stats["cache_hits"] += 1
                self.logger.debug(f"Cache hit for key: {cache_key[:16]}...")
            else:
                self._processing_stats["cache_misses"] += 1
            return result
        except Exception as e:
            self.logger.warning(f"Cache retrieval failed: {e}")
            self._processing_stats["cache_misses"] += 1
            return None

    def cache_result(self, cache_key: str, result: Any) -> bool:
        """Cache processing result.

        Args:
            cache_key: Cache key to store under
            result: Result to cache

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.context.cache_manager:
            return False

        try:
            success = self.context.cache_manager.set(cache_key, result)
            if success:
                self.logger.debug(f"Cached result for key: {cache_key[:16]}...")
            return success
        except Exception as e:
            self.logger.warning(f"Cache storage failed: {e}")
            return False

    def process_with_cache(self, input_data: Any, **kwargs) -> Any:
        """Process input data with caching support.

        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters

        Returns:
            Processed data (from cache or fresh processing)
        """
        start_time = datetime.now()
        self._processing_stats["total_operations"] += 1

        try:
            # Validate input
            if not self.validate_input(input_data):
                raise ProcessingValidationError("Input validation failed")

            # Check cache first
            cache_key = self.get_cache_key(input_data, **kwargs)
            cached_result = self.get_cached_result(cache_key)

            if cached_result is not None:
                self.logger.info("Using cached processing result")
                return cached_result

            # Process fresh data
            self.logger.info(
                f"Processing {len(input_data) if hasattr(input_data, '__len__') else 'data'} items..."
            )

            with self.logger.timer(f"{self.__class__.__name__}.process"):
                result = self.process(input_data, **kwargs)

            # Cache the result
            self.cache_result(cache_key, result)

            self._processing_stats["successful_operations"] += 1
            return result

        except Exception as e:
            self._processing_stats["failed_operations"] += 1
            self.logger.error(f"Processing failed: {e}", exc_info=True)
            raise ProcessingError(f"Processing failed: {e}") from e

        finally:
            # Track processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self._processing_stats["total_processing_time"] += processing_time

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics.

        Returns:
            Dictionary with processing metrics
        """
        total_ops = self._processing_stats["total_operations"]

        return {
            **self._processing_stats,
            "success_rate": self._processing_stats["successful_operations"]
            / max(total_ops, 1),
            "failure_rate": self._processing_stats["failed_operations"]
            / max(total_ops, 1),
            "average_processing_time": self._processing_stats["total_processing_time"]
            / max(total_ops, 1),
            "cache_hit_rate": self._processing_stats["cache_hits"]
            / max(
                self._processing_stats["cache_hits"]
                + self._processing_stats["cache_misses"],
                1,
            ),
        }

    def reset_stats(self):
        """Reset processing statistics."""
        self._processing_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }


class ServiceMappingProcessor(BaseProcessor):
    """Base class for service mapping processors."""

    @abstractmethod
    def map_services_to_regions(
        self, services: List[str], **kwargs
    ) -> Dict[str, List[str]]:
        """Map services to regions where they are available.

        Args:
            services: List of service codes to map
            **kwargs: Additional mapping parameters

        Returns:
            Dictionary mapping region codes to lists of available services
        """
        pass

    @abstractmethod
    def get_service_regions(self, service_code: str) -> List[str]:
        """Get regions where a specific service is available.

        Args:
            service_code: AWS service code

        Returns:
            List of region codes where service is available
        """
        pass
