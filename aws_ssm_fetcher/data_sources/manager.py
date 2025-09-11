"""Unified data source manager for coordinating AWS data fetching."""

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from ..core.logging import get_logger
from .aws_ssm_client import AWSSSMClient
from .rss_client import RSSClient


class DataSourceStrategy(Enum):
    """Data source fallback strategies."""

    SSM_ONLY = "ssm_only"
    RSS_ONLY = "rss_only"
    SSM_WITH_RSS_FALLBACK = "ssm_with_rss_fallback"
    RSS_WITH_SSM_FALLBACK = "rss_with_ssm_fallback"
    MERGE_SSM_RSS = "merge_ssm_rss"
    AUTO = "auto"


class DataSourceManager:
    """Unified manager for coordinating multiple data sources.

    Provides a single interface for fetching AWS data while managing:
    - Multiple data sources (SSM, RSS)
    - Fallback strategies when sources fail
    - Data validation and merging
    - Performance optimization through caching
    - Error handling and retries
    """

    def __init__(self, config=None, cache_manager=None, aws_session=None):
        """Initialize the data source manager.

        Args:
            config: Configuration object with AWS and caching settings
            cache_manager: Cache manager for data persistence
            aws_session: Boto3 session for AWS API calls
        """
        self.config = config
        self.cache_manager = cache_manager
        self.aws_session = aws_session
        self.logger = get_logger("data_source_manager")

        # Initialize data source clients
        self.ssm_client = None
        self.rss_client = None

        # Default fallback data for when all sources fail
        self.fallback_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "eu-north-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-south-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ca-central-1",
            "sa-east-1",
        ]

        self.fallback_services = [
            "ec2",
            "s3",
            "rds",
            "lambda",
            "dynamodb",
            "cloudformation",
            "iam",
            "cloudwatch",
            "sns",
            "sqs",
            "elasticloadbalancing",
            "autoscaling",
            "ecs",
            "eks",
            "vpc",
            "route53",
            "cloudfront",
            "apigateway",
            "secretsmanager",
            "ssm",
        ]

        # Performance tracking
        self._performance_stats = {
            "ssm_calls": 0,
            "rss_calls": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "total_requests": 0,
        }

    def get_ssm_client(self) -> AWSSSMClient:
        """Get or create SSM client."""
        if self.ssm_client is None:
            region = getattr(self.config, "aws_region", "us-east-1")
            self.ssm_client = AWSSSMClient(
                aws_session=self.aws_session,
                cache_manager=self.cache_manager,
                region=region,
                max_retries=getattr(self.config, "max_retries", 3),
                base_delay=getattr(self.config, "base_delay", 1.0),
            )
        return cast(AWSSSMClient, self.ssm_client)

    def get_rss_client(self) -> RSSClient:
        """Get or create RSS client."""
        if self.rss_client is None:
            self.rss_client = RSSClient(
                cache_manager=self.cache_manager,
                timeout=getattr(self.config, "rss_timeout", 30),
                max_retries=getattr(self.config, "max_retries", 3),
            )
        return cast(RSSClient, self.rss_client)

    def fetch_regions(
        self, strategy: DataSourceStrategy = DataSourceStrategy.AUTO
    ) -> List[str]:
        """Fetch AWS regions using specified strategy.

        Args:
            strategy: Data source strategy to use

        Returns:
            List of AWS region codes
        """
        self._performance_stats["total_requests"] += 1

        self.logger.info(f"Fetching regions using strategy: {strategy.value}")

        if strategy == DataSourceStrategy.AUTO:
            strategy = self._determine_optimal_strategy_for_regions()

        try:
            if strategy == DataSourceStrategy.SSM_ONLY:
                return self._fetch_regions_from_ssm()

            elif strategy == DataSourceStrategy.RSS_ONLY:
                return self._fetch_regions_from_rss()

            elif strategy == DataSourceStrategy.SSM_WITH_RSS_FALLBACK:
                regions = self._fetch_regions_from_ssm()
                if not regions or len(regions) < 5:  # Minimum reasonable number
                    self.logger.warning(
                        "SSM returned insufficient regions, trying RSS fallback"
                    )
                    rss_regions = self._fetch_regions_from_rss()
                    return rss_regions if rss_regions else self._get_fallback_regions()
                return regions

            elif strategy == DataSourceStrategy.RSS_WITH_SSM_FALLBACK:
                regions = self._fetch_regions_from_rss()
                if not regions or len(regions) < 5:
                    self.logger.warning(
                        "RSS returned insufficient regions, trying SSM fallback"
                    )
                    ssm_regions = self._fetch_regions_from_ssm()
                    return ssm_regions if ssm_regions else self._get_fallback_regions()
                return regions

            elif strategy == DataSourceStrategy.MERGE_SSM_RSS:
                return self._fetch_regions_merged()

            else:
                self.logger.error(f"Unknown strategy: {strategy}")
                return self._get_fallback_regions()

        except Exception as e:
            self.logger.error(f"Failed to fetch regions: {e}")
            return self._get_fallback_regions()

    def fetch_services(
        self, strategy: DataSourceStrategy = DataSourceStrategy.AUTO
    ) -> List[str]:
        """Fetch AWS services using specified strategy.

        Args:
            strategy: Data source strategy to use

        Returns:
            List of AWS service codes
        """
        self._performance_stats["total_requests"] += 1

        self.logger.info(f"Fetching services using strategy: {strategy.value}")

        if strategy == DataSourceStrategy.AUTO:
            strategy = DataSourceStrategy.SSM_ONLY  # SSM is primary for services

        try:
            if strategy in [
                DataSourceStrategy.SSM_ONLY,
                DataSourceStrategy.SSM_WITH_RSS_FALLBACK,
            ]:
                services = self._fetch_services_from_ssm()
                if services and len(services) >= 50:  # Reasonable minimum
                    return services
                else:
                    self.logger.warning(
                        "SSM returned insufficient services, using fallback"
                    )
                    return self._get_fallback_services()

            else:
                return self._get_fallback_services()

        except Exception as e:
            self.logger.error(f"Failed to fetch services: {e}")
            return self._get_fallback_services()

    def fetch_region_metadata(
        self, regions: List[str]
    ) -> Tuple[Dict[str, str], Dict[str, Dict]]:
        """Fetch region display names and RSS metadata.

        Args:
            regions: List of region codes

        Returns:
            Tuple of (region_names_dict, rss_metadata_dict)
        """
        self._performance_stats["total_requests"] += 1

        # Fetch region names from SSM
        region_names = {}
        rss_metadata = {}

        try:
            ssm_client = self.get_ssm_client()
            region_names = ssm_client.fetch_region_names(regions)
            self._performance_stats["ssm_calls"] += 1
        except Exception as e:
            self.logger.error(f"Failed to fetch region names from SSM: {e}")

        # Fetch RSS metadata if available
        try:
            rss_client = self.get_rss_client()
            rss_metadata = rss_client.fetch_region_rss_data()
            self._performance_stats["rss_calls"] += 1

            # Merge RSS data with region names
            for region_code, rss_data in rss_metadata.items():
                if region_code in regions:
                    # Use RSS region name if SSM name is missing or generic
                    ssm_name = region_names.get(region_code, "")
                    rss_name = rss_data.get("region_name", "")

                    if not ssm_name or ssm_name == region_code:
                        region_names[region_code] = rss_name
                    elif rss_name and len(rss_name) > len(ssm_name):
                        # Use more descriptive name
                        region_names[region_code] = rss_name

        except Exception as e:
            self.logger.error(f"Failed to fetch RSS metadata: {e}")

        # Fill in missing region names with fallbacks
        for region in regions:
            if region not in region_names or not region_names[region]:
                region_names[region] = self._generate_region_display_name(region)

        self.logger.info(f"Fetched metadata for {len(region_names)} regions")
        return region_names, rss_metadata

    def fetch_service_metadata(self, services: List[str]) -> Dict[str, str]:
        """Fetch service display names.

        Args:
            services: List of service codes

        Returns:
            Dictionary mapping service codes to display names
        """
        self._performance_stats["total_requests"] += 1

        try:
            ssm_client = self.get_ssm_client()
            service_names = ssm_client.fetch_service_names(services)
            self._performance_stats["ssm_calls"] += 1

            # Fill in missing service names with fallbacks
            for service in services:
                if service not in service_names or not service_names[service]:
                    service_names[service] = self._generate_service_display_name(
                        service
                    )

            self.logger.info(f"Fetched metadata for {len(service_names)} services")
            return service_names

        except Exception as e:
            self.logger.error(f"Failed to fetch service metadata: {e}")
            # Return fallback names for all services
            return {
                service: self._generate_service_display_name(service)
                for service in services
            }

    def fetch_region_service_mapping(
        self, regions: List[str], services: List[str]
    ) -> Dict[str, List[str]]:
        """Fetch mapping of services available in each region.

        Args:
            regions: List of region codes
            services: List of service codes

        Returns:
            Dictionary mapping region codes to lists of available services
        """
        self._performance_stats["total_requests"] += 1

        try:
            ssm_client = self.get_ssm_client()
            mapping = ssm_client.get_region_service_mapping(regions, services)
            self._performance_stats["ssm_calls"] += 1

            if not mapping:
                self.logger.warning(
                    "No region-service mapping returned, generating fallback"
                )
                return self._generate_fallback_mapping(regions, services)

            return mapping

        except Exception as e:
            self.logger.error(f"Failed to fetch region-service mapping: {e}")
            return self._generate_fallback_mapping(regions, services)

    def fetch_availability_zones(self, regions: List[str]) -> Dict[str, int]:
        """Fetch availability zone counts for regions.

        Args:
            regions: List of region codes

        Returns:
            Dictionary mapping region codes to AZ counts
        """
        self._performance_stats["total_requests"] += 1

        try:
            ssm_client = self.get_ssm_client()
            az_data = ssm_client.fetch_availability_zones(regions)
            self._performance_stats["ssm_calls"] += 1
            return az_data

        except Exception as e:
            self.logger.error(f"Failed to fetch availability zones: {e}")
            # Return fallback AZ counts
            return {region: 3 for region in regions}  # Default to 3 AZs

    def validate_data_consistency(
        self,
        regions: List[str],
        services: List[str],
        region_service_mapping: Dict[str, List[str]],
    ) -> bool:
        """Validate consistency of fetched data.

        Args:
            regions: List of region codes
            services: List of service codes
            region_service_mapping: Region to services mapping

        Returns:
            True if data is consistent, False otherwise
        """
        issues = []

        # Check region codes format
        invalid_regions = [r for r in regions if not self._is_valid_region_code(r)]
        if invalid_regions:
            issues.append(f"Invalid region codes: {invalid_regions}")

        # Check service codes format
        invalid_services = [s for s in services if not self._is_valid_service_code(s)]
        if invalid_services:
            issues.append(f"Invalid service codes: {invalid_services}")

        # Check mapping consistency
        mapped_regions = set(region_service_mapping.keys())
        region_set = set(regions)

        missing_regions = region_set - mapped_regions
        if missing_regions:
            issues.append(f"Regions missing from mapping: {missing_regions}")

        extra_regions = mapped_regions - region_set
        if extra_regions:
            issues.append(f"Extra regions in mapping: {extra_regions}")

        # Log validation results
        if issues:
            for issue in issues:
                self.logger.warning(f"Data consistency issue: {issue}")
            return False
        else:
            self.logger.info("Data consistency validation passed")
            return True

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for data source operations."""
        return {
            **self._performance_stats,
            "cache_hit_rate": self._performance_stats["cache_hits"]
            / max(self._performance_stats["total_requests"], 1),
            "fallback_rate": self._performance_stats["fallback_used"]
            / max(self._performance_stats["total_requests"], 1),
        }

    # Private helper methods

    def _determine_optimal_strategy_for_regions(self) -> DataSourceStrategy:
        """Determine the optimal strategy for fetching regions."""
        # For now, use SSM with RSS fallback as it's most reliable
        return DataSourceStrategy.SSM_WITH_RSS_FALLBACK

    def _fetch_regions_from_ssm(self) -> List[str]:
        """Fetch regions from SSM client."""
        ssm_client = self.get_ssm_client()
        regions = ssm_client.discover_regions_from_ssm_enhanced()
        self._performance_stats["ssm_calls"] += 1
        return regions

    def _fetch_regions_from_rss(self) -> List[str]:
        """Fetch regions from RSS client."""
        rss_client = self.get_rss_client()
        rss_data = rss_client.fetch_region_rss_data()
        self._performance_stats["rss_calls"] += 1
        return list(rss_data.keys()) if rss_data else []

    def _fetch_regions_merged(self) -> List[str]:
        """Fetch regions from both sources and merge."""
        ssm_regions = set(self._fetch_regions_from_ssm() or [])
        rss_regions = set(self._fetch_regions_from_rss() or [])

        # Merge and prioritize regions that appear in both sources
        all_regions = ssm_regions.union(rss_regions)
        return sorted(list(all_regions))

    def _fetch_services_from_ssm(self) -> List[str]:
        """Fetch services from SSM client."""
        ssm_client = self.get_ssm_client()
        services = ssm_client.discover_services_from_ssm_enhanced()
        self._performance_stats["ssm_calls"] += 1
        return services

    def _get_fallback_regions(self) -> List[str]:
        """Get fallback list of regions when all sources fail."""
        self._performance_stats["fallback_used"] += 1
        self.logger.info(
            f"Using fallback regions ({len(self.fallback_regions)} regions)"
        )
        return cast(List[str], self.fallback_regions.copy())

    def _get_fallback_services(self) -> List[str]:
        """Get fallback list of services when all sources fail."""
        self._performance_stats["fallback_used"] += 1
        self.logger.info(
            f"Using fallback services ({len(self.fallback_services)} services)"
        )
        return cast(List[str], self.fallback_services.copy())

    def _generate_region_display_name(self, region_code: str) -> str:
        """Generate a display name for a region code."""
        # Simple mapping for common regions
        region_names = {
            "us-east-1": "US East (N. Virginia)",
            "us-east-2": "US East (Ohio)",
            "us-west-1": "US West (N. California)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "Europe (Ireland)",
            "eu-west-2": "Europe (London)",
            "eu-west-3": "Europe (Paris)",
            "eu-central-1": "Europe (Frankfurt)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
            "ap-southeast-2": "Asia Pacific (Sydney)",
        }
        return region_names.get(region_code, region_code.upper())

    def _generate_service_display_name(self, service_code: str) -> str:
        """Generate a display name for a service code."""
        # Simple mapping for common services
        service_names = {
            "ec2": "Amazon Elastic Compute Cloud",
            "s3": "Amazon Simple Storage Service",
            "rds": "Amazon Relational Database Service",
            "lambda": "AWS Lambda",
            "dynamodb": "Amazon DynamoDB",
            "iam": "AWS Identity and Access Management",
            "cloudformation": "AWS CloudFormation",
            "sns": "Amazon Simple Notification Service",
            "sqs": "Amazon Simple Queue Service",
        }
        return service_names.get(service_code, service_code.upper())

    def _generate_fallback_mapping(
        self, regions: List[str], services: List[str]
    ) -> Dict[str, List[str]]:
        """Generate fallback region-service mapping."""
        # Assume core services are available in all regions
        core_services = ["ec2", "s3", "iam", "cloudformation", "cloudwatch"]

        mapping = {}
        for region in regions:
            # Core services + subset of other services
            available_services = core_services.copy()
            available_services.extend(
                services[: min(len(services), 20)]
            )  # Add first 20 services
            mapping[region] = sorted(list(set(available_services)))

        return mapping

    def _is_valid_region_code(self, region_code: str) -> bool:
        """Check if region code has valid format."""
        import re

        return bool(re.match(r"^[a-z]{2}-[a-z]+-[0-9]{1,2}$", region_code))

    def _is_valid_service_code(self, service_code: str) -> bool:
        """Check if service code has valid format."""
        return bool(
            service_code and isinstance(service_code, str) and len(service_code) > 1
        )
