"""AWS SSM Parameter Store client for fetching service and region data."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from ..core.error_handling import (ErrorHandler, NonRetryableError,
                                   RetryableError,
                                   with_retry_and_circuit_breaker)
from ..core.logging import get_logger
from .base import AWSDataSource


class AWSSSMClient(AWSDataSource):
    """Enhanced client for fetching data from AWS Systems Manager Parameter Store.

    Provides comprehensive AWS data fetching capabilities including:
    - Region and service discovery
    - Batch parameter operations
    - Availability zone enumeration
    - Regional service availability testing
    - Intelligent caching and retry logic
    """

    def __init__(
        self,
        aws_session=None,
        cache_manager=None,
        region="us-east-1",
        max_retries=3,
        base_delay=1.0,
    ):
        """Initialize enhanced SSM client.

        Args:
            aws_session: Boto3 session for AWS API calls
            cache_manager: Optional cache manager for data persistence
            region: AWS region for SSM client operations
            max_retries: Maximum retry attempts for failed API calls
            base_delay: Base delay for exponential backoff (seconds)
        """
        super().__init__(aws_session, cache_manager)
        self.region = region
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = get_logger(f"ssm_client.{region}")
        self._client = None

        # Initialize error handler for enhanced retry logic
        self._error_handler = ErrorHandler()
        self._retry_config = self._error_handler.get_aws_retry_config()
        self._circuit_config = self._error_handler.get_aws_circuit_breaker_config()

    def get_client(self):
        """Get SSM client with connection reuse."""
        if self._client is None:
            if self.aws_session:
                self._client = self.aws_session.client("ssm", region_name=self.region)
            else:
                self._client = boto3.client("ssm", region_name=self.region)
            self.logger.info(f"Initialized SSM client for region: {self.region}")
        return self._client

    def fetch_data(self, data_type: str, **kwargs) -> Optional[List]:
        """Fetch data based on type.

        Args:
            data_type: Type of data to fetch ('regions', 'services', 'service_regions')
            **kwargs: Additional parameters

        Returns:
            List of fetched data or None if failed
        """
        if data_type == "regions":
            return self.discover_regions()
        elif data_type == "services":
            return self.discover_services()
        elif data_type == "service_regions":
            service_code = kwargs.get("service_code")
            if service_code:
                return self.get_service_regions(service_code)
        elif data_type == "region_names":
            regions = kwargs.get("regions", [])
            return self.fetch_region_names(regions)
        elif data_type == "service_names":
            services = kwargs.get("services", [])
            return self.fetch_service_names(services)

        self.logger.error(f"Unknown data type: {data_type}")
        return None

    @with_retry_and_circuit_breaker()
    def discover_regions(self) -> List[str]:
        """Discover all AWS regions from SSM parameters.

        Returns:
            List of region codes
        """
        cache_key = "discovered_regions"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached discovered regions")
            return cached_data

        self.logger.info("Discovering AWS regions from SSM parameters...")

        try:
            ssm = self.get_client()
            regions = []

            paginator = ssm.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path="/aws/service/global-infrastructure/regions",
                Recursive=False,
                MaxResults=10,
            )

            for page in page_iterator:
                for param in page["Parameters"]:
                    region_code = param["Value"]
                    if region_code and region_code not in regions:
                        regions.append(region_code)

                # Throttling protection
                time.sleep(0.1)

            regions.sort()
            self.logger.info(f"Successfully discovered {len(regions)} regions from SSM")

            # Cache the results
            self.cache_data(cache_key, regions)

            return regions

        except Exception as e:
            # Classify error for appropriate handling
            should_retry, error_category = self._error_handler.classify_aws_error(e)
            self.logger.error(
                f"Failed to discover regions from SSM ({error_category}): {e}"
            )

            if should_retry:
                raise RetryableError(f"Retryable error discovering regions: {e}") from e
            else:
                # Non-retryable errors return empty list rather than raising
                self.logger.warning("Non-retryable error, returning empty list")
                return []

    @with_retry_and_circuit_breaker()
    def discover_services(self) -> List[str]:
        """Discover all AWS services from SSM parameters.

        Returns:
            List of service codes
        """
        cache_key = "discovered_services"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached discovered services")
            return cached_data

        self.logger.info("Discovering AWS services from SSM parameters...")

        try:
            ssm = self.get_client()
            services = []

            paginator = ssm.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path="/aws/service/global-infrastructure/services",
                Recursive=False,
                MaxResults=10,
            )

            total_processed = 0
            for page in page_iterator:
                for param in page["Parameters"]:
                    service_code = param["Value"]
                    if service_code and service_code not in services:
                        services.append(service_code)
                        total_processed += 1

                # Log progress
                if total_processed % 50 == 0:
                    self.logger.info(f"Processed {total_processed} services...")

                # Throttling protection
                time.sleep(0.1)

            services.sort()
            self.logger.info(
                f"Successfully discovered {len(services)} services from SSM"
            )

            # Cache the results
            self.cache_data(cache_key, services)

            return services

        except Exception as e:
            # Classify error for appropriate handling
            should_retry, error_category = self._error_handler.classify_aws_error(e)
            self.logger.error(
                f"Failed to discover services from SSM ({error_category}): {e}"
            )

            if should_retry:
                raise RetryableError(
                    f"Retryable error discovering services: {e}"
                ) from e
            else:
                # Non-retryable errors return empty list rather than raising
                self.logger.warning("Non-retryable error, returning empty list")
                return []

    def get_service_regions(self, service_code: str) -> List[str]:
        """Get regions where a specific service is available.

        Args:
            service_code: AWS service code

        Returns:
            List of region codes where service is available
        """
        try:
            ssm = self.get_client()
            service_path = (
                f"/aws/service/global-infrastructure/services/{service_code}/regions"
            )

            paginator = ssm.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path=service_path, Recursive=False, MaxResults=10
            )

            regions = []
            for page in page_iterator:
                for param in page["Parameters"]:
                    region_code = param["Value"]
                    if region_code:
                        regions.append(region_code)

            return sorted(regions)

        except Exception as e:
            self.logger.warning(
                f"Failed to get regions for service {service_code}: {e}"
            )
            return []

    def fetch_region_names(self, regions: List[str]) -> Dict[str, str]:
        """Fetch display names for regions.

        Args:
            regions: List of region codes

        Returns:
            Dictionary mapping region codes to display names
        """
        cache_key = "region_names"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached region names")
            return cached_data

        self.logger.info("Fetching region display names...")

        region_names = {}
        ssm = self.get_client()

        for region_code in regions:
            try:
                param_name = (
                    f"/aws/service/global-infrastructure/regions/{region_code}/longName"
                )
                response = ssm.get_parameter(Name=param_name)
                region_names[region_code] = response["Parameter"]["Value"]

            except Exception as e:
                self.logger.warning(f"Failed to get name for region {region_code}: {e}")
                region_names[region_code] = region_code  # Fallback to code

            # Small delay to avoid throttling
            time.sleep(0.05)

        self.logger.info(f"Successfully fetched names for {len(region_names)} regions")

        # Cache the results
        self.cache_data(cache_key, region_names)

        return region_names

    def fetch_service_names(self, services: List[str]) -> Dict[str, str]:
        """Fetch display names for services.

        Args:
            services: List of service codes

        Returns:
            Dictionary mapping service codes to display names
        """
        cache_key = "service_names"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached service names")
            return cached_data

        self.logger.info("Fetching service display names...")

        service_names = {}
        ssm = self.get_client()

        for service_code in services:
            try:
                param_name = f"/aws/service/global-infrastructure/services/{service_code}/longName"
                response = ssm.get_parameter(Name=param_name)
                service_names[service_code] = response["Parameter"]["Value"]

            except Exception as e:
                self.logger.warning(
                    f"Failed to get name for service {service_code}: {e}"
                )
                service_names[service_code] = service_code  # Fallback to code

            # Small delay to avoid throttling
            time.sleep(0.05)

        self.logger.info(
            f"Successfully fetched names for {len(service_names)} services"
        )

        # Cache the results
        self.cache_data(cache_key, service_names)

        return service_names

    # ==========================================
    # EXTRACTED METHODS FROM MAIN SCRIPT
    # ==========================================

    def get_parameter_value(self, parameter_path: str) -> Optional[str]:
        """Get a single parameter value from SSM.

        Args:
            parameter_path: SSM parameter path

        Returns:
            Parameter value or None if failed
        """
        try:
            ssm = self.get_client()
            response = ssm.get_parameter(Name=parameter_path)
            return response["Parameter"]["Value"]
        except ClientError as e:
            self.logger.warning(f"Failed to get parameter {parameter_path}: {e}")
            return None

    def get_parameters_batch(
        self, parameter_paths: List[str]
    ) -> Dict[str, Optional[str]]:
        """Get multiple parameters in batches (max 10 per request).

        Args:
            parameter_paths: List of SSM parameter paths

        Returns:
            Dictionary mapping parameter paths to values (None for failed)
        """
        results = {}
        ssm = self.get_client()

        # Process in batches of 10 (SSM limit)
        for i in range(0, len(parameter_paths), 10):
            batch = parameter_paths[i : i + 10]
            try:
                response = ssm.get_parameters(Names=batch)

                # Process successful parameters
                for param in response["Parameters"]:
                    results[param["Name"]] = param["Value"]

                # Log any failed parameters
                for invalid in response["InvalidParameters"]:
                    self.logger.warning(f"Invalid parameter: {invalid}")
                    results[invalid] = None

            except ClientError as e:
                self.logger.error(f"Batch parameter request failed: {e}")
                for path in batch:
                    results[path] = None

        return results

    def fetch_all_ssm_parameters_by_path(self, parameter_path: str) -> List[str]:
        """Fetch all SSM parameters using get_parameters_by_path with pagination and throttling protection.

        Args:
            parameter_path: Base path to fetch parameters from

        Returns:
            List of parameter names found at the path
        """
        self.logger.info(f"Fetching all SSM parameters by path: {parameter_path}")

        all_parameters = []
        retry_count = 0
        ssm = self.get_client()

        while retry_count <= self.max_retries:
            try:
                paginator = ssm.get_paginator("get_parameters_by_path")
                page_iterator = paginator.paginate(
                    Path=parameter_path,
                    Recursive=True,
                    MaxResults=10,  # Reduced to minimize throttling
                )

                total_params = 0
                page_count = 0
                for page in page_iterator:
                    for param in page["Parameters"]:
                        all_parameters.append(param["Name"])
                        total_params += 1

                    page_count += 1

                    # Add delay between pages to avoid throttling
                    if page_count % 5 == 0:  # Every 5 pages
                        time.sleep(0.5)

                    # Log progress every 50 parameters
                    if total_params % 50 == 0:
                        self.logger.info(f"Processed {total_params} parameters...")

                self.logger.info(
                    f"Found {total_params} total parameters at path {parameter_path}"
                )
                break  # Success, exit retry loop

            except ClientError as e:
                if "ThrottlingException" in str(e) and retry_count < self.max_retries:
                    retry_count += 1
                    delay = self.base_delay * (2**retry_count)  # Exponential backoff
                    self.logger.warning(
                        f"Throttling detected, retrying in {delay}s (attempt {retry_count}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"Failed to fetch parameters at path {parameter_path}: {e}"
                    )
                    break
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch parameters at path {parameter_path}: {e}"
                )
                break

        return all_parameters

    def fetch_availability_zones(self, regions: List[str]) -> Dict[str, int]:
        """Fetch availability zone counts for regions from SSM with full pagination.

        Args:
            regions: List of region codes to get AZ counts for

        Returns:
            Dictionary mapping region codes to AZ counts
        """
        cache_key = "availability_zones"

        # Try to load from cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached availability zone data")
            return cached_data

        self.logger.info("Fetching availability zone data with full pagination...")

        # Get ALL availability zone parameters with pagination
        all_az_params = self.fetch_all_ssm_parameters_by_path(
            "/aws/service/global-infrastructure/availability-zones"
        )

        az_data = {}
        ssm = self.get_client()

        # Process each region to count its AZs
        for region in regions:
            az_count = 0

            # Look for AZ parameters that belong to this region
            for param_name in all_az_params:
                if "/region" in param_name:
                    try:
                        # Get the region for this AZ parameter
                        response = ssm.get_parameter(Name=param_name)
                        if response["Parameter"]["Value"] == region:
                            az_count += 1
                    except Exception as e:
                        # If we can't get the parameter, try pattern matching as fallback
                        az_match = re.search(
                            r"/availability-zones/([^/]+)/", param_name
                        )
                        if az_match:
                            az_code = az_match.group(1)
                            # Common AZ to region mappings
                            region_mappings = {
                                "use1": "us-east-1",
                                "use2": "us-east-2",
                                "usw1": "us-west-1",
                                "usw2": "us-west-2",
                                "euw1": "eu-west-1",
                                "euw2": "eu-west-2",
                                "euw3": "eu-west-3",
                                "euc1": "eu-central-1",
                                "euc2": "eu-central-2",
                                "eun1": "eu-north-1",
                                "eus1": "eu-south-1",
                                "eus2": "eu-south-2",
                                "apne1": "ap-northeast-1",
                                "apne2": "ap-northeast-2",
                                "apne3": "ap-northeast-3",
                                "aps1": "ap-south-1",
                                "aps2": "ap-south-2",
                                "apse1": "ap-southeast-1",
                                "apse2": "ap-southeast-2",
                                "apse3": "ap-southeast-3",
                                "apse4": "ap-southeast-4",
                                "ape1": "ap-east-1",
                                "ape2": "ap-east-2",
                                "cac1": "ca-central-1",
                                "caw1": "ca-west-1",
                                "sae1": "sa-east-1",
                                "afs1": "af-south-1",
                                "mes1": "me-south-1",
                                "mec1": "me-central-1",
                                "ilc1": "il-central-1",
                            }

                            az_region_prefix = az_code.rstrip("0123456789-az")
                            if region_mappings.get(az_region_prefix) == region:
                                az_count += 1

            if az_count > 0:
                az_data[region] = az_count
                self.logger.debug(f"Found {az_count} AZs for {region}")
            else:
                # Fallback to known AZ counts for established regions
                common_az_counts = {
                    "us-east-1": 6,
                    "us-east-2": 3,
                    "us-west-1": 3,
                    "us-west-2": 4,
                    "eu-west-1": 3,
                    "eu-west-2": 3,
                    "eu-west-3": 3,
                    "eu-central-1": 3,
                    "ap-northeast-1": 3,
                    "ap-northeast-2": 4,
                    "ap-southeast-1": 3,
                    "ap-southeast-2": 3,
                    "ap-south-1": 3,
                    "ca-central-1": 3,
                    "sa-east-1": 3,
                }
                az_data[region] = common_az_counts.get(region, 3)  # Default to 3 AZs

        # Save to cache
        self.cache_data(cache_key, az_data)

        self.logger.info(f"Successfully fetched AZ data for {len(az_data)} regions")
        return az_data

    def discover_regions_from_ssm_enhanced(self) -> List[str]:
        """Enhanced region discovery from SSM parameters with targeted approach.

        Returns:
            List of discovered region codes
        """
        cache_key = "discovered_regions_enhanced"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached discovered regions")
            return cached_data

        self.logger.info("Discovering all regions from SSM parameters...")
        discovered_regions = []

        try:
            # First try: Get regions from the canonical regions path
            regions_params = self.fetch_all_ssm_parameters_by_path(
                "/aws/service/global-infrastructure/regions"
            )

            for param_name in regions_params:
                if param_name.endswith("/region"):
                    continue  # Skip the 'region' parameter itself

                # Extract region code from parameter path
                region_match = re.search(r"/regions/([^/]+)", param_name)
                if region_match:
                    region_code = region_match.group(1)
                    if region_code and region_code not in discovered_regions:
                        discovered_regions.append(region_code)

            self.logger.info(
                f"Found {len(discovered_regions)} regions from direct path"
            )

            # If we didn't find many regions, try targeted parameter sampling
            if len(discovered_regions) < 10:
                self.logger.info(
                    "Limited regions found, trying targeted parameter sampling..."
                )

                # Sample from service parameters to find more regions
                service_params = self.fetch_all_ssm_parameters_by_path(
                    "/aws/service/global-infrastructure/services"
                )

                for param_name in service_params[
                    :50
                ]:  # Sample first 50 service parameters
                    # Look for regional service availability patterns
                    region_match = re.search(
                        r"/services/[^/]+/regions/([^/]+)", param_name
                    )
                    if region_match:
                        region_code = region_match.group(1)
                        if region_code and region_code not in discovered_regions:
                            discovered_regions.append(region_code)

            discovered_regions.sort()
            self.logger.info(f"Discovered {len(discovered_regions)} regions from SSM")

            # Cache the results
            self.cache_data(cache_key, discovered_regions)

            return discovered_regions

        except Exception as e:
            self.logger.error(f"Failed to discover regions from SSM: {e}")
            return []

    def discover_services_from_ssm_enhanced(self) -> List[str]:
        """Enhanced service discovery from SSM parameters.

        Returns:
            List of discovered service codes
        """
        cache_key = "discovered_services_enhanced"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached discovered services")
            return cached_data

        self.logger.info("Discovering all services from SSM parameters...")
        services = set()

        try:
            # Get all service parameters with pagination
            service_params = self.fetch_all_ssm_parameters_by_path(
                "/aws/service/global-infrastructure/services"
            )

            pages_processed = 0
            for param_name in service_params:
                # Extract service codes from parameter paths
                service_match = re.search(r"/services/([^/]+)", param_name)
                if service_match:
                    service_code = service_match.group(1)
                    if service_code:
                        services.add(service_code)

                pages_processed += 1
                if pages_processed % 100 == 0:
                    self.logger.info(
                        f"Processed {pages_processed} pages, found {len(services)} unique services so far..."
                    )

            discovered_services = sorted(list(services))

            # If we found fewer services than expected, try recursive approach
            if len(discovered_services) < 200:
                self.logger.info(
                    f"Found {len(services)} services with non-recursive scan, trying recursive approach to find more..."
                )

                # Try getting services list directly
                try:
                    ssm = self.get_client()
                    paginator = ssm.get_paginator("get_parameters_by_path")
                    page_iterator = paginator.paginate(
                        Path="/aws/service/global-infrastructure/services",
                        Recursive=False,
                        MaxResults=10,
                    )

                    for page in page_iterator:
                        for param in page["Parameters"]:
                            if param["Value"] not in services:
                                services.add(param["Value"])
                        time.sleep(0.1)  # Throttling protection

                except Exception as e:
                    self.logger.warning(f"Recursive approach failed: {e}")

            discovered_services = sorted(list(services))
            self.logger.info(f"Discovered {len(discovered_services)} services from SSM")

            # Cache the results
            self.cache_data(cache_key, discovered_services)

            return discovered_services

        except Exception as e:
            self.logger.error(f"Failed to discover services from SSM: {e}")
            return []

    def get_region_service_mapping(
        self, regions: List[str], services: List[str]
    ) -> Dict[str, List[str]]:
        """Map services to regions using actual AWS SSM data.

        Args:
            regions: List of region codes
            services: List of service codes

        Returns:
            Dictionary mapping region codes to lists of available services
        """
        cache_key = "region_services_mapping"

        # Try cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached region-services mapping")
            return cached_data

        self.logger.info("Mapping services to regions using actual AWS SSM data...")

        region_services = {}
        total_mappings = 0

        try:
            for i, service_code in enumerate(services):
                self.logger.info(
                    f"Processing service {i+1:3d}/{len(services)}: {service_code}"
                )

                try:
                    # Get regions where this service is available
                    service_regions = self.get_service_regions(service_code)

                    # Add this service to each region where it's available
                    for region in service_regions:
                        if (
                            region in regions
                        ):  # Only include regions we're interested in
                            if region not in region_services:
                                region_services[region] = []
                            region_services[region].append(service_code)
                            total_mappings += 1

                    if service_regions:
                        self.logger.info(
                            f"  {service_code} available in {len(service_regions)} regions"
                        )

                    # Small delay to avoid throttling
                    time.sleep(0.05)

                except Exception as e:
                    self.logger.warning(
                        f"Failed to get regions for service {service_code}: {e}"
                    )
                    continue

            # Sort services within each region
            for region in region_services:
                region_services[region].sort()

            self.logger.info(
                f"Successfully mapped {len(region_services)} regions with {total_mappings} total service mappings"
            )

            # Cache the results
            self.cache_data(cache_key, region_services)

            return region_services

        except Exception as e:
            self.logger.error(f"Failed to map services to regions: {e}")
            return {}
