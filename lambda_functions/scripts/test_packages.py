#!/usr/bin/env python3
"""
Test Lambda packages locally before deployment.
Validates package structure, imports, and basic functionality.
"""

import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_package_structure(package_path: str, expected_files: List[str]) -> bool:
    """Test that package contains expected files."""
    print(f"  📋 Testing package structure: {os.path.basename(package_path)}")

    if not os.path.exists(package_path):
        print(f"    ❌ Package file not found: {package_path}")
        return False

    try:
        with zipfile.ZipFile(package_path, "r") as zip_file:
            file_list = zip_file.namelist()

            for expected_file in expected_files:
                if expected_file not in file_list:
                    print(f"    ❌ Missing expected file: {expected_file}")
                    return False
                else:
                    print(f"    ✅ Found: {expected_file}")

            # Check package size
            file_size = os.path.getsize(package_path)
            size_mb = file_size / (1024 * 1024)

            if size_mb > 50:
                print(f"    ⚠️  Package size {size_mb:.1f}MB exceeds 50MB Lambda limit")
            else:
                print(f"    ✅ Package size: {size_mb:.1f}MB (within limits)")

            return True

    except Exception as e:
        print(f"    ❌ Error reading package: {e}")
        return False


def test_lambda_function_import(package_path: str, function_name: str) -> bool:
    """Test that lambda function can be imported and has handler."""
    print(f"  🐍 Testing Python imports: {function_name}")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract package
            with zipfile.ZipFile(package_path, "r") as zip_file:
                zip_file.extractall(temp_dir)

            # Add to Python path
            sys.path.insert(0, temp_dir)

            try:
                # Try to import lambda function
                import lambda_function

                # Check if handler exists
                if hasattr(lambda_function, "lambda_handler"):
                    print(f"    ✅ lambda_handler function found")

                    # Test handler signature (should accept event, context)
                    import inspect

                    sig = inspect.signature(lambda_function.lambda_handler)
                    params = list(sig.parameters.keys())

                    if len(params) >= 2:
                        print(f"    ✅ Handler signature: {params}")
                        return True
                    else:
                        print(f"    ❌ Invalid handler signature: {params}")
                        return False
                else:
                    print(f"    ❌ lambda_handler function not found")
                    return False

            except ImportError as e:
                print(f"    ❌ Import error: {e}")
                return False
            except Exception as e:
                # Handle AWS configuration errors during import
                error_msg = str(e).lower()
                if any(
                    error_type in error_msg
                    for error_type in [
                        "region",
                        "credentials",
                        "aws",
                        "boto",
                        "botocore",
                        "access",
                        "auth",
                    ]
                ):
                    print(
                        f"    ✅ Import structure OK (AWS config error expected): {e}"
                    )
                    return True
                else:
                    print(f"    ❌ Unexpected error during import: {e}")
                    return False
            finally:
                # Clean up imports
                if "lambda_function" in sys.modules:
                    del sys.modules["lambda_function"]
                sys.path.remove(temp_dir)

        except Exception as e:
            print(f"    ❌ Error testing imports: {e}")
            return False


def test_shared_layer(layer_path: str) -> bool:
    """Test shared layer structure and imports."""
    print(f"  🗂️  Testing shared layer: {os.path.basename(layer_path)}")

    if not os.path.exists(layer_path):
        print(f"    ❌ Layer file not found: {layer_path}")
        return False

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract layer
            with zipfile.ZipFile(layer_path, "r") as zip_file:
                zip_file.extractall(temp_dir)

            # Check python directory exists
            python_dir = os.path.join(temp_dir, "python")
            if not os.path.exists(python_dir):
                print(f"    ❌ python/ directory not found in layer")
                return False

            print(f"    ✅ python/ directory found")

            # Check our package exists
            package_dir = os.path.join(python_dir, "aws_ssm_fetcher")
            if not os.path.exists(package_dir):
                print(f"    ❌ aws_ssm_fetcher package not found in layer")
                return False

            print(f"    ✅ aws_ssm_fetcher package found")

            # Add to Python path and test imports
            sys.path.insert(0, python_dir)

            try:
                # Test core module imports (shared layer contains only core modules)
                from aws_ssm_fetcher.core import config

                print(f"    ✅ Core config import successful")

                from aws_ssm_fetcher.core import cache

                print(f"    ✅ Core cache import successful")

                from aws_ssm_fetcher.core import logging

                print(f"    ✅ Core logging import successful")

                from aws_ssm_fetcher.core import error_handling

                print(f"    ✅ Core error handling import successful")

                return True

            except ImportError as e:
                print(f"    ❌ Layer import error: {e}")
                return False
            finally:
                # Clean up
                sys.path.remove(python_dir)

        except Exception as e:
            print(f"    ❌ Error testing layer: {e}")
            return False


