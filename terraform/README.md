# AWS SSM Data Fetcher - Terraform Infrastructure ✅ DEPLOYED

This directory contains the Terraform infrastructure code for deploying the AWS SSM Data Fetcher Lambda functions and supporting resources. **All 42 resources successfully deployed and operational in AWS!** 🎉

## Architecture

The infrastructure creates a complete serverless data processing pipeline **now live in AWS**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Fetcher  │───▶│   Processor     │───▶│Report Generator │
│    Lambda       │    │    Lambda       │    │     Lambda      │
│   (14.7MB)     │    │   (49.8MB)     │    │    (16.3MB)    │
│  🟢 DEPLOYED   │    │  🟢 DEPLOYED   │    │  🟢 DEPLOYED   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │  Shared Layer   │
                    │    (324KB)      │
                    │  🟢 DEPLOYED   │
                    └─────────────────┘
                                 │
                                 ▼
           ┌─────────────────────────────────────────┐
           │        🟢 AWS Infrastructure LIVE       │
           │  S3: aws-ssm-fetcher-prod-*             │
           │  Step Functions: aws-ssm-fetcher-prod   │
           │  CloudWatch Dashboard & Monitoring      │
           └─────────────────────────────────────────┘
```

## ✅ Resources Successfully Deployed

### Core Infrastructure (✅ LIVE)
- **S3 Bucket**: `aws-ssm-fetcher-prod-*` → Active with lifecycle policies
- **IAM Roles & Policies**: Lambda execution, Step Functions, CloudWatch Events → Applied
- **CloudWatch**: Log groups, dashboard, alarms, and monitoring → Operational

### Lambda Functions (✅ DEPLOYED)
- **Data Fetcher**: `aws-ssm-fetcher-prod-data-fetcher` → Operational
- **Processor**: `aws-ssm-fetcher-prod-processor` → Operational
- **Report Generator**: `aws-ssm-fetcher-prod-report-generator` → Operational
- **Shared Layer**: Common modules shared across all functions → Active

### Orchestration (✅ OPERATIONAL)
- **Step Functions**: `aws-ssm-fetcher-prod-pipeline` → Active and monitoring enabled
- **CloudWatch Events**: Ready for scheduled execution
- **SNS**: Notifications configured for success/failure events

### Monitoring (✅ ACTIVE)
- **CloudWatch Dashboard**: `aws-ssm-fetcher-prod-dashboard` → Live monitoring
- **CloudWatch Alarms**: Error and duration monitoring → Enabled
- **Dead Letter Queues**: Failed execution handling → Configured

## Directory Structure

```
terraform/
├── main.tf                     # Main Terraform configuration
├── variables.tf                # Input variables
├── outputs.tf                  # Output values
├── README.md                   # This file
├── terraform.tfvars            # Production configuration variables
└── modules/                    # Reusable Terraform modules
    ├── s3/                     # S3 bucket configuration
    ├── iam/                    # IAM roles and policies
    ├── lambda-layer/           # Shared Lambda layer
    ├── lambda-function/        # Lambda function module
    ├── step-functions/         # Step Functions orchestration
    └── cloudwatch/             # Monitoring and alarms
```

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **Terraform >= 1.5** installed
3. **S3 bucket** for Terraform state (recommended)
4. **Lambda packages built** in `../lambda_functions/` directory

## Quick Start

### 1. Initialize Terraform
```bash
cd terraform
terraform init

# Optional: Configure remote state
terraform init \
  -backend-config="bucket=your-terraform-state-bucket" \
  -backend-config="key=aws-ssm-fetcher/terraform.tfstate" \
  -backend-config="region=us-east-1"
```

### 2. Plan Deployment
```bash
# Production environment (PROD-only deployment)
terraform plan
```

### 3. Deploy Infrastructure
```bash
# Deploy to production via GitHub Actions (RECOMMENDED)
gh workflow run "Terraform Deployment" --ref main

# Or deploy locally (development/testing only)
terraform apply
```

## Production Configuration

### Current Settings (terraform.tfvars)
- **Log Level**: INFO
- **Monitoring**: Enabled, 14-day retention
- **Scheduling**: Daily execution (6 AM UTC)
- **Notifications**: Enabled via SNS
- **S3**: Protected from force destroy
- **Lambda Memory**: Optimized for performance
- **Lambda Timeout**: 15 minutes per function

## Usage After Deployment

### Manual Execution
```bash
# Get Step Function ARN from Terraform outputs
terraform output step_function_arn

# Execute the pipeline
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:region:account:stateMachine:aws-ssm-fetcher-prod-pipeline" \
  --input '{}'
```

### Monitor Execution
```bash
# Get dashboard URL
terraform output cloudwatch_dashboard_url

# View logs
aws logs tail /aws/lambda/aws-ssm-fetcher-prod-data-fetcher --follow
```

### Download Reports
```bash
# Get S3 bucket name
terraform output s3_bucket_name

# List available reports
aws s3 ls s3://your-bucket-name/reports/

# Download specific report
aws s3 cp s3://your-bucket-name/reports/latest/ ./reports/ --recursive
```

## Customization

### Environment Variables
Each Lambda function receives these environment variables:
- `S3_BUCKET`: Name of the S3 bucket
- `CACHE_PREFIX`: Prefix for cache objects
- `OUTPUT_PREFIX`: Prefix for output objects
- `LOG_LEVEL`: Logging level
- `ENVIRONMENT`: Current environment

### Scheduled Execution
Enable scheduled execution by setting:
```hcl
enable_scheduled_execution = true
schedule_expression       = "rate(24 hours)"  # or "cron(0 0 * * ? *)"
```

### Monitoring
Configure monitoring and alerting:
```hcl
enable_monitoring         = true
enable_sns_notifications = true
sns_email               = "your-email@example.com"
```

## Troubleshooting

### Lambda Package Issues
If Lambda functions fail to deploy:
1. Ensure packages are built: `cd ../lambda_functions && ./scripts/build_packages.sh`
2. Check package sizes: `ls -lh ../lambda_functions/*.zip`
3. Verify Python runtime compatibility

### Permission Issues
If functions can't access resources:
1. Check IAM roles in the `iam` module
2. Verify S3 bucket policies
3. Review CloudWatch logs for specific errors

### Step Functions Failures
If the pipeline fails:
1. Check Step Functions console for execution details
2. Review individual Lambda function logs
3. Verify input/output format between functions

## Cleanup

```bash
# Destroy infrastructure (WARNING: This will delete all resources)
terraform destroy
```

## Security Considerations

1. **IAM Principle of Least Privilege**: Each role has minimal required permissions
2. **S3 Encryption**: All objects encrypted at rest
3. **VPC**: Lambda functions can be deployed in VPC if required
4. **Secrets Management**: Use AWS Systems Manager Parameter Store for sensitive data

## Cost Optimization

1. **Lambda Sizing**: Functions sized appropriately for workload
2. **S3 Lifecycle**: Automatic cleanup of cache and old reports
3. **Log Retention**: Configurable retention periods
4. **Monitoring**: Alarms prevent runaway costs

## Support

For issues with the Terraform infrastructure:
1. Check the troubleshooting section above
2. Review AWS CloudWatch logs
3. Validate Terraform configuration with `terraform validate`
4. Check the main project documentation in `../README.md`
