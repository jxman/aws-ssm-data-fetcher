"""Processing modules for AWS SSM data transformation and analysis."""

from .base import BaseProcessor, ProcessingContext, ServiceMappingProcessor
from .regional_validator_simple import (
    RegionDiscoverer,
    RegionDiscoveryError,
    ServiceDiscoverer,
    ServiceDiscoveryError,
    ValidationError,
)
from .service_mapper import ServiceMapper

# Note: Heavy dependency modules (data_transformer, statistics_analyzer, etc.)
# are excluded from default imports to avoid pandas/numpy conflicts in Lambda environments.
# Import them directly when needed with appropriate error handling.

__all__ = [
    "BaseProcessor",
    "ProcessingContext",
    "ServiceMappingProcessor",
    "RegionDiscoverer",
    "ServiceDiscoverer",
    "ServiceMapper",
    "ValidationError",
    "RegionDiscoveryError",
    "ServiceDiscoveryError",
]
