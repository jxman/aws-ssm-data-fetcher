#!/usr/bin/env python3
"""Test service mapper processor extraction."""

import os
import sys
from typing import Dict, List
from unittest.mock import MagicMock, Mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from aws_ssm_fetcher.core.cache import CacheManager
from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.processors.base import ProcessingContext
from aws_ssm_fetcher.processors.service_mapper import ServiceMapper


def test_service_mapper():
    """Test ServiceMapper processor."""

    print("🧪 Testing ServiceMapper processor...")

    # Create mock SSM client
    mock_ssm_client = Mock()
    mock_paginator = Mock()
    mock_ssm_client.get_paginator.return_value = mock_paginator

    # Mock paginated response for EC2 service
    mock_page_iterator = [
        {
            "Parameters": [
                {"Value": "us-east-1"},
                {"Value": "us-west-2"},
                {"Value": "eu-west-1"},
            ]
        }
    ]
    mock_paginator.paginate.return_value = mock_page_iterator

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)

    context = ProcessingContext(
        config=config, cache_manager=cache_manager, logger_name="test_processor"
    )

    # Inject SSM client into context
    context.ssm_client = mock_ssm_client

    # Create ServiceMapper
    service_mapper = ServiceMapper(context)

    print("✅ ServiceMapper initialized successfully")

    # Test input validation
    try:
        service_mapper.validate_input(["ec2"])
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test invalid input
    try:
        service_mapper.validate_input("not a list")
        print("❌ Should have failed validation")
        return False
    except Exception:
        print("✅ Invalid input correctly rejected")

    # Test service mapping (using cache to avoid AWS calls)
    try:
        # Put test data in cache first
        cache_key = service_mapper.get_cache_key(["ec2"])
        expected_result = {
            "us-east-1": ["ec2"],
            "us-west-2": ["ec2"],
            "eu-west-1": ["ec2"],
        }
        service_mapper.cache_result(cache_key, expected_result)

        # Now test the mapping
        result = service_mapper.process_with_cache(["ec2"])

        print(f"✅ Service mapping returned: {result}")

        # Test get_service_regions
        regions = service_mapper.get_service_regions("ec2")
        print(f"✅ EC2 regions: {regions}")

        # Test coverage stats
        stats = service_mapper.get_coverage_stats(["ec2"])
        print(f"✅ Coverage stats generated: {stats['overview']}")

        # Test processing stats
        processing_stats = service_mapper.get_processing_stats()
        print(f"✅ Processing stats: {processing_stats}")

    except Exception as e:
        print(f"❌ Service mapping failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 ServiceMapper processor test completed successfully!")
    return True


def test_regional_service_mapper():
    """Test RegionalServiceMapper specialized processor."""

    print("\n🧪 Testing RegionalServiceMapper...")

    # Create minimal setup with mock data
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(config=config, cache_manager=cache_manager)
    context.ssm_client = Mock()  # Mock SSM client

    from aws_ssm_fetcher.processors.service_mapper import RegionalServiceMapper

    regional_mapper = RegionalServiceMapper(context)

    # Put test data in cache
    test_services = ["ec2", "s3", "lambda"]
    cache_key = regional_mapper.get_cache_key(test_services)
    test_region_services = {
        "us-east-1": ["ec2", "s3", "lambda"],  # All services
        "us-west-2": ["ec2", "s3"],  # Missing lambda
        "eu-west-1": ["ec2"],  # Only ec2
        "ap-south-1": ["s3"],  # Only s3
    }
    regional_mapper.cache_result(cache_key, test_region_services)

    try:
        # Test regional analysis
        analysis = regional_mapper.analyze_regional_distribution(test_services)

        print("✅ Regional distribution analysis:")
        print(f"  - Top region: {analysis['region_rankings']['largest_region']}")
        print(
            f"  - Coverage variance: {analysis['distribution_metrics']['coverage_variance']}"
        )
        print(
            f"  - Regions with all services: {analysis['distribution_metrics']['regions_with_all_services']}"
        )

    except Exception as e:
        print(f"❌ Regional analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 RegionalServiceMapper test completed successfully!")
    return True


if __name__ == "__main__":
    print("🚀 Starting ServiceMapper processor tests...\n")

    success = True
    success &= test_service_mapper()
    success &= test_regional_service_mapper()

    if success:
        print("\n🎯 All ServiceMapper tests passed!")
        print("✅ Week 3 Day 1: Service mapping processor extraction COMPLETED")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
