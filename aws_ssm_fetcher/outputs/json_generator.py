"""JSON output generator for AWS SSM Data Fetcher."""

import json
from datetime import datetime
from typing import Any, Dict, List

import pytz

from .base import BaseOutputGenerator, OutputContext, OutputError


class JSONGenerator(BaseOutputGenerator):
    """Generate comprehensive JSON output with metadata."""

    def _get_est_timestamp(self) -> str:
        """Get current timestamp in EST timezone with timezone code.

        Returns:
            Formatted timestamp string in EST with timezone code
        """
        # Get current UTC time
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        # Convert to EST (US/Eastern handles EDT/EST automatically)
        eastern = pytz.timezone("US/Eastern")
        est_time = utc_now.astimezone(eastern)

        # Format with timezone abbreviation (EST/EDT)
        return est_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _get_est_isoformat(self) -> str:
        """Get current timestamp in EST timezone in ISO format.

        Returns:
            ISO formatted timestamp string in EST
        """
        # Get current UTC time
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        # Convert to EST (US/Eastern handles EDT/EST automatically)
        eastern = pytz.timezone("US/Eastern")
        est_time = utc_now.astimezone(eastern)

        # Return ISO format
        return est_time.isoformat()

    def get_default_filename(self) -> str:
        """Get default filename for JSON output.

        Returns:
            Default JSON filename
        """
        return "aws_regions_services.json"

    def generate(self, data: List[Dict]) -> str:
        """Generate JSON file with comprehensive structure and metadata.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to generated JSON file

        Raises:
            OutputError: If JSON generation fails
        """
        self.validate_data(data)

        try:
            filename = self.context.filename or self.get_default_filename()
            filepath = self._get_filepath(filename)

            self.logger.info(f"Generating JSON output: {filepath}")

            # Create comprehensive JSON structure
            json_data = self._create_json_structure(data)

            # Write JSON file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            # Log summary
            stats = self._get_data_statistics(data)
            self._log_output_summary(filepath, stats)

            return filepath

        except Exception as e:
            raise OutputError(f"JSON generation failed: {e}") from e

    def _create_json_structure(self, data: List[Dict]) -> Dict[str, Any]:
        """Create comprehensive JSON structure with metadata.

        Args:
            data: Regional service data

        Returns:
            Complete JSON structure
        """
        stats = self._get_data_statistics(data)

        # Create enhanced metadata with EST timezone
        base_metadata: Dict[str, Any] = self.context.metadata or {}

        # Get current EST timestamp
        est_timestamp = self._get_est_timestamp()
        est_iso = self._get_est_isoformat()

        metadata: Dict[str, Any] = {
            "generated_at": est_iso,
            "generated_at_readable": est_timestamp,
            "timezone": "US/Eastern",
            "total_combinations": stats["combinations"],
            "unique_regions": stats["regions"],
            "unique_services": stats["services"],
            "format_version": "2.0",
        }

        # Add base metadata (but preserve our EST timestamps)
        for key, value in base_metadata.items():
            if key not in metadata:
                metadata[key] = value

        # Ensure execution_date is also in EST format if present
        if "execution_date" not in metadata:
            utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
            eastern = pytz.timezone("US/Eastern")
            est_time = utc_now.astimezone(eastern)
            metadata["execution_date"] = est_time.strftime("%Y-%m-%d")

        # Add additional metadata if available
        if self.context.region_names:
            metadata["region_names_included"] = True
            metadata["total_region_names"] = len(self.context.region_names)

        if self.context.service_names:
            metadata["service_names_included"] = True
            metadata["total_service_names"] = len(self.context.service_names)

        if self.context.rss_data:
            metadata["rss_data_included"] = True
            metadata["regions_with_launch_dates"] = len(self.context.rss_data)

        # Create main JSON structure
        json_structure = {
            "metadata": metadata,
            "data": {
                "regional_services": data,
                "summary": {
                    "regions": stats["regions"],
                    "services": stats["services"],
                    "total_combinations": stats["combinations"],
                },
            },
        }

        # Add enrichment data if available
        if (
            self.context.region_names
            or self.context.service_names
            or self.context.rss_data
        ):
            json_structure["enrichment"] = {}

            if self.context.region_names:
                json_structure["enrichment"]["region_names"] = self.context.region_names

            if self.context.service_names:
                json_structure["enrichment"][
                    "service_names"
                ] = self.context.service_names

            if self.context.rss_data:
                json_structure["enrichment"]["rss_data"] = self.context.rss_data

        # Add analysis if all_services is provided
        if self.context.all_services:
            json_structure["analysis"] = self._generate_analysis(data)

        return json_structure

    def _generate_analysis(self, data: List[Dict]) -> Dict[str, Any]:
        """Generate analytical data for JSON output.

        Args:
            data: Regional service data

        Returns:
            Analysis dictionary
        """
        if not data:
            return {"note": "No data available for analysis"}

        # Calculate service coverage by region
        region_coverage: Dict[str, List[str]] = {}
        service_coverage: Dict[str, List[str]] = {}

        for item in data:
            region = item.get("Region Code")
            service = item.get("Service Name") or item.get("Service Code")

            if region:
                if region not in region_coverage:
                    region_coverage[region] = []
                if service:
                    region_coverage[region].append(service)

            if service:
                if service not in service_coverage:
                    service_coverage[service] = []
                if region:
                    service_coverage[service].append(region)

        # Calculate statistics
        total_services = (
            len(self.context.all_services)
            if self.context.all_services
            else len(service_coverage)
        )

        analysis = {
            "service_coverage_by_region": {
                region: {
                    "services": list(set(services)),
                    "service_count": len(set(services)),
                    "coverage_percentage": (
                        len(set(services)) / total_services if total_services > 0 else 0
                    ),
                }
                for region, services in region_coverage.items()
            },
            "regional_coverage_by_service": {
                service: {
                    "regions": list(set(regions)),
                    "region_count": len(set(regions)),
                    "coverage_percentage": (
                        len(set(regions)) / len(region_coverage)
                        if region_coverage
                        else 0
                    ),
                }
                for service, regions in service_coverage.items()
            },
            "top_regions_by_service_count": sorted(
                [
                    (region, len(set(services)))
                    for region, services in region_coverage.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:10],
            "top_services_by_region_count": sorted(
                [
                    (service, len(set(regions)))
                    for service, regions in service_coverage.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        }

        return analysis


class CompactJSONGenerator(JSONGenerator):
    """Generate compact JSON output without indentation."""

    def get_default_filename(self) -> str:
        """Get default filename for compact JSON output.

        Returns:
            Default compact JSON filename
        """
        return "aws_regions_services_compact.json"

    def generate(self, data: List[Dict]) -> str:
        """Generate compact JSON file without indentation.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to generated compact JSON file

        Raises:
            OutputError: If JSON generation fails
        """
        self.validate_data(data)

        try:
            filename = self.context.filename or self.get_default_filename()
            filepath = self._get_filepath(filename)

            self.logger.info(f"Generating compact JSON output: {filepath}")

            # Create JSON structure
            json_data = self._create_json_structure(data)

            # Write compact JSON file (no indentation)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(json_data, f, separators=(",", ":"), ensure_ascii=False)

            # Log summary
            stats = self._get_data_statistics(data)
            self._log_output_summary(filepath, stats)

            return filepath

        except Exception as e:
            raise OutputError(f"Compact JSON generation failed: {e}") from e
