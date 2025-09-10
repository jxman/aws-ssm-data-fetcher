"""
AWS Lambda Function: Data Fetcher
Fetches AWS SSM data and RSS feed data for processing.
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
    Lambda handler for data fetching.

    Args:
        event: Lambda event data
        context: Lambda context object

    Returns:
        Response with execution details
    """
    execution_id = event.get("execution_id", f"exec_{int(datetime.now().timestamp())}")

    try:
        logger.info(f"Starting data fetching for execution: {execution_id}")

        # Initialize configuration from environment
        config = {
            "aws_region": os.getenv("AWS_REGION", "us-east-1"),
            "cache_enabled": os.getenv("CACHE_ENABLED", "true").lower() == "true",
            "output_bucket": os.getenv("OUTPUT_S3_BUCKET"),
            "cache_bucket": os.getenv("CACHE_S3_BUCKET"),
            "execution_id": execution_id,
        }

        # Validate required configuration
        if not config["output_bucket"]:
            raise ValueError("OUTPUT_S3_BUCKET environment variable is required")

        # Import our modules from the shared layer
        from aws_ssm_fetcher.core.cache import CacheManager
        from aws_ssm_fetcher.core.config import Config
        from aws_ssm_fetcher.data_sources.rss_client import RSSClient
        from aws_ssm_fetcher.processors import RegionDiscoverer, ServiceDiscoverer

        # Create Lambda-optimized configuration
        lambda_config = Config.for_lambda("data_fetcher")
        lambda_config.aws_region = config["aws_region"]

        # Initialize cache manager with S3 backend
        cache_manager = CacheManager(lambda_config)

        # Initialize data discoverers
        region_discoverer = RegionDiscoverer(None)
        service_discoverer = ServiceDiscoverer(None)
        rss_client = RSSClient(cache_manager)

        # Fetch data
        logger.info("Discovering AWS regions...")
        regions_data = region_discoverer.process({})

        logger.info("Discovering AWS services...")
        services_data = service_discoverer.process({})

        logger.info("Fetching RSS feed data...")
        rss_data = rss_client.fetch_region_rss_data()

        # Prepare data package for processing
        raw_data = {
            "execution_id": execution_id,
            "timestamp": datetime.now().isoformat(),
            "regions": regions_data,
            "services": services_data,
            "rss_data": rss_data,
            "config": {
                "aws_region": config["aws_region"],
                "cache_enabled": config["cache_enabled"],
            },
        }

        # Store raw data in S3 for processor
        s3_key = f"raw-data/{execution_id}/data.json"
        s3_client.put_object(
            Bucket=config["output_bucket"],
            Key=s3_key,
            Body=json.dumps(raw_data, indent=2),
            ContentType="application/json",
        )

        logger.info(f"Raw data stored in S3: s3://{config['output_bucket']}/{s3_key}")

        # Invoke processor function if specified
        processor_function = os.getenv("PROCESSOR_FUNCTION")
        if processor_function:
            logger.info(f"Invoking processor function: {processor_function}")

            processor_event = {
                "execution_id": execution_id,
                "s3_bucket": config["output_bucket"],
                "s3_key": s3_key,
                "source": "data_fetcher",
            }

            lambda_client.invoke(
                FunctionName=processor_function,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(processor_event),
            )

        # Return success response
        response = {
            "status": "success",
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "Data fetching completed successfully",
            "data_location": f"s3://{config['output_bucket']}/{s3_key}",
            "statistics": {
                "regions_discovered": len(regions_data.get("regions", [])),
                "services_discovered": len(services_data.get("services", [])),
                "rss_entries": len(rss_data) if rss_data else 0,
            },
        }

        logger.info(f"Data fetching completed: {json.dumps(response['statistics'])}")
        return response

    except Exception as e:
        error_msg = f"Data fetching failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "status": "failed",
            "statusCode": 500,
            "execution_id": execution_id,
            "error": error_msg,
            "message": "Data fetching failed",
        }
