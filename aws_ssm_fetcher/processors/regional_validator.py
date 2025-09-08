"""Regional testing and validation processor for AWS SSM data integrity."""

import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..core.error_handling import ErrorHandler, with_retry_and_circuit_breaker
from .base import (BaseProcessor, ProcessingContext, ProcessingError,
                   ProcessingValidationError)


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
        super().__init__(context)
        self.error_handler = ErrorHandler()

        # Get SSM client from context
        if not hasattr(context, "ssm_client"):
            raise ProcessingError("SSM client not found in processing context")

        self.ssm_client = context.ssm_client

        # Configure retry and circuit breaker for AWS operations
        retry_config = self.error_handler.get_aws_retry_config()
        circuit_config = self.error_handler.get_aws_circuit_breaker_config()

        self._get_parameters_by_path_with_reliability = with_retry_and_circuit_breaker(
            retry_config, circuit_config
        )(self._get_parameters_by_path)

        # Known AWS region patterns for validation
        self.region_patterns = [
            r"^us-(east|west)-[12]$",  # US regions
            r"^eu-(west|central|north|south)-[12]$",  # Europe regions
            r"^ap-(northeast|southeast|south|east)-[1-7]$",  # Asia Pacific regions
            r"^ca-(central|west)-[12]$",  # Canada regions
            r"^sa-east-[12]$",  # South America regions
            r"^af-south-[12]$",  # Africa regions
            r"^me-(south|central)-[12]$",  # Middle East regions
            r"^il-central-[12]$",  # Israel regions
            r"^mx-central-[12]$",  # Mexico regions
            r"^cn-(north|northwest)-[12]$",  # China regions
            r"^us-gov-(east|west)-[12]$",  # Government regions
        ]

    def validate_input(self, input_data: Any) -> bool:
        """Validate input parameters for region discovery.

        Args:
            input_data: Discovery parameters (can be None for default discovery)

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        # Region discovery can work with None input (uses defaults)
        if input_data is not None:
            if not isinstance(input_data, dict):
                raise ProcessingValidationError(
                    "Input must be a dictionary of discovery parameters"
                )

            # Validate discovery parameters
            valid_params = [
                "max_pages",
                "recursive",
                "region_pattern",
                "validate_regions",
            ]
            for param in input_data:
                if param not in valid_params:
                    raise ProcessingValidationError(f"Unknown parameter: {param}")

        return True

    def process(self, input_data: Optional[Dict] = None, **kwargs) -> List[str]:
        """Discover AWS regions from SSM parameters.

        Args:
            input_data: Optional discovery parameters
            **kwargs: Additional processing parameters

        Returns:
            List of discovered region codes

        Raises:
            ProcessingError: If region discovery fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        # Set default discovery parameters
        params = input_data or {}
        max_pages = params.get("max_pages", 10)
        use_recursive = params.get("recursive", True)
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

            # Store discovery metadata
            self.context.metadata.update(
                {
                    "region_discovery_stats": {
                        "total_discovered": len(discovered_regions),
                        "validation_enabled": validate_regions,
                        "discovery_method": (
                            "directory + recursive"
                            if use_recursive
                            else "directory_only"
                        ),
                        "discovery_timestamp": datetime.now().isoformat(),
                    }
                }
            )

            return discovered_regions

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
                MaxResults=10,
            )

            pages_processed = 0
            for page in page_iterator:
                for param in page["Parameters"]:
                    # Extract region code from paths like /aws/service/global-infrastructure/regions/us-east-1
                    region_match = re.search(r"/regions/([a-z0-9-]+)$", param["Name"])
                    if region_match:
                        region_code = region_match.group(1)
                        regions.add(region_code)

                pages_processed += 1
                if pages_processed >= max_pages:
                    break

            self.logger.debug(f"Directory discovery found {len(regions)} regions")

        except Exception as e:
            self.logger.warning(f"Directory discovery failed: {e}")

        return regions

    def _discover_regions_from_parameters(self) -> Set[str]:
        """Discover regions from recursive parameter scan."""
        regions = set()

        try:
            # Sample parameters for region codes
            sample_response = self._get_parameters_by_path_with_reliability(
                "/aws/service/global-infrastructure/regions",
                recursive=True,
                max_results=50,
            )

            for param in sample_response.get("Parameters", []):
                region_match = re.search(r"/regions/([a-z0-9-]+)/", param["Name"])
                if region_match:
                    region_code = region_match.group(1)
                    regions.add(region_code)

            self.logger.debug(f"Recursive discovery found {len(regions)} regions")

        except Exception as e:
            self.logger.warning(f"Recursive discovery failed: {e}")

        return regions

    def _get_parameters_by_path(
        self, path: str, recursive: bool = False, max_results: int = 10
    ) -> Dict:
        """Get parameters by path with error handling."""
        return self.ssm_client.get_parameters_by_path(
            Path=path, Recursive=recursive, MaxResults=max_results
        )

    def _validate_discovered_regions(self, regions: List[str]) -> List[str]:
        """Validate discovered regions against known patterns."""
        validated_regions = []

        for region in regions:
            # Check against known region patterns
            is_valid = any(
                re.match(pattern, region) for pattern in self.region_patterns
            )

            # Additional validation: must be alphanumeric with hyphens only
            if is_valid and re.match(r"^[a-z0-9-]+$", region) and len(region) >= 8:
                validated_regions.append(region)
            else:
                self.logger.debug(f"Rejected invalid region format: {region}")

        return validated_regions


