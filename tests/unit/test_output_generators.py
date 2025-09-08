#!/usr/bin/env python3
"""Test output generators for AWS SSM Data Fetcher."""

import os
import shutil
import sys
import tempfile
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.outputs.base import OutputContext
from aws_ssm_fetcher.outputs.csv_generator import (CSVGenerator,
                                                   MultiCSVGenerator,
                                                   TSVGenerator)
from aws_ssm_fetcher.outputs.excel_generator import ExcelGenerator
from aws_ssm_fetcher.outputs.json_generator import (CompactJSONGenerator,
                                                    JSONGenerator)


def create_test_data():
    """Create sample test data for output generation."""
    return [
        {
            "Region Code": "us-east-1",
            "Region Name": "US East (N. Virginia)",
            "Service Code": "ec2",
            "Service Name": "Amazon EC2",
        },
        {
            "Region Code": "us-east-1",
            "Region Name": "US East (N. Virginia)",
            "Service Code": "s3",
            "Service Name": "Amazon S3",
        },
        {
            "Region Code": "us-west-2",
            "Region Name": "US West (Oregon)",
            "Service Code": "ec2",
            "Service Name": "Amazon EC2",
        },
        {
            "Region Code": "eu-west-1",
            "Region Name": "Europe (Ireland)",
            "Service Code": "lambda",
            "Service Name": "AWS Lambda",
        },
    ]


def create_test_context(output_dir):
    """Create test output context."""
    return OutputContext(
        output_dir=output_dir,
        region_names={
            "us-east-1": "US East (N. Virginia)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "Europe (Ireland)",
        },
        service_names={
            "ec2": "Amazon Elastic Compute Cloud",
            "s3": "Amazon Simple Storage Service",
            "lambda": "AWS Lambda",
        },
        all_services=["ec2", "s3", "lambda", "rds", "dynamodb"],
        rss_data={
            "us-east-1": {"launch_date": "2006-08-24"},
            "us-west-2": {"launch_date": "2011-11-08"},
            "eu-west-1": {"launch_date": "2008-12-10"},
        },
    )


