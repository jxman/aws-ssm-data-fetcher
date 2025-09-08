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

        # Extract input parameters
        s3_bucket = event.get("s3_bucket")
        s3_key = event.get("s3_key")

        if not s3_bucket or not s3_key:
            raise ValueError("s3_bucket and s3_key are required in event")

        # Load raw data from S3
        logger.info(f"Loading raw data from s3://{s3_bucket}/{s3_key}")
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        raw_data = json.loads(response["Body"].read().decode("utf-8"))

        # Import processing modules from shared layer
        from aws_ssm_fetcher.core.cache import CacheManager
        from aws_ssm_fetcher.core.config import Config
        from aws_ssm_fetcher.processors.base import ProcessingContext
        from aws_ssm_fetcher.processors.data_transformer import DataTransformer
        from aws_ssm_fetcher.processors.pipeline import (
            PipelineOrchestrator,
            ProcessingPipeline,
        )
        from aws_ssm_fetcher.processors.service_mapper import ServiceMapper
        from aws_ssm_fetcher.processors.statistics_analyzer import StatisticsAnalyzer

        # Create Lambda-optimized configuration
        lambda_config = Config.for_lambda("processor")
        lambda_config.aws_region = raw_data.get("config", {}).get(
            "aws_region", "us-east-1"
        )

        # Initialize cache manager
        cache_manager = CacheManager(lambda_config)

        # Create processing context
        processing_context = ProcessingContext(
            config=lambda_config,
            cache_manager=cache_manager,
            logger_name="lambda_processor",
        )

        # Create pipeline orchestrator
        orchestrator = PipelineOrchestrator(processing_context)

        # Configure processing pipeline
        pipeline_config = {
            "enable_validation": True,
            "enable_statistics": True,
            "parallel_processing": True,
            "timeout_seconds": 300,  # 5 minutes max processing time
        }

        logger.info("Executing processing pipeline...")

        # Transform raw data to pipeline input format
        pipeline_input = {
            "regions_data": raw_data.get("regions", {}),
            "services_data": raw_data.get("services", {}),
            "rss_data": raw_data.get("rss_data", {}),
            "execution_metadata": {
                "execution_id": execution_id,
                "source_timestamp": raw_data.get("timestamp"),
                "processing_timestamp": datetime.now().isoformat(),
            },
        }

        # Execute complete processing pipeline
        pipeline_results = orchestrator.execute_pipeline(
            pipeline_config, pipeline_input
        )

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

            # Store metadata
            processed_data["metadata"]["regions"] = {
                r.get("code", r): r.get("name", r) for r in regions
            }
            processed_data["metadata"]["services"] = {
                s.get("code", s): s.get("name", s) for s in services
            }

        # Extract mapping results for final data
        if "mapping" in pipeline_results.get("stage_results", {}):
            mapping_results = pipeline_results["stage_results"]["mapping"]
            service_mappings = mapping_results.get("service_region_mappings", {})

            # Convert to regional services format
            regional_services = []
            for service, regions in service_mappings.items():
                service_name = processed_data["metadata"]["services"].get(
                    service, service
                )
                for region in regions:
                    region_name = processed_data["metadata"]["regions"].get(
                        region, region
                    )
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
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=processed_s3_key,
            Body=json.dumps(processed_data, indent=2),
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

        # Return success response
        response = {
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "Data processing completed successfully",
            "processed_data_location": f"s3://{s3_bucket}/{processed_s3_key}",
            "pipeline_summary": pipeline_results.get("pipeline_execution", {}),
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
            "statusCode": 500,
            "execution_id": execution_id,
            "error": error_msg,
            "message": "Data processing failed",
        }
