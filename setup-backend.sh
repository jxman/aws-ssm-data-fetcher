#!/bin/bash

# AWS SSM Data Fetcher - Backend Setup Script
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Terraform S3 Backend${NC}"

# Generate unique bucket name
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="terraform-state-aws-ssm-fetcher-${ACCOUNT_ID}"
REGION="us-east-1"

echo -e "${BLUE}Creating S3 bucket: ${BUCKET_NAME}${NC}"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${REGION}

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket ${BUCKET_NAME} \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo -e "${GREEN}✅ Backend setup complete!${NC}"
echo ""
echo -e "${BLUE}📋 Backend configuration:${NC}"
echo "Bucket: ${BUCKET_NAME}"
echo "Region: ${REGION}"
echo ""
echo -e "${BLUE}💡 To use this backend, uncomment the backend block in terraform/main.tf and update:${NC}"
echo "bucket = \"${BUCKET_NAME}\""
echo "key    = \"aws-ssm-fetcher/terraform.tfstate\""
echo "region = \"${REGION}\""