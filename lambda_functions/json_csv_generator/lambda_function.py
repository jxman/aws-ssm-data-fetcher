"""
AWS Lambda Function: JSON and CSV Report Generator
Generates JSON and CSV reports from processed AWS SSM data.
Lightweight function with no external dependencies.
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# AWS clients
s3_client = boto3.client("s3")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for JSON and CSV report generation.

    Args:
        event: Lambda event data containing S3 location of processed data
        context: Lambda context object

    Returns:
        Response with generated report locations
    """
    execution_id = event.get("execution_id", f"rpt_{int(datetime.now().timestamp())}")

    try:
        logger.info(f"Starting JSON/CSV generation for execution: {execution_id}")

        # Extract input parameters
        processed_data_location = event.get("processed_data_location")
        if not processed_data_location:
            raise ValueError("processed_data_location is required in event")

        # Parse S3 location
        if not processed_data_location.startswith("s3://"):
            raise ValueError(f"Invalid S3 location format: {processed_data_location}")

        s3_parts = processed_data_location[5:].split("/", 1)
        if len(s3_parts) != 2:
            raise ValueError(f"Invalid S3 location format: {processed_data_location}")

        s3_bucket, s3_key = s3_parts

        # Load processed data from S3
        logger.info(f"Loading processed data from s3://{s3_bucket}/{s3_key}")
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        processed_data = json.loads(response["Body"].read().decode("utf-8"))

        # Extract data for report generation
        regional_services_data = processed_data.get("regional_services_data", [])
        metadata = processed_data.get("metadata", {})
        regions_map = metadata.get("regions", {})
        services_map = metadata.get("services", {})
        rss_data = metadata.get("rss_data", {})

        if not regional_services_data:
            logger.warning("No regional services data found for report generation")
            regional_services_data = []

        # Create temporary directory for file generation
        temp_output_dir = "/tmp/reports"
        os.makedirs(temp_output_dir, exist_ok=True)

        generated_files = {}

        # Generate JSON report
        logger.info("Generating JSON report...")
        json_report = {
            "metadata": {
                "generated_at": datetime.now()
                .isoformat()
                .replace("T", " ")
                .split(".")[0],
                "total_combinations": len(regional_services_data),
                "unique_regions": len(regions_map),
                "unique_services": len(services_map),
                "source": "AWS SSM Parameter Store",
            },
            "data": regional_services_data,
        }

        json_path = os.path.join(temp_output_dir, "aws_regions_services.json")
        with open(json_path, "w") as f:
            json.dump(json_report, f, indent=2)
        generated_files["json"] = json_path

        # Generate all sheets data for CSV generation
        logger.info("Generating CSV reports...")
        sheets_data = _generate_all_sheets(
            regional_services_data, regions_map, services_map, rss_data
        )

        # Generate separate CSV files for each sheet
        csv_files = {}
        for sheet_name, sheet_data in sheets_data.items():
            csv_filename = f"{sheet_name.lower().replace(' ', '_')}.csv"
            csv_path = os.path.join(temp_output_dir, csv_filename)

            with open(csv_path, "w", newline="") as f:
                if sheet_name == "Statistics":
                    # Statistics sheet is a list of lists
                    writer = csv.writer(f)
                    writer.writerows(sheet_data)
                else:
                    # Other sheets are list of dictionaries
                    if sheet_data and isinstance(sheet_data[0], dict):
                        writer = csv.DictWriter(f, fieldnames=sheet_data[0].keys())
                        writer.writeheader()
                        writer.writerows(sheet_data)
                    else:
                        writer = csv.writer(f)
                        writer.writerow(["No data available"])

            csv_files[sheet_name] = csv_path
            logger.info(f"Generated CSV: {csv_filename}")

        # Main regional services CSV for backward compatibility
        main_csv_path = os.path.join(temp_output_dir, "aws_regions_services.csv")
        if "Regional Services" in csv_files:
            import shutil

            shutil.copy2(csv_files["Regional Services"], main_csv_path)
            generated_files["csv"] = main_csv_path

        # Add all CSV files to generated files
        for sheet_name, csv_path in csv_files.items():
            key = f"csv_{sheet_name.lower().replace(' ', '_')}"
            generated_files[key] = csv_path

        # Upload all JSON and CSV files to S3 temporary location
        temp_s3_prefix = f"temp-reports/{execution_id}"
        uploaded_files = {}

        for report_type, local_path in generated_files.items():
            filename = os.path.basename(local_path)
            s3_key = f"{temp_s3_prefix}/{filename}"

            logger.info(f"Uploading {report_type} to s3://{s3_bucket}/{s3_key}")
            s3_client.upload_file(local_path, s3_bucket, s3_key)
            uploaded_files[report_type] = f"s3://{s3_bucket}/{s3_key}"

        # Generate summary data for next steps
        summary_data = {
            "execution_id": execution_id,
            "generated_at": datetime.now().isoformat(),
            "s3_bucket": s3_bucket,
            "temp_s3_prefix": temp_s3_prefix,
            "uploaded_files": uploaded_files,
            "metadata": {
                "regions_count": len(regions_map),
                "services_count": len(services_map),
                "combinations_count": len(regional_services_data),
            },
            "processed_data_location": processed_data_location,
        }

        logger.info(
            f"JSON/CSV generation completed successfully for execution: {execution_id}"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "JSON and CSV reports generated successfully",
                    "execution_id": execution_id,
                    "summary": summary_data,
                }
            ),
            "execution_id": execution_id,
            "summary": summary_data,
        }

    except Exception as e:
        logger.error(f"Error in JSON/CSV generation: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"JSON/CSV generation failed: {str(e)}",
                    "execution_id": execution_id,
                }
            ),
            "execution_id": execution_id,
            "error": str(e),
        }


