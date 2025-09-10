"""Simplified regional testing and validation processor for AWS SSM data integrity."""

import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..core.error_handling import ErrorHandler, with_retry_and_circuit_breaker
from .base import (
    BaseProcessor,
    ProcessingContext,
    ProcessingError,
    ProcessingValidationError,
)


class ValidationError(ProcessingError):
    """Exception raised during validation operations."""

    pass


class RegionDiscoveryError(ProcessingError):
    """Exception raised during region discovery operations."""

    pass


class ServiceDiscoveryError(ProcessingError):
    """Exception raised during service discovery operations."""

    pass


class RegionDiscoverer(BaseProcessor):
    """Processor for discovering AWS regions from SSM parameters."""

    def __init__(self, context: ProcessingContext):
        """Initialize region discoverer processor.

        Args:
            context: Processing context with SSM client and config
        """
        self.error_handler = ErrorHandler()

        # For Lambda environment where context might be None
        if context is None:
            import boto3

            self.context = None
            self.ssm_client = boto3.client("ssm")
            self.logger = self.error_handler.logger
            # Initialize basic processing stats
            self._processing_stats = {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "total_processing_time": 0.0,
                "cache_hits": 0,
            }
        else:
            super().__init__(context)
            # Get SSM client from context
            if not hasattr(context, "ssm_client"):
                raise ProcessingError("SSM client not found in processing context")
            self.ssm_client = context.ssm_client

    def validate_input(self, input_data: Optional[Dict]) -> bool:
        """Validate input data for region discovery.

        Args:
            input_data: Input data to validate

        Returns:
            True if valid, False otherwise
        """
        # For discovery, input can be None or a dict with optional parameters
        return input_data is None or isinstance(input_data, dict)

    def process(self, input_data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Discover AWS regions from SSM parameters.

        Args:
            input_data: Optional discovery parameters
            **kwargs: Additional processing parameters

        Returns:
            Dictionary with regions data

        Raises:
            ProcessingError: If region discovery fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        # Set default discovery parameters
        params = input_data or {}
        max_pages = params.get(
            "max_pages", 50
        )  # Increased to ensure all regions are found via pagination
        use_recursive = params.get(
            "recursive", False
        )  # Disabled to avoid DescribeParameters permission requirement
        validate_regions = params.get("validate_regions", True)

        self.logger.info("Discovering AWS regions from SSM parameters")

        try:
            regions = set()

            # Primary discovery: Get region directory structure
            regions.update(self._discover_regions_from_directory(max_pages))

            # Secondary discovery: Recursive parameter scan if needed
            if len(regions) < 20 and use_recursive:
                self.logger.info("Limited regions found, trying recursive discovery...")
                regions.update(self._discover_regions_from_parameters())

            # Convert to sorted list
            discovered_regions = sorted(list(regions))

            # Validate discovered regions
            if validate_regions:
                validated_regions = self._validate_discovered_regions(
                    discovered_regions
                )
                self.logger.info(
                    f"Validated {len(validated_regions)}/{len(discovered_regions)} discovered regions"
                )
                discovered_regions = validated_regions

            self.logger.info(
                f"Successfully discovered {len(discovered_regions)} regions"
            )

            # Return data in expected format
            return {
                "regions": discovered_regions,
                "region_discovery_stats": {
                    "total_discovered": len(discovered_regions),
                    "validation_enabled": validate_regions,
                    "discovery_method": (
                        "directory + recursive" if use_recursive else "directory_only"
                    ),
                    "discovery_timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            self.logger.error(f"Region discovery failed: {e}", exc_info=True)
            raise RegionDiscoveryError(f"Failed to discover regions: {e}") from e

    def _discover_regions_from_directory(self, max_pages: int) -> Set[str]:
        """Discover regions from the regions directory structure."""
        regions = set()

        try:
            paginator = self.ssm_client.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path="/aws/service/global-infrastructure/regions",
                Recursive=False,
                MaxResults=10,  # AWS SSM API maximum
            )

            pages_processed = 0
            for page in page_iterator:
                for param in page["Parameters"]:
                    # Extract region code from paths like /aws/service/global-infrastructure/regions/us-east-1
                    region_match = re.search(r"/regions/([a-z0-9-]+)$", param["Name"])
                    if region_match:
                        regions.add(region_match.group(1))

                pages_processed += 1
                if pages_processed >= max_pages:
                    break

            self.logger.info(f"Found {len(regions)} regions from directory structure")
            return regions

        except Exception as e:
            self.logger.warning(f"Directory-based region discovery failed: {e}")
            return set()

    def _discover_regions_from_parameters(self) -> Set[str]:
        """Discover regions from parameter names containing region patterns."""
        regions = set()

        try:
            # Common region patterns
            region_patterns = [
                r"/aws/service/([a-z0-9-]+)/.*",
                r".*/([a-z]{2}-[a-z]+-[0-9]+)/.*",
            ]

            paginator = self.ssm_client.get_paginator("describe_parameters")
            page_iterator = paginator.paginate(
                MaxResults=10,
                ParameterFilters=[
                    {
                        "Key": "Name",
                        "Option": "BeginsWith",
                        "Values": ["/aws/service/"],
                    }
                ],
            )

            parameters_scanned = 0
            max_parameters = 1000  # Limit to avoid timeout

            for page in page_iterator:
                for param in page["Parameters"]:
                    param_name = param["Name"]

                    # Try each pattern
                    for pattern in region_patterns:
                        match = re.search(pattern, param_name)
                        if match:
                            potential_region = match.group(1)
                            # Basic validation: region-like format
                            if re.match(r"^[a-z]{2}-[a-z]+-[0-9]+$", potential_region):
                                regions.add(potential_region)

                    parameters_scanned += 1
                    if parameters_scanned >= max_parameters:
                        break

                if parameters_scanned >= max_parameters:
                    break

            self.logger.info(f"Found {len(regions)} regions from parameter scanning")
            return regions

        except Exception as e:
            self.logger.warning(f"Parameter-based region discovery failed: {e}")
            return set()

    def _validate_discovered_regions(self, regions: List[str]) -> List[str]:
        """Validate discovered regions against known patterns."""
        validated = []

        for region in regions:
            # Basic validation: proper region format (including gov regions)
            if re.match(r"^[a-z]{2}(-[a-z]+)+-[0-9]+$", region):
                validated.append(region)
            else:
                self.logger.warning(f"Skipping invalid region format: {region}")

        return validated


class ServiceDiscoverer(BaseProcessor):
    """Processor for discovering AWS services from SSM parameters."""

    def __init__(self, context: ProcessingContext):
        """Initialize service discoverer processor.

        Args:
            context: Processing context with SSM client and config
        """
        self.error_handler = ErrorHandler()

        # For Lambda environment where context might be None
        if context is None:
            import boto3

            self.context = None
            self.ssm_client = boto3.client("ssm")
            self.logger = self.error_handler.logger
            # Initialize basic processing stats
            self._processing_stats = {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "total_processing_time": 0.0,
                "cache_hits": 0,
            }
        else:
            super().__init__(context)
            # Get SSM client from context
            if not hasattr(context, "ssm_client"):
                raise ProcessingError("SSM client not found in processing context")
            self.ssm_client = context.ssm_client

    def validate_input(self, input_data: Optional[Dict]) -> bool:
        """Validate input data for service discovery.

        Args:
            input_data: Input data to validate

        Returns:
            True if valid, False otherwise
        """
        # For discovery, input can be None or a dict with optional parameters
        return input_data is None or isinstance(input_data, dict)

    def process(self, input_data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Discover AWS services from SSM parameters.

        Args:
            input_data: Optional discovery parameters
            **kwargs: Additional processing parameters

        Returns:
            Dictionary with services data

        Raises:
            ProcessingError: If service discovery fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        params = input_data or {}
        max_pages = params.get("max_pages", 50)  # More pages for services
        use_recursive = params.get(
            "use_recursive", False
        )  # Disabled to avoid DescribeParameters permission requirement
        validate_services = params.get("validate_services", True)
        min_expected_services = params.get("min_expected_services", 300)

        self.logger.info("Discovering AWS services from SSM parameters")

        try:
            services = set()

            # Primary discovery: Directory-based service discovery
            services.update(self._discover_services_from_directory(max_pages))

            # Secondary discovery: Parameter pattern scanning
            if len(services) < min_expected_services and use_recursive:
                self.logger.info(
                    f"Found {len(services)} services, scanning parameters for more..."
                )
                services.update(self._discover_services_from_parameters())

            # Convert to sorted list
            discovered_services = sorted(list(services))

            # Basic validation
            if validate_services:
                validated_services = self._validate_discovered_services(
                    discovered_services
                )
                self.logger.info(
                    f"Validated {len(validated_services)}/{len(discovered_services)} discovered services"
                )
                discovered_services = validated_services

            self.logger.info(
                f"Successfully discovered {len(discovered_services)} services"
            )

            # Return data in expected format
            return {
                "services": discovered_services,
                "service_discovery_stats": {
                    "total_discovered": len(discovered_services),
                    "validation_enabled": validate_services,
                    "discovery_method": (
                        "directory + recursive" if use_recursive else "directory_only"
                    ),
                    "discovery_timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            self.logger.error(f"Service discovery failed: {e}", exc_info=True)
            raise ServiceDiscoveryError(f"Failed to discover services: {e}") from e

    def _discover_services_from_directory(self, max_pages: int) -> Set[str]:
        """Discover services from directory structure."""
        services = set()

        try:
            paginator = self.ssm_client.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path="/aws/service/global-infrastructure/services",
                Recursive=False,
                MaxResults=10,
            )

            pages_processed = 0
            for page in page_iterator:
                for param in page["Parameters"]:
                    # Extract service from paths like /aws/service/global-infrastructure/services/ec2
                    service_match = re.search(
                        r"/services/([a-zA-Z0-9-]+)$", param["Name"]
                    )
                    if service_match:
                        services.add(service_match.group(1))

                pages_processed += 1
                if pages_processed >= max_pages:
                    break

            self.logger.info(f"Found {len(services)} services from directory structure")
            return services

        except Exception as e:
            self.logger.warning(f"Directory-based service discovery failed: {e}")
            return set()

    def _discover_services_from_parameters(self) -> Set[str]:
        """Discover services from parameter patterns."""
        services = set()

        try:
            # Service patterns in SSM parameter names
            service_patterns = [
                r"/aws/service/([a-zA-Z0-9-]+)/",
                r"/aws/([a-zA-Z0-9-]+)/",
            ]

            paginator = self.ssm_client.get_paginator("describe_parameters")
            page_iterator = paginator.paginate(
                MaxResults=10,
                ParameterFilters=[
                    {
                        "Key": "Name",
                        "Option": "BeginsWith",
                        "Values": ["/aws/service/"],
                    }
                ],
            )

            parameters_scanned = 0
            max_parameters = 2000

            for page in page_iterator:
                for param in page["Parameters"]:
                    param_name = param["Name"]

                    # Try each pattern
                    for pattern in service_patterns:
                        match = re.search(pattern, param_name)
                        if match:
                            potential_service = match.group(1)
                            # Basic filtering
                            if (
                                len(potential_service) >= 2
                                and potential_service != "service"
                            ):
                                services.add(potential_service)

                    parameters_scanned += 1
                    if parameters_scanned >= max_parameters:
                        break

                if parameters_scanned >= max_parameters:
                    break

            self.logger.info(f"Found {len(services)} services from parameter scanning")
            return services

        except Exception as e:
            self.logger.warning(f"Parameter-based service discovery failed: {e}")
            return set()

    def _validate_discovered_services(self, services: List[str]) -> List[str]:
        """Basic validation of discovered services."""
        validated = []

        # Known invalid service patterns
        invalid_patterns = [
            "global-infrastructure",
            "regions",
            "services",
            "availability-zones",
        ]

        for service in services:
            # Skip known invalid patterns
            if service in invalid_patterns:
                continue

            # Basic format validation
            if len(service) >= 2 and re.match(r"^[a-zA-Z0-9-]+$", service):
                validated.append(service)
            else:
                self.logger.warning(f"Skipping invalid service format: {service}")

        return validated
