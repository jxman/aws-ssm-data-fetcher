"""
AWS Lambda Function: Report Orchestrator
Coordinates final report packaging and uploads all reports to final S3 location.
Lightweight function that handles final coordination and cleanup.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# AWS clients
s3_client = boto3.client("s3")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for report orchestration and final packaging.

    Args:
        event: Lambda event data from Excel generator
        context: Lambda context object

    Returns:
        Final response with all report locations
    """
    try:
        # Extract summary data from previous step
        summary = event.get("summary", {})
        execution_id = summary.get(
            "execution_id", f"coord_{int(datetime.now().timestamp())}"
        )

        logger.info(f"Starting report orchestration for execution: {execution_id}")

        s3_bucket = summary.get("s3_bucket")
        temp_s3_prefix = summary.get("temp_s3_prefix")
        uploaded_files = summary.get("uploaded_files", {})

        if not s3_bucket or not temp_s3_prefix:
            raise ValueError("s3_bucket and temp_s3_prefix are required in summary")

        if not uploaded_files:
            raise ValueError("No uploaded files found in summary")

        # Define final report location
        final_s3_prefix = "reports"

        # Copy all files from temp location to final location
        final_locations = {}

        for report_type, temp_location in uploaded_files.items():
            if not temp_location.startswith("s3://"):
                continue

            # Parse temp S3 location
            temp_s3_parts = temp_location[5:].split("/", 1)
            if len(temp_s3_parts) != 2:
                continue

            temp_bucket, temp_key = temp_s3_parts

            # Extract filename
            filename = temp_key.split("/")[-1]

            # Define final location
            final_key = f"{final_s3_prefix}/{filename}"
            final_location = f"s3://{s3_bucket}/{final_key}"

            # Copy file to final location
            logger.info(
                f"Moving {report_type} from {temp_location} to {final_location}"
            )

            copy_source = {"Bucket": temp_bucket, "Key": temp_key}
            s3_client.copy_object(
                CopySource=copy_source, Bucket=s3_bucket, Key=final_key
            )

            final_locations[report_type] = final_location

        # Generate final summary report
        final_summary = {
            "execution_id": execution_id,
            "completion_timestamp": datetime.now().isoformat(),
            "source_data": summary.get("processed_data_location"),
            "reports_generated": final_locations,
            "statistics": {
                "regions_processed": summary.get("metadata", {}).get(
                    "regions_count", 0
                ),
                "services_processed": summary.get("metadata", {}).get(
                    "services_count", 0
                ),
                "regional_combinations": summary.get("metadata", {}).get(
                    "combinations_count", 0
                ),
                "report_formats": len(final_locations),
            },
            "pipeline_summary": {
                "total_stages": 3,
                "completed_stages": 3,
                "processing_time_seconds": _calculate_processing_time(summary),
                "status": "completed",
            },
        }

        # Save final summary
        summary_key = f"{final_s3_prefix}/summary.json"
        logger.info(f"Uploading final summary to s3://{s3_bucket}/{summary_key}")

        s3_client.put_object(
            Bucket=s3_bucket,
            Key=summary_key,
            Body=json.dumps(final_summary, indent=2),
            ContentType="application/json",
        )

        final_locations["summary"] = f"s3://{s3_bucket}/{summary_key}"

        # Clean up temporary files
        try:
            _cleanup_temp_files(s3_bucket, temp_s3_prefix)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")

        # Send SNS notification if configured
        try:
            _send_completion_notification(
                execution_id, final_summary, len(final_locations)
            )
        except Exception as e:
            logger.warning(f"Failed to send SNS notification: {e}")

        logger.info(
            f"Report orchestration completed successfully for execution: {execution_id}"
        )

        return {
            "status": "success",
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "Report generation completed successfully",
            "reports_location": f"s3://{s3_bucket}/{final_s3_prefix}/",
            "execution_summary": final_summary,
            "reports": final_locations,
        }

    except Exception as e:
        logger.error(f"Error in report orchestration: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())

        execution_id = event.get("summary", {}).get("execution_id", "unknown")

        return {
            "status": "error",
            "statusCode": 500,
            "execution_id": execution_id,
            "message": f"Report orchestration failed: {str(e)}",
            "error": str(e),
        }


def _calculate_processing_time(summary: Dict[str, Any]) -> float:
    """Calculate approximate processing time."""
    try:
        generated_at = summary.get("generated_at", "")
        if generated_at:
            start_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            end_time = datetime.now()
            return (end_time - start_time).total_seconds()
    except Exception:
        pass
    return 2.0  # Default estimate


def _cleanup_temp_files(s3_bucket: str, temp_s3_prefix: str) -> None:
    """Clean up temporary files from S3."""
    logger.info(f"Cleaning up temporary files from s3://{s3_bucket}/{temp_s3_prefix}/")

    # List all objects with the temp prefix
    response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=temp_s3_prefix)

    objects_to_delete = []
    for obj in response.get("Contents", []):
        objects_to_delete.append({"Key": obj["Key"]})

    if objects_to_delete:
        # Delete the objects
        s3_client.delete_objects(
            Bucket=s3_bucket, Delete={"Objects": objects_to_delete}
        )
        logger.info(f"Deleted {len(objects_to_delete)} temporary files")


def _send_completion_notification(
    execution_id: str, summary: Dict[str, Any], report_count: int
) -> None:
    """Send SNS notification about completion."""
    try:
        # Try to get SNS topic from environment
        sns_topic_arn = os.getenv("SNS_TOPIC_ARN")
        if not sns_topic_arn:
            logger.info("No SNS topic configured, skipping notification")
            return

        # Create SNS client
        sns_client = boto3.client("sns")

        # Create notification message
        stats = summary.get("statistics", {})
        message = f"""
AWS SSM Data Fetcher - Report Generation Complete

Execution ID: {execution_id}
Status: Successfully Completed

Statistics:
- Regions Processed: {stats.get('regions_processed', 0)}
- Services Processed: {stats.get('services_processed', 0)}
- Regional Combinations: {stats.get('regional_combinations', 0)}
- Report Formats Generated: {report_count}

Processing Time: {summary.get('pipeline_summary', {}).get('processing_time_seconds', 0):.1f} seconds

Reports available at: {summary.get('source_data', 'N/A').replace('processed-data', 'reports')}
""".strip()

        # Send notification
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=f"AWS SSM Data Fetcher - Execution {execution_id} Complete",
            Message=message,
        )

        logger.info("SNS notification sent successfully")

    except Exception as e:
        logger.warning(f"Failed to send SNS notification: {e}")
        # Don't raise - this is not critical for the main function