class ServiceDiscoverer(BaseProcessor):
    """Processor for discovering AWS services from SSM parameters."""

    def __init__(self, context: ProcessingContext):
        """Initialize service discoverer processor.

        Args:
            context: Processing context with SSM client and config
        """
        super().__init__(context)
        self.error_handler = ErrorHandler()

        # Get SSM client from context
        if not hasattr(context, "ssm_client"):
            raise ProcessingError("SSM client not found in processing context")

        self.ssm_client = context.ssm_client

        # Configure retry and circuit breaker
        retry_config = self.error_handler.get_aws_retry_config()
        circuit_config = self.error_handler.get_aws_circuit_breaker_config()

        self._get_parameters_by_path_with_reliability = with_retry_and_circuit_breaker(
            retry_config, circuit_config
        )(self._get_parameters_by_path)

        # Known AWS service patterns for validation
        self.service_patterns = [
            r"^[a-z0-9]+(-[a-z0-9]+)*$",  # Standard service codes
            r"^[a-z0-9]+$",  # Simple service codes
        ]

        # Service categories for validation
        self.known_service_prefixes = {
            "compute": ["ec2", "lambda", "batch", "ecs", "eks", "fargate"],
            "storage": ["s3", "ebs", "efs", "fsx", "glacier", "backup"],
            "database": ["rds", "dynamodb", "docdb", "neptune", "elasticache", "dax"],
            "networking": ["vpc", "cloudfront", "route53", "elb", "apigateway"],
            "security": ["iam", "kms", "cognito", "waf", "shield", "macie"],
            "analytics": ["athena", "glue", "emr", "kinesis", "redshift", "quicksight"],
            "ml": ["sagemaker", "comprehend", "rekognition", "textract", "translate"],
            "developer": ["codebuild", "codecommit", "codepipeline", "codedeploy"],
            "management": [
                "cloudwatch",
                "cloudtrail",
                "config",
                "ssm",
                "organizations",
            ],
        }

    def validate_input(self, input_data: Any) -> bool:
        """Validate input parameters for service discovery.

        Args:
            input_data: Discovery parameters (can be None for default discovery)

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        if input_data is not None:
            if not isinstance(input_data, dict):
                raise ProcessingValidationError(
                    "Input must be a dictionary of discovery parameters"
                )

            valid_params = [
                "max_pages",
                "use_recursive",
                "validate_services",
                "min_expected_services",
            ]
            for param in input_data:
                if param not in valid_params:
                    raise ProcessingValidationError(f"Unknown parameter: {param}")

        return True

    def process(self, input_data: Optional[Dict] = None, **kwargs) -> List[str]:
        """Discover AWS services from SSM parameters.

        Args:
            input_data: Optional discovery parameters
            **kwargs: Additional processing parameters

        Returns:
            List of discovered service codes

        Raises:
            ProcessingError: If service discovery fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        params = input_data or {}
        max_pages = params.get("max_pages", 100)  # More pages for services
        use_recursive = params.get("use_recursive", True)
        validate_services = params.get("validate_services", True)
        min_expected_services = params.get("min_expected_services", 300)

        self.logger.info("Discovering AWS services from SSM parameters")

        try:
            services = set()

            # Primary discovery: Get service directory structure
            services.update(self._discover_services_from_directory(max_pages))

            # Secondary discovery: Recursive scan if needed
            if len(services) < min_expected_services and use_recursive:
                self.logger.info(
                    f"Found {len(services)} services, trying recursive discovery for more..."
                )
                services.update(self._discover_services_from_parameters())

            # Convert to sorted list
            discovered_services = sorted(list(services))

            # Validate discovered services
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

            # Store discovery metadata
            self.context.metadata.update(
                {
                    "service_discovery_stats": {
                        "total_discovered": len(discovered_services),
                        "validation_enabled": validate_services,
                        "discovery_method": (
                            "directory + recursive"
                            if use_recursive
                            else "directory_only"
                        ),
                        "discovery_timestamp": datetime.now().isoformat(),
                        "service_categories": self._categorize_services(
                            discovered_services
                        ),
                    }
                }
            )

            return discovered_services

        except Exception as e:
            self.logger.error(f"Service discovery failed: {e}", exc_info=True)
            raise ServiceDiscoveryError(f"Failed to discover services: {e}") from e

    def _discover_services_from_directory(self, max_pages: int) -> Set[str]:
        """Discover services from the services directory structure."""
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
                    # Extract service code from paths like /aws/service/global-infrastructure/services/ec2
                    service_match = re.search(r"/services/([a-z0-9-]+)$", param["Name"])
                    if service_match:
                        service_code = service_match.group(1)
                        services.add(service_code)

                pages_processed += 1

                # Log progress periodically
                if pages_processed % 25 == 0:
                    self.logger.debug(
                        f"Directory discovery: processed {pages_processed} pages, found {len(services)} services"
                    )
                    time.sleep(0.1)  # Small delay to avoid throttling

                if pages_processed >= max_pages:
                    break

            self.logger.debug(f"Directory discovery found {len(services)} services")

        except Exception as e:
            self.logger.warning(f"Directory discovery failed: {e}")

        return services

    def _discover_services_from_parameters(self) -> Set[str]:
        """Discover services from recursive parameter scan."""
        services = set()

        try:
            # Get all service parameters (this could be a lot)
            all_service_params = self._fetch_all_service_parameters()

            for param in all_service_params:
                service_match = re.search(r"/services/([a-z0-9-]+)/", param)
                if service_match:
                    service_code = service_match.group(1)
                    services.add(service_code)

            self.logger.debug(f"Recursive discovery found {len(services)} services")

        except Exception as e:
            self.logger.warning(f"Recursive discovery failed: {e}")

        return services

    def _fetch_all_service_parameters(self) -> List[str]:
        """Fetch all service parameter names with pagination."""
        parameter_names = []

        try:
            paginator = self.ssm_client.get_paginator("get_parameters_by_path")
            page_iterator = paginator.paginate(
                Path="/aws/service/global-infrastructure/services",
                Recursive=True,
                MaxResults=10,
            )

            pages_processed = 0
            for page in page_iterator:
                for param in page["Parameters"]:
                    parameter_names.append(param["Name"])

                pages_processed += 1

                # Throttle to avoid API limits
                if pages_processed % 10 == 0:
                    time.sleep(0.2)

                # Log progress every 50 pages
                if pages_processed % 50 == 0:
                    self.logger.debug(
                        f"Fetched {len(parameter_names)} parameters from {pages_processed} pages"
                    )

                # Safety limit
                if pages_processed >= 1000:
                    self.logger.warning("Hit safety limit for parameter fetching")
                    break

        except Exception as e:
            self.logger.warning(f"Failed to fetch service parameters: {e}")

        return parameter_names

    def _get_parameters_by_path(
        self, path: str, recursive: bool = False, max_results: int = 10
    ) -> Dict:
        """Get parameters by path with error handling."""
        return self.ssm_client.get_parameters_by_path(
            Path=path, Recursive=recursive, MaxResults=max_results
        )

    def _validate_discovered_services(self, services: List[str]) -> List[str]:
        """Validate discovered services against known patterns."""
        validated_services = []

        for service in services:
            # Check basic format
            is_valid_format = any(
                re.match(pattern, service) for pattern in self.service_patterns
            )

            # Additional validation: reasonable length and characters
            if (
                is_valid_format
                and 2 <= len(service) <= 50
                and service.replace("-", "").replace("_", "").isalnum()
            ):
                validated_services.append(service)
            else:
                self.logger.debug(f"Rejected invalid service format: {service}")

        return validated_services

    def _categorize_services(self, services: List[str]) -> Dict[str, int]:
        """Categorize discovered services by type."""
        categories = Counter()

        for service in services:
            service_lower = service.lower()
            categorized = False

            # Check against known service prefixes
            for category, prefixes in self.known_service_prefixes.items():
                if any(
                    service_lower.startswith(prefix) or prefix in service_lower
                    for prefix in prefixes
                ):
                    categories[category] += 1
                    categorized = True
                    break

            if not categorized:
                categories["other"] += 1

        return dict(categories)


