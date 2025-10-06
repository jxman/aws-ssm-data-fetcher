"""Data transformation processor for AWS SSM analysis results."""

import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from .base import (
    BaseProcessor,
    ProcessingContext,
    ProcessingError,
    ProcessingValidationError,
)

# import pandas as pd  # Disabled - will handle pandas-dependent functionality separately


class DataTransformationError(ProcessingError):
    """Exception raised during data transformation operations."""

    pass


class DataTransformer(BaseProcessor):
    """Processor for transforming AWS service-region data into various formats."""

    def __init__(self, context: ProcessingContext):
        """Initialize data transformer processor.

        Args:
            context: Processing context with config and cache
        """
        super().__init__(context)
        self.total_regions = 38  # Known AWS region count for coverage calculations

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data structure.

        Args:
            input_data: Data to validate (expects list of dicts with region/service info)

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

        # Validate first few items to check structure
        sample_size = min(5, len(input_data))
        for i, item in enumerate(input_data[:sample_size]):
            if not isinstance(item, dict):
                raise ProcessingValidationError(f"Item {i} must be a dictionary")

            # Check for required fields
            required_fields = ["Region Code", "Service Code", "Service Name"]
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                raise ProcessingValidationError(
                    f"Item {i} missing required fields: {missing_fields}"
                )

        return True

    def process(
        self,
        input_data: List[Dict],
        transformation_type: str = "service_matrix",
        **kwargs,
    ) -> Any:
        """Transform service-region data into specified format.

        Args:
            input_data: List of service-region mapping dictionaries
            transformation_type: Type of transformation to apply
            **kwargs: Additional transformation parameters

        Returns:
            Transformed data (format depends on transformation_type)

        Raises:
            ProcessingError: If transformation fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        self.logger.info(
            f"Applying {transformation_type} transformation to {len(input_data)} records"
        )

        transformation_methods = {
            "service_matrix": self.generate_service_matrix,
            "region_summary": self.generate_region_summary,
            "service_summary": self.generate_service_summary,
            "statistics": self.generate_statistics,
            "pivot_table": self.generate_pivot_table,
            "coverage_analysis": self.generate_coverage_analysis,
        }

        if transformation_type not in transformation_methods:
            raise ProcessingError(f"Unknown transformation type: {transformation_type}")

        try:
            method = transformation_methods[transformation_type]
            result = method(input_data, **kwargs)

            self.logger.info(
                f"Successfully applied {transformation_type} transformation"
            )
            return result

        except Exception as e:
            self.logger.error(
                f"Transformation {transformation_type} failed: {e}", exc_info=True
            )
            raise DataTransformationError(
                f"Failed to apply {transformation_type} transformation: {e}"
            ) from e

    def generate_service_matrix(self, data: List[Dict], **kwargs) -> List[Dict]:
        """Generate service matrix showing which services are available in which regions.

        Args:
            data: Service-region mapping data
            **kwargs: Additional parameters

        Returns:
            List of dictionaries with services as rows and regions as columns
        """
        # Get unique services and regions
        services = sorted(set(item["Service Name"] for item in data))
        regions = sorted(set(item["Region Code"] for item in data))

        self.logger.info(
            f"Creating service matrix: {len(services)} services × {len(regions)} regions"
        )

        # Create lookup for service-region combinations
        service_regions_lookup = {}
        for item in data:
            service = item["Service Name"]
            region = item["Region Code"]
            if service not in service_regions_lookup:
                service_regions_lookup[service] = set()
            service_regions_lookup[service].add(region)

        matrix_data = []
        for service in services:
            row = {"Service": service}
            service_regions = service_regions_lookup.get(service, set())

            for region in regions:
                row[region] = "✓" if region in service_regions else "✗"

            matrix_data.append(row)

        return matrix_data

    def generate_region_summary(
        self,
        data: List[Dict],
        region_names: Dict[str, str] = None,
        rss_data: Dict[str, Dict] = None,
        az_data: Dict[str, int] = None,
        all_services: List[str] = None,
        **kwargs,
    ) -> List[Dict]:
        """Generate region summary with service counts and metadata.

        Args:
            data: Service-region mapping data
            region_names: Mapping of region codes to names
            rss_data: RSS feed data for regions
            az_data: Availability zone data
            all_services: Complete list of services for coverage calculation
            **kwargs: Additional parameters

        Returns:
            List of dictionaries with region summary information
        """
        region_names = region_names or {}
        rss_data = rss_data or {}
        az_data = az_data or {}

        # Get unique regions
        unique_regions = sorted(set(item["Region Code"] for item in data))

        self.logger.info(f"Generating region summary for {len(unique_regions)} regions")

        summary_data = []
        for region_code in unique_regions:
            region_data = [item for item in data if item["Region Code"] == region_code]
            service_count = len(region_data)

            # Get RSS metadata for this region
            rss_region_data = rss_data.get(region_code, {})
            launch_date = rss_region_data.get("launch_date", "N/A")
            launch_date_source = (
                "AWS RSS Feed" if launch_date != "N/A" else "Not Available"
            )
            announcement_url = rss_region_data.get("announcement_url", "N/A")

            # Get availability zone count
            az_count = az_data.get(region_code, "N/A")

            # Calculate coverage percentage if total services known
            coverage_pct = None
            if all_services:
                coverage_pct = round((service_count / len(all_services)) * 100, 1)

            summary_row = {
                "Region Code": region_code,
                "Region Name": region_names.get(region_code, region_code),
                "Launch Date": launch_date,
                "Launch Date Source": launch_date_source,
                "Announcement URL": announcement_url,
                "Availability Zones": az_count if az_count != "N/A" else "N/A",
                "Service Count": service_count,
            }

            if coverage_pct is not None:
                summary_row["Coverage %"] = coverage_pct

            summary_data.append(summary_row)

        return summary_data

    def generate_service_summary(
        self,
        data: List[Dict],
        all_services: List[str] = None,
        service_names: Dict[str, str] = None,
        **kwargs,
    ) -> List[Dict]:
        """Generate service summary with region counts and coverage.

        Args:
            data: Service-region mapping data
            all_services: Complete list of services to analyze
            service_names: Mapping of service codes to names
            **kwargs: Additional parameters

        Returns:
            List of dictionaries with service summary information
        """
        service_names = service_names or {}

        self.logger.info(f"Generating service summary for discovered services")

        summary_data = []

        if all_services:
            self.logger.info(
                f"Analyzing {len(all_services)} total services for regional availability"
            )

            for service_code in sorted(all_services):
                service_name = service_names.get(service_code, service_code)

                # Count regions where this service appears
                service_data = [
                    item for item in data if item["Service Code"] == service_code
                ]
                region_count = len(service_data)
                coverage_pct = round((region_count / self.total_regions) * 100, 1)

                summary_data.append(
                    {
                        "Service Code": service_code,
                        "Service Name": service_name,
                        "Region Count": region_count,
                        "Coverage %": coverage_pct
                        / 100,  # Store as decimal for Excel formatting
                    }
                )
        else:
            # Fallback: analyze only services present in data
            unique_services = sorted(set(item["Service Name"] for item in data))
            for service_name in unique_services:
                service_data = [
                    item for item in data if item["Service Name"] == service_name
                ]
                region_count = len(service_data)
                coverage_pct = round((region_count / self.total_regions) * 100, 1)

                # Get service code (take first occurrence)
                service_code = service_data[0]["Service Code"]

                summary_data.append(
                    {
                        "Service Code": service_code,
                        "Service Name": service_name,
                        "Region Count": region_count,
                        "Coverage %": coverage_pct / 100,
                    }
                )

        return summary_data

    def generate_statistics(
        self, data: List[Dict], all_services: List[str] = None, **kwargs
    ) -> List[Dict]:
        """Generate summary statistics about the data.

        Args:
            data: Service-region mapping data
            all_services: Complete list of services for total count
            **kwargs: Additional parameters

        Returns:
            List of dictionaries with statistics information
        """
        # Use total discovered services count if available
        unique_services = set(item["Service Name"] for item in data)
        total_services = len(all_services) if all_services else len(unique_services)
        unique_regions = set(item["Region Code"] for item in data)

        self.logger.info(f"Generating statistics for {len(data)} data points")

        # Calculate various statistics
        region_counts = {}
        for item in data:
            region = item["Region Code"]
            region_counts[region] = region_counts.get(region, 0) + 1

        service_counts = {}
        for item in data:
            service = item["Service Name"]
            service_counts[service] = service_counts.get(service, 0) + 1

        # Calculate statistics from counts
        region_count_values = list(region_counts.values())
        service_count_values = list(service_counts.values())

        import statistics

        stats = [
            ["Generator", "AWS SSM Data Fetcher - Modular Architecture v3.0"],
            ["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["Summary Statistics", ""],
            ["Total Regions", len(unique_regions)],
            ["Total Services", total_services],
            ["Total Combinations", len(data)],
            ["", ""],
            ["Regional Service Distribution", ""],
            [
                "Avg Services per Region",
                (
                    round(statistics.mean(region_count_values), 1)
                    if region_count_values
                    else 0
                ),
            ],
            [
                "Max Services (Region)",
                max(region_count_values) if region_count_values else 0,
            ],
            [
                "Min Services (Region)",
                min(region_count_values) if region_count_values else 0,
            ],
            [
                "Std Dev Services per Region",
                (
                    round(statistics.stdev(region_count_values), 1)
                    if len(region_count_values) > 1
                    else 0
                ),
            ],
            ["", ""],
            ["Service Distribution", ""],
            [
                "Avg Regions per Service",
                (
                    round(statistics.mean(service_count_values), 1)
                    if service_count_values
                    else 0
                ),
            ],
            [
                "Max Regions (Service)",
                max(service_count_values) if service_count_values else 0,
            ],
            [
                "Min Regions (Service)",
                min(service_count_values) if service_count_values else 0,
            ],
            [
                "Std Dev Regions per Service",
                (
                    round(statistics.stdev(service_count_values), 1)
                    if len(service_count_values) > 1
                    else 0
                ),
            ],
        ]

        stats_list = [{"Metric": stat[0], "Value": stat[1]} for stat in stats]
        return stats_list

    def generate_pivot_table(
        self,
        data: List[Dict],
        rows: str = "Region Code",
        columns: str = "Service Code",
        values: str = "Service Name",
        aggfunc: str = "count",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate pivot table from the data.

        Args:
            data: Service-region mapping data
            rows: Column to use as rows
            columns: Column to use as columns
            values: Column to use as values
            aggfunc: Aggregation function
            **kwargs: Additional parameters

        Returns:
            Dictionary with pivot table structure
        """
        self.logger.info(
            f"Creating pivot table: rows={rows}, columns={columns}, values={values}"
        )

        try:
            # Simple pivot table implementation
            pivot_data = {}
            for item in data:
                row_key = item.get(rows)
                col_key = item.get(columns)
                if row_key not in pivot_data:
                    pivot_data[row_key] = {}
                if col_key not in pivot_data[row_key]:
                    pivot_data[row_key][col_key] = 0
                pivot_data[row_key][col_key] += 1

            return pivot_data

        except Exception as e:
            raise DataTransformationError(f"Failed to create pivot table: {e}") from e

    def generate_coverage_analysis(
        self, data: List[Dict], all_services: List[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Generate detailed coverage analysis.

        Args:
            data: Service-region mapping data
            all_services: Complete list of services
            **kwargs: Additional parameters

        Returns:
            Dictionary with coverage analysis results
        """
        self.logger.info("Performing detailed coverage analysis")

        # Get unique values
        unique_services = set(item["Service Name"] for item in data)
        unique_regions = set(item["Region Code"] for item in data)
        total_services = len(all_services) if all_services else len(unique_services)
        total_regions = len(unique_regions)

        # Regional analysis
        region_coverage = {}
        for region in unique_regions:
            region_data = [item for item in data if item["Region Code"] == region]
            service_count = len(region_data)
            coverage_pct = (service_count / total_services) * 100

            region_coverage[region] = {
                "service_count": service_count,
                "coverage_percentage": round(coverage_pct, 2),
            }

        # Service availability analysis
        service_availability = {}
        for service in unique_services:
            service_data = [item for item in data if item["Service Name"] == service]
            region_count = len(service_data)
            availability_pct = (region_count / total_regions) * 100

            service_availability[service] = {
                "region_count": region_count,
                "availability_percentage": round(availability_pct, 2),
            }

        # Overall statistics
        coverage_values = [
            info["coverage_percentage"] for info in region_coverage.values()
        ]
        availability_values = [
            info["availability_percentage"] for info in service_availability.values()
        ]

        analysis = {
            "overview": {
                "total_regions": total_regions,
                "total_services": total_services,
                "total_mappings": len(data),
                "avg_services_per_region": round(len(data) / total_regions, 1),
                "avg_regions_per_service": round(len(data) / len(unique_services), 1),
            },
            "regional_coverage": {
                "by_region": region_coverage,
                "statistics": {
                    "mean_coverage": round(
                        sum(coverage_values) / len(coverage_values), 2
                    ),
                    "max_coverage": max(coverage_values),
                    "min_coverage": min(coverage_values),
                    "std_coverage": (
                        round(statistics.stdev(coverage_values), 2)
                        if len(coverage_values) > 1
                        else 0
                    ),
                },
            },
            "service_availability": {
                "by_service": service_availability,
                "statistics": {
                    "mean_availability": round(
                        sum(availability_values) / len(availability_values), 2
                    ),
                    "max_availability": max(availability_values),
                    "min_availability": min(availability_values),
                    "std_availability": (
                        round(statistics.stdev(availability_values), 2)
                        if len(availability_values) > 1
                        else 0
                    ),
                },
            },
        }

        return analysis

    def transform_to_hierarchical(
        self, data: List[Dict], group_by: str = "Region Code"
    ) -> Dict[str, List[Dict]]:
        """Transform flat data into hierarchical structure.

        Args:
            data: Flat service-region mapping data
            group_by: Field to group by

        Returns:
            Dictionary with hierarchical structure
        """
        self.logger.info(f"Creating hierarchical structure grouped by {group_by}")

        hierarchical_data = {}
        unique_groups = set(item[group_by] for item in data)
        for group_value in unique_groups:
            group_data = [item for item in data if item[group_by] == group_value]
            hierarchical_data[group_value] = group_data

        return hierarchical_data

    def apply_filters(self, data: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply filters to the data.

        Args:
            data: Service-region mapping data
            filters: Dictionary of field->value filters

        Returns:
            Filtered data
        """
        self.logger.info(f"Applying {len(filters)} filters to data")

        filtered_data = data.copy()

        for field, value in filters.items():
            # Check if field exists in any data item
            if not any(field in item for item in filtered_data):
                self.logger.warning(f"Filter field '{field}' not found in data")
                continue

            if isinstance(value, list):
                filtered_data = [
                    item for item in filtered_data if item.get(field) in value
                ]
            else:
                filtered_data = [
                    item for item in filtered_data if item.get(field) == value
                ]

        self.logger.info(f"Filtered data: {len(data)} -> {len(filtered_data)} records")

        return filtered_data