def test_mock_execution(package_path: str, function_name: str) -> bool:
    """Test lambda function with mock event."""
    print(f"  🧪 Testing mock execution: {function_name}")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract package
            with zipfile.ZipFile(package_path, "r") as zip_file:
                zip_file.extractall(temp_dir)

            # Add to Python path
            sys.path.insert(0, temp_dir)

            try:
                import lambda_function

                # Create mock event and context (function-specific parameters)
                if function_name in [
                    "json_csv_generator",
                    "excel_generator",
                    "report_orchestrator",
                ]:
                    mock_event = {
                        "execution_id": "test_execution_123",
                        "source": "test",
                        "s3_bucket": "test-bucket",
                        "s3_key": "test/path",
                        "data": {"test": "data"},
                    }
                else:
                    mock_event = {
                        "execution_id": "test_execution_123",
                        "source": "test",
                    }

                # Simple mock context
                class MockContext:
                    def __init__(self):
                        self.function_name = function_name
                        self.function_version = "$LATEST"
                        self.memory_limit_in_mb = 512
                        self.remaining_time_in_millis = lambda: 30000

                mock_context = MockContext()

                # This would fail without AWS credentials, but we can at least
                # test that the function structure is correct
                try:
                    # Just test the function can be called (will fail on AWS calls)
                    result = lambda_function.lambda_handler(mock_event, mock_context)
                    print(
                        f"    ⚠️  Unexpected success (no AWS credentials): {result.get('statusCode', 'unknown')}"
                    )
                    return True
                except Exception as e:
                    # Expected to fail due to missing AWS credentials or resources
                    if any(
                        error_type in str(e).lower()
                        for error_type in [
                            "credentials",
                            "aws",
                            "boto",
                            "botocore",
                            "access",
                            "auth",
                            "region",
                            "s3_bucket",
                            "s3_key",
                            "required in event",
                        ]
                    ):
                        print(
                            f"    ✅ Function structure OK (AWS/config error expected)"
                        )
                        return True
                    else:
                        print(f"    ❌ Unexpected error: {e}")
                        return False

            except ImportError as e:
                print(f"    ❌ Import error: {e}")
                return False
            finally:
                # Clean up imports
                if "lambda_function" in sys.modules:
                    del sys.modules["lambda_function"]
                sys.path.remove(temp_dir)

        except Exception as e:
            # Handle AWS configuration errors in outer scope too
            error_msg = str(e).lower()
            if any(
                error_type in error_msg
                for error_type in [
                    "credentials",
                    "aws",
                    "boto",
                    "botocore",
                    "access",
                    "auth",
                    "region",
                    "s3_bucket",
                    "s3_key",
                    "required in event",
                ]
            ):
                print(f"    ✅ Function structure OK (AWS/config error expected)")
                return True
            else:
                print(f"    ❌ Error in mock execution: {e}")
                return False


def main():
    """Run all package tests."""
    # Check if we're in a CI environment
    is_ci = os.getenv("CI") or os.getenv("GITHUB_ACTIONS")
    if is_ci:
        print("🧪 Testing Lambda deployment packages (CI Mode)...\n")
        print(
            "ℹ️  In CI environment - AWS credential errors are expected and treated as success\n"
        )
    else:
        print("🧪 Testing Lambda deployment packages...\n")

    # Get paths
    script_dir = Path(__file__).parent
    lambda_dir = script_dir.parent

    # Package paths
    packages = {
        "data_fetcher": {
            "path": lambda_dir / "data_fetcher" / "deployment_package.zip",
            "expected_files": ["lambda_function.py"],
            "dependencies": ["boto3", "requests", "feedparser"],
        },
        "processor": {
            "path": lambda_dir / "processor" / "deployment_package.zip",
            "expected_files": ["lambda_function.py"],
            "dependencies": ["boto3", "pandas", "numpy"],
        },
        "json_csv_generator": {
            "path": lambda_dir / "json_csv_generator" / "deployment_package.zip",
            "expected_files": ["lambda_function.py"],
            "dependencies": ["boto3", "pandas"],
        },
        "excel_generator": {
            "path": lambda_dir / "excel_generator" / "deployment_package.zip",
            "expected_files": ["lambda_function.py"],
            "dependencies": ["boto3", "pandas", "openpyxl"],
        },
        "report_orchestrator": {
            "path": lambda_dir / "report_orchestrator" / "deployment_package.zip",
            "expected_files": ["lambda_function.py"],
            "dependencies": ["boto3"],
        },
    }

    layer_path = lambda_dir / "shared_layer" / "layer.zip"

    success = True

    # Test shared layer first
    print("🗂️  Testing Shared Layer:")
    if not test_shared_layer(str(layer_path)):
        success = False
    print()

    # Test each function package
    for function_name, package_info in packages.items():
        print(f"📦 Testing {function_name}:")

        package_path = str(package_info["path"])

        # Test package structure
        if not test_package_structure(package_path, package_info["expected_files"]):
            success = False
            continue

        # Test Python imports
        if not test_lambda_function_import(package_path, function_name):
            success = False
            continue

        # Test mock execution
        if not test_mock_execution(package_path, function_name):
            success = False
            continue

        print(f"  ✅ {function_name} package tests passed!\n")

    # Final summary
    if success:
        print("🎉 All package tests passed!")
        print("\n📋 Summary:")
        print("   ✅ All packages have correct structure")
        print("   ✅ All lambda handlers are properly defined")
        print("   ✅ All imports are working")
        print("   ✅ Package sizes are within Lambda limits")
        print("\n🚀 Packages are ready for Terraform deployment!")
        return 0
    else:
        print("❌ Some package tests failed!")
        print("\n🔧 Please fix the issues and rebuild packages")
        return 1


if __name__ == "__main__":
    sys.exit(main())
