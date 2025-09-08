"""
AWS Lambda Function: Report Generator
Generates Excel, JSON, and CSV reports from processed AWS SSM data.
"""

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
# SNS client will be created when needed to avoid region errors during testing


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for report generation.

    Args:
        event: Lambda event data containing S3 location of processed data
        context: Lambda context object

    Returns:
        Response with report generation details
    """
    execution_id = event.get("execution_id", f"rpt_{int(datetime.now().timestamp())}")

    try:
        logger.info(f"Starting report generation for execution: {execution_id}")

        # Extract input parameters
        s3_bucket = event.get("s3_bucket")
        s3_key = event.get("s3_key")

        if not s3_bucket or not s3_key:
            raise ValueError("s3_bucket and s3_key are required in event")

        # Load processed data from S3
        logger.info(f"Loading processed data from s3://{s3_bucket}/{s3_key}")
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        processed_data = json.loads(response["Body"].read().decode("utf-8"))

        # Import output generation modules from shared layer
        from aws_ssm_fetcher.core.config import Config
        from aws_ssm_fetcher.outputs.base import OutputContext
        from aws_ssm_fetcher.outputs.csv_generator import (
            CSVGenerator,
            MultiCSVGenerator,
        )
        from aws_ssm_fetcher.outputs.excel_generator import ExcelGenerator
        from aws_ssm_fetcher.outputs.json_generator import (
            CompactJSONGenerator,
            JSONGenerator,
        )

        # Extract data for report generation
        regional_services_data = processed_data.get("regional_services_data", [])
        metadata = processed_data.get("metadata", {})

        if not regional_services_data:
            logger.warning("No regional services data found for report generation")

        # Create temporary directory for file generation
        temp_output_dir = "/tmp/reports"
        os.makedirs(temp_output_dir, exist_ok=True)

        # Create output context
        output_context = OutputContext(
            output_dir=temp_output_dir,
            region_names=metadata.get("regions", {}),
            service_names=metadata.get("services", {}),
            rss_data=metadata.get("rss_data", {}),
            all_services=list(metadata.get("services", {}).keys()),
            metadata={
                "generated_at": datetime.now().isoformat(),
                "source": "AWS SSM Parameter Store",
                "execution_id": execution_id,
                "pipeline_results": processed_data.get("pipeline_execution", {}),
            },
        )

        # Generate all report formats
        generated_files = {}

        # Generate Excel report
        logger.info("Generating Excel report...")
        excel_generator = ExcelGenerator(output_context)
        excel_path = excel_generator.generate(regional_services_data)
        generated_files["excel"] = excel_path

        # Generate JSON reports
        logger.info("Generating JSON reports...")
        json_generator = JSONGenerator(output_context)
        json_path = json_generator.generate(regional_services_data)
        generated_files["json"] = json_path

        # Generate compact JSON
        compact_json_context = OutputContext(**output_context.__dict__)
        compact_json_context.filename = "aws_regions_services_compact.json"
        compact_json_generator = CompactJSONGenerator(compact_json_context)
        compact_json_path = compact_json_generator.generate(regional_services_data)
        generated_files["compact_json"] = compact_json_path

        # Generate CSV reports
        logger.info("Generating CSV reports...")
        csv_generator = CSVGenerator(output_context)
        csv_path = csv_generator.generate(regional_services_data)
        generated_files["csv"] = csv_path

        # Generate multi-CSV (one per sheet)
        multi_csv_context = OutputContext(**output_context.__dict__)
        multi_csv_context.filename = "aws_regions_services_sheets"
        multi_csv_generator = MultiCSVGenerator(multi_csv_context)
        multi_csv_dir = multi_csv_generator.generate(regional_services_data)
        generated_files["multi_csv"] = multi_csv_dir

        # Upload all generated files to S3
        s3_reports = {}
        reports_base_key = f"reports/{execution_id}"

        for format_name, file_path in generated_files.items():
            if format_name == "multi_csv":
                # Handle directory of CSV files
                for file_name in os.listdir(file_path):
                    if file_name.endswith(".csv"):
                        local_file = os.path.join(file_path, file_name)
                        s3_report_key = f"{reports_base_key}/csv_sheets/{file_name}"

                        with open(local_file, "rb") as f:
                            s3_client.put_object(
                                Bucket=s3_bucket,
                                Key=s3_report_key,
                                Body=f.read(),
                                ContentType="text/csv",
                            )

                        if "csv_sheets" not in s3_reports:
                            s3_reports["csv_sheets"] = []
                        s3_reports["csv_sheets"].append(
                            f"s3://{s3_bucket}/{s3_report_key}"
                        )
            else:
                # Handle single files
                file_extension = os.path.splitext(file_path)[1]
                s3_report_key = f"{reports_base_key}/{format_name}{file_extension}"

                # Determine content type
                content_type_map = {
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".json": "application/json",
                    ".csv": "text/csv",
                }
                content_type = content_type_map.get(
                    file_extension, "application/octet-stream"
                )

                with open(file_path, "rb") as f:
                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=s3_report_key,
                        Body=f.read(),
                        ContentType=content_type,
                    )

                s3_reports[format_name] = f"s3://{s3_bucket}/{s3_report_key}"

        logger.info(
            f"All reports uploaded to S3 under: s3://{s3_bucket}/{reports_base_key}/"
        )

        # Create execution summary
        execution_summary = {
            "execution_id": execution_id,
            "completion_timestamp": datetime.now().isoformat(),
            "source_data": f"s3://{s3_bucket}/{s3_key}",
            "reports_generated": s3_reports,
            "statistics": {
                "regions_processed": len(metadata.get("regions", {})),
                "services_processed": len(metadata.get("services", {})),
                "regional_combinations": len(regional_services_data),
                "report_formats": len(s3_reports),
            },
            "pipeline_summary": processed_data.get("pipeline_execution", {}),
        }

        # Store execution summary
        summary_key = f"{reports_base_key}/execution_summary.json"
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=summary_key,
            Body=json.dumps(execution_summary, indent=2),
            ContentType="application/json",
        )

        # Send notification if SNS topic is configured
        sns_topic = os.getenv("COMPLETION_SNS_TOPIC")
        if sns_topic:
            try:
                # Create SNS client only when needed
                sns_client = boto3.client("sns")

                notification_message = {
                    "message": "AWS SSM Data Report Generation Completed",
                    "execution_id": execution_id,
                    "reports_location": f"s3://{s3_bucket}/{reports_base_key}/",
                    "statistics": execution_summary["statistics"],
                }

                sns_client.publish(
                    TopicArn=sns_topic,
                    Subject=f"AWS SSM Report Complete - {execution_id}",
                    Message=json.dumps(notification_message, indent=2),
                )
                logger.info(f"Completion notification sent to SNS: {sns_topic}")
            except Exception as e:
                logger.warning(f"Failed to send SNS notification: {e}")

        # Return success response
        response = {
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "Report generation completed successfully",
            "reports_location": f"s3://{s3_bucket}/{reports_base_key}/",
            "execution_summary": execution_summary,
            "reports_generated": s3_reports,
        }

        logger.info(
            f"Report generation completed: {json.dumps(response['statistics'])}"
        )
        return response

    except Exception as e:
        error_msg = f"Report generation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "statusCode": 500,
            "execution_id": execution_id,
            "error": error_msg,
            "message": "Report generation failed",
        }
