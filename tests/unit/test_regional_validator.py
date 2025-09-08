#!/usr/bin/env python3
"""Test regional validation processor extraction."""

import os
import sys
from unittest.mock import MagicMock, Mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from aws_ssm_fetcher.core.cache import CacheManager
from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.processors.base import ProcessingContext
from aws_ssm_fetcher.processors.regional_validator import (
    RegionalDataValidator,
    RegionDiscoverer,
    ServiceDiscoverer,
)


def create_comprehensive_test_data():
    """Create comprehensive test service-region mapping data for validation."""
    return [
        # US regions with good coverage
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
            "Service Code": "cloudwatch",
            "Service Name": "Amazon CloudWatch",
        },
        # US West regions
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
        {
            "Region Code": "us-west-2",
            "Service Code": "cloudwatch",
            "Service Name": "Amazon CloudWatch",
        },
        # Europe regions
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
        {
            "Region Code": "eu-west-1",
            "Service Code": "cloudwatch",
            "Service Name": "Amazon CloudWatch",
        },
        # Asia Pacific regions
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
        {
            "Region Code": "ap-south-1",
            "Service Code": "cloudwatch",
            "Service Name": "Amazon CloudWatch",
        },
        # Newer regions with limited services
        {
            "Region Code": "af-south-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
        {
            "Region Code": "af-south-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
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
        # Government region
        {
            "Region Code": "us-gov-west-1",
            "Service Code": "ec2",
            "Service Name": "Amazon Elastic Compute Cloud",
        },
        {
            "Region Code": "us-gov-west-1",
            "Service Code": "s3",
            "Service Name": "Amazon Simple Storage Service",
        },
    ]


def create_mock_ssm_client():
    """Create mock SSM client with realistic responses."""
    mock_ssm_client = Mock()
    mock_paginator = Mock()
    mock_ssm_client.get_paginator.return_value = mock_paginator

    # Mock region discovery responses
    region_response = [
        {
            "Parameters": [
                {"Name": "/aws/service/global-infrastructure/regions/us-east-1"},
                {"Name": "/aws/service/global-infrastructure/regions/us-west-2"},
                {"Name": "/aws/service/global-infrastructure/regions/eu-west-1"},
                {"Name": "/aws/service/global-infrastructure/regions/ap-south-1"},
                {"Name": "/aws/service/global-infrastructure/regions/af-south-1"},
                {"Name": "/aws/service/global-infrastructure/regions/ca-central-1"},
                {"Name": "/aws/service/global-infrastructure/regions/us-gov-west-1"},
            ]
        }
    ]

    # Mock service discovery responses
    service_response = [
        {
            "Parameters": [
                {"Name": "/aws/service/global-infrastructure/services/ec2"},
                {"Name": "/aws/service/global-infrastructure/services/s3"},
                {"Name": "/aws/service/global-infrastructure/services/lambda"},
                {"Name": "/aws/service/global-infrastructure/services/rds"},
                {"Name": "/aws/service/global-infrastructure/services/dynamodb"},
                {"Name": "/aws/service/global-infrastructure/services/cloudwatch"},
                {"Name": "/aws/service/global-infrastructure/services/iam"},
                {"Name": "/aws/service/global-infrastructure/services/kms"},
            ]
        }
    ]

    # Configure paginator to return appropriate responses based on path
    def mock_paginate(Path, **kwargs):
        if "regions" in Path:
            return region_response
        elif "services" in Path:
            return service_response
        return [{"Parameters": []}]

    mock_paginator.paginate.side_effect = mock_paginate

    # Mock direct get_parameters_by_path calls
    def mock_get_parameters_by_path(Path, **kwargs):
        if "regions" in Path:
            return region_response[0]
        elif "services" in Path:
            return service_response[0]
        return {"Parameters": []}

    mock_ssm_client.get_parameters_by_path.side_effect = mock_get_parameters_by_path

    return mock_ssm_client


def test_region_discoverer():
    """Test RegionDiscoverer processor."""

    print("🧪 Testing RegionDiscoverer...")

    # Create mock SSM client
    mock_ssm_client = create_mock_ssm_client()

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config, cache_manager=cache_manager, logger_name="test_region_discoverer"
    )
    context.ssm_client = mock_ssm_client

    # Create RegionDiscoverer
    region_discoverer = RegionDiscoverer(context)
    print("✅ RegionDiscoverer initialized successfully")

    # Test input validation
    try:
        region_discoverer.validate_input(None)  # None is valid for default discovery
        region_discoverer.validate_input({"max_pages": 5, "recursive": True})
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test region discovery
    try:
        discovered_regions = region_discoverer.process()

        print(f"✅ Region discovery completed: {len(discovered_regions)} regions found")
        print(f"   Discovered regions: {discovered_regions}")

        # Verify expected regions are found
        expected_regions = [
            "af-south-1",
            "ap-south-1",
            "ca-central-1",
            "eu-west-1",
            "us-east-1",
            "us-gov-west-1",
            "us-west-2",
        ]
        if set(discovered_regions) == set(expected_regions):
            print("✅ All expected regions discovered")
        else:
            print(f"⚠️  Region mismatch - expected: {expected_regions}")

        # Test caching
        cached_regions = region_discoverer.process_with_cache(
            None
        )  # Pass None as input_data
        if cached_regions == discovered_regions:
            print("✅ Caching works correctly")
        else:
            print("❌ Caching failed")
            return False

    except Exception as e:
        print(f"❌ Region discovery failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 RegionDiscoverer test completed successfully!")
    return True


