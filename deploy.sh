#!/bin/bash

# AWS SSM Data Fetcher - Local Terraform Deployment Script
#
# ⚠️  WARNING: This is a local deployment script for development/testing only.
# ⚠️  PRODUCTION deployments must use GitHub Actions workflow.
#
# This project has been simplified to PROD-only deployment through GitHub Actions.
# This script is maintained for local development and testing purposes only.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values (PROD-only deployment)
ENVIRONMENT="prod"
ACTION="plan"
AUTO_APPROVE=false
BUILD_PACKAGES=true

# Function to display usage
usage() {
    echo -e "${YELLOW}⚠️  IMPORTANT: This is a local development script only!${NC}"
    echo -e "${YELLOW}   For production deployments, use: gh workflow run \"Terraform Deployment\"${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Local Terraform deployment script (PROD-only configuration)"
    echo ""
    echo "Options:"
    echo "  -a, --action ACTION      Terraform action (plan, apply, destroy) [default: plan]"
    echo "  -y, --auto-approve      Auto-approve Terraform apply/destroy"
    echo "  -s, --skip-build        Skip Lambda package build"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       # Plan prod environment locally"
    echo "  $0 -a apply              # Deploy prod locally (NOT RECOMMENDED)"
    echo "  $0 -a destroy            # Destroy prod environment locally"
    echo ""
    echo "Recommended production workflow:"
    echo "  gh workflow run \"Terraform Deployment\" --ref main -f action=plan"
    echo "  gh workflow run \"Terraform Deployment\" --ref main -f action=apply"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -y|--auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -s|--skip-build)
            BUILD_PACKAGES=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate environment (PROD-only)
if [[ "$ENVIRONMENT" != "prod" ]]; then
    echo -e "${RED}Error: Only production environment is supported${NC}"
    exit 1
fi

# Validate action
if [[ ! "$ACTION" =~ ^(plan|apply|destroy|init)$ ]]; then
    echo -e "${RED}Error: Action must be one of: plan, apply, destroy, init${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 AWS SSM Data Fetcher Deployment${NC}"
echo -e "${BLUE}Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "${BLUE}Action: ${GREEN}$ACTION${NC}"
echo -e "${BLUE}Auto-approve: ${GREEN}$AUTO_APPROVE${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo -e "${RED}❌ AWS CLI is not configured or credentials are invalid${NC}"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &>/dev/null; then
    echo -e "${RED}❌ Terraform is not installed${NC}"
    exit 1
fi

# Check Terraform version
TERRAFORM_VERSION=$(terraform --version | head -n1 | cut -d' ' -f2 | sed 's/v//')
REQUIRED_VERSION="1.5"
if ! printf '%s\n%s\n' "$REQUIRED_VERSION" "$TERRAFORM_VERSION" | sort -V -C; then
    echo -e "${RED}❌ Terraform version >= $REQUIRED_VERSION is required (found: $TERRAFORM_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Build Lambda packages if requested
if [ "$BUILD_PACKAGES" = true ] && [ "$ACTION" != "destroy" ]; then
    echo -e "${YELLOW}📦 Building Lambda packages...${NC}"

    if [ -f "lambda_functions/scripts/build_packages.sh" ]; then
        cd lambda_functions
        chmod +x scripts/build_packages.sh
        ./scripts/build_packages.sh
        cd ..
        echo -e "${GREEN}✅ Lambda packages built successfully${NC}"
    else
        echo -e "${RED}❌ Build script not found at lambda_functions/scripts/build_packages.sh${NC}"
        exit 1
    fi
fi

# Change to terraform directory
cd terraform

# Initialize Terraform if needed or requested
if [ ! -f ".terraform/terraform.tfstate" ] || [ "$ACTION" = "init" ]; then
    echo -e "${YELLOW}🔧 Initializing Terraform...${NC}"
    terraform init
    echo -e "${GREEN}✅ Terraform initialized${NC}"
fi

# Set Terraform variables (PROD-only)
TF_VAR_FILE="terraform.tfvars"

if [ ! -f "$TF_VAR_FILE" ]; then
    echo -e "${RED}❌ Terraform variables file not found: $TF_VAR_FILE${NC}"
    exit 1
fi

# Execute Terraform action
echo -e "${YELLOW}🏗️  Executing terraform $ACTION for $ENVIRONMENT environment...${NC}"

case $ACTION in
    plan)
        terraform plan -var-file="$TF_VAR_FILE"
        ;;
    apply)
        if [ "$AUTO_APPROVE" = true ]; then
            terraform apply -var-file="$TF_VAR_FILE" -auto-approve
        else
            terraform apply -var-file="$TF_VAR_FILE"
        fi

        # Display outputs after successful apply
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Infrastructure deployed successfully!${NC}"
            echo ""
            echo -e "${BLUE}📊 Important outputs:${NC}"
            echo "S3 Bucket: $(terraform output -raw s3_bucket_name)"
            echo "Step Function: $(terraform output -raw step_function_name)"
            echo "Dashboard: $(terraform output -raw cloudwatch_dashboard_url)"
            echo ""
            echo -e "${YELLOW}💡 Next steps:${NC}"
            echo "1. Test the pipeline:"
            echo "   aws stepfunctions start-execution --state-machine-arn $(terraform output -raw step_function_arn) --input '{}'"
            echo ""
            echo "2. Monitor execution:"
            echo "   Open: $(terraform output -raw cloudwatch_dashboard_url)"
            echo ""
            echo "3. Download reports:"
            echo "   aws s3 ls s3://$(terraform output -raw s3_bucket_name)/reports/"
        fi
        ;;
    destroy)
        echo -e "${RED}⚠️  WARNING: This will destroy all infrastructure for $ENVIRONMENT environment!${NC}"
        echo -e "${RED}⚠️  This action is irreversible!${NC}"
        echo ""

        if [ "$AUTO_APPROVE" != true ]; then
            read -p "Are you sure you want to proceed? (yes/no): " confirm
            if [ "$confirm" != "yes" ]; then
                echo -e "${YELLOW}Operation cancelled.${NC}"
                exit 0
            fi
        fi

        if [ "$AUTO_APPROVE" = true ]; then
            terraform destroy -var-file="$TF_VAR_FILE" -auto-approve
        else
            terraform destroy -var-file="$TF_VAR_FILE"
        fi

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Infrastructure destroyed successfully!${NC}"
        fi
        ;;
    init)
        echo -e "${GREEN}✅ Terraform already initialized above${NC}"
        ;;
esac

echo -e "${BLUE}🎉 Deployment script completed!${NC}"
