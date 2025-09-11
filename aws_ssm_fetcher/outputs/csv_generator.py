"""CSV output generator for AWS SSM Data Fetcher."""

import csv
from typing import Dict, List

import pandas as pd

from .base import BaseOutputGenerator, OutputContext, OutputError


class CSVGenerator(BaseOutputGenerator):
    """Generate CSV output files."""

    def get_default_filename(self) -> str:
        """Get default filename for CSV output.

        Returns:
            Default CSV filename
        """
        return "aws_regions_services.csv"

    def generate(self, data: List[Dict]) -> str:
        """Generate CSV file from regional service data.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to generated CSV file

        Raises:
            OutputError: If CSV generation fails
        """
        self.validate_data(data)

        try:
            filename = self.context.filename or self.get_default_filename()
            filepath = self._get_filepath(filename)

            self.logger.info(f"Generating CSV output: {filepath}")

            # Convert to DataFrame and save as CSV
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding="utf-8")

            # Log summary
            stats = self._get_data_statistics(data)
            self._log_output_summary(filepath, stats)

            return filepath

        except Exception as e:
            raise OutputError(f"CSV generation failed: {e}") from e


class MultiCSVGenerator(BaseOutputGenerator):
    """Generate multiple CSV files (one per Excel sheet equivalent)."""

    def get_default_filename(self) -> str:
        """Get default base filename for multi-CSV output.

        Returns:
            Default base CSV filename (will be modified for each sheet)
        """
        return "aws_regions_services"

    def generate(self, data: List[Dict]) -> str:
        """Generate multiple CSV files equivalent to Excel sheets.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to output directory containing generated CSV files

        Raises:
            OutputError: If CSV generation fails
        """
        self.validate_data(data)

        try:
            base_filename = self.context.filename or self.get_default_filename()
            base_filename = base_filename.replace(
                ".csv", ""
            )  # Remove extension if present

            self.logger.info(f"Generating multiple CSV files: {base_filename}_*.csv")

            # Generate data for all sheets
            sheets_data = self._generate_sheets_data(data)

            # Write each sheet as separate CSV
            generated_files = []
            for sheet_name, sheet_df in sheets_data.items():
                # Create filename for this sheet
                safe_sheet_name = sheet_name.lower().replace(" ", "_")
                csv_filename = f"{base_filename}_{safe_sheet_name}.csv"
                csv_filepath = self._get_filepath(csv_filename)

                # Write CSV
                sheet_df.to_csv(csv_filepath, index=False, encoding="utf-8")
                generated_files.append(csv_filepath)

                self.logger.info(
                    f"  - Generated: {csv_filename} ({len(sheet_df)} rows)"
                )

            # Log summary
            stats = self._get_data_statistics(data)
            self.logger.info(
                f"Multi-CSV generation completed: {len(generated_files)} files"
            )
            self._log_output_summary(self.context.output_dir, stats)

            return self.context.output_dir

        except Exception as e:
            raise OutputError(f"Multi-CSV generation failed: {e}") from e

    def _generate_sheets_data(self, data: List[Dict]) -> Dict[str, pd.DataFrame]:
        """Generate data equivalent to Excel sheets.

        Args:
            data: Regional service data

        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        df = pd.DataFrame(data)
        sheets_data = {}

        # Regional Services (raw data)
        sheets_data["Regional Services"] = df.copy()

        # Service Matrix
        sheets_data["Service Matrix"] = self._create_service_matrix(data)

        # Region Summary
        sheets_data["Region Summary"] = self._create_region_summary(data)

        # Service Summary
        sheets_data["Service Summary"] = self._create_service_summary(data)

        # Statistics
        sheets_data["Statistics"] = self._create_statistics(data)

        return sheets_data

    def _create_service_matrix(self, data: List[Dict]) -> pd.DataFrame:
        """Create service availability matrix.

        Args:
            data: Regional service data

        Returns:
            DataFrame with service matrix
        """
        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame({"Service": [], "Note": ["No data available"]})

        # Get unique services and regions
        services = (
            sorted(df["Service Name"].unique()) if "Service Name" in df.columns else []
        )
        regions = (
            sorted(df["Region Code"].unique()) if "Region Code" in df.columns else []
        )

        if not services or not regions:
            return pd.DataFrame({"Service": [], "Note": ["No data available"]})

        # Create matrix
        matrix_data = []
        for service in services:
            row = {"Service": service}
            service_regions = set(
                df[df["Service Name"] == service]["Region Code"].tolist()
            )

            for region in regions:
                # Use 1/0 for CSV instead of ✓/✗ for better compatibility
                row[region] = 1 if region in service_regions else 0

            matrix_data.append(row)

        return pd.DataFrame(matrix_data)

    def _create_region_summary(self, data: List[Dict]) -> pd.DataFrame:
        """Create region summary.

        Args:
            data: Regional service data

        Returns:
            DataFrame with region summary
        """
        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame({"Region": [], "Note": ["No data available"]})

        regions = df["Region Code"].unique() if "Region Code" in df.columns else []
        summary_data = []

        for region in regions:
            region_data = df[df["Region Code"] == region]

            # Get region name from context
            region_name = region
            if self.context.region_names and region in self.context.region_names:
                region_name = self.context.region_names[region]

            # Count services
            service_count = len(region_data)

            # Get launch date from RSS data
            launch_date = "N/A"
            if (
                self.context.rss_data
                and region in self.context.rss_data
                and "launch_date" in self.context.rss_data[region]
            ):
                launch_date = self.context.rss_data[region]["launch_date"]

            summary_data.append(
                {
                    "Region Code": region,
                    "Region Name": region_name,
                    "Service Count": service_count,
                    "Launch Date": launch_date,
                }
            )

        return pd.DataFrame(summary_data)

    def _create_service_summary(self, data: List[Dict]) -> pd.DataFrame:
        """Create service summary.

        Args:
            data: Regional service data

        Returns:
            DataFrame with service summary
        """
        df = pd.DataFrame(data)

        if df.empty or "Service Name" not in df.columns:
            return pd.DataFrame({"Service": [], "Note": ["No data available"]})

        services = df["Service Name"].unique()
        total_regions = (
            df["Region Code"].nunique() if "Region Code" in df.columns else 1
        )
        summary_data = []

        for service in services:
            service_data = df[df["Service Name"] == service]

            # Get service name from context
            display_name = service
            if self.context.service_names and service in self.context.service_names:
                display_name = self.context.service_names[service]

            region_count = (
                service_data["Region Code"].nunique()
                if "Region Code" in service_data.columns
                else 1
            )
            coverage_pct = (region_count / total_regions) if total_regions > 0 else 0

            summary_data.append(
                {
                    "Service Code": service,
                    "Service Name": display_name,
                    "Region Count": region_count,
                    "Coverage Percentage": coverage_pct,  # Use decimal for CSV
                }
            )

        return pd.DataFrame(summary_data).sort_values(
            "Coverage Percentage", ascending=False
        )

    def _create_statistics(self, data: List[Dict]) -> pd.DataFrame:
        """Create statistics summary.

        Args:
            data: Regional service data

        Returns:
            DataFrame with statistics
        """
        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame({"Metric": ["No data"], "Value": ["N/A"]})

        # Calculate statistics
        total_combinations = len(df)
        unique_regions = (
            df["Region Code"].nunique() if "Region Code" in df.columns else 0
        )
        unique_services = (
            df["Service Name"].nunique() if "Service Name" in df.columns else 0
        )

        avg_services_per_region = (
            total_combinations / unique_regions if unique_regions > 0 else 0
        )
        avg_regions_per_service = (
            total_combinations / unique_services if unique_services > 0 else 0
        )

        stats_data = [
            {
                "Metric": "Total Service-Region Combinations",
                "Value": total_combinations,
            },
            {"Metric": "Unique Regions", "Value": unique_regions},
            {"Metric": "Unique Services", "Value": unique_services},
            {
                "Metric": "Average Services per Region",
                "Value": round(avg_services_per_region, 2),
            },
            {
                "Metric": "Average Regions per Service",
                "Value": round(avg_regions_per_service, 2),
            },
            {"Metric": "Data Source", "Value": "AWS SSM Parameter Store"},
            {
                "Metric": "Generated At",
                "Value": self.context.metadata.get("generated_at", "N/A") if self.context.metadata else "N/A",
            },
        ]

        return pd.DataFrame(stats_data)


class TSVGenerator(CSVGenerator):
    """Generate Tab-Separated Values (TSV) output."""

    def get_default_filename(self) -> str:
        """Get default filename for TSV output.

        Returns:
            Default TSV filename
        """
        return "aws_regions_services.tsv"

    def generate(self, data: List[Dict]) -> str:
        """Generate TSV file from regional service data.

        Args:
            data: List of dictionaries containing regional service data

        Returns:
            Path to generated TSV file

        Raises:
            OutputError: If TSV generation fails
        """
        self.validate_data(data)

        try:
            filename = self.context.filename or self.get_default_filename()
            filepath = self._get_filepath(filename)

            self.logger.info(f"Generating TSV output: {filepath}")

            # Convert to DataFrame and save as TSV (tab-separated)
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding="utf-8", sep="\t")

            # Log summary
            stats = self._get_data_statistics(data)
            self._log_output_summary(filepath, stats)

            return filepath

        except Exception as e:
            raise OutputError(f"TSV generation failed: {e}") from e
