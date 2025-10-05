#!/usr/bin/env python3
"""
Build Lambda Layer with Linux-compatible packages
Uses docker to ensure compatibility with AWS Lambda runtime
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def check_docker():
    """Check if Docker is available"""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker available: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("❌ Docker not available - using local pip with platform flags")
    return False


def build_with_docker():
    """Build using Docker container for Lambda compatibility"""
    docker_command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{os.getcwd()}:/workspace",
        "-w",
        "/workspace",
        "public.ecr.aws/lambda/python:3.11",
        "bash",
        "-c",
        """
        pip install -r requirements_lambda.txt -t /tmp/python --upgrade --quiet &&
        mkdir -p lambda_functions/shared_layer/build/python &&
        cp -r /tmp/python/* lambda_functions/shared_layer/build/python/ &&
        find lambda_functions/shared_layer/build -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true &&
        find lambda_functions/shared_layer/build -type f -name "*.pyc" -delete 2>/dev/null || true
        """,
    ]

    print("🐳 Building layer using Docker with Lambda runtime environment...")
    result = subprocess.run(docker_command)
    return result.returncode == 0


def build_with_pip():
    """Build using local pip with platform flags"""
    print("🛠️  Building layer using local pip with platform constraints...")

    build_dir = Path("lambda_functions/shared_layer/build/python")
    build_dir.mkdir(parents=True, exist_ok=True)

    # Remove existing packages
    if build_dir.exists():
        shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)

    # Try platform-specific install
    pip_command = [
        "pip",
        "install",
        "-r",
        "requirements_lambda.txt",
        "-t",
        str(build_dir),
        "--platform",
        "linux_x86_64",
        "--implementation",
        "cp",
        "--python-version",
        "3.11",
        "--only-binary=:all:",
        "--upgrade",
        "--no-deps",
    ]

    print("   Trying platform-specific install...")
    result = subprocess.run(pip_command, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"   Platform-specific install failed: {result.stderr}")
        print("   Trying basic install...")

        # Fallback to basic install
        basic_command = [
            "pip",
            "install",
            "-r",
            "requirements_lambda.txt",
            "-t",
            str(build_dir),
            "--upgrade",
        ]

        result = subprocess.run(basic_command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Basic install failed: {result.stderr}")
            return False

    # Clean up unnecessary files
    cleanup_commands = [
        [
            "find",
            str(build_dir),
            "-type",
            "d",
            "-name",
            "__pycache__",
            "-exec",
            "rm",
            "-rf",
            "{}",
            "+",
        ],
        ["find", str(build_dir), "-type", "f", "-name", "*.pyc", "-delete"],
        ["find", str(build_dir), "-type", "f", "-name", "*.pyo", "-delete"],
    ]

    for cmd in cleanup_commands:
        subprocess.run(cmd, stderr=subprocess.DEVNULL)

    return True


def copy_aws_package():
    """Copy our aws_ssm_fetcher package to the build"""
    source_pkg = Path("lambda_functions/shared_layer/python/aws_ssm_fetcher")
    dest_pkg = Path("lambda_functions/shared_layer/build/python/aws_ssm_fetcher")

    if source_pkg.exists():
        if dest_pkg.exists():
            shutil.rmtree(dest_pkg)
        shutil.copytree(source_pkg, dest_pkg)
        print("✅ Copied aws_ssm_fetcher package")
        return True
    else:
        print(f"❌ aws_ssm_fetcher package not found at {source_pkg}")
        return False


def create_layer_zip():
    """Create the layer zip file"""
    build_dir = Path("lambda_functions/shared_layer/build")
    layer_zip = Path("lambda_functions/shared_layer/layer.zip")

    if layer_zip.exists():
        layer_zip.unlink()

    # Create zip file
    print("📦 Creating layer.zip...")
    os.chdir(build_dir)
    result = subprocess.run(["zip", "-r", "../layer.zip", ".", "-q"])
    os.chdir("../../../..")  # Back to project root

    if result.returncode == 0:
        size = layer_zip.stat().st_size / (1024 * 1024)
        print(f"✅ Layer created: {size:.1f}MB")

        # Clean up build directory
        if build_dir.exists():
            shutil.rmtree(build_dir)

        return True
    else:
        print("❌ Failed to create layer zip")
        return False


def main():
    """Main build process"""
    print("🚀 Building Lambda Layer with Linux-compatible packages...")

    # Check if we're in the right directory
    if not Path("requirements_lambda.txt").exists():
        print("❌ requirements_lambda.txt not found. Run from project root.")
        sys.exit(1)

    # Try Docker first, then fall back to local pip
    success = False

    if check_docker():
        success = build_with_docker()

    if not success:
        success = build_with_pip()

    if not success:
        print("❌ Failed to install dependencies")
        sys.exit(1)

    # Copy our package
    if not copy_aws_package():
        sys.exit(1)

    # Create final zip
    if not create_layer_zip():
        sys.exit(1)

    print("🎉 Lambda layer built successfully!")
    print("   Ready for Terraform deployment")


if __name__ == "__main__":
    main()