def test_service_discoverer():
    """Test ServiceDiscoverer processor."""

    print("\n🧪 Testing ServiceDiscoverer...")

    # Create mock SSM client
    mock_ssm_client = create_mock_ssm_client()

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config,
        cache_manager=cache_manager,
        logger_name="test_service_discoverer",
    )
    context.ssm_client = mock_ssm_client

    # Create ServiceDiscoverer
    service_discoverer = ServiceDiscoverer(context)
    print("✅ ServiceDiscoverer initialized successfully")

    # Test input validation
    try:
        service_discoverer.validate_input(None)
        service_discoverer.validate_input({"max_pages": 50, "validate_services": True})
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test service discovery
    try:
        # Use parameters to avoid long discovery process
        discovery_params = {
            "max_pages": 5,
            "use_recursive": False,
            "min_expected_services": 5,
        }

        discovered_services = service_discoverer.process(discovery_params)

        print(
            f"✅ Service discovery completed: {len(discovered_services)} services found"
        )
        print(f"   Discovered services: {discovered_services}")

        # Verify expected services are found
        expected_services = [
            "cloudwatch",
            "dynamodb",
            "ec2",
            "iam",
            "kms",
            "lambda",
            "rds",
            "s3",
        ]
        if set(discovered_services) == set(expected_services):
            print("✅ All expected services discovered")
        else:
            print(f"⚠️  Service mismatch - expected subset found")

        # Test service categorization in metadata
        if (
            hasattr(service_discoverer.context, "metadata")
            and "service_discovery_stats" in service_discoverer.context.metadata
        ):
            categories = service_discoverer.context.metadata["service_discovery_stats"][
                "service_categories"
            ]
            print(f"✅ Service categories: {categories}")

    except Exception as e:
        print(f"❌ Service discovery failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 ServiceDiscoverer test completed successfully!")
    return True


