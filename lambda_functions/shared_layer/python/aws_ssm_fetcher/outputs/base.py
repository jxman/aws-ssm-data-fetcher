"""Base classes for output generation in AWS SSM Data Fetcher."""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


class OutputError(Exception):
    """Custom exception for output generation errors."""

    pass


@dataclass
class OutputContext:
    """Context information for output generation."""

    output_dir: str = "output"
    filename: Optional[str] = None
    region_names: Optional[Dict[str, str]] = None
    service_names: Optional[Dict[str, str]] = None
    rss_data: Optional[Dict[str, Dict]] = None
    all_services: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default metadata if not provided."""
        if self.metadata is None:
            self.metadata = {
                "generated_at": datetime.now().isoformat(),
                "source": "AWS SSM Parameter Store",
            }


class BaseOutputGenerator(ABC):
    """Abstract base class for output generators."""

    def __init__(self, context: OutputContext):
        """Initialize output generator.

        Args:
            context: Output context with configuration and metadata
        """
        self.context = context
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._ensure_output_directory()

    def _ensure_output_directory(self):
        """Ensure output directory exists."""
        if not os.path.exists(self.context.output_dir):
            os.makedirs(self.context.output_dir)
            self.logger.info(f"Created output directory: {self.context.output_dir}")

    def _get_filepath(self, filename: str) -> str:
        """Get full filepath for output file.

        Args:
            filename: Base filename

        Returns:
            Full filepath including output directory
        """
        if filename.startswith(self.context.output_dir):
            return filename
        return os.path.join(self.context.output_dir, filename)

    def _get_data_statistics(self, data: List[Dict]) -> Dict[str, int]:
        """Get basic statistics about the data.

        Args:
            data: List of data dictionaries

        Returns:
            Dictionary with data statistics
        """
        if not data:
            return {"regions": 0, "services": 0, "combinations": 0}

        regions = set()
        services = set()

        for item in data:
            if "Region Code" in item:
                regions.add(item["Region Code"])
            if "Service Code" in item or "Service Name" in item:
                service = item.get("Service Code") or item.get("Service Name")
                if service:
                    services.add(service)

        return {
            "regions": len(regions),
            "services": len(services),
            "combinations": len(data),
        }

    def _log_output_summary(self, filepath: str, stats: Dict[str, int]):
        """Log summary of generated output.

        Args:
            filepath: Path to generated file
            stats: Data statistics
        """
        self.logger.info(f"Output file saved: {filepath}")
        self.logger.info(f"  - Regions: {stats['regions']}")
        self.logger.info(f"  - Services: {stats['services']}")
        self.logger.info(f"  - Combinations: {stats['combinations']}")

    @abstractmethod
    def generate(self, data: List[Dict]) -> str:
        """Generate output file from data.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to generated output file

        Raises:
            OutputError: If output generation fails
        """
        pass

    @abstractmethod
    def get_default_filename(self) -> str:
        """Get default filename for this output format.

        Returns:
            Default filename with appropriate extension
        """
        pass

    def validate_data(self, data: List[Dict]) -> bool:
        """Validate input data for output generation.

        Args:
            data: Data to validate

        Returns:
            True if data is valid

        Raises:
            OutputError: If data validation fails
        """
        if not isinstance(data, list):
            raise OutputError("Data must be a list of dictionaries")

        if not data:
            self.logger.warning("Data list is empty")
            return True

        # Validate first item has required keys
        first_item = data[0]
        required_keys = ["Region Code", "Service Code"]
        missing_keys = [key for key in required_keys if key not in first_item]

        if missing_keys:
            # Check for alternative key names
            if "Service Name" not in first_item:
                raise OutputError(
                    f"Data items must contain keys: {required_keys} or 'Service Name'"
                )

        return True