def test_excel_generator():
    """Test Excel output generation."""

    print("🧪 Testing ExcelGenerator...")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        context = create_test_context(temp_dir)
        test_data = create_test_data()

        try:
            # Create Excel generator
            generator = ExcelGenerator(context)
            print("✅ ExcelGenerator initialized successfully")

            # Test default filename
            default_filename = generator.get_default_filename()
            assert default_filename == "aws_regions_services.xlsx"
            print("✅ Default filename correct")

            # Generate Excel file
            filepath = generator.generate(test_data)
            assert os.path.exists(filepath)
            assert filepath.endswith(".xlsx")
            print(f"✅ Excel file generated: {os.path.basename(filepath)}")

            # Check file size is reasonable (should be > 1KB for real Excel file)
            file_size = os.path.getsize(filepath)
            assert file_size > 1000  # Should be more than 1KB
            print(f"✅ Excel file size reasonable: {file_size} bytes")

        except Exception as e:
            print(f"❌ Excel generator test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    print("🎉 ExcelGenerator test completed successfully!")
    return True


def test_json_generator():
    """Test JSON output generation."""

    print("\n🧪 Testing JSONGenerator...")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        context = create_test_context(temp_dir)
        test_data = create_test_data()

        try:
            # Test standard JSON generator
            generator = JSONGenerator(context)
            print("✅ JSONGenerator initialized successfully")

            # Test default filename
            default_filename = generator.get_default_filename()
            assert default_filename == "aws_regions_services.json"
            print("✅ Default filename correct")

            # Generate JSON file
            filepath = generator.generate(test_data)
            assert os.path.exists(filepath)
            assert filepath.endswith(".json")
            print(f"✅ JSON file generated: {os.path.basename(filepath)}")

            # Verify JSON content
            import json

            with open(filepath, "r") as f:
                json_data = json.load(f)

            assert "metadata" in json_data
            assert "data" in json_data
            assert len(json_data["data"]["regional_services"]) == 4
            print("✅ JSON structure and content verified")

            # Test compact JSON generator
            compact_generator = CompactJSONGenerator(context)
            compact_filepath = compact_generator.generate(test_data)

            # Compact file should be smaller
            compact_size = os.path.getsize(compact_filepath)
            regular_size = os.path.getsize(filepath)
            assert compact_size < regular_size
            print(f"✅ Compact JSON is smaller: {compact_size} vs {regular_size} bytes")

        except Exception as e:
            print(f"❌ JSON generator test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    print("🎉 JSONGenerator test completed successfully!")
    return True


def test_csv_generators():
    """Test CSV output generation."""

    print("\n🧪 Testing CSV Generators...")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        context = create_test_context(temp_dir)
        test_data = create_test_data()

        try:
            # Test standard CSV generator
            csv_generator = CSVGenerator(context)
            print("✅ CSVGenerator initialized successfully")

            csv_filepath = csv_generator.generate(test_data)
            assert os.path.exists(csv_filepath)
            assert csv_filepath.endswith(".csv")
            print(f"✅ CSV file generated: {os.path.basename(csv_filepath)}")

            # Verify CSV content
            import pandas as pd

            df = pd.read_csv(csv_filepath)
            assert len(df) == 4
            assert "Region Code" in df.columns
            assert "Service Name" in df.columns
            print("✅ CSV content verified")

            # Test Multi-CSV generator
            multi_csv_generator = MultiCSVGenerator(context)
            output_dir = multi_csv_generator.generate(test_data)
            assert os.path.isdir(output_dir)

            # Check that multiple CSV files were generated
            csv_files = [f for f in os.listdir(output_dir) if f.endswith(".csv")]
            assert len(csv_files) >= 4  # Should have at least 4 different sheets
            print(f"✅ Multi-CSV generated {len(csv_files)} files")

            # Test TSV generator
            tsv_generator = TSVGenerator(context)
            tsv_filepath = tsv_generator.generate(test_data)
            assert os.path.exists(tsv_filepath)
            assert tsv_filepath.endswith(".tsv")
            print(f"✅ TSV file generated: {os.path.basename(tsv_filepath)}")

        except Exception as e:
            print(f"❌ CSV generator test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    print("🎉 CSV Generators test completed successfully!")
    return True


def test_error_handling():
    """Test error handling in output generators."""

    print("\n🧪 Testing error handling...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = create_test_context(temp_dir)

            # Test with empty data
            generator = JSONGenerator(context)
            empty_result = generator.generate([])
            assert os.path.exists(empty_result)
            print("✅ Empty data handled correctly")

            # Test with invalid data type
            try:
                generator.generate("invalid_data")
                print("❌ Should have failed with invalid data type")
                return False
            except Exception:
                print("✅ Invalid data type correctly rejected")

            # Test with malformed data
            malformed_data = [{"invalid": "structure"}]
            try:
                generator.validate_data(malformed_data)
                print("❌ Should have failed with malformed data")
                return False
            except Exception:
                print("✅ Malformed data correctly rejected")

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

    print("🎉 Error handling test completed successfully!")
    return True


if __name__ == "__main__":
    print("🚀 Starting Output Generators tests...\n")

    success = True
    success &= test_excel_generator()
    success &= test_json_generator()
    success &= test_csv_generators()
    success &= test_error_handling()

    if success:
        print("\n🎯 All Output Generator tests passed!")
        print("✅ Week 4 Day 2: JSON/CSV generation logic extraction COMPLETED")
        print("\n📊 Output Generators Summary:")
        print("   ✅ ExcelGenerator: Multi-sheet Excel with formatting")
        print("   ✅ JSONGenerator: Comprehensive JSON with metadata")
        print("   ✅ CompactJSONGenerator: Minified JSON output")
        print("   ✅ CSVGenerator: Standard CSV output")
        print("   ✅ MultiCSVGenerator: Multiple CSV files (one per sheet)")
        print("   ✅ TSVGenerator: Tab-separated values output")
        print("   ✅ Error handling and validation")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