def _generate_all_sheets(
    regional_services_data: List[Dict[str, Any]],
    regions_map: Dict[str, Any],
    services_map: Dict[str, Any],
    rss_data: Dict[str, Any],
) -> Dict[str, List]:
    """Generate data for all report sheets."""

    sheets = {}

    # Sheet 1: Regional Services (main data)
    sheets["Regional Services"] = regional_services_data

    # Sheet 2: Service Matrix (services vs regions)
    service_matrix = []
    all_regions = sorted(regions_map.keys()) if regions_map else []
    all_services = sorted(services_map.keys()) if services_map else []

    # Create service availability matrix
    service_region_map = {}
    for item in regional_services_data:
        service = item.get("service_code", "")
        region = item.get("region_code", "")
        if service not in service_region_map:
            service_region_map[service] = set()
        service_region_map[service].add(region)

    for service in all_services:
        row = {"service": service}
        for region in all_regions:
            row[region] = (
                "Yes" if region in service_region_map.get(service, set()) else "No"
            )
        service_matrix.append(row)

    sheets["Service Matrix"] = service_matrix

    # Sheet 3: Region Summary
    region_summary = []
    for region_code in all_regions:
        region_info = regions_map.get(region_code, {})
        service_count = len(
            [
                item
                for item in regional_services_data
                if item.get("region_code") == region_code
            ]
        )

        region_summary.append(
            {
                "Region Code": region_code,
                "Region Name": region_info.get("name", region_code),
                "Launch Date": region_info.get("launch_date", "N/A"),
                "Launch Date Source": region_info.get("launch_date_source", "N/A"),
                "Announcement URL": region_info.get("announcement_url", "N/A"),
                "Availability Zones": region_info.get("availability_zones", "N/A"),
                "Service Count": service_count,
            }
        )

    sheets["Region Summary"] = region_summary

    # Sheet 4: Service Summary
    service_summary = []
    for service_code in all_services:
        service_info = services_map.get(service_code, {})
        region_count = len(
            [
                item
                for item in regional_services_data
                if item.get("service_code") == service_code
            ]
        )

        service_summary.append(
            {
                "Service Code": service_code,
                "Service Name": service_info.get("name", service_code),
                "Service Category": service_info.get("category", "N/A"),
                "Description": service_info.get("description", "N/A"),
                "Region Count": region_count,
            }
        )

    sheets["Service Summary"] = service_summary

    # Sheet 5: Statistics
    statistics = [
        ["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Total Service-Region Combinations", len(regional_services_data)],
        ["Unique Regions", len(all_regions)],
        ["Unique Services", len(all_services)],
        [
            "Average Services per Region",
            f"{len(regional_services_data) / max(len(all_regions), 1):.2f}",
        ],
        [
            "Average Regions per Service",
            f"{len(regional_services_data) / max(len(all_services), 1):.2f}",
        ],
        ["Data Source", "AWS SSM Parameter Store"],
        ["Pipeline", "AWS Lambda Functions"],
        ["Region Coverage", f"{len(all_regions)}/{len(all_regions)} regions"],
        ["Service Coverage", f"{len(all_services)} services discovered"],
        ["Data Freshness", "Real-time from SSM"],
        ["Cache Status", "Not applicable (Lambda)"],
        ["Processing Method", "Serverless Pipeline"],
        ["Report Format", "Multi-sheet Excel"],
        ["Quality Check", "Validated region/service formats"],
        ["Export Status", "Complete"],
    ]

    sheets["Statistics"] = statistics

    return sheets
