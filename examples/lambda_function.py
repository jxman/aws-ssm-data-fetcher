#!/usr/bin/env python3
"""
AWS Lambda function to fetch SSM data and upload to S3
"""

import json
import logging
import os
import pickle
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional

import boto3
import feedparser
import pandas as pd
import requests
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class S3CacheManager:
    """S3-based cache manager for Lambda environment."""

    def __init__(
        self, bucket_name: str, cache_prefix: str = "cache/", cache_hours: int = 24
    ):
        self.s3 = boto3.client("s3")
        self.bucket_name = bucket_name
        self.cache_prefix = cache_prefix
        self.cache_hours = cache_hours

    def _get_cache_key(self, cache_key: str) -> str:
        """Get S3 key for cache item."""
        safe_key = cache_key.replace("/", "_").replace(":", "_")
        return f"{self.cache_prefix}{safe_key}.pkl"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache exists and is within TTL."""
        s3_key = self._get_cache_key(cache_key)

        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            last_modified = response["LastModified"].replace(tzinfo=None)
            ttl_time = datetime.utcnow() - timedelta(hours=self.cache_hours)

            return last_modified > ttl_time
        except ClientError:
            return False

    def load_from_cache(self, cache_key: str) -> Optional[any]:
        """Load data from S3 cache if valid."""
        if not self._is_cache_valid(cache_key):
            return None

        s3_key = self._get_cache_key(cache_key)

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            data = pickle.loads(response["Body"].read())
            logger.info(f"Loaded from S3 cache: {cache_key}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load S3 cache {cache_key}: {e}")
            return None

    def save_to_cache(self, cache_key: str, data: any) -> None:
        """Save data to S3 cache."""
        s3_key = self._get_cache_key(cache_key)

        try:
            serialized_data = pickle.dumps(data)
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=serialized_data,
                ContentType="application/octet-stream",
            )
            logger.info(f"Saved to S3 cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to save S3 cache {cache_key}: {e}")

    def clear_cache(self, cache_key: Optional[str] = None) -> int:
        """Clear S3 cache items."""
        cleared_count = 0

        try:
            if cache_key:
                # Clear specific cache entry
                s3_key = self._get_cache_key(cache_key)
                self.s3.delete_object(Bucket=self.bucket_name, Key=s3_key)
                cleared_count = 1
                logger.info(f"Cleared S3 cache: {cache_key}")
            else:
                # Clear all cache files with the prefix
                paginator = self.s3.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(
                    Bucket=self.bucket_name, Prefix=self.cache_prefix
                )

                for page in page_iterator:
                    if "Contents" in page:
                        delete_keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
                        if delete_keys:
                            self.s3.delete_objects(
                                Bucket=self.bucket_name, Delete={"Objects": delete_keys}
                            )
                            cleared_count += len(delete_keys)

                logger.info(f"Cleared all S3 cache files: {cleared_count} files")
        except Exception as e:
            logger.error(f"Failed to clear S3 cache: {e}")

        return cleared_count


def fetch_region_rss_data(
    cache_manager: Optional[S3CacheManager] = None,
) -> Dict[str, Dict]:
    """Fetch region launch dates and metadata from AWS RSS feed."""
    cache_key = "region_rss_data"

    # Try to load from cache first
    if cache_manager:
        cached_data = cache_manager.load_from_cache(cache_key)
        if cached_data is not None:
            logger.info("Using cached RSS region data")
            return cached_data

    logger.info("Fetching AWS regions RSS data...")
    rss_url = (
        "https://docs.aws.amazon.com/global-infrastructure/latest/regions/regions.rss"
    )

    try:
        # Fetch RSS feed
        response = requests.get(rss_url, timeout=30)
        response.raise_for_status()

        # Parse RSS feed
        feed = feedparser.parse(response.content)

        region_data = {}

        for entry in feed.entries:
            try:
                # Extract information from RSS entry
                title = entry.title
                description = getattr(entry, "description", "")
                published = getattr(entry, "published", "")
                link = getattr(entry, "link", "")

                # Parse region code from title or description
                region_code_match = re.search(
                    r"([a-z]{2}-[a-z]+-[0-9]{1,2})", title + " " + description
                )

                if region_code_match:
                    region_code = region_code_match.group(1)

                    # Extract region name (everything before the dash and region code)
                    region_name_match = re.search(
                        r"^(.+?)\s*-\s*" + re.escape(region_code), title
                    )
                    region_name = (
                        region_name_match.group(1).strip()
                        if region_name_match
                        else title.split("-")[0].strip()
                    )

                    # Parse launch date from published date
                    launch_date = "N/A"
                    if published:
                        try:
                            parsed_date = datetime.strptime(
                                published, "%a, %d %b %Y %H:%M:%S %z"
                            )
                            launch_date = parsed_date.strftime("%Y-%m-%d")
                        except ValueError:
                            try:
                                parsed_date = datetime.strptime(
                                    published, "%a, %d %b %Y %H:%M:%S GMT"
                                )
                                launch_date = parsed_date.strftime("%Y-%m-%d")
                            except ValueError:
                                date_match = re.search(
                                    r"(\w+ \d{1,2}, \d{4})", description
                                )
                                if date_match:
                                    try:
                                        parsed_date = datetime.strptime(
                                            date_match.group(1), "%B %d, %Y"
                                        )
                                        launch_date = parsed_date.strftime("%Y-%m-%d")
                                    except ValueError:
                                        pass

                    region_data[region_code] = {
                        "region_name": region_name,
                        "launch_date": launch_date,
                        "announcement_url": link,
                        "rss_title": title,
                        "description": description,
                    }

            except Exception as e:
                logger.warning(f"Failed to parse RSS entry: {e}")
                continue

        # Save to cache
        if cache_manager:
            cache_manager.save_to_cache(cache_key, region_data)

        logger.info(f"Successfully fetched RSS data for {len(region_data)} regions")
        return region_data

    except Exception as e:
        logger.error(f"Failed to fetch RSS data: {e}")
        return {}


def get_known_regions():
    """Return list of known AWS regions."""
    return [
        "af-south-1",
        "ap-east-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-northeast-3",
        "ap-south-1",
        "ap-south-2",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-southeast-3",
        "ap-southeast-4",
        "ca-central-1",
        "ca-west-1",
        "eu-central-1",
        "eu-central-2",
        "eu-north-1",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "il-central-1",
        "me-central-1",
        "me-south-1",
        "sa-east-1",
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "us-gov-east-1",
        "us-gov-west-1",
    ]


def get_known_services():
    """Return list of known AWS services."""
    return [
        "accessanalyzer",
        "account",
        "acm",
        "acm-pca",
        "amplify",
        "apigateway",
        "apigatewayv2",
        "appconfig",
        "appconfigdata",
        "appflow",
        "application-autoscaling",
        "appmesh",
        "apprunner",
        "appstream",
        "appsync",
        "athena",
        "autoscaling",
        "backup",
        "batch",
        "bedrock",
        "budgets",
        "chime",
        "cloud9",
        "cloudformation",
        "cloudfront",
        "cloudsearch",
        "cloudtrail",
        "cloudwatch",
        "codeartifact",
        "codebuild",
        "codecommit",
        "codedeploy",
        "codeguru-reviewer",
        "codepipeline",
        "cognito-identity",
        "cognito-idp",
        "comprehend",
        "config",
        "connect",
        "databrew",
        "dataexchange",
        "datapipeline",
        "datasync",
        "dax",
        "detective",
        "devicefarm",
        "directconnect",
        "discovery",
        "dms",
        "docdb",
        "ds",
        "dynamodb",
        "ebs",
        "ec2",
        "ecr",
        "ecs",
        "efs",
        "eks",
        "elasticache",
        "elasticbeanstalk",
        "emr",
        "events",
        "firehose",
        "fms",
        "forecast",
        "frauddetector",
        "fsx",
        "gamelift",
        "glacier",
        "globalaccelerator",
        "glue",
        "greengrass",
        "groundstation",
        "guardduty",
        "health",
        "iam",
        "imagebuilder",
        "inspector",
        "inspector2",
        "iot",
        "iotanalytics",
        "iotevents",
        "kafka",
        "kendra",
        "kinesis",
        "kinesisanalytics",
        "kms",
        "lakeformation",
        "lambda",
        "license-manager",
        "lightsail",
        "logs",
        "machinelearning",
        "managedblockchain",
        "mediaconnect",
        "mediaconvert",
        "medialive",
        "mediapackage",
        "mediastore",
        "mediatailor",
        "memorydb",
        "mq",
        "mturk",
        "neptune",
        "networkmanager",
        "organizations",
        "outposts",
        "personalize",
        "pinpoint",
        "polly",
        "pricing",
        "qldb",
        "quicksight",
        "ram",
        "rds",
        "redshift",
        "rekognition",
        "resource-groups",
        "robomaker",
        "route53",
        "route53domains",
        "route53resolver",
        "s3",
        "s3control",
        "sagemaker",
        "secretsmanager",
        "securityhub",
        "serverlessrepo",
        "servicecatalog",
        "servicediscovery",
        "ses",
        "shield",
        "signer",
        "sns",
        "sqs",
        "ssm",
        "stepfunctions",
        "storagegateway",
        "sts",
        "support",
        "swf",
        "synthetics",
        "textract",
        "timestream",
        "transcribe",
        "transfer",
        "translate",
        "waf",
        "workdocs",
        "workmail",
        "workspaces",
        "xray",
    ]


def get_parameters_batch(ssm_client, parameter_paths: List[str]) -> Dict[str, str]:
    """Get multiple parameters in batches."""
    results = {}

    for i in range(0, len(parameter_paths), 10):
        batch = parameter_paths[i : i + 10]
        try:
            response = ssm_client.get_parameters(Names=batch)
            for param in response["Parameters"]:
                results[param["Name"]] = param["Value"]
            for invalid in response["InvalidParameters"]:
                results[invalid] = None
        except ClientError as e:
            logger.error(f"Batch parameter request failed: {e}")
            for path in batch:
                results[path] = None

    return results


def fetch_region_names(
    ssm_client, regions: List[str], cache_manager: Optional[S3CacheManager] = None
) -> Dict[str, str]:
    """Fetch human-readable names for regions."""
    cache_key = "region_names"

    # Try to load from cache first
    if cache_manager:
        cached_data = cache_manager.load_from_cache(cache_key)
        if cached_data is not None:
            # Filter cached data to only include requested regions
            filtered_data = {k: v for k, v in cached_data.items() if k in regions}
            if len(filtered_data) == len(regions):
                logger.info(f"Using cached region names for {len(regions)} regions")
                return filtered_data

    logger.info("Fetching region display names...")

    region_name_paths = [
        f"/aws/service/global-infrastructure/regions/{region}/longName"
        for region in regions
    ]
    region_name_results = get_parameters_batch(ssm_client, region_name_paths)

    region_names = {}
    for region in regions:
        path = f"/aws/service/global-infrastructure/regions/{region}/longName"
        name = region_name_results.get(path)
        region_names[region] = name if name else region

    # Save to cache
    if cache_manager:
        cache_manager.save_to_cache(cache_key, region_names)

    return region_names


def fetch_service_names(
    ssm_client, services: List[str], cache_manager: Optional[S3CacheManager] = None
) -> Dict[str, str]:
    """Fetch human-readable names for services."""
    cache_key = "service_names"

    # Try to load from cache first
    if cache_manager:
        cached_data = cache_manager.load_from_cache(cache_key)
        if cached_data is not None:
            # Filter cached data to only include requested services
            filtered_data = {k: v for k, v in cached_data.items() if k in services}
            if len(filtered_data) == len(services):
                logger.info(f"Using cached service names for {len(services)} services")
                return filtered_data

    logger.info("Fetching service display names...")

    service_name_paths = [
        f"/aws/service/global-infrastructure/services/{service}/longName"
        for service in services
    ]
    service_name_results = get_parameters_batch(ssm_client, service_name_paths)

    service_names = {}
    for service in services:
        path = f"/aws/service/global-infrastructure/services/{service}/longName"
        name = service_name_results.get(path)
        service_names[service] = name if name else service

    # Save to cache
    if cache_manager:
        cache_manager.save_to_cache(cache_key, service_names)

    return service_names


def generate_regional_services(
    regions: List[str], services: List[str], service_names: Dict[str, str]
) -> Dict[str, List[str]]:
    """Generate simplified regional service availability."""
    regional_services = {}

    # Core services available in most regions
    core_services = [
        "ec2",
        "s3",
        "iam",
        "cloudformation",
        "cloudwatch",
        "sns",
        "sqs",
        "lambda",
        "dynamodb",
        "rds",
    ]

    # Services that exist (have valid names)
    valid_services = [s for s in services if service_names.get(s) != s]

    for region in regions:
        if region in ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]:
            # Major regions get all valid services
            regional_services[region] = valid_services
        elif region in ["af-south-1", "ap-east-1", "eu-south-1", "me-south-1"]:
            # Newer regions get only core services
            regional_services[region] = [
                s for s in core_services if s in valid_services
            ]
        else:
            # Other regions get core services plus some extras
            available = [s for s in core_services if s in valid_services]
            # Add some common extended services
            extras = [
                "autoscaling",
                "cloudtrail",
                "config",
                "elasticache",
                "logs",
                "route53",
            ]
            available.extend([s for s in extras if s in valid_services])
            regional_services[region] = available

    return regional_services


def generate_data_matrix(
    regions: List[str],
    region_names: Dict[str, str],
    service_names: Dict[str, str],
    regional_services: Dict[str, List[str]],
) -> List[Dict]:
    """Generate the data matrix."""
    data = []

    for region_code in regions:
        region_name = region_names.get(region_code, region_code)
        services_in_region = regional_services.get(region_code, [])

        for service_code in services_in_region:
            service_name = service_names.get(service_code, service_code)
            data.append(
                {
                    "Region Code": region_code,
                    "Region Name": region_name,
                    "Service Code": service_code,
                    "Service Name": service_name,
                }
            )

    return data


def upload_to_s3(s3_client, bucket_name: str, data: List[Dict], timestamp: str):
    """Upload Excel and JSON files to S3."""

    # Generate Excel file in memory
    df = pd.DataFrame(data)
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name="AWS Regions and Services")
    excel_buffer.seek(0)

    # Upload Excel file
    excel_key = f"aws-data/aws_regions_services.xlsx"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=excel_key,
        Body=excel_buffer.getvalue(),
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Generate JSON data
    json_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_combinations": len(data),
            "unique_regions": len(set(item["Region Code"] for item in data)),
            "unique_services": len(set(item["Service Code"] for item in data)),
            "source": "AWS SSM Parameter Store - Lambda Function",
        },
        "data": data,
    }

    # Upload JSON file
    json_key = f"aws-data/aws_regions_services.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=json_key,
        Body=json.dumps(json_data, indent=2),
        ContentType="application/json",
    )

    return excel_key, json_key


def lambda_handler(event, context):
    """AWS Lambda handler function."""

    try:
        # Get S3 bucket name from environment or event
        bucket_name = event.get("bucket_name") or context.function_name + "-data"

        # Check for cache management commands
        clear_cache = event.get("clear_cache", False)
        cache_hours = event.get("cache_hours", 24)
        disable_cache = event.get("disable_cache", False)

        # Initialize AWS clients
        ssm = boto3.client("ssm", region_name="us-east-1")
        s3 = boto3.client("s3")

        # Initialize cache manager
        cache_manager = (
            None
            if disable_cache
            else S3CacheManager(bucket_name=bucket_name, cache_hours=cache_hours)
        )

        # Handle cache clearing
        if clear_cache and cache_manager:
            cleared_count = cache_manager.clear_cache()
            logger.info(f"Cleared {cleared_count} cache files from S3")

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get data
        logger.info("Starting AWS SSM data fetch...")
        regions = get_known_regions()
        services = get_known_services()

        # Fetch names (with caching)
        region_names = fetch_region_names(ssm, regions, cache_manager)
        service_names = fetch_service_names(ssm, services, cache_manager)

        # Fetch RSS data for region launch dates
        rss_data = fetch_region_rss_data(cache_manager)

        # Generate regional availability
        regional_services = generate_regional_services(regions, services, service_names)

        # Generate data matrix
        data = generate_data_matrix(
            regions, region_names, service_names, regional_services
        )

        # Upload to S3
        excel_key, json_key = upload_to_s3(s3, bucket_name, data, timestamp)

        logger.info(f"Successfully uploaded files to S3: {excel_key}, {json_key}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "AWS data fetch completed successfully",
                    "excel_file": f"s3://{bucket_name}/{excel_key}",
                    "json_file": f"s3://{bucket_name}/{json_key}",
                    "total_combinations": len(data),
                    "unique_regions": len(set(item["Region Code"] for item in data)),
                    "unique_services": len(set(item["Service Code"] for item in data)),
                }
            ),
        }

    except Exception as e:
        logger.error(f"Lambda function failed: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


if __name__ == "__main__":
    # For local testing
    test_event = {"bucket_name": "test-bucket"}
    test_context = type("Context", (), {"function_name": "aws-ssm-fetcher"})()

    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))