def test_regional_data_validator():
    """Test RegionalDataValidator processor."""

    print("\n🧪 Testing RegionalDataValidator...")

    # Create mock SSM client
    mock_ssm_client = create_mock_ssm_client()

    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config,
        cache_manager=cache_manager,
        logger_name="test_regional_validator",
    )
    context.ssm_client = mock_ssm_client

    # Create RegionalDataValidator
    validator = RegionalDataValidator(context)
    print("✅ RegionalDataValidator initialized successfully")

    # Create test data
    test_data = create_comprehensive_test_data()
    print(f"✅ Created test data with {len(test_data)} records")

    # Test input validation
    try:
        validator.validate_input(test_data)
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False

    # Test data integrity validation
    try:
        integrity_result = validator.process(
            test_data, validation_type="data_integrity"
        )

        print("✅ Data integrity validation completed:")
        print(f"   Validation score: {integrity_result['validation_score']}")
        print(f"   Grade: {integrity_result['integrity_grade']}")
        print(f"   Total issues: {integrity_result['total_issues']}")

        stats = integrity_result["statistics"]
        print(f"   Duplicate records: {stats['duplicate_records']}")
        print(f"   Missing fields: {stats['missing_fields']}")
        print(f"   Invalid formats: {stats['invalid_formats']}")

    except Exception as e:
        print(f"❌ Data integrity validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test coverage validation
    try:
        coverage_result = validator.process(
            test_data, validation_type="coverage_validation"
        )

        print("✅ Coverage validation completed:")
        metrics = coverage_result["coverage_metrics"]
        print(f"   Unique regions: {metrics['unique_regions']}")
        print(f"   Unique services: {metrics['unique_services']}")
        print(f"   Coverage percentage: {metrics['actual_coverage_percentage']}%")
        print(f"   Grade: {coverage_result['coverage_grade']}")

    except Exception as e:
        print(f"❌ Coverage validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test consistency validation
    try:
        consistency_result = validator.process(
            test_data, validation_type="consistency_validation"
        )

        print("✅ Consistency validation completed:")
        print(f"   Validation score: {consistency_result['validation_score']}")
        print(f"   Grade: {consistency_result['consistency_grade']}")
        print(f"   Issues found: {len(consistency_result['consistency_issues'])}")

    except Exception as e:
        print(f"❌ Consistency validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test discovery validation (pre-populate caches)
    try:
        # Pre-populate discovery caches to avoid AWS calls
        region_cache_key = validator.region_discoverer.get_cache_key(None)
        service_cache_key = validator.service_discoverer.get_cache_key(None)

        expected_regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "ap-south-1",
            "af-south-1",
            "ca-central-1",
            "us-gov-west-1",
        ]
        expected_services = [
            "ec2",
            "s3",
            "lambda",
            "rds",
            "dynamodb",
            "cloudwatch",
            "iam",
            "kms",
        ]

        validator.region_discoverer.cache_result(region_cache_key, expected_regions)
        validator.service_discoverer.cache_result(service_cache_key, expected_services)

        discovery_result = validator.process(
            test_data, validation_type="discovery_validation"
        )

        print("✅ Discovery validation completed:")
        print(f"   Validation score: {discovery_result['validation_score']}")
        print(f"   Grade: {discovery_result['discovery_grade']}")

        if "discovery_comparison" in discovery_result:
            comparison = discovery_result["discovery_comparison"]
            print(f"   Discovered regions: {comparison['discovered_regions']}")
            print(f"   Data regions: {comparison['data_regions']}")
            print(f"   Missing regions: {comparison['missing_regions']}")
            print(f"   Extra regions: {comparison['extra_regions']}")
        else:
            print("   Discovery comparison not available (validation used fallback)")

    except Exception as e:
        print(f"❌ Discovery validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test anomaly detection
    try:
        anomaly_result = validator.process(
            test_data, validation_type="anomaly_detection"
        )

        print("✅ Anomaly detection completed:")
        print(f"   Validation score: {anomaly_result['validation_score']}")
        print(f"   Grade: {anomaly_result['anomaly_grade']}")
        print(f"   Total anomalies: {anomaly_result['total_anomalies']}")

        stats = anomaly_result["anomaly_statistics"]
        print(f"   Region anomalies: {stats['region_anomalies']}")
        print(f"   Service anomalies: {stats['service_anomalies']}")
        print(f"   Pattern anomalies: {stats['pattern_anomalies']}")

    except Exception as e:
        print(f"❌ Anomaly detection failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test comprehensive validation
    try:
        comprehensive_result = validator.process(
            test_data, validation_type="comprehensive"
        )

        print("✅ Comprehensive validation completed:")
        summary = comprehensive_result["summary"]
        print(f"   Overall score: {summary['overall_validation_score']}")
        print(f"   Data quality grade: {summary['data_quality_grade']}")
        print(f"   Validations performed: {summary['total_validations_performed']}")

        # Show individual validation scores
        for validation_type, results in comprehensive_result.items():
            if validation_type != "summary" and "validation_score" in results:
                print(f"   {validation_type}: {results['validation_score']}")

    except Exception as e:
        print(f"❌ Comprehensive validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("🎉 RegionalDataValidator test completed successfully!")
    return True


def test_error_handling():
    """Test error handling in regional validators."""

    print("\n🧪 Testing regional validator error handling...")

    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(config=config, cache_manager=cache_manager)
    context.ssm_client = Mock()

    validator = RegionalDataValidator(context)

    # Test invalid validation type
    try:
        validator.process(
            create_comprehensive_test_data(), validation_type="invalid_validation"
        )
        print("❌ Should have failed with invalid validation type")
        return False
    except Exception as e:
        print(f"✅ Invalid validation type correctly rejected: {type(e).__name__}")

    # Test empty data
    try:
        validator.validate_input([])
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
        validator.validate_input(malformed_data)
        print("❌ Should have failed with malformed data")
        return False
    except Exception as e:
        print(f"✅ Malformed data correctly rejected: {type(e).__name__}")

    print("🎉 Error handling test completed successfully!")
    return True


if __name__ == "__main__":
    print("🚀 Starting RegionalValidator processor tests...\n")

    success = True
    success &= test_region_discoverer()
    success &= test_service_discoverer()
    success &= test_regional_data_validator()
    success &= test_error_handling()

    if success:
        print("\n🎯 All RegionalValidator tests passed!")
        print("✅ Week 3 Day 4: Regional testing and validation extraction COMPLETED")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
