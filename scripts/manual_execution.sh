#!/bin/bash
# Manual Step Functions Execution Script
# Triggers the AWS SSM Fetcher pipeline manually outside of scheduled EventBridge

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
TERRAFORM_DIR="$(dirname "$0")/../terraform"

echo -e "${BLUE}🚀 AWS SSM Fetcher Manual Execution${NC}"
echo "================================================="

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed. Please install it first.${NC}"
    echo "Install: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if terraform is available and terraform directory exists
if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}❌ Terraform directory not found: $TERRAFORM_DIR${NC}"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform is not installed. Please install it first.${NC}"
    exit 1
fi

# Get Step Function ARN from Terraform outputs
echo -e "${BLUE}📋 Getting Step Function ARN from Terraform...${NC}"
cd "$TERRAFORM_DIR"

if [ ! -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
    echo -e "${RED}❌ Terraform state not found. Please ensure infrastructure is deployed.${NC}"
    exit 1
fi

STEP_FUNCTION_ARN=$(terraform output -raw step_function_arn 2>/dev/null)
if [ -z "$STEP_FUNCTION_ARN" ]; then
    echo -e "${RED}❌ Could not retrieve Step Function ARN from Terraform outputs.${NC}"
    echo "Please ensure the infrastructure is deployed and terraform outputs are available."
    exit 1
fi

S3_BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null)
cd - > /dev/null

echo -e "${GREEN}✅ Step Function ARN: $STEP_FUNCTION_ARN${NC}"
echo -e "${GREEN}✅ S3 Bucket: $S3_BUCKET${NC}"

# Generate execution name with timestamp
EXECUTION_NAME="manual-execution-$(date +%Y%m%d-%H%M%S)"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Create input payload
INPUT_PAYLOAD=$(cat <<EOF
{
  "source": "manual-script",
  "timestamp": "$TIMESTAMP",
  "full_run": true,
  "trigger_type": "manual",
  "execution_name": "$EXECUTION_NAME"
}
EOF
)

echo ""
echo -e "${BLUE}📝 Execution Details:${NC}"
echo "  Name: $EXECUTION_NAME"
echo "  Timestamp: $TIMESTAMP"
echo "  Input: $INPUT_PAYLOAD"

# Confirm execution
echo ""
read -p "🤔 Do you want to start the manual execution? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Execution cancelled by user.${NC}"
    exit 0
fi

# Start Step Function execution
echo -e "${BLUE}🚀 Starting Step Function execution...${NC}"
EXECUTION_ARN=$(aws stepfunctions start-execution \
    --state-machine-arn "$STEP_FUNCTION_ARN" \
    --name "$EXECUTION_NAME" \
    --input "$INPUT_PAYLOAD" \
    --region "$REGION" \
    --query 'executionArn' \
    --output text)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Execution started successfully!${NC}"
    echo ""
    echo -e "${BLUE}📊 Execution Details:${NC}"
    echo "  ARN: $EXECUTION_ARN"
    echo "  Name: $EXECUTION_NAME"
    echo "  Region: $REGION"
    echo ""
    echo -e "${BLUE}🔗 Monitoring Links:${NC}"
    echo "  AWS Console: https://console.aws.amazon.com/states/home?region=$REGION#/executions/details/$EXECUTION_ARN"
    echo "  S3 Bucket: https://s3.console.aws.amazon.com/s3/buckets/$S3_BUCKET?region=$REGION"
    echo ""

    # Wait a moment and check initial status
    echo -e "${BLUE}⏳ Checking initial status...${NC}"
    sleep 3

    STATUS=$(aws stepfunctions describe-execution \
        --execution-arn "$EXECUTION_ARN" \
        --region "$REGION" \
        --query 'status' \
        --output text)

    echo -e "${GREEN}📊 Current Status: $STATUS${NC}"

    if [ "$STATUS" = "RUNNING" ]; then
        echo ""
        echo -e "${YELLOW}⏳ Execution is running. This typically takes 5-15 minutes.${NC}"
        echo ""
        echo -e "${BLUE}💡 You can monitor progress using:${NC}"
        echo "  • AWS Console (link above)"
        echo "  • CloudWatch logs for individual Lambda functions"
        echo "  • Check S3 bucket for generated reports when complete"
        echo ""
        echo -e "${BLUE}🔄 To check status later, run:${NC}"
        echo "  aws stepfunctions describe-execution --execution-arn \"$EXECUTION_ARN\" --region $REGION"
    fi

else
    echo -e "${RED}❌ Failed to start execution. Please check your AWS credentials and permissions.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Manual execution initiated successfully!${NC}"
echo "================================================="
