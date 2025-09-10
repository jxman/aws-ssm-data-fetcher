# 🏗️ Terraform Infrastructure - Complete Guide

## Overview

This document provides comprehensive information about the Terraform infrastructure created for the AWS SSM Data Fetcher project. The infrastructure implements a complete serverless pipeline with best practices for security, monitoring, and multi-environment deployment.

## 🎯 Infrastructure Architecture

### High-Level Architecture
```
                    CloudWatch Events (Optional Scheduling)
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   Step Functions   │
                        │    State Machine    │
                        └─────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Fetcher  │    │   Processor     │    │Report Generator │
│    Lambda       │    │    Lambda       │    │     Lambda      │
│   (14.7MB)     │    │   (49.8MB)     │    │    (16.3MB)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   Shared Layer      │
                        │     (324KB)         │
                        └─────────────────────┘
                                    │
                                    ▼
         ┌──────────────────────────────────────────────────────┐
         │                AWS Infrastructure                     │
         │  S3 Bucket • IAM Roles • CloudWatch • SNS • DLQs   │
         └──────────────────────────────────────────────────────┘
```

## 🛠️ Infrastructure Components

### Core Infrastructure Modules

#### 1. S3 Storage (`modules/s3/`)
- **Purpose**: Secure cache and output storage
- **Features**:
  - Server-side encryption (AES-256)
  - Versioning enabled
  - Public access blocked
  - Lifecycle policies:
    - Cache cleanup (7 days)
    - Reports archival (IA after 7 days, delete after 30)
  - Bucket naming: `{project}-{environment}-{random-suffix}`

#### 2. IAM Security (`modules/iam/`)
- **Lambda Execution Role**:
  - SSM Parameter Store read access
  - S3 bucket read/write access
  - CloudWatch logs management
  - EC2 describe permissions
- **Step Functions Role**:
  - Lambda function invocation
  - CloudWatch logging
- **CloudWatch Events Role**:
  - Step Functions execution
- **Security**: All roles follow least-privilege principle

#### 3. Lambda Layer (`modules/lambda-layer/`)
- **Shared Layer** (324KB):
  - Core utility modules
  - Configuration management
  - Logging utilities
  - Error handling
- **Optimization**: Heavy dependencies excluded to minimize size

#### 4. Lambda Functions (`modules/lambda-function/`)
- **Configurable Module** supporting:
  - Auto-scaling
  - Dead letter queues
  - VPC configuration (optional)
  - Environment variables
  - CloudWatch log groups with retention
  - Function aliases for versioning

#### 5. Step Functions (`modules/step-functions/`)
- **State Machine Features**:
  - Sequential Lambda execution
  - Comprehensive error handling
  - Retry logic with exponential backoff
  - Success/failure notifications
  - CloudWatch logging
- **Orchestration Flow**:
  1. Data Fetcher → Status Check
  2. Processor → Status Check
  3. Report Generator → Success Notification
  4. Any failure → Failure Notification

#### 6. CloudWatch Monitoring (`modules/cloudwatch/`)
- **Dashboard** with widgets for:
  - Lambda duration, errors, invocations
  - Step Functions execution metrics
- **Alarms**:
  - Lambda error rates (>5 errors)
  - Lambda duration (>1 minute)
  - Step Functions failures
- **Log Groups** with configurable retention
- **SNS Integration** for alert notifications

## 🌍 Multi-Environment Configuration

### Environment-Specific Settings

#### Development (`environments/dev.tfvars`)
```hcl
environment                = "dev"
log_level                 = "DEBUG"
retention_days            = 7
enable_sns_notifications  = false
enable_scheduled_execution = false
s3_force_destroy          = true
```

#### Staging (`environments/staging.tfvars`)
```hcl
environment                = "staging"
log_level                 = "INFO"
retention_days            = 14
enable_sns_notifications  = true
enable_scheduled_execution = true
schedule_expression       = "rate(12 hours)"
s3_force_destroy          = false
```

#### Production (`environments/prod.tfvars`)
```hcl
environment                = "prod"
log_level                 = "WARNING"
retention_days            = 30
enable_sns_notifications  = true
enable_scheduled_execution = true
schedule_expression       = "rate(24 hours)"
s3_force_destroy          = false
```

## 🔧 Deployment Process

### Automated Deployment Script

The `deploy.sh` script provides:
- **Prerequisites validation** (AWS CLI, Terraform version)
- **Lambda package building** (automatic)
- **Environment-specific deployment**
- **Interactive confirmations** for destructive operations
- **Post-deployment output display**

### Deployment Commands

```bash
# Plan deployment
./deploy.sh -e dev

# Deploy with auto-approval
./deploy.sh -e dev -a apply -y

# Destroy environment (with confirmation)
./deploy.sh -e dev -a destroy
```

## 🔒 Security Implementation

### IAM Security Model
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter*",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/aws/service/*"
    }
  ]
}
```

### S3 Security Features
- **Encryption**: AES-256 server-side encryption
- **Access Control**: Bucket policies restricting access
- **Public Access**: Completely blocked
- **Versioning**: Enabled for data protection

### Network Security
- **VPC Support**: Optional VPC deployment
- **Security Groups**: Configurable for Lambda functions
- **Encryption in Transit**: All AWS API calls use TLS

## 📊 Monitoring & Alerting

### CloudWatch Dashboard Widgets
1. **Lambda Duration** - Average execution time
2. **Lambda Errors** - Error count per function
3. **Lambda Invocations** - Invocation count
4. **Step Functions Executions** - Success/failure/started metrics

### Alarm Configuration
```hcl
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
}
```

### SNS Notifications
- **Success Notifications**: Pipeline completion
- **Failure Notifications**: Any step failure
- **Alarm Notifications**: CloudWatch alarm triggers
- **Email Subscriptions**: Configurable email endpoints

## 🔄 Step Functions Pipeline

### State Machine Definition
```json
{
  "Comment": "AWS SSM Data Fetcher Pipeline",
  "StartAt": "DataFetcher",
  "States": {
    "DataFetcher": {
      "Type": "Task",
      "Resource": "${data_fetcher_arn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 6,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "FailureNotification"
        }
      ],
      "Next": "ProcessorCheck"
    }
  }
}
```

### Error Handling Strategy
- **Exponential Backoff**: Retry with increasing delays
- **Maximum Attempts**: 6 retries for service exceptions
- **Dead Letter Queues**: Capture failed executions
- **Notifications**: Immediate alert on failures

## 📈 Cost Optimization

### Lambda Optimization
- **Memory Allocation**: Right-sized for each function
  - Data Fetcher: 1GB (I/O intensive)
  - Processor: 3GB (CPU/memory intensive)
  - Report Generator: 2GB (moderate processing)
- **Timeout Configuration**: Optimized timeouts to prevent runaway costs

### S3 Lifecycle Management
- **Cache Data**: 7-day automatic cleanup
- **Reports**: Standard IA after 7 days, deletion after 30 days
- **Versioning**: Automatic cleanup of old versions

### CloudWatch Cost Control
- **Log Retention**: Environment-specific retention periods
- **Alarm Thresholds**: Prevent excessive alarm notifications
- **Dashboard Optimization**: Essential metrics only

## 🧪 Testing Strategy

### Infrastructure Testing
```bash
# Validate Terraform configuration
terraform validate

# Security scan (if tfsec installed)
tfsec .

# Plan review
terraform plan -var-file="environments/dev.tfvars"
```

### Function Testing
```bash
# Local Lambda testing
python lambda_functions/scripts/test_packages.py

# AWS environment testing
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:region:account:stateMachine:name" \
  --input '{}'
```

## 📚 Infrastructure Outputs

### Key Outputs
- **S3 Bucket Name**: For manual file access
- **Lambda Function ARNs**: For direct invocation
- **Step Function ARN**: For pipeline execution
- **CloudWatch Dashboard URL**: For monitoring
- **SNS Topic ARNs**: For notification management

### Usage Examples
```bash
# Get bucket name
BUCKET=$(terraform output -raw s3_bucket_name)

# Start pipeline execution
aws stepfunctions start-execution \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --input '{}'

# Open dashboard
open $(terraform output -raw cloudwatch_dashboard_url)
```

## 🔧 Troubleshooting

### Common Issues

#### Lambda Package Too Large
```bash
# Check package sizes
ls -lh lambda_functions/*.zip

# Rebuild with optimization
cd lambda_functions && ./scripts/build_packages.sh
```

#### Permission Issues
- Check IAM roles in AWS Console
- Verify S3 bucket policies
- Review CloudWatch logs for specific errors

#### Step Functions Failures
- Check Step Functions console for execution details
- Review individual Lambda function logs
- Verify input/output formats between functions

### Debugging Commands
```bash
# View recent logs
aws logs tail /aws/lambda/aws-ssm-fetcher-dev-data-fetcher --follow

# Check Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw step_function_arn)

# Monitor alarms
aws cloudwatch describe-alarms --state-value ALARM
```

## 🚀 Production Readiness

### Pre-Production Checklist
- [ ] All environments tested (dev/staging/prod)
- [ ] Security review completed
- [ ] Cost optimization verified
- [ ] Monitoring dashboards configured
- [ ] Alert notifications tested
- [ ] Backup and recovery procedures documented
- [ ] Performance baselines established

### Production Deployment
1. **Deploy to staging** for final validation
2. **Run end-to-end tests**
3. **Validate monitoring and alerting**
4. **Deploy to production** with zero downtime
5. **Monitor initial executions**
6. **Enable scheduled execution** if required

## 📋 Maintenance

### Regular Tasks
- **Monthly**: Review CloudWatch costs and usage
- **Quarterly**: Update Lambda runtimes and dependencies
- **Annually**: Review and update security policies
- **As needed**: Scale resources based on usage patterns

### Version Management
- **Terraform State**: Store in S3 with versioning
- **Lambda Functions**: Use aliases for blue/green deployments
- **Infrastructure Changes**: Always plan before apply

---

This infrastructure represents a production-ready, secure, and cost-optimized serverless solution for the AWS SSM Data Fetcher project. The modular design enables easy maintenance, scaling, and customization for different deployment requirements.
