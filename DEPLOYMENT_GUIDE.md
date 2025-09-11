# 🚀 AWS SSM Data Fetcher - Production Deployment Guide

Complete guide for deploying the AWS SSM Data Fetcher serverless application to production using GitHub Actions CI/CD pipeline.

## 📋 Overview

The AWS SSM Data Fetcher is a production-ready serverless application that automatically discovers AWS services across all 38 AWS regions and generates comprehensive reports in multiple formats (Excel, JSON, CSV). All deployment is handled through GitHub Actions with OIDC authentication.

## ✅ Prerequisites

1. **AWS Account** with administrative access
2. **GitHub Repository** access to `jxman/aws-ssm-data-fetcher`
3. **AWS CLI** configured locally (for initial setup only)
4. **Terraform >= 1.13** installed locally (for initial setup only)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Fetcher  │───▶│   Processor     │───▶│  JSON-CSV Gen   │
│  (38 Regions +  │    │ (Transform &    │    │ • JSON reports  │
│   396 Services) │    │   Analyze Data) │    │ • 5 CSV files   │
│     ~14MB       │    │     ~49MB       │    │    3.2KB        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│Report Orchestr. │◀───│  Excel Gen      │◀───│  Shared Layer   │
│ • Coordination  │    │ • Excel (5 tabs)│    │ (requests, core)│
│ • Final upload  │    │ • openpyxl only │    │     ~34MB       │
│    2.6KB        │    │     259KB       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘

🎯 **Modular Architecture Benefits:**
- **5 Specialized Functions**: Each optimized for specific task (99.5% size reduction)
- **Parallel Execution**: JSON/CSV and Excel generation can run concurrently
- **Isolated Failures**: Individual retry logic and error handling per function
- **Right-Sized Resources**: Memory allocation optimized per function type
- **Enhanced Monitoring**: Detailed CloudWatch metrics for each stage

           ┌─────────────────────────────────────────┐
           │   🚀 PRODUCTION OPERATIONAL SYSTEM      │
           │ S3 • IAM • CloudWatch • Step Functions │
           │     8,558 Service-Region Combinations   │
           │       GitHub Actions CI/CD              │
           │       OIDC Authentication               │
           └─────────────────────────────────────────┘
```

## 🚀 Production Deployment (GitHub Actions)

### Step 1: Deploy Infrastructure via GitHub Actions

The recommended and **only supported** way to deploy to production:

```bash
# Trigger production deployment
gh workflow run "Terraform Deployment" --ref main

# Monitor deployment progress
gh run list --limit 5
gh run view [RUN_ID] --web
```

### Step 2: Verify Deployment

After successful deployment, verify all components:

```bash
# Check Step Function
aws stepfunctions list-state-machines --query 'stateMachines[?starts_with(name, `aws-ssm-fetcher-prod`)]'

# Check Lambda functions (5 specialized functions)
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `aws-ssm-fetcher-prod`)]'

# Verify individual functions are deployed
aws lambda get-function --function-name aws-ssm-fetcher-prod-data-fetcher
aws lambda get-function --function-name aws-ssm-fetcher-prod-processor
aws lambda get-function --function-name aws-ssm-fetcher-prod-json-csv-generator
aws lambda get-function --function-name aws-ssm-fetcher-prod-excel-generator
aws lambda get-function --function-name aws-ssm-fetcher-prod-report-orchestrator

# Check S3 bucket
aws s3 ls | grep aws-ssm-fetcher-prod
```

## 🔧 Manual Execution (Post-Deployment)

### Execute the Data Pipeline

```bash
# Get Step Function ARN
aws stepfunctions list-state-machines --query 'stateMachines[?starts_with(name, `aws-ssm-fetcher-prod`)].stateMachineArn' --output text

# Execute pipeline
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT:stateMachine:aws-ssm-fetcher-prod-pipeline" \
  --input '{}'
```

### Monitor Execution

```bash
# View CloudWatch dashboard
open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=aws-ssm-fetcher-prod-dashboard"

# Monitor logs
aws logs tail /aws/lambda/aws-ssm-fetcher-prod-data-fetcher --follow
```

### Download Reports

The pipeline generates comprehensive reports in multiple formats:

```bash
# List available reports
aws s3 ls s3://YOUR-BUCKET-NAME/reports/

# Download latest reports (includes Excel + 5 CSVs)
aws s3 sync s3://YOUR-BUCKET-NAME/reports/ ./reports/

