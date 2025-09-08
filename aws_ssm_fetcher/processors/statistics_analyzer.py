"""Statistics and analytics processor for AWS SSM data analysis."""

import re
import statistics as stats
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from ..core.error_handling import ErrorHandler, with_retry
from .base import (
    BaseProcessor,
    ProcessingContext,
    ProcessingError,
    ProcessingValidationError,
)


class StatisticsAnalysisError(ProcessingError):
    """Exception raised during statistics analysis operations."""

    pass


class AvailabilityZoneAnalyzer(BaseProcessor):
    """Processor for analyzing AWS availability zones."""

    def __init__(self, context: ProcessingContext):
        """Initialize AZ analyzer processor.

        Args:
            context: Processing context with SSM client and config
        """
        super().__init__(context)
        self.error_handler = ErrorHandler()

        # Get SSM client from context (injected dependency)
        if not hasattr(context, "ssm_client"):
            raise ProcessingError("SSM client not found in processing context")

        self.ssm_client = context.ssm_client

        # Common AZ to region mappings for fallback
        self.region_mappings = {
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

        # Known AZ counts for established regions (fallback)
        self.common_az_counts = {
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

        # Configure retry for AWS operations
        retry_config = self.error_handler.get_aws_retry_config()
        self._get_parameter_with_retry = with_retry(retry_config)(self._get_parameter)

    def validate_input(self, input_data: Any) -> bool:
        """Validate input region list.

        Args:
            input_data: List of region codes to validate

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        if not isinstance(input_data, list):
            raise ProcessingValidationError("Input must be a list of region codes")

        if not input_data:
            raise ProcessingValidationError("Region list cannot be empty")

        # Validate region code format
        for region_code in input_data:
            if not isinstance(region_code, str):
                raise ProcessingValidationError(
                    f"Region code must be string: {region_code}"
                )

            if not region_code.strip():
                raise ProcessingValidationError("Region code cannot be empty")

            # Basic AWS region code validation
            if not re.match(r"^[a-z0-9-]+$", region_code):
                raise ProcessingValidationError(
                    f"Invalid region code format: {region_code}"
                )

        return True

    def process(self, input_data: List[str], **kwargs) -> Dict[str, int]:
        """Fetch availability zone counts for regions.

        Args:
            input_data: List of region codes
            **kwargs: Additional processing parameters

        Returns:
            Dictionary mapping region codes to AZ counts

        Raises:
            ProcessingError: If AZ analysis fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        self.logger.info(f"Analyzing availability zones for {len(input_data)} regions")

        try:
            # Get all AZ parameters with pagination
            all_az_params = self._fetch_all_ssm_parameters_by_path(
                "/aws/service/global-infrastructure/availability-zones"
            )

            az_data = {}

            for region in input_data:
                az_count = self._count_azs_for_region(region, all_az_params)
                if az_count > 0:
                    az_data[region] = az_count
                    self.logger.debug(f"Found {az_count} AZs for {region}")
                else:
                    # Use fallback
                    fallback_count = self.common_az_counts.get(region, 3)
                    az_data[region] = fallback_count
                    self.logger.debug(
                        f"Using fallback count {fallback_count} AZs for {region}"
                    )

            self.logger.info(
                f"Successfully analyzed AZ data for {len(az_data)} regions"
            )
            return az_data

        except Exception as e:
            self.logger.error(f"AZ analysis failed: {e}", exc_info=True)
            raise StatisticsAnalysisError(
                f"Failed to analyze availability zones: {e}"
            ) from e

    def _fetch_all_ssm_parameters_by_path(self, parameter_path: str) -> List[str]:
        """Fetch all SSM parameter names under a path with pagination."""
        parameter_names = []
        paginator = self.ssm_client.get_paginator("get_parameters_by_path")

        try:
            page_iterator = paginator.paginate(
                Path=parameter_path, Recursive=True, MaxResults=10
            )

            for page in page_iterator:
                for param in page["Parameters"]:
                    parameter_names.append(param["Name"])

        except Exception as e:
            self.logger.warning(
                f"Failed to fetch parameters for path {parameter_path}: {e}"
            )

        return parameter_names

    def _count_azs_for_region(self, region: str, all_az_params: List[str]) -> int:
        """Count availability zones for a specific region."""
        az_count = 0

        # Look for AZ parameters that belong to this region
        for param_name in all_az_params:
            if "/region" in param_name:
                try:
                    # Get the region for this AZ parameter
                    response = self._get_parameter_with_retry(param_name)
                    if response and response["Parameter"]["Value"] == region:
                        az_count += 1
                except Exception:
                    # Try pattern matching as fallback
                    az_count += self._pattern_match_az_to_region(param_name, region)

        return az_count

    def _get_parameter(self, param_name: str) -> Optional[Dict]:
        """Get SSM parameter value."""
        try:
            return self.ssm_client.get_parameter(Name=param_name)
        except Exception as e:
            self.logger.debug(f"Failed to get parameter {param_name}: {e}")
            return None

    def _pattern_match_az_to_region(self, param_name: str, region: str) -> int:
        """Pattern match AZ parameter to region as fallback."""
        az_match = re.search(r"/availability-zones/([^/]+)/", param_name)
        if az_match:
            az_code = az_match.group(1)
            az_region_prefix = az_code.rstrip("0123456789-az")
            if self.region_mappings.get(az_region_prefix) == region:
                return 1
        return 0


class StatisticsAnalyzer(BaseProcessor):
    """Comprehensive statistics and analytics processor for AWS service-region data."""

    def __init__(self, context: ProcessingContext):
        """Initialize statistics analyzer processor.

        Args:
            context: Processing context with config and cache
        """
        super().__init__(context)
        self.az_analyzer = AvailabilityZoneAnalyzer(context)

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data structure.

        Args:
            input_data: Data to validate (expects list of dicts with service-region info)

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        if not isinstance(input_data, list):
            raise ProcessingValidationError(
                "Input must be a list of service-region mappings"
            )

        if not input_data:
            raise ProcessingValidationError("Input data cannot be empty")

        # Validate structure
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
        self, input_data: List[Dict], analysis_type: str = "comprehensive", **kwargs
    ) -> Dict[str, Any]:
        """Perform statistical analysis on service-region data.

        Args:
            input_data: List of service-region mapping dictionaries
            analysis_type: Type of analysis to perform
            **kwargs: Additional analysis parameters

        Returns:
            Dictionary with analysis results

        Raises:
            ProcessingError: If analysis fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        self.logger.info(
            f"Performing {analysis_type} statistical analysis on {len(input_data)} records"
        )

        analysis_methods = {
            "comprehensive": self.comprehensive_analysis,
            "regional_distribution": self.regional_distribution_analysis,
            "service_coverage": self.service_coverage_analysis,
            "availability_zones": self.availability_zone_analysis,
            "geographic_distribution": self.geographic_distribution_analysis,
            "service_patterns": self.service_pattern_analysis,
            "performance_metrics": self.performance_metrics_analysis,
        }

        if analysis_type not in analysis_methods:
            raise ProcessingError(f"Unknown analysis type: {analysis_type}")

        try:
            method = analysis_methods[analysis_type]
            result = method(input_data, **kwargs)

            self.logger.info(f"Successfully completed {analysis_type} analysis")
            return result

        except Exception as e:
            self.logger.error(f"Analysis {analysis_type} failed: {e}", exc_info=True)
            raise StatisticsAnalysisError(
                f"Failed to perform {analysis_type} analysis: {e}"
            ) from e

    def comprehensive_analysis(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Perform comprehensive statistical analysis.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with comprehensive analysis results
        """
        df = pd.DataFrame(data)

        # Basic counts
        total_regions = df["Region Code"].nunique()
        total_services = (
            df["Service Code"].nunique()
            if "Service Code" in df.columns
            else df["Service Name"].nunique()
        )
        total_mappings = len(df)

        # Regional statistics
        region_groups = df.groupby("Region Code").size()
        regional_stats = {
            "mean_services_per_region": round(region_groups.mean(), 2),
            "median_services_per_region": round(region_groups.median(), 2),
            "std_services_per_region": round(region_groups.std(), 2),
            "max_services_per_region": int(region_groups.max()),
            "min_services_per_region": int(region_groups.min()),
            "regions_above_average": int(sum(region_groups > region_groups.mean())),
            "regions_below_average": int(sum(region_groups < region_groups.mean())),
        }

        # Service statistics
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"
        service_groups = df.groupby(service_col).size()
        service_stats = {
            "mean_regions_per_service": round(service_groups.mean(), 2),
            "median_regions_per_service": round(service_groups.median(), 2),
            "std_regions_per_service": round(service_groups.std(), 2),
            "max_regions_per_service": int(service_groups.max()),
            "min_regions_per_service": int(service_groups.min()),
            "services_above_average": int(sum(service_groups > service_groups.mean())),
            "services_below_average": int(sum(service_groups < service_groups.mean())),
        }

        # Coverage analysis
        coverage_stats = {
            "total_possible_mappings": total_regions * total_services,
            "actual_mappings": total_mappings,
            "overall_coverage_percentage": round(
                (total_mappings / (total_regions * total_services)) * 100, 2
            ),
            "average_service_availability": round(
                (total_mappings / total_services) / total_regions * 100, 2
            ),
            "average_regional_coverage": round(
                (total_mappings / total_regions) / total_services * 100, 2
            ),
        }

        return {
            "overview": {
                "total_regions": total_regions,
                "total_services": total_services,
                "total_mappings": total_mappings,
                "analysis_timestamp": datetime.now().isoformat(),
            },
            "regional_statistics": regional_stats,
            "service_statistics": service_stats,
            "coverage_statistics": coverage_stats,
            "top_regions": self._get_top_regions(df),
            "top_services": self._get_top_services(df),
            "distribution_analysis": self._analyze_distributions(df),
        }

    def regional_distribution_analysis(
        self, data: List[Dict], **kwargs
    ) -> Dict[str, Any]:
        """Analyze regional distribution patterns.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with regional distribution analysis
        """
        df = pd.DataFrame(data)

        # Group by region and count services
        region_counts = df.groupby("Region Code").size().sort_values(ascending=False)

        # Geographic grouping
        geographic_groups = self._group_regions_geographically(
            region_counts.index.tolist()
        )

        # Calculate geographic statistics
        geo_stats = {}
        for geo_region, regions in geographic_groups.items():
            region_data = region_counts[region_counts.index.isin(regions)]
            if not region_data.empty:
                geo_stats[geo_region] = {
                    "region_count": len(region_data),
                    "total_services": int(region_data.sum()),
                    "avg_services_per_region": round(region_data.mean(), 2),
                    "max_services": int(region_data.max()),
                    "min_services": int(region_data.min()),
                    "regions": region_data.to_dict(),
                }

        return {
            "regional_rankings": region_counts.head(20).to_dict(),
            "geographic_distribution": geo_stats,
            "regional_tiers": self._categorize_regions_by_service_count(region_counts),
            "regional_gaps": self._identify_regional_gaps(df),
            "regional_diversity": self._calculate_regional_diversity(df),
        }

    def service_coverage_analysis(
        self, data: List[Dict], all_services: List[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Analyze service coverage patterns.

        Args:
            data: Service-region mapping data
            all_services: Complete list of services for analysis
            **kwargs: Additional parameters

        Returns:
            Dictionary with service coverage analysis
        """
        df = pd.DataFrame(data)
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"

        # Service availability across regions
        service_coverage = df.groupby(service_col).size().sort_values(ascending=False)
        total_regions = df["Region Code"].nunique()

        # Coverage categories
        universal_services = service_coverage[service_coverage == total_regions]
        high_coverage = service_coverage[
            (service_coverage >= total_regions * 0.8)
            & (service_coverage < total_regions)
        ]
        medium_coverage = service_coverage[
            (service_coverage >= total_regions * 0.5)
            & (service_coverage < total_regions * 0.8)
        ]
        low_coverage = service_coverage[service_coverage < total_regions * 0.5]

        # Service patterns
        service_patterns = self._identify_service_patterns(df)

        # Missing services analysis
        missing_services_analysis = {}
        if all_services:
            present_services = set(df[service_col].unique())
            missing_services = set(all_services) - present_services
            missing_services_analysis = {
                "total_missing": len(missing_services),
                "missing_percentage": round(
                    (len(missing_services) / len(all_services)) * 100, 2
                ),
                "missing_services": list(missing_services)[:20],  # Show first 20
            }

        return {
            "service_coverage_distribution": {
                "universal_services": len(universal_services),
                "high_coverage_services": len(high_coverage),
                "medium_coverage_services": len(medium_coverage),
                "low_coverage_services": len(low_coverage),
            },
            "top_services_by_coverage": service_coverage.head(20).to_dict(),
            "service_patterns": service_patterns,
            "missing_services": missing_services_analysis,
            "service_categories": self._categorize_services_by_coverage(
                service_coverage, total_regions
            ),
        }

    def availability_zone_analysis(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Analyze availability zones in relation to service distribution.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with AZ analysis results
        """
        df = pd.DataFrame(data)
        regions = df["Region Code"].unique().tolist()

        # Get AZ data
        az_data = self.az_analyzer.process_with_cache(regions)

        # Correlate AZ counts with service counts
        region_service_counts = df.groupby("Region Code").size().to_dict()

        correlation_data = []
        for region in regions:
            if region in az_data and region in region_service_counts:
                correlation_data.append(
                    {
                        "region": region,
                        "az_count": az_data[region],
                        "service_count": region_service_counts[region],
                    }
                )

        correlation_df = pd.DataFrame(correlation_data)

        # Calculate correlation if we have enough data
        correlation = None
        if len(correlation_df) >= 3:
            correlation = correlation_df["az_count"].corr(
                correlation_df["service_count"]
            )

        # AZ distribution analysis
        az_distribution = Counter(az_data.values())

        return {
            "az_summary": {
                "total_regions_with_az_data": len(az_data),
                "total_azs_analyzed": sum(az_data.values()),
                "avg_azs_per_region": (
                    round(sum(az_data.values()) / len(az_data), 2) if az_data else 0
                ),
                "max_azs_in_region": max(az_data.values()) if az_data else 0,
                "min_azs_in_region": min(az_data.values()) if az_data else 0,
            },
            "az_service_correlation": {
                "correlation_coefficient": (
                    round(correlation, 3) if correlation is not None else None
                ),
                "correlation_interpretation": (
                    self._interpret_correlation(correlation)
                    if correlation is not None
                    else None
                ),
            },
            "az_distribution": dict(az_distribution),
            "regions_by_az_count": az_data,
            "high_az_regions": {k: v for k, v in az_data.items() if v >= 4},
            "correlation_data": correlation_data,
        }

    def geographic_distribution_analysis(
        self, data: List[Dict], **kwargs
    ) -> Dict[str, Any]:
        """Analyze geographic distribution of services.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with geographic distribution analysis
        """
        df = pd.DataFrame(data)

        # Group regions geographically
        region_groups = self._group_regions_geographically(df["Region Code"].unique())

        # Analyze each geographic region
        geographic_analysis = {}
        for geo_region, regions in region_groups.items():
            region_data = df[df["Region Code"].isin(regions)]

            if not region_data.empty:
                geographic_analysis[geo_region] = {
                    "region_count": len(regions),
                    "total_services": (
                        region_data["Service Code"].nunique()
                        if "Service Code" in region_data.columns
                        else region_data["Service Name"].nunique()
                    ),
                    "total_mappings": len(region_data),
                    "avg_services_per_region": round(
                        len(region_data) / len(regions), 2
                    ),
                    "unique_services": len(
                        set(
                            region_data["Service Code"]
                            if "Service Code" in region_data.columns
                            else region_data["Service Name"]
                        )
                    ),
                    "regions": list(regions),
                }

        # Cross-geographic service availability
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"
        service_geographic_presence = {}

        for service in df[service_col].unique():
            service_data = df[df[service_col] == service]
            service_regions = set(service_data["Region Code"])

            presence = {}
            for geo_region, regions in region_groups.items():
                overlap = service_regions.intersection(set(regions))
                presence[geo_region] = len(overlap)

            service_geographic_presence[service] = presence

        return {
            "geographic_regions": geographic_analysis,
            "cross_geographic_services": service_geographic_presence,
            "geographic_coverage_leaders": self._find_geographic_leaders(
                geographic_analysis
            ),
            "geographic_service_gaps": self._identify_geographic_gaps(
                service_geographic_presence, region_groups
            ),
        }

    def service_pattern_analysis(self, data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Analyze patterns in service availability.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with service pattern analysis
        """
        df = pd.DataFrame(data)
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"

        # Identify service patterns based on names/codes
        patterns = {
            "compute_services": [],
            "storage_services": [],
            "database_services": [],
            "networking_services": [],
            "security_services": [],
            "analytics_services": [],
            "ml_ai_services": [],
            "developer_tools": [],
            "management_services": [],
        }

        for service in df[service_col].unique():
            service_lower = str(service).lower()

            if any(
                keyword in service_lower
                for keyword in [
                    "ec2",
                    "lambda",
                    "batch",
                    "compute",
                    "ecs",
                    "eks",
                    "fargate",
                ]
            ):
                patterns["compute_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["s3", "ebs", "efs", "fsx", "storage", "glacier"]
            ):
                patterns["storage_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["rds", "dynamodb", "aurora", "database", "db", "dax"]
            ):
                patterns["database_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["vpc", "elb", "cloudfront", "route53", "network", "api"]
            ):
                patterns["networking_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["iam", "kms", "security", "waf", "shield", "cognito"]
            ):
                patterns["security_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in [
                    "athena",
                    "glue",
                    "kinesis",
                    "analytics",
                    "redshift",
                    "emr",
                ]
            ):
                patterns["analytics_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in [
                    "sagemaker",
                    "comprehend",
                    "rekognition",
                    "ml",
                    "ai",
                    "lex",
                ]
            ):
                patterns["ml_ai_services"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["code", "developer", "build", "deploy", "pipeline"]
            ):
                patterns["developer_tools"].append(service)
            elif any(
                keyword in service_lower
                for keyword in ["cloudwatch", "cloudtrail", "config", "systems", "ssm"]
            ):
                patterns["management_services"].append(service)

        # Analyze coverage by pattern
        pattern_coverage = {}
        for pattern_name, services in patterns.items():
            if services:
                pattern_data = df[df[service_col].isin(services)]
                pattern_coverage[pattern_name] = {
                    "service_count": len(services),
                    "avg_regional_availability": (
                        round(len(pattern_data) / len(services), 2) if services else 0
                    ),
                    "total_mappings": len(pattern_data),
                    "services": services[:10],  # Show first 10
                }

        return {
            "service_patterns": patterns,
            "pattern_coverage_analysis": pattern_coverage,
            "pattern_statistics": self._calculate_pattern_statistics(pattern_coverage),
        }

    def performance_metrics_analysis(
        self, data: List[Dict], **kwargs
    ) -> Dict[str, Any]:
        """Analyze performance-related metrics from the processing context.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            Dictionary with performance metrics analysis
        """
        processing_stats = self.get_processing_stats()

        # Data processing efficiency
        data_efficiency = {
            "records_per_operation": len(data)
            / max(processing_stats["total_operations"], 1),
            "cache_efficiency": processing_stats.get("cache_hit_rate", 0) * 100,
            "processing_speed": len(data)
            / max(processing_stats["total_processing_time"], 0.001),
            "error_rate": processing_stats.get("failure_rate", 0) * 100,
        }

        # Data quality metrics
        df = pd.DataFrame(data)
        data_quality = {
            "completeness": self._calculate_data_completeness(df),
            "consistency": self._calculate_data_consistency(df),
            "coverage": self._calculate_coverage_metrics(df),
        }

        return {
            "processing_performance": processing_stats,
            "data_efficiency_metrics": data_efficiency,
            "data_quality_metrics": data_quality,
            "recommendations": self._generate_performance_recommendations(
                data_efficiency, data_quality
            ),
        }

    def _get_top_regions(self, df: pd.DataFrame, n: int = 10) -> Dict[str, int]:
        """Get top N regions by service count."""
        return df.groupby("Region Code").size().nlargest(n).to_dict()

    def _get_top_services(self, df: pd.DataFrame, n: int = 10) -> Dict[str, int]:
        """Get top N services by region count."""
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"
        return df.groupby(service_col).size().nlargest(n).to_dict()

    def _analyze_distributions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze statistical distributions."""
        region_counts = df.groupby("Region Code").size()
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"
        service_counts = df.groupby(service_col).size()

        return {
            "regional_distribution": {
                "skewness": round(region_counts.skew(), 3),
                "kurtosis": round(region_counts.kurtosis(), 3),
                "quartiles": region_counts.quantile([0.25, 0.5, 0.75]).to_dict(),
            },
            "service_distribution": {
                "skewness": round(service_counts.skew(), 3),
                "kurtosis": round(service_counts.kurtosis(), 3),
                "quartiles": service_counts.quantile([0.25, 0.5, 0.75]).to_dict(),
            },
        }

    def _group_regions_geographically(self, regions: List[str]) -> Dict[str, List[str]]:
        """Group regions by geographic location."""
        geographic_groups = {
            "US": [],
            "Europe": [],
            "Asia Pacific": [],
            "Canada": [],
            "South America": [],
            "Africa": [],
            "Middle East": [],
            "Government": [],
        }

        for region in regions:
            if region.startswith("us-"):
                if "gov" in region:
                    geographic_groups["Government"].append(region)
                else:
                    geographic_groups["US"].append(region)
            elif region.startswith("eu-"):
                geographic_groups["Europe"].append(region)
            elif region.startswith("ap-"):
                geographic_groups["Asia Pacific"].append(region)
            elif region.startswith("ca-"):
                geographic_groups["Canada"].append(region)
            elif region.startswith("sa-"):
                geographic_groups["South America"].append(region)
            elif region.startswith("af-"):
                geographic_groups["Africa"].append(region)
            elif region.startswith("me-") or region.startswith("il-"):
                geographic_groups["Middle East"].append(region)
            elif region.startswith("cn-"):
                geographic_groups["Asia Pacific"].append(region)  # China regions

        # Remove empty groups
        return {k: v for k, v in geographic_groups.items() if v}

    def _categorize_regions_by_service_count(
        self, region_counts: pd.Series
    ) -> Dict[str, List[str]]:
        """Categorize regions by service count tiers."""
        q75 = region_counts.quantile(0.75)
        q50 = region_counts.quantile(0.50)
        q25 = region_counts.quantile(0.25)

        return {
            "tier_1_high": region_counts[region_counts >= q75].index.tolist(),
            "tier_2_medium_high": region_counts[
                (region_counts >= q50) & (region_counts < q75)
            ].index.tolist(),
            "tier_3_medium_low": region_counts[
                (region_counts >= q25) & (region_counts < q50)
            ].index.tolist(),
            "tier_4_low": region_counts[region_counts < q25].index.tolist(),
        }

    def _identify_regional_gaps(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Identify regions with notable service gaps."""
        region_counts = df.groupby("Region Code").size()
        mean_count = region_counts.mean()
        std_count = region_counts.std()

        return {
            "underserved_regions": region_counts[
                region_counts < (mean_count - std_count)
            ].to_dict(),
            "overserved_regions": region_counts[
                region_counts > (mean_count + std_count)
            ].to_dict(),
            "gap_threshold": round(mean_count - std_count, 2),
            "excellence_threshold": round(mean_count + std_count, 2),
        }

    def _calculate_regional_diversity(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate diversity metrics for regional service distribution."""
        import math

        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"

        diversity_metrics = {}
        for region in df["Region Code"].unique():
            region_services = df[df["Region Code"] == region][service_col].tolist()

            # Shannon diversity index
            service_counts = Counter(region_services)
            total_services = len(region_services)

            if total_services > 0:
                # Calculate Shannon diversity: H = -Σ(pi * ln(pi))
                shannon_diversity = -sum(
                    (count / total_services) * math.log(count / total_services)
                    for count in service_counts.values()
                    if count > 0
                )
                diversity_metrics[region] = round(shannon_diversity, 3)

        return diversity_metrics

    def _identify_service_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Identify patterns in service availability."""
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"

        # Co-occurrence analysis
        service_regions = df.groupby(service_col)["Region Code"].apply(set).to_dict()

        # Find services that often appear together
        co_occurrence = {}
        services = list(service_regions.keys())

        for i, service1 in enumerate(services):
            for service2 in services[i + 1 :]:
                overlap = len(
                    service_regions[service1].intersection(service_regions[service2])
                )
                total_regions = len(
                    service_regions[service1].union(service_regions[service2])
                )

                if total_regions > 0:
                    jaccard_similarity = overlap / total_regions
                    if (
                        jaccard_similarity > 0.5
                    ):  # Services appear together in >50% of regions
                        co_occurrence[f"{service1}+{service2}"] = round(
                            jaccard_similarity, 3
                        )

        return {
            "high_co_occurrence_pairs": dict(
                sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)[:10]
            )
        }

    def _categorize_services_by_coverage(
        self, service_coverage: pd.Series, total_regions: int
    ) -> Dict[str, List[str]]:
        """Categorize services by their regional coverage."""
        return {
            "universal_coverage": service_coverage[
                service_coverage == total_regions
            ].index.tolist(),
            "high_coverage": service_coverage[
                service_coverage >= total_regions * 0.8
            ].index.tolist(),
            "medium_coverage": service_coverage[
                (service_coverage >= total_regions * 0.5)
                & (service_coverage < total_regions * 0.8)
            ].index.tolist(),
            "low_coverage": service_coverage[
                service_coverage < total_regions * 0.5
            ].index.tolist(),
        }

    def _interpret_correlation(self, correlation: float) -> str:
        """Interpret correlation coefficient."""
        abs_corr = abs(correlation)
        direction = "positive" if correlation > 0 else "negative"

        if abs_corr >= 0.8:
            strength = "very strong"
        elif abs_corr >= 0.6:
            strength = "strong"
        elif abs_corr >= 0.4:
            strength = "moderate"
        elif abs_corr >= 0.2:
            strength = "weak"
        else:
            strength = "very weak"

        return f"{strength} {direction} correlation"

    def _find_geographic_leaders(
        self, geographic_analysis: Dict[str, Any]
    ) -> Dict[str, str]:
        """Find leading regions in each geographic area."""
        leaders = {}
        for geo_region, stats in geographic_analysis.items():
            if stats["regions"]:
                # Find region with highest service density
                leaders[geo_region] = max(
                    stats["regions"], key=lambda x: stats["avg_services_per_region"]
                )
        return leaders

    def _identify_geographic_gaps(
        self, service_presence: Dict[str, Dict], region_groups: Dict[str, List]
    ) -> Dict[str, List[str]]:
        """Identify services with poor geographic coverage."""
        gaps = {}
        for geo_region in region_groups:
            missing_services = []
            for service, presence in service_presence.items():
                if presence.get(geo_region, 0) == 0:
                    missing_services.append(service)
            if missing_services:
                gaps[geo_region] = missing_services[:10]  # Top 10 missing
        return gaps

    def _calculate_pattern_statistics(
        self, pattern_coverage: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Calculate statistics across service patterns."""
        if not pattern_coverage:
            return {}

        avg_availability = [
            stats["avg_regional_availability"] for stats in pattern_coverage.values()
        ]
        service_counts = [stats["service_count"] for stats in pattern_coverage.values()]

        return {
            "most_available_pattern": max(
                pattern_coverage.items(),
                key=lambda x: x[1]["avg_regional_availability"],
            )[0],
            "largest_pattern": max(
                pattern_coverage.items(), key=lambda x: x[1]["service_count"]
            )[0],
            "pattern_availability_variance": round(
                stats.stdev(avg_availability) if len(avg_availability) > 1 else 0, 3
            ),
            "total_categorized_services": sum(service_counts),
        }

    def _calculate_data_completeness(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate data completeness metrics."""
        return {
            "overall_completeness": round(
                (1 - df.isnull().sum().sum() / df.size) * 100, 2
            ),
            "field_completeness": {
                col: round((1 - df[col].isnull().sum() / len(df)) * 100, 2)
                for col in df.columns
            },
        }

    def _calculate_data_consistency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate data consistency metrics."""
        return {
            "unique_region_codes": df["Region Code"].nunique(),
            "unique_services": (
                df["Service Code"].nunique()
                if "Service Code" in df.columns
                else df["Service Name"].nunique()
            ),
            "duplicate_records": len(df) - len(df.drop_duplicates()),
            "format_consistency": self._check_format_consistency(df),
        }

    def _calculate_coverage_metrics(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate coverage metrics."""
        total_regions = df["Region Code"].nunique()
        service_col = "Service Code" if "Service Code" in df.columns else "Service Name"
        total_services = df[service_col].nunique()

        return {
            "regional_coverage": round(
                (total_regions / 40) * 100, 2
            ),  # Assume 40 total AWS regions
            "service_coverage": round(
                (total_services / 400) * 100, 2
            ),  # Assume 400 total AWS services
            "mapping_density": round(
                (len(df) / (total_regions * total_services)) * 100, 2
            ),
        }

    def _check_format_consistency(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Check format consistency of key fields."""
        return {
            "region_code_format": all(
                re.match(r"^[a-z0-9-]+$", str(code))
                for code in df["Region Code"].dropna()
            ),
            "service_code_format": all(
                re.match(r"^[a-z0-9-]+$", str(code))
                for code in df.get("Service Code", pd.Series()).dropna()
            ),
        }

    def _generate_performance_recommendations(
        self, efficiency: Dict, quality: Dict
    ) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []

        if efficiency["cache_efficiency"] < 80:
            recommendations.append(
                "Consider increasing cache retention to improve efficiency"
            )

        if efficiency["error_rate"] > 5:
            recommendations.append(
                "High error rate detected - review error handling and retry logic"
            )

        if quality["completeness"]["overall_completeness"] < 95:
            recommendations.append(
                "Data completeness below 95% - review data collection processes"
            )

        if not recommendations:
            recommendations.append("Performance metrics are within acceptable ranges")

        return recommendations
