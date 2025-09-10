# 🚀 AWS SSM Data Fetcher - Production Deployment Guide

Complete guide for deploying the AWS SSM Data Fetcher serverless application to production using GitHub Actions CI/CD pipeline.

## 📋 Overview

The AWS SSM Data Fetcher is a production-ready serverless application that automatically discovers AWS services and generates comprehensive reports. All deployment is handled through GitHub Actions with OIDC authentication.

## ✅ Prerequisites

1. **AWS Account** with administrative access
2. **GitHub Repository** access to `jxman/aws-ssm-data-fetcher`
3. **AWS CLI** configured locally (for initial setup only)
4. **Terraform >= 1.13** installed locally (for initial setup only)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Fetcher  │───▶│   Processor     │───▶│Report Generator │
│  (Fetch & Cache)│    │ (Transform &    │    │ (Excel/JSON/CSV)│
│    Lambda       │    │   Analyze Data) │    │    Lambda       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │  Shared Layer   │
                    │ (Core Modules)  │
                    └─────────────────┘
                                 │
                                 ▼
           ┌─────────────────────────────────────────┐
           │      🚀 AWS Infrastructure (PROD)       │
           │ S3 • IAM • CloudWatch • Step Functions │
           │        GitHub Actions CI/CD             │
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

# Check Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `aws-ssm-fetcher-prod`)]'

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

```bash
# List available reports
aws s3 ls s3://YOUR-BUCKET-NAME/reports/

# Download latest reports
aws s3 sync s3://YOUR-BUCKET-NAME/reports/ ./reports/
```

## 🛠️ Configuration

### Production Settings

The production deployment uses these optimized settings:

- **Log Level**: INFO
- **Monitoring**: 14-day log retention
- **Scheduling**: Daily execution at 6 AM UTC
- **Notifications**: Enabled via SNS
- **Lambda Memory**: Optimized for performance
- **Lambda Timeout**: 15 minutes per function
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