# Available report formats:
# - aws_regions_services.xlsx (Excel with 5 tabs)
# - aws_regions_services.json (full data)
# - regional_services.csv (regional service mappings)
# - service_matrix.csv (service availability matrix)
# - region_summary.csv (region statistics)
# - service_summary.csv (service statistics)
# - statistics.csv (overall statistics)
```

## 🛠️ Configuration

### Production Settings

The production deployment uses these optimized settings:

- **Data Coverage**: 38 AWS regions, 396+ services, 8,558+ combinations
- **Report Formats**: Excel (5 tabs) + JSON + 5 CSV files
- **Log Level**: INFO
- **Monitoring**: 14-day log retention
- **Scheduling**: Daily execution at 6 AM UTC
- **Notifications**: Enabled via SNS
- **Lambda Architecture**: 5 specialized functions with optimized resource allocation:
  - **Data Fetcher**: 1024MB, 15min timeout (~14MB package)
  - **Processor**: 3008MB, 15min timeout (~49MB package)
  - **JSON-CSV Generator**: 512MB, 5min timeout (3.2KB package)
  - **Excel Generator**: 1024MB, 5min timeout (259KB package)
  - **Report Orchestrator**: 512MB, 5min timeout (2.6KB package)
- **Dependencies**: Minimal shared layer (34MB) + function-specific dependencies
- **S3**: Protected from accidental deletion

### Environment Variables

Each Lambda function receives:
- `S3_BUCKET`: Production S3 bucket name
- `ENVIRONMENT`: Set to "prod"
- `LOG_LEVEL`: Set to "INFO"
- `CACHE_PREFIX`: "cache/"
- `OUTPUT_PREFIX`: "raw-data/"

## 🔒 Security Features

### OIDC Authentication
- **No long-lived credentials** stored in GitHub
- **Repository-specific** IAM role isolation
- **Least-privilege** permissions model
- **Audit trail** through CloudTrail

### Resource Security
- **S3 encryption** at rest
- **CloudWatch Logs** encryption
- **IAM policies** with minimal required permissions
- **VPC support** available if needed

## 📊 Monitoring & Alerts

### CloudWatch Dashboard
- **Lambda metrics**: Duration, errors, invocations
- **Step Function metrics**: Execution status
- **S3 metrics**: Object counts and sizes
- **Cost monitoring**: Resource utilization

### Automated Alerts
- **Lambda errors** > 5 in 5 minutes
- **Lambda duration** > 1 minute
- **Step Function failures** (any failure)
- **SNS notifications** to configured email

## 🧪 Testing

### Infrastructure Testing
All infrastructure changes are automatically tested:
- **Terraform validation**
- **Security scanning** with Checkov
- **Plan verification**
- **Apply with verification**

### Functional Testing
Test the deployed pipeline:
```bash
# Execute test run
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT:stateMachine:aws-ssm-fetcher-prod-pipeline" \
  --input '{}' \
  --name "test-execution-$(date +%s)"
```

## 🔄 Maintenance

### Regular Operations
- **Daily automated execution** via EventBridge
- **Automatic log rotation** (14 days retention)
- **S3 lifecycle policies** for report cleanup
- **CloudWatch alarms** for proactive monitoring

### Updates and Changes
All updates must go through GitHub Actions:

```bash
# Deploy infrastructure changes
git push origin main  # Triggers automatic deployment

# Or manually trigger
gh workflow run "Terraform Deployment" --ref main
```

## 🚨 Troubleshooting

### Common Issues

**Lambda Package Too Large**
```bash
# Check package sizes
ls -lh lambda_functions/*.zip

# Rebuild if needed
cd lambda_functions && ./scripts/build_packages.sh
```

**Permission Errors**
- Check IAM roles in AWS Console
- Verify OIDC provider configuration
- Review CloudWatch logs for specific errors

**Step Function Failures**
- Check Step Functions console for execution details
- Review individual Lambda function logs
- Verify input/output format between functions

### Support Resources
- **CloudWatch Logs**: `/aws/lambda/aws-ssm-fetcher-prod-*`
- **CloudWatch Dashboard**: `aws-ssm-fetcher-prod-dashboard`
- **GitHub Actions**: Repository Actions tab
- **Terraform State**: Managed in S3 backend

## 🧹 Cleanup

**⚠️ WARNING: This will delete all production resources**

```bash
# DANGER: Only run if you want to destroy everything
gh workflow run "Terraform Deployment" --ref main -f action=destroy
```

## 📚 Additional Resources

- **Terraform Documentation**: `terraform/README.md`
- **Architecture Guide**: `docs/architecture/`
- **GitHub Actions Workflows**: `.github/workflows/`
- **Lambda Function Code**: `lambda_functions/`

---

**🎉 Your AWS SSM Data Fetcher is now deployed and operational!**

The system will automatically execute daily and generate comprehensive AWS service and region reports available in your S3 bucket.
