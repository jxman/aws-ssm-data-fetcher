"""Setup configuration for AWS SSM Data Fetcher package."""

from setuptools import setup, find_packages

# Read the README file for the long description
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "AWS SSM Data Fetcher - Modular package for AWS service availability reporting"

setup(
    name="aws-ssm-fetcher",
    version="2.0.0",
    author="AWS SSM Data Fetcher",
    description="Modular package for AWS service availability reporting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "boto3>=1.26.0",
        "pandas>=1.5.0",
        "openpyxl>=3.0.0",
        "requests>=2.28.0",
        "botocore>=1.29.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.991",
        ],
        "lambda": [
            "aws-lambda-powertools>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aws-ssm-fetcher=aws_ssm_fetcher.cli.main:main",
        ],
    },
)