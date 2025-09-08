#!/usr/bin/env python3
"""Test data transformation processor extraction."""

import sys
import os
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.core.cache import CacheManager
from aws_ssm_fetcher.processors.base import ProcessingContext
from aws_ssm_fetcher.processors.data_transformer import DataTransformer

def create_test_data():
    """Create test service-region mapping data."""
    return [
        {'Region Code': 'us-east-1', 'Service Code': 'ec2', 'Service Name': 'Amazon Elastic Compute Cloud'},
        {'Region Code': 'us-east-1', 'Service Code': 's3', 'Service Name': 'Amazon Simple Storage Service'},
        {'Region Code': 'us-east-1', 'Service Code': 'lambda', 'Service Name': 'AWS Lambda'},
        {'Region Code': 'us-west-2', 'Service Code': 'ec2', 'Service Name': 'Amazon Elastic Compute Cloud'},
        {'Region Code': 'us-west-2', 'Service Code': 's3', 'Service Name': 'Amazon Simple Storage Service'},
        {'Region Code': 'eu-west-1', 'Service Code': 'ec2', 'Service Name': 'Amazon Elastic Compute Cloud'},
        {'Region Code': 'eu-west-1', 'Service Code': 'lambda', 'Service Name': 'AWS Lambda'},
        {'Region Code': 'ap-south-1', 'Service Code': 's3', 'Service Name': 'Amazon Simple Storage Service'}
    ]

def test_data_transformer():
    """Test DataTransformer processor."""
    
    print("🧪 Testing DataTransformer processor...")
    
    # Create processing context
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(
        config=config,
        cache_manager=cache_manager,
        logger_name="test_transformer"
    )
    
    # Create DataTransformer
    transformer = DataTransformer(context)
    print("✅ DataTransformer initialized successfully")
    
    # Create test data
    test_data = create_test_data()
    print(f"✅ Created test data with {len(test_data)} records")
    
    # Test input validation
    try:
        transformer.validate_input(test_data)
        print("✅ Input validation passed")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")
        return False
    
    # Test invalid input
    try:
        transformer.validate_input("not a list")
        print("❌ Should have failed validation")
        return False
    except Exception:
        print("✅ Invalid input correctly rejected")
    
    # Test service matrix transformation
    try:
        service_matrix = transformer.process(test_data, transformation_type="service_matrix")
        print(f"✅ Service matrix generated: {service_matrix.shape}")
        print(f"   Services: {list(service_matrix['Service'])}")
        print(f"   Regions: {[col for col in service_matrix.columns if col != 'Service']}")
    except Exception as e:
        print(f"❌ Service matrix generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test region summary transformation
    try:
        region_names = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-south-1': 'Asia Pacific (Mumbai)'
        }
        
        region_summary = transformer.process(
            test_data, 
            transformation_type="region_summary",
            region_names=region_names
        )
        print(f"✅ Region summary generated: {region_summary.shape}")
        print(f"   Regions: {list(region_summary['Region Code'])}")
        print(f"   Service counts: {list(region_summary['Service Count'])}")
    except Exception as e:
        print(f"❌ Region summary generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test service summary transformation
    try:
        all_services = ['ec2', 's3', 'lambda', 'rds', 'dynamodb']
        service_names = {
            'ec2': 'Amazon Elastic Compute Cloud',
            's3': 'Amazon Simple Storage Service',
            'lambda': 'AWS Lambda',
            'rds': 'Amazon Relational Database Service',
            'dynamodb': 'Amazon DynamoDB'
        }
        
        service_summary = transformer.process(
            test_data,
            transformation_type="service_summary",
            all_services=all_services,
            service_names=service_names
        )
        print(f"✅ Service summary generated: {service_summary.shape}")
        print(f"   Services analyzed: {len(service_summary)}")
    except Exception as e:
        print(f"❌ Service summary generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test statistics generation
    try:
        statistics = transformer.process(
            test_data,
            transformation_type="statistics",
            all_services=all_services
        )
        print(f"✅ Statistics generated: {statistics.shape}")
        print(f"   Total regions in stats: {statistics.iloc[4, 1] if len(statistics) > 4 else 'N/A'}")
    except Exception as e:
        print(f"❌ Statistics generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test coverage analysis
    try:
        coverage_analysis = transformer.process(
            test_data,
            transformation_type="coverage_analysis",
            all_services=all_services
        )
        print(f"✅ Coverage analysis generated")
        print(f"   Total mappings: {coverage_analysis['overview']['total_mappings']}")
        print(f"   Avg services per region: {coverage_analysis['overview']['avg_services_per_region']}")
    except Exception as e:
        print(f"❌ Coverage analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test hierarchical transformation
    try:
        hierarchical = transformer.transform_to_hierarchical(test_data, group_by='Region Code')
        print(f"✅ Hierarchical transformation generated")
        print(f"   Regions: {list(hierarchical.keys())}")
        print(f"   US-East-1 services: {len(hierarchical.get('us-east-1', []))}")
    except Exception as e:
        print(f"❌ Hierarchical transformation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test filters
    try:
        filtered_data = transformer.apply_filters(
            test_data,
            {'Region Code': ['us-east-1', 'us-west-2']}
        )
        print(f"✅ Filters applied successfully")
        print(f"   Original: {len(test_data)} records, Filtered: {len(filtered_data)} records")
    except Exception as e:
        print(f"❌ Filter application failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test processing stats
    try:
        processing_stats = transformer.get_processing_stats()
        print(f"✅ Processing stats: {processing_stats}")
    except Exception as e:
        print(f"❌ Processing stats failed: {e}")
        return False
    
    print("🎉 DataTransformer processor test completed successfully!")
    return True

def test_error_handling():
    """Test error handling in DataTransformer."""
    
    print("\n🧪 Testing DataTransformer error handling...")
    
    config = Config()
    cache_manager = CacheManager(config)
    context = ProcessingContext(config=config, cache_manager=cache_manager)
    transformer = DataTransformer(context)
    
    # Test invalid transformation type
    try:
        transformer.process(create_test_data(), transformation_type="invalid_type")
        print("❌ Should have failed with invalid transformation type")
        return False
    except Exception as e:
        print(f"✅ Invalid transformation type correctly rejected: {type(e).__name__}")
    
    # Test empty data
    try:
        transformer.validate_input([])
        print("❌ Should have failed with empty data")
        return False
    except Exception as e:
        print(f"✅ Empty data correctly rejected: {type(e).__name__}")
    
    # Test malformed data
    try:
        malformed_data = [
            {'Region Code': 'us-east-1'},  # Missing required fields
            {'Service Code': 'ec2'}       # Missing required fields
        ]
        transformer.validate_input(malformed_data)
        print("❌ Should have failed with malformed data")
        return False
    except Exception as e:
        print(f"✅ Malformed data correctly rejected: {type(e).__name__}")
    
    print("🎉 Error handling test completed successfully!")
    return True

if __name__ == "__main__":
    print("🚀 Starting DataTransformer processor tests...\n")
    
    success = True
    success &= test_data_transformer()
    success &= test_error_handling()
    
    if success:
        print("\n🎯 All DataTransformer tests passed!")
        print("✅ Week 3 Day 2: Data transformation engine extraction COMPLETED")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)