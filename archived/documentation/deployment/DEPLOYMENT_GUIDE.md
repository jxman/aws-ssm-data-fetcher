# AWS SSM Data Fetcher - Deployment Guide

⚠️ **IMPORTANT**: This project now uses **GitHub Actions for all deployments**. Manual deployment methods are deprecated.

**👉 For production deployment, see: [PRODUCTION_DEPLOYMENT_GUIDE.md](../../PRODUCTION_DEPLOYMENT_GUIDE.md)**

## Modern Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Fetcher  │───▶│   Processor     │───▶│Report Generator │
│   Lambda        │    │   Lambda        │    │   Lambda        │
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
           │         Step Functions Pipeline         │
           │     S3 • CloudWatch • Monitoring       │
           │        GitHub Actions CI/CD             │
           └─────────────────────────────────────────┘
```

## 🚀 Quick Start (Automated Deployment)

### Prerequisites
- Access to AWS account with admin permissions
- GitHub repository access: `jxman/aws-ssm-data-fetcher`
- AWS CLI configured (for initial OIDC setup only)

### 1. Deploy Infrastructure
```bash
# All deployments now use GitHub Actions
gh workflow run "Terraform Deployment" --ref main -f environment=prod

# Monitor deployment
gh run list --limit 5
gh run view [RUN_ID] --web
```

### 2. Execute Pipeline
```bash
# Run scheduled execution
gh workflow run "Scheduled Lambda Execution" --ref main -f environment=prod

# Check results
gh run view [RUN_ID]
```

---

## 📋 Modern Deployment Process

### Infrastructure Components
The GitHub Actions CI/CD pipeline automatically deploys:

- **3 Lambda Functions**: Data fetcher, processor, and report generator
- **1 Shared Layer**: Core modules and common dependencies
- **Step Functions**: Orchestration pipeline for data processing
- **S3 Bucket**: Secure storage with lifecycle policies and encryption
- **CloudWatch**: Comprehensive monitoring, dashboards, and alarms
- **IAM Roles**: Least-privilege security policies
- **Dead Letter Queues**: Error handling and retry mechanisms

### Automatic Scheduling
- **Daily Execution**: Automatically runs at 6 AM UTC
- **Multi-Environment**: Supports dev, staging, and production
- **Monitoring**: Real-time execution tracking and notifications
- **Error Handling**: Automatic retries and failure notifications

---

## 📊 Output Files and Reports

### Generated Reports
The pipeline automatically creates three types of reports:

1. **Excel Report** (`aws_regions_services.xlsx`)
   - Multi-sheet workbook with comprehensive data
   - Regional services availability matrix
   - Statistics and analytics
   - Professional formatting with conditional styling

2. **JSON Report** (`aws_regions_services.json`)
   - Structured data with metadata
   - API-friendly format
   - Compact variant for efficient consumption

3. **CSV Reports** (Multiple formats)
   - Detailed data export
   - Summary statistics
   - Matrix format for analysis

### Storage and Access
- **S3 Storage**: Secure, encrypted storage with automatic lifecycle management
- **Report Retention**: 30-day retention policy for cost optimization
- **Access Logs**: Complete audit trail for compliance
- **CloudFront Integration**: Ready for web distribution (optional)

---

## 🏗️ Legacy Manual Deployment (DEPRECATED)

⚠️ **DEPRECATED**: The manual deployment steps below are provided for reference only.

**Current deployment method**: Use GitHub Actions workflows as described in [PRODUCTION_DEPLOYMENT_GUIDE.md](../../PRODUCTION_DEPLOYMENT_GUIDE.md)

<details>
<summary>Click to view legacy manual deployment instructions</summary>

## Output Files

The Lambda function will create two files in your S3 bucket daily:

- `aws-data/aws_regions_services.xlsx` - Excel format (5 comprehensive sheets)
- `aws-data/aws_regions_services.json` - JSON format with metadata
- Files are overwritten on each run to maintain consistent naming

## Monitoring

- **CloudWatch Logs**: Monitor function execution and errors
- **CloudWatch Metrics**: Track invocation count, duration, errors
- **S3 Events**: Optional notification when files are created

## Cost Estimation

For daily execution:
- **Lambda**: ~$0.20/month (512MB memory, 60-second execution)
- **S3**: ~$0.02/month for storage (small files)
- **CloudWatch Logs**: ~$0.50/month

Total: **~$0.72/month**

## Website Integration

To serve the data on a website:

1. **Static Website**: Host on S3 with CloudFront
2. **API Gateway**: Create REST API to serve JSON data
3. **CloudFront**: Add caching for better performance

Example CloudFront setup:

```bash
# Create CloudFront distribution for S3 bucket
aws cloudfront create-distribution \
    --distribution-config file://cloudfront-config.json
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check IAM role permissions
2. **Timeout**: Increase Lambda timeout (max 15 minutes)
3. **Memory Issues**: Increase Lambda memory allocation
4. **SSM Rate Limits**: Function includes built-in retry logic

### Debugging

```bash
# View recent logs
aws logs describe-log-streams \
    --log-group-name /aws/lambda/aws-ssm-data-fetcher \
    --order-by LastEventTime \
    --descending

# Get specific log stream
aws logs get-log-events \
    --log-group-name /aws/lambda/aws-ssm-data-fetcher \
    --log-stream-name LOG_STREAM_NAME
```

## Updates and Maintenance

To update the function:

```bash
# Update code
zip -r aws-ssm-fetcher-updated.zip lambda_function.py

# Deploy update
aws lambda update-function-code \
    --function-name aws-ssm-data-fetcher \
    --zip-file fileb://aws-ssm-fetcher-updated.zip
```

## Security Considerations

- **Least Privilege**: IAM role has minimal required permissions
- **VPC**: Consider running Lambda in VPC for additional security
- **Encryption**: Enable S3 bucket encryption
- **Access Logs**: Enable S3 access logging for audit trail

</details>

---

## 🔧 Modern Troubleshooting

### Common Issues with GitHub Actions Deployment

1. **Authentication Failures**
   ```bash
   # Verify OIDC setup
   aws iam list-open-id-connect-providers
   ```

2. **Terraform State Issues**
   ```bash
   # Check state bucket
   aws s3 ls s3://aws-ssm-fetcher-terraform-state-[username]
   ```

3. **Pipeline Execution Failures**
   ```bash
   # View recent workflow runs
   gh run list --limit 5
   gh run view [RUN_ID] --log-failed
   ```

### Getting Help

- **GitHub Issues**: https://github.com/jxman/aws-ssm-data-fetcher/issues
- **Production Guide**: [PRODUCTION_DEPLOYMENT_GUIDE.md](../../PRODUCTION_DEPLOYMENT_GUIDE.md)
- **Architecture Documentation**: [../architecture/](../architecture/)

---

## ✅ Next Steps

After reviewing this guide:

1. **Follow the Production Guide**: See [PRODUCTION_DEPLOYMENT_GUIDE.md](../../PRODUCTION_DEPLOYMENT_GUIDE.md) for complete deployment instructions
2. **Review Architecture**: Understanding the system design in [../architecture/](../architecture/)
3. **Monitor Operations**: Set up CloudWatch monitoring and alerts
4. **Plan Maintenance**: Review ongoing operational requirements