class RegionalDataValidator(BaseProcessor):
    """Comprehensive validator for regional AWS data integrity."""

    def __init__(self, context: ProcessingContext):
        """Initialize regional data validator.

        Args:
            context: Processing context with config and cache
        """
        super().__init__(context)
        self.region_discoverer = RegionDiscoverer(context)
        self.service_discoverer = ServiceDiscoverer(context)

        # Validation thresholds
        self.validation_thresholds = {
            "min_regions": 25,
            "max_regions": 50,
            "min_services": 200,
            "max_services": 500,
            "min_mappings_per_region": 50,
            "max_mappings_per_region": 400,
            "min_regions_per_service": 1,
            "max_regions_per_service": 45,
            "expected_coverage_percentage": 60.0,
        }

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data for regional validation.

        Args:
            input_data: Regional data to validate (list of service-region mappings)

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        if not isinstance(input_data, list):
            raise ProcessingValidationError(
                "Input must be a list of regional data mappings"
            )

        if not input_data:
            raise ProcessingValidationError("Input data cannot be empty")

        # Check data structure
        sample_size = min(3, len(input_data))
        for i, item in enumerate(input_data[:sample_size]):
            if not isinstance(item, dict):
                raise ProcessingValidationError(f"Item {i} must be a dictionary")

            required_fields = ["Region Code", "Service Code"]
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                raise ProcessingValidationError(
                    f"Item {i} missing required fields: {missing_fields}"
                )

        return True

    def process(
        self, input_data: List[Dict], validation_type: str = "comprehensive", **kwargs
    ) -> Dict[str, Any]:
        """Validate regional AWS data for integrity and completeness.

        Args:
            input_data: List of service-region mapping dictionaries
            validation_type: Type of validation to perform
            **kwargs: Additional validation parameters

        Returns:
            Dictionary with validation results

        Raises:
            ProcessingError: If validation fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        self.logger.info(
            f"Performing {validation_type} validation on {len(input_data)} regional mappings"
        )

        validation_methods = {
            "comprehensive": self.comprehensive_validation,
            "data_integrity": self.data_integrity_validation,
            "coverage_validation": self.coverage_validation,
            "consistency_validation": self.consistency_validation,
            "discovery_validation": self.discovery_validation,
            "anomaly_detection": self.anomaly_detection_validation,
        }

        if validation_type not in validation_methods:
            raise ProcessingError(f"Unknown validation type: {validation_type}")

        try:
            method = validation_methods[validation_type]
            result = method(input_data, **kwargs)

            self.logger.info(f"Successfully completed {validation_type} validation")
            return result

        except Exception as e:
            self.logger.error(
                f"Validation {validation_type} failed: {e}", exc_info=True
            )
            raise ValidationError(
                f"Failed to perform {validation_type} validation: {e}"
            ) from e

    def comprehensive_validation(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Perform comprehensive validation covering all aspects."""
        self.logger.info("Performing comprehensive regional data validation")

        # Run all validation types
        results = {}

        try:
            results["data_integrity"] = self.data_integrity_validation(data, **kwargs)
            results["coverage"] = self.coverage_validation(data, **kwargs)
            results["consistency"] = self.consistency_validation(data, **kwargs)
            results["discovery"] = self.discovery_validation(data, **kwargs)
            results["anomaly_detection"] = self.anomaly_detection_validation(
                data, **kwargs
            )

            # Compute overall validation score
            scores = []
            for validation_result in results.values():
                if "validation_score" in validation_result:
                    scores.append(validation_result["validation_score"])

            overall_score = sum(scores) / len(scores) if scores else 0

            results["summary"] = {
                "overall_validation_score": round(overall_score, 2),
                "total_validations_performed": len(results)
                - 1,  # Exclude summary itself
                "validation_timestamp": datetime.now().isoformat(),
                "data_quality_grade": self._get_quality_grade(overall_score),
            }

            return results

        except Exception as e:
            self.logger.error(f"Comprehensive validation failed: {e}")
            raise ValidationError(f"Comprehensive validation failed: {e}") from e

    def data_integrity_validation(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Validate data integrity and structure."""
        self.logger.debug("Validating data integrity")

        issues = []
        stats = {
            "total_records": len(data),
            "duplicate_records": 0,
            "missing_fields": 0,
            "invalid_formats": 0,
            "empty_values": 0,
        }

        # Check for duplicates
        seen_combinations = set()
        for i, record in enumerate(data):
            key = (record.get("Region Code"), record.get("Service Code"))
            if key in seen_combinations:
                stats["duplicate_records"] += 1
                issues.append(f"Duplicate record at index {i}: {key}")
            else:
                seen_combinations.add(key)

        # Check field completeness and format
        required_fields = ["Region Code", "Service Code"]
        for i, record in enumerate(data):
            # Missing fields
            missing = [field for field in required_fields if field not in record]
            if missing:
                stats["missing_fields"] += 1
                issues.append(f"Record {i} missing fields: {missing}")

            # Empty values
            empty_fields = [
                field
                for field in required_fields
                if field in record and not str(record[field]).strip()
            ]
            if empty_fields:
                stats["empty_values"] += 1
                issues.append(f"Record {i} has empty values in: {empty_fields}")

            # Format validation
            region_code = record.get("Region Code", "")
            service_code = record.get("Service Code", "")

            if region_code and not re.match(r"^[a-z0-9-]+$", str(region_code)):
                stats["invalid_formats"] += 1
                issues.append(f"Invalid region format at {i}: {region_code}")

            if service_code and not re.match(r"^[a-z0-9-]+$", str(service_code)):
                stats["invalid_formats"] += 1
                issues.append(f"Invalid service format at {i}: {service_code}")

        # Calculate integrity score
        total_possible_issues = len(data) * 4  # 4 checks per record
        actual_issues = sum(
            [
                stats["duplicate_records"],
                stats["missing_fields"],
                stats["invalid_formats"],
                stats["empty_values"],
            ]
        )
        integrity_score = max(
            0, (total_possible_issues - actual_issues) / total_possible_issues * 100
        )

        return {
            "validation_score": round(integrity_score, 2),
            "statistics": stats,
            "issues": issues[:20],  # Limit to first 20 issues
            "total_issues": len(issues),
            "integrity_grade": self._get_quality_grade(integrity_score),
        }

    def coverage_validation(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Validate data coverage against expected thresholds."""
        self.logger.debug("Validating data coverage")

        import pandas as pd

        df = pd.DataFrame(data)

        # Calculate coverage metrics
        unique_regions = df["Region Code"].nunique()
        unique_services = df["Service Code"].nunique()
        total_mappings = len(data)

        # Expected coverage calculations
        expected_total_mappings = unique_regions * unique_services
        actual_coverage = (
            (total_mappings / expected_total_mappings) * 100
            if expected_total_mappings > 0
            else 0
        )

        # Regional coverage analysis
        region_service_counts = df.groupby("Region Code").size()
        avg_services_per_region = region_service_counts.mean()

        # Service availability analysis
        service_region_counts = df.groupby("Service Code").size()
        avg_regions_per_service = service_region_counts.mean()

        # Validation against thresholds
        coverage_issues = []

        if unique_regions < self.validation_thresholds["min_regions"]:
            coverage_issues.append(
                f"Too few regions: {unique_regions} < {self.validation_thresholds['min_regions']}"
            )

        if unique_services < self.validation_thresholds["min_services"]:
            coverage_issues.append(
                f"Too few services: {unique_services} < {self.validation_thresholds['min_services']}"
            )

        if actual_coverage < self.validation_thresholds["expected_coverage_percentage"]:
            coverage_issues.append(
                f"Low coverage: {actual_coverage:.1f}% < {self.validation_thresholds['expected_coverage_percentage']}%"
            )

        # Calculate coverage score
        coverage_score = min(
            100,
            (
                actual_coverage
                / self.validation_thresholds["expected_coverage_percentage"]
            )
            * 100,
        )

        return {
            "validation_score": round(coverage_score, 2),
            "coverage_metrics": {
                "unique_regions": unique_regions,
                "unique_services": unique_services,
                "total_mappings": total_mappings,
                "theoretical_max_mappings": expected_total_mappings,
                "actual_coverage_percentage": round(actual_coverage, 2),
                "avg_services_per_region": round(avg_services_per_region, 1),
                "avg_regions_per_service": round(avg_regions_per_service, 1),
            },
            "coverage_issues": coverage_issues,
            "coverage_grade": self._get_quality_grade(coverage_score),
        }

    def consistency_validation(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Validate data consistency and patterns."""
        self.logger.debug("Validating data consistency")

        import pandas as pd

        df = pd.DataFrame(data)

        consistency_issues = []
        consistency_stats = {}

        # Regional consistency checks
        region_service_counts = df.groupby("Region Code").size()
        region_consistency = {
            "std_dev": region_service_counts.std(),
            "coefficient_of_variation": (
                region_service_counts.std() / region_service_counts.mean()
                if region_service_counts.mean() > 0
                else 0
            ),
            "outlier_regions": [],
        }

        # Identify region outliers (more than 2 std devs from mean)
        mean_services = region_service_counts.mean()
        std_services = region_service_counts.std()

        for region, count in region_service_counts.items():
            if abs(count - mean_services) > 2 * std_services:
                region_consistency["outlier_regions"].append((region, count))
                consistency_issues.append(
                    f"Region {region} has unusual service count: {count}"
                )

        # Service consistency checks
        service_region_counts = df.groupby("Service Code").size()
        service_consistency = {
            "std_dev": service_region_counts.std(),
            "coefficient_of_variation": (
                service_region_counts.std() / service_region_counts.mean()
                if service_region_counts.mean() > 0
                else 0
            ),
            "outlier_services": [],
        }

        # Identify service outliers
        mean_regions = service_region_counts.mean()
        std_regions = service_region_counts.std()

        for service, count in service_region_counts.items():
            if abs(count - mean_regions) > 2 * std_regions:
                service_consistency["outlier_services"].append((service, count))
                consistency_issues.append(
                    f"Service {service} has unusual region count: {count}"
                )

        # Calculate consistency score
        region_cv = region_consistency["coefficient_of_variation"]
        service_cv = service_consistency["coefficient_of_variation"]
        avg_cv = (region_cv + service_cv) / 2

        # Lower coefficient of variation = higher consistency score
        consistency_score = max(0, 100 - (avg_cv * 20))  # Scale CV to 0-100 score

        return {
            "validation_score": round(consistency_score, 2),
            "regional_consistency": region_consistency,
            "service_consistency": service_consistency,
            "consistency_issues": consistency_issues,
            "consistency_grade": self._get_quality_grade(consistency_score),
        }

    def discovery_validation(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Validate data against discovered regions and services."""
        self.logger.debug("Validating against discovered regions and services")

        try:
            # Discover current regions and services
            discovered_regions = self.region_discoverer.process_with_cache()
            discovered_services = self.service_discoverer.process_with_cache()

            # Extract data regions and services
            import pandas as pd

            df = pd.DataFrame(data)
            data_regions = set(df["Region Code"].unique())
            data_services = set(df["Service Code"].unique())

            # Compare with discovered data
            missing_regions = set(discovered_regions) - data_regions
            extra_regions = data_regions - set(discovered_regions)
            missing_services = set(discovered_services) - data_services
            extra_services = data_services - set(discovered_services)

            # Calculate discovery alignment score
            total_discovered = len(discovered_regions) + len(discovered_services)
            total_found = len(data_regions.intersection(set(discovered_regions))) + len(
                data_services.intersection(set(discovered_services))
            )
            alignment_score = (
                (total_found / total_discovered * 100) if total_discovered > 0 else 0
            )

            discovery_issues = []
            if missing_regions:
                discovery_issues.append(
                    f"Missing {len(missing_regions)} discovered regions"
                )
            if extra_regions:
                discovery_issues.append(f"Found {len(extra_regions)} unknown regions")
            if missing_services:
                discovery_issues.append(
                    f"Missing {len(missing_services)} discovered services"
                )
            if extra_services:
                discovery_issues.append(f"Found {len(extra_services)} unknown services")

            return {
                "validation_score": round(alignment_score, 2),
                "discovery_comparison": {
                    "discovered_regions": len(discovered_regions),
                    "data_regions": len(data_regions),
                    "discovered_services": len(discovered_services),
                    "data_services": len(data_services),
                    "missing_regions": len(missing_regions),
                    "extra_regions": len(extra_regions),
                    "missing_services": len(missing_services),
                    "extra_services": len(extra_services),
                },
                "discovery_issues": discovery_issues,
                "discovery_grade": self._get_quality_grade(alignment_score),
            }

        except Exception as e:
            self.logger.warning(f"Discovery validation failed: {e}")
            return {
                "validation_score": 50.0,  # Neutral score if discovery fails
                "discovery_issues": [f"Discovery validation failed: {e}"],
                "discovery_grade": "C",
            }

    def anomaly_detection_validation(
        self, data: List[Dict], **kwargs
    ) -> Dict[str, Any]:
        """Detect anomalies in regional data patterns."""
        self.logger.debug("Detecting data anomalies")

        import pandas as pd

        df = pd.DataFrame(data)

        anomalies = []
        anomaly_stats = {
            "region_anomalies": 0,
            "service_anomalies": 0,
            "pattern_anomalies": 0,
        }

        # Statistical anomaly detection
        region_counts = df.groupby("Region Code").size()
        service_counts = df.groupby("Service Code").size()

        # Z-score based anomaly detection for regions
        region_mean = region_counts.mean()
        region_std = region_counts.std()

        if region_std > 0:
            region_z_scores = (region_counts - region_mean) / region_std
            region_anomalies = region_z_scores[abs(region_z_scores) > 3]  # 3-sigma rule

            for region, z_score in region_anomalies.items():
                anomalies.append(
                    f"Region {region} has anomalous service count (z-score: {z_score:.2f})"
                )
                anomaly_stats["region_anomalies"] += 1

        # Z-score based anomaly detection for services
        service_mean = service_counts.mean()
        service_std = service_counts.std()

        if service_std > 0:
            service_z_scores = (service_counts - service_mean) / service_std
            service_anomalies = service_z_scores[abs(service_z_scores) > 3]

            for service, z_score in service_anomalies.items():
                anomalies.append(
                    f"Service {service} has anomalous region count (z-score: {z_score:.2f})"
                )
                anomaly_stats["service_anomalies"] += 1

        # Pattern anomaly detection
        # Check for services that should be universal but aren't
        expected_universal_services = ["s3", "ec2", "iam", "cloudwatch"]
        total_regions = df["Region Code"].nunique()

        for service in expected_universal_services:
            if service in service_counts:
                service_region_count = service_counts[service]
                if (
                    service_region_count < total_regions * 0.8
                ):  # Should be in 80%+ of regions
                    anomalies.append(
                        f"Universal service {service} only in {service_region_count}/{total_regions} regions"
                    )
                    anomaly_stats["pattern_anomalies"] += 1

        # Calculate anomaly score (lower is better, fewer anomalies)
        total_potential_anomalies = (
            len(region_counts) + len(service_counts) + len(expected_universal_services)
        )
        total_detected_anomalies = sum(anomaly_stats.values())
        anomaly_score = max(
            0, 100 - (total_detected_anomalies / total_potential_anomalies * 100)
        )

        return {
            "validation_score": round(anomaly_score, 2),
            "anomaly_statistics": anomaly_stats,
            "detected_anomalies": anomalies[:15],  # Limit to first 15
            "total_anomalies": len(anomalies),
            "anomaly_grade": self._get_quality_grade(anomaly_score),
        }

    def _get_quality_grade(self, score: float) -> str:
        """Convert numerical score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
