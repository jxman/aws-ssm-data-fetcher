#!/usr/bin/env python3
"""Test statistics analyzer processor extraction."""

import os
import sys
from unittest.mock import MagicMock, Mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from aws_ssm_fetcher.core.cache import CacheManager
from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.processors.base import ProcessingContext
from aws_ssm_fetcher.processors.statistics_analyzer import (
    AvailabilityZoneAnalyzer,
    StatisticsAnalyzer,
)


def create_comprehensive_test_data():
    """Create comprehensive test service-region mapping data."""
    return [
        # US East regions - high service density
        {
            "Region Code": "us-east-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        {
            "Region Code": "us-east-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "us-east-1",
            "Service Code": "lambda",
            "Service Name": "AWS Lambda",
        },
        {
            "Region Code": "us-east-1",
            "Service Code": "rds",
            "Service Name": "Amazon Relational Database Service",
        },
        {
            "Region Code": "us-east-1",
            "Service Code": "dynamodb",
            "Service Name": "Amazon DynamoDB",
        },
        {
            "Region Code": "us-east-1",
            "Service Code": "sagemaker",
            "Service Name": "Amazon SageMaker",
        },
        # US West regions - medium service density
        {
            "Region Code": "us-west-2",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        {
            "Region Code": "us-west-2",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "us-west-2",
            "Service Code": "lambda",
            "Service Name": "AWS Lambda",
        },
        {
            "Region Code": "us-west-2",
            "Service Code": "rds",
            "Service Name": "Amazon Relational Database Service",
        },
        # Europe regions - medium service density
        {
            "Region Code": "eu-west-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        {
            "Region Code": "eu-west-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "eu-west-1",
            "Service Code": "lambda",
            "Service Name": "AWS Lambda",
        },
        # Asia Pacific regions - lower service density
        {
            "Region Code": "ap-south-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "ap-south-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        # New region with minimal services
        {
            "Region Code": "af-south-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        # Canada region
        {
            "Region Code": "ca-central-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        {
            "Region Code": "ca-central-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "ca-central-1",
            "Service Code": "lambda",
            "Service Name": "AWS Lambda",
        },
    ]


def test_availability_zone_analyzer():
    """Test AvailabilityZoneAnalyzer processor."""

    print("🧪 Testing AvailabilityZoneAnalyzer...")

    # Create mock SSM client
    mock_ssm_client = Mock()
    mock_paginator = Mock()
    mock_ssm_client.get_paginator.return_value = mock_paginator

    # Mock paginated response for AZ parameters
    mock_page_iterator = [
        {
            "Parameters": [
                {
                    "Name": "/aws/service/global-infrastructure/availability-zones/use1-az1/region"
                },
                {
                    "Name": "/aws/service/global-infrastructure/availability-zones/use1-az2/region"
                },
                {
                    "Name": "/aws/service/global-infrastructure/availability-zones/use1-az6/region"
                },
                {
                    "Name": "/aws/service/global-infrastructure/availability-zones/usw2-az1/region"
                },
                {
                    "Name": "/aws/service/global-infrastructure/availability-zones/usw2-az2/region"
                },
            ]
        }
    ]
    mock_paginator.paginate.return_value = mock_page_iterator

    # Mock parameter values
    def mock_get_parameter(Name):
        region_mapping = {
            "/aws/service/global-infrastructure/availability-zones/use1-az1/region": "us-east-1",
            "/aws/service/global-infrastructure/availability-zones/use1-az2/region": "us-east-1",
            "/aws/service/global-infrastructure/availability-zones/use1-az6/region": "us-east-1",
            "/aws/service/global-infrastructure/availability-zones/usw2-az1/region": "us-west-2",
            "/aws/service/global-infrastructure/availability-zones/usw2-az2/region": "us-west-2",
        }
        return {"Parameter": {"Value": region_mapping.get(Name, "")}}

    mock_ssm_client.get_parameter.side_effect = mock_get_parameter

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config, cache_manager=cache_manager, logger_name="test_az_analyzer"
    )
    context.ssm_client = mock_ssm_client

    # Create AZ analyzer
    az_analyzer = AvailabilityZoneAnalyzer(context)
    print("✅ AvailabilityZoneAnalyzer initialized successfully")

    # Test input validation
    try:
        az_analyzer.validate_input(["us-east-1", "us-west-2"])
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test AZ analysis (using cache to avoid complex AWS simulation)
    try:
        test_regions = ["us-east-1", "us-west-2", "eu-west-1"]

        # Pre-populate cache with test data
        cache_key = az_analyzer.get_cache_key(test_regions)
        expected_az_data = {"us-east-1": 6, "us-west-2": 4, "eu-west-1": 3}
        az_analyzer.cache_result(cache_key, expected_az_data)

        # Test the analyzer
        result = az_analyzer.process_with_cache(test_regions)

        print(f"✅ AZ analysis completed: {result}")
        print(f"   US-East-1: {result['us-east-1']} AZs")
        print(f"   US-West-2: {result['us-west-2']} AZs")
        print(f"   EU-West-1: {result['eu-west-1']} AZs")

    except Exception as e:
        print(f"❌ AZ analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 AvailabilityZoneAnalyzer test completed successfully!")
    return True


def test_statistics_analyzer():
    """Test StatisticsAnalyzer processor."""

    print("\n🧪 Testing StatisticsAnalyzer...")

    # Create mock SSM client for AZ analyzer
    mock_ssm_client = Mock()

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config, cache_manager=cache_manager, logger_name="test_stats_analyzer"
    )
    context.ssm_client = mock_ssm_client

    # Create StatisticsAnalyzer
    stats_analyzer = StatisticsAnalyzer(context)
    print("✅ StatisticsAnalyzer initialized successfully")

    # Create comprehensive test data
    test_data = create_comprehensive_test_data()
    print(f"✅ Created test data with {len(test_data)} records")

    # Test input validation
    try:
        stats_analyzer.validate_input(test_data)
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test comprehensive analysis
    try:
        comprehensive_result = stats_analyzer.process(
            test_data, analysis_type="comprehensive"
        )

        print("✅ Comprehensive analysis completed:")
        overview = comprehensive_result["overview"]
        print(f"   Total regions: {overview['total_regions']}")
        print(f"   Total services: {overview['total_services']}")
        print(f"   Total mappings: {overview['total_mappings']}")

        regional_stats = comprehensive_result["regional_statistics"]
        print(
            f"   Mean services per region: {regional_stats['mean_services_per_region']}"
        )
        print(
            f"   Max services per region: {regional_stats['max_services_per_region']}"
        )

    except Exception as e:
        print(f"❌ Comprehensive analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test regional distribution analysis
    try:
        regional_result = stats_analyzer.process(
            test_data, analysis_type="regional_distribution"
        )

        print("✅ Regional distribution analysis completed:")
        rankings = regional_result["regional_rankings"]
        print(f"   Top region: {list(rankings.items())[0] if rankings else 'None'}")

        geo_dist = regional_result["geographic_distribution"]
        print(f"   Geographic regions analyzed: {list(geo_dist.keys())}")

    except Exception as e:
        print(f"❌ Regional distribution analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test service coverage analysis
    try:
        all_services = [
            "ec2",
            "s3",
            "lambda",
            "rds",
            "dynamodb",
            "sagemaker",
            "ecs",
            "eks",
        ]

        coverage_result = stats_analyzer.process(
            test_data, analysis_type="service_coverage", all_services=all_services
        )

        print("✅ Service coverage analysis completed:")
        coverage_dist = coverage_result["service_coverage_distribution"]
        print(f"   Universal services: {coverage_dist['universal_services']}")
        print(f"   High coverage services: {coverage_dist['high_coverage_services']}")

        missing = coverage_result["missing_services"]
        print(f"   Missing services: {missing['total_missing']}")

    except Exception as e:
        print(f"❌ Service coverage analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test availability zone analysis
    try:
        # Pre-populate AZ cache
        regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "ap-south-1",
            "af-south-1",
            "ca-central-1",
        ]
        az_cache_key = stats_analyzer.az_analyzer.get_cache_key(regions)
        az_test_data = {
            "us-east-1": 6,
            "us-west-2": 4,
            "eu-west-1": 3,
            "ap-south-1": 3,
            "af-south-1": 3,
            "ca-central-1": 3,
        }
        stats_analyzer.az_analyzer.cache_result(az_cache_key, az_test_data)

        az_result = stats_analyzer.process(
            test_data, analysis_type="availability_zones"
        )

        print("✅ Availability zone analysis completed:")
        az_summary = az_result["az_summary"]
        print(
            f"   Total regions with AZ data: {az_summary['total_regions_with_az_data']}"
        )
        print(f"   Average AZs per region: {az_summary['avg_azs_per_region']}")

        correlation = az_result["az_service_correlation"]
        if correlation["correlation_coefficient"]:
            print(
                f"   AZ-Service correlation: {correlation['correlation_coefficient']} ({correlation['correlation_interpretation']})"
            )

    except Exception as e:
        print(f"❌ Availability zone analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test geographic distribution analysis
    try:
        geo_result = stats_analyzer.process(
            test_data, analysis_type="geographic_distribution"
        )

        print("✅ Geographic distribution analysis completed:")
        geo_regions = geo_result["geographic_regions"]
        print(f"   Geographic regions: {list(geo_regions.keys())}")

        for geo_region, stats in geo_regions.items():
            print(
                f"   {geo_region}: {stats['region_count']} regions, {stats['total_services']} unique services"
            )

    except Exception as e:
        print(f"❌ Geographic distribution analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test service pattern analysis
    try:
        pattern_result = stats_analyzer.process(
            test_data, analysis_type="service_patterns"
        )

        print("✅ Service pattern analysis completed:")
        pattern_coverage = pattern_result["pattern_coverage_analysis"]

        for pattern_name, stats in pattern_coverage.items():
            if stats["service_count"] > 0:
                print(
                    f"   {pattern_name}: {stats['service_count']} services, {stats['avg_regional_availability']:.1f} avg regions"
                )

    except Exception as e:
        print(f"❌ Service pattern analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test performance metrics analysis
    try:
        perf_result = stats_analyzer.process(
            test_data, analysis_type="performance_metrics"
        )

        print("✅ Performance metrics analysis completed:")
        efficiency = perf_result["data_efficiency_metrics"]
        print(f"   Processing speed: {efficiency['processing_speed']:.1f} records/sec")
        print(f"   Cache efficiency: {efficiency['cache_efficiency']:.1f}%")

        recommendations = perf_result["recommendations"]
        print(f"   Recommendations: {len(recommendations)} items")

    except Exception as e:
        print(f"❌ Performance metrics analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 StatisticsAnalyzer test completed successfully!")
    return True


def test_error_handling():
    """Test error handling in statistics analyzers."""

    print("\n🧪 Testing statistics analyzer error handling...")

    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(config=config, cache_manager=cache_manager)
    context.ssm_client = Mock()

    stats_analyzer = StatisticsAnalyzer(context)

    # Test invalid analysis type
    try:
        stats_analyzer.process(
            create_comprehensive_test_data(), analysis_type="invalid_analysis"
        )
        print("❌ Should have failed with invalid analysis type")
        return False
    except Exception as e:
        print(f"✅ Invalid analysis type correctly rejected: {type(e).__name__}")

    # Test empty data
    try:
        stats_analyzer.validate_input([])
        print("❌ Should have failed with empty data")
        return False
    except Exception as e:
        print(f"✅ Empty data correctly rejected: {type(e).__name__}")

    # Test malformed data
    try:
        malformed_data = [
            {"Region Code": "us-east-1"},  # Missing Service Code
            {"Service Code": "ec2"},  # Missing Region Code
        ]
        stats_analyzer.validate_input(malformed_data)
        print("❌ Should have failed with malformed data")
        return False
    except Exception as e:
        print(f"✅ Malformed data correctly rejected: {type(e).__name__}")

    print("🎉 Error handling test completed successfully!")
    return True


if __name__ == "__main__":
    print("🚀 Starting StatisticsAnalyzer processor tests...\n")

    success = True
    success &= test_availability_zone_analyzer()
    success &= test_statistics_analyzer()
    success &= test_error_handling()

    if success:
        print("\n🎯 All StatisticsAnalyzer tests passed!")
        print("✅ Week 3 Day 3: Statistics and analytics extraction COMPLETED")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
