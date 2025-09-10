#!/bin/bash

# Import existing AWS resources into Terraform state
# This resolves the "ResourceAlreadyExistsException" errors

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Importing existing AWS resources into Terraform state...${NC}"

cd terraform

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init \
  -backend-config="bucket=$TF_STATE_BUCKET" \
  -backend-config="key=aws-ssm-fetcher/prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true"

# Import S3 bucket
echo -e "${YELLOW}Importing S3 bucket...${NC}"
S3_BUCKET=$(aws s3 ls | grep aws-ssm-fetcher-prod | awk '{print $3}')
if [ -n "$S3_BUCKET" ]; then
  echo "Found S3 bucket: $S3_BUCKET"
  terraform import module.s3_storage.aws_s3_bucket.main "$S3_BUCKET" || echo "Already imported or not found"
else
  echo "No S3 bucket found matching pattern"
fi

# Import CloudWatch Log Groups
echo -e "${YELLOW}Importing CloudWatch Log Groups...${NC}"

# Data fetcher log group
echo "Importing data-fetcher log group..."
terraform import module.lambda_data_fetcher.aws_cloudwatch_log_group.lambda_logs "/aws/lambda/aws-ssm-fetcher-prod-data-fetcher" || echo "Already imported or not found"

# Processor log group
echo "Importing processor log group..."
terraform import module.lambda_processor.aws_cloudwatch_log_group.lambda_logs "/aws/lambda/aws-ssm-fetcher-prod-processor" || echo "Already imported or not found"

# Report generator log group
echo "Importing report-generator log group..."
terraform import module.lambda_report_generator.aws_cloudwatch_log_group.lambda_logs "/aws/lambda/aws-ssm-fetcher-prod-report-generator" || echo "Already imported or not found"

# Optional: Import other resources that might exist
echo -e "${YELLOW}Checking for other existing resources...${NC}"

# Check for Lambda functions
echo "Checking Lambda functions..."
LAMBDA_FUNCTIONS=$(aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`aws-ssm-fetcher-prod`)].FunctionName' --output text)
if [ -n "$LAMBDA_FUNCTIONS" ]; then
  echo "Found Lambda functions: $LAMBDA_FUNCTIONS"
  for func in $LAMBDA_FUNCTIONS; do
    echo "Note: Lambda function $func exists and may need manual import if deployment fails"
  done
fi

# Check for Step Function
echo "Checking Step Functions..."
STEP_FUNCTIONS=$(aws stepfunctions list-state-machines --query 'stateMachines[?contains(name,`aws-ssm-fetcher-prod`)].name' --output text)
if [ -n "$STEP_FUNCTIONS" ]; then
  echo "Found Step Functions: $STEP_FUNCTIONS"
  echo "Note: Step Functions exist and may need manual import if deployment fails"
fi

echo -e "${GREEN}✅ Import process completed!${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo "1. Run: terraform plan (should show minimal changes now)"
echo "2. Run: terraform apply (should succeed without resource conflicts)"
echo "3. If any resources still conflict, import them manually using:"
echo "   terraform import <resource_address> <resource_id>"

echo -e "${YELLOW}Note: You'll need TF_STATE_BUCKET environment variable set${NC}"
echo "Example: export TF_STATE_BUCKET=your-terraform-state-bucket-name"
