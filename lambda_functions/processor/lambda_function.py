"""
AWS Lambda Function: Processor
Processes raw AWS SSM data through the complete transformation pipeline.
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
lambda_client = boto3.client("lambda")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for data processing.

    Args:
        event: Lambda event data containing S3 location of raw data
        context: Lambda context object

    Returns:
        Response with processing details
    """
    execution_id = event.get("execution_id", f"proc_{int(datetime.now().timestamp())}")

    try:
        logger.info(f"Starting data processing for execution: {execution_id}")

        # Extract input parameters from Step Functions event
        data_location = event.get("data_location")
        if not data_location:
            raise ValueError("data_location is required in event")

        # Parse S3 location (format: s3://bucket/key)
        if not data_location.startswith("s3://"):
            raise ValueError(f"Invalid S3 location format: {data_location}")

        s3_parts = data_location[5:].split("/", 1)
        if len(s3_parts) != 2:
            raise ValueError(f"Invalid S3 location format: {data_location}")

        s3_bucket, s3_key = s3_parts

        # Load raw data from S3
        logger.info(f"Loading raw data from s3://{s3_bucket}/{s3_key}")
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        raw_data = json.loads(response["Body"].read().decode("utf-8"))

        # Import our modules from the shared layer for real processing
        from aws_ssm_fetcher.core.config import Config
        from aws_ssm_fetcher.data_sources.aws_ssm_client import AWSSSMClient
        from aws_ssm_fetcher.processors import ServiceMapper
        from aws_ssm_fetcher.processors.base import ProcessingContext

        # Structured processing using real AWS SSM service mapping
        logger.info("Processing raw data using real AWS SSM service mappings...")

        # The data structure has regions and services as direct arrays
        regions_list = raw_data.get("regions", [])
        services_list = raw_data.get("services", [])
        rss_data = raw_data.get("rss_data", {})

        logger.info(
            f"Mapping {len(services_list)} services across {len(regions_list)} regions using real AWS SSM data"
        )

        # Initialize AWS SSM client and processing context for pipeline processing
        lambda_config = Config.for_lambda("processor")
        # Use boto3 SSM client directly for ServiceMapper (needs get_paginator method)
        ssm_client = boto3.client("ssm")

        processing_context = ProcessingContext(config=lambda_config)
        # Add SSM client to context as an attribute
        processing_context.ssm_client = ssm_client

        # Use ProcessingPipeline to get enriched metadata and accurate service-region mappings
        try:
            from aws_ssm_fetcher.processors import ProcessingPipeline

            # Create pipeline for processing with enrichment
            pipeline = ProcessingPipeline(processing_context)

            # Execute the full pipeline to get enriched discovery and mapping results
            logger.info(
                f"Running full processing pipeline with discovery and enrichment"
            )

            # Execute the pipeline (it will do its own discovery and enrichment)
            pipeline_results = pipeline.process()
            logger.info(f"Pipeline processing completed with enriched metadata")

            # Extract service mappings from pipeline results
            mapping_results = pipeline_results.get("stage_results", {}).get(
                "mapping", {}
            )
            service_region_mappings = mapping_results.get("service_region_mappings", {})

            # Report on processing coverage
            processed_services = len(service_region_mappings)
            total_services = len(services_list)
            coverage_pct = (
                (processed_services / total_services * 100) if total_services > 0 else 0
            )

            logger.info(
                f"Pipeline mapping coverage: {processed_services}/{total_services} services ({coverage_pct:.1f}%)"
            )

            mapping_stats = {
                "total_services_mapped": processed_services,
                "total_services_available": total_services,
                "coverage_percentage": round(coverage_pct, 1),
                "total_regions_with_services": (
                    len(set().union(*service_region_mappings.values()))
                    if service_region_mappings
                    else 0
                ),
                "total_service_region_combinations": sum(
                    len(regions) for regions in service_region_mappings.values()
                ),
            }

        except Exception as e:
            logger.warning(
                f"Failed to use real service mapping, falling back to basic mapping: {e}"
            )
            # Fallback to basic mapping if real mapping fails
            service_region_mappings = {}
            mapping_stats = {
                "total_services_mapped": 0,
                "total_regions_with_services": 0,
                "total_service_region_combinations": 0,
                "fallback_used": True,
            }

        # Note: pipeline_results already contains enriched discovery data
        # Don't overwrite with basic mappings - the pipeline already provides enriched data

        # Only update the mapping results if needed
        if "mapping" not in pipeline_results.get("stage_results", {}):
            if "stage_results" not in pipeline_results:
                pipeline_results["stage_results"] = {}
            pipeline_results["stage_results"]["mapping"] = {
                "service_region_mappings": service_region_mappings,
                "mapping_stats": mapping_stats,
            }

        # Prepare processed data package
        processed_data = {
            "execution_id": execution_id,
            "processing_timestamp": datetime.now().isoformat(),
            "source_data_location": f"s3://{s3_bucket}/{s3_key}",
            "pipeline_results": pipeline_results,
            "pipeline_execution": pipeline_results.get("pipeline_execution", {}),
            "stage_results": pipeline_results.get("stage_results", {}),
            "regional_services_data": [],  # Will be populated from pipeline results
            "metadata": {
                "regions": {},
                "services": {},
                "rss_data": raw_data.get("rss_data", {}),
            },
        }

        # Extract regional services data from pipeline results
        if "discovery" in pipeline_results.get("stage_results", {}):
            discovery_results = pipeline_results["stage_results"]["discovery"]
            regions = discovery_results.get("regions", [])
            services = discovery_results.get("services", [])

            # Store enriched metadata (full objects, not just code->name mappings)
            processed_data["metadata"]["regions"] = {
                r.get("code", r): r for r in regions
            }
            processed_data["metadata"]["services"] = {
                s.get("code", s): s for s in services
            }

        # Extract mapping results for final data
        if "mapping" in pipeline_results.get("stage_results", {}):
            mapping_results = pipeline_results["stage_results"]["mapping"]
            service_mappings = mapping_results.get("service_region_mappings", {})

            # Convert to regional services format
            regional_services = []
            for service, regions in service_mappings.items():
                service_metadata = processed_data["metadata"]["services"].get(
                    service, {"code": service, "name": service}
                )
                # Extract service name from enriched metadata object
                if isinstance(service_metadata, dict):
                    service_name = service_metadata.get("name", service)
                else:
                    service_name = service_metadata

                for region in regions:
                    region_metadata = processed_data["metadata"]["regions"].get(
                        region, {"code": region, "name": region}
                    )
                    # Extract region name from enriched metadata object
                    if isinstance(region_metadata, dict):
                        region_name = region_metadata.get("name", region)
                    else:
                        region_name = region_metadata

                    regional_services.append(
                        {
                            "Region Code": region,
                            "Region Name": region_name,
                            "Service Code": service,
                            "Service Name": service_name,
                        }
                    )

            processed_data["regional_services_data"] = regional_services

        # Store processed data in S3 for report generator
        processed_s3_key = f"processed-data/{execution_id}/processed_data.json"

        # Custom JSON serializer to handle datetime objects
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        s3_client.put_object(
            Bucket=s3_bucket,
            Key=processed_s3_key,
            Body=json.dumps(processed_data, indent=2, default=json_serializer),
            ContentType="application/json",
        )

        logger.info(f"Processed data stored in S3: s3://{s3_bucket}/{processed_s3_key}")

        # Invoke report generator function if specified
        report_generator_function = os.getenv("REPORT_GENERATOR_FUNCTION")
        if report_generator_function:
            logger.info(f"Invoking report generator: {report_generator_function}")

            generator_event = {
                "execution_id": execution_id,
                "s3_bucket": s3_bucket,
                "s3_key": processed_s3_key,
                "source": "processor",
            }

            lambda_client.invoke(
                FunctionName=report_generator_function,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(generator_event),
            )

        # Return success response (ensure all data is JSON serializable)
        pipeline_summary = pipeline_results.get("pipeline_execution", {})

        # Clean pipeline summary to remove datetime objects
        serializable_pipeline_summary = {
            "total_stages": pipeline_summary.get("total_stages", 0),
            "completed_stages": pipeline_summary.get("completed_stages", 0),
            "processing_time_seconds": pipeline_summary.get(
                "processing_time_seconds", 0
            ),
            "status": pipeline_summary.get("status", "unknown"),
        }

        response = {
            "status": "success",
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "Data processing completed successfully",
            "processed_data_location": f"s3://{s3_bucket}/{processed_s3_key}",
            "pipeline_summary": serializable_pipeline_summary,
            "statistics": {
                "regions_processed": len(processed_data["metadata"]["regions"]),
                "services_processed": len(processed_data["metadata"]["services"]),
                "regional_combinations": len(processed_data["regional_services_data"]),
                "pipeline_success": pipeline_results.get("success", False),
            },
        }

        logger.info(f"Processing completed: {json.dumps(response['statistics'])}")
        return response

    except Exception as e:
        error_msg = f"Data processing failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "status": "failed",
            "statusCode": 500,
            "execution_id": execution_id,
            "error": error_msg,
            "message": "Data processing failed",
        }
