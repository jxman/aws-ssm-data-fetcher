# 🚀 Production Deployment Guide - AWS SSM Data Fetcher

## 📋 Overview

This guide provides complete step-by-step instructions for deploying the AWS SSM Data Fetcher to production using GitHub Actions CI/CD pipeline. The system is fully automated and ready for production deployment.

## 🎯 Current Status

✅ **Repository Setup**: Complete with CI/CD pipeline  
✅ **Infrastructure Code**: All Terraform templates ready  
✅ **GitHub Actions**: Fully configured workflows  
✅ **Security**: OIDC authentication implemented  
✅ **Monitoring**: CloudWatch dashboards and alarms ready  

## 🏗️ Architecture Overview

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
           │         AWS Infrastructure              │
           │ S3 • IAM • CloudWatch • Step Functions │
           │        GitHub Actions CI/CD             │
           └─────────────────────────────────────────┘
```

## 📋 Prerequisites

### 1. AWS Account Setup
- [ ] AWS account with admin access
- [ ] AWS region selected (recommended: `us-east-1`)
- [ ] Terraform state bucket created (see setup instructions)

### 2. GitHub Repository Access
- [ ] Access to `jxman/aws-ssm-data-fetcher` repository
- [ ] Admin permissions to configure secrets and environments

### 3. Local Development Environment (Optional)
- [ ] AWS CLI installed and configured
- [ ] Terraform 1.5.0+ installed
- [ ] GitHub CLI installed (`gh`)

## 🔧 Step 1: AWS OIDC Infrastructure Bootstrap

The first step is to create the AWS OIDC infrastructure that allows GitHub Actions to securely deploy to AWS.

### 1.1 Create Terraform State Bucket

```bash
# Create unique S3 bucket for Terraform state
aws s3 mb s3://aws-ssm-fetcher-terraform-state-$(whoami) --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket aws-ssm-fetcher-terraform-state-$(whoami) \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket aws-ssm-fetcher-terraform-state-$(whoami) \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### 1.2 Deploy OIDC Infrastructure

```bash
# Clone the repository
git clone https://github.com/jxman/aws-ssm-data-fetcher.git
cd aws-ssm-data-fetcher

# Navigate to bootstrap directory
cd bootstrap

# Initialize and deploy OIDC infrastructure
terraform init
terraform plan -var="tf_state_bucket=aws-ssm-fetcher-terraform-state-$(whoami)"
terraform apply -var="tf_state_bucket=aws-ssm-fetcher-terraform-state-$(whoami)"
```

**Expected Output:**
```
Apply complete! Resources: 3 added, 0 changed, 0 destroyed.

Outputs:
github_actions_role_arn = "arn:aws:iam::123456789012:role/GithubActionsOIDC-aws-ssm-fetcher-Role"
oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
```

## 🔐 Step 2: Configure GitHub Repository Secrets

### 2.1 Required Secrets

Add these secrets to your GitHub repository (`Settings` → `Secrets and Variables` → `Actions`):

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AWS_ROLE_ARN` | `arn:aws:iam::ACCOUNT:role/GithubActionsOIDC-aws-ssm-fetcher-Role` | IAM role for GitHub Actions |
| `TF_STATE_BUCKET` | `aws-ssm-fetcher-terraform-state-$(whoami)` | S3 bucket for Terraform state |

### 2.2 Using GitHub CLI

```bash
# Set the role ARN (replace with your account ID)
gh secret set AWS_ROLE_ARN --body "arn:aws:iam::123456789012:role/GithubActionsOIDC-aws-ssm-fetcher-Role"

# Set the state bucket (replace with your bucket name)
gh secret set TF_STATE_BUCKET --body "aws-ssm-fetcher-terraform-state-$(whoami)"
```

### 2.3 Environment Setup

Create environments for each deployment stage:

1. Go to `Settings` → `Environments`
2. Create three environments:
   - `dev`
   - `staging` 
   - `prod`

Each environment should have the same secrets configured.

## 🚀 Step 3: Deploy Infrastructure

### 3.1 Trigger Terraform Deployment

```bash
# Deploy to development environment
gh workflow run "Terraform Deployment" --ref main -f environment=dev

# Monitor the deployment
gh run list --limit 5
gh run view [RUN_ID] --web
```

### 3.2 Expected Infrastructure

The deployment will create approximately 42 AWS resources:

**Core Infrastructure:**
- S3 bucket with lifecycle policies and encryption
- 3 Lambda functions + 1 shared layer
- Step Functions state machine for orchestration
- IAM roles and policies with least-privilege access
- CloudWatch dashboards and alarms
- Dead letter queues for error handling

**Monitoring:**
- CloudWatch logs for all Lambda functions
- Custom metrics and alarms
- Dashboard with key performance indicators

### 3.3 Verify Deployment

```bash
# Check deployment status
gh run view --log

# Verify resources in AWS Console
aws stepfunctions list-state-machines --query 'stateMachines[?contains(name, `aws-ssm-fetcher-dev`)]'
aws s3 ls | grep aws-ssm-fetcher
```

## ⚡ Step 4: Test the Pipeline

### 4.1 Manual Pipeline Execution

```bash
# Run the scheduled execution workflow
gh workflow run "Scheduled Lambda Execution" --ref main -f environment=dev

# Monitor execution
gh run list --limit 1
gh run view [RUN_ID]
```

### 4.2 Expected Results

A successful pipeline execution will:

1. ✅ **Check Infrastructure**: Validate that all resources exist
2. ✅ **Execute Step Functions**: Run the data fetching pipeline
3. ✅ **Monitor Progress**: Track execution with real-time updates
4. ✅ **Generate Reports**: Create Excel, JSON, and CSV reports
5. ✅ **Store Results**: Upload reports to S3 bucket
6. ✅ **Cleanup**: Manage old reports per lifecycle policies

### 4.3 Verify Results

```bash
# Check S3 bucket for generated reports
aws s3 ls s3://your-bucket-name/reports/ --recursive

# View CloudWatch dashboard
aws cloudwatch get-dashboard --dashboard-name aws-ssm-fetcher-dev-dashboard
```

## 🌍 Step 5: Multi-Environment Deployment

### 5.1 Staging Environment

```bash
# Deploy to staging
gh workflow run "Terraform Deployment" --ref main -f environment=staging

# Test staging pipeline
gh workflow run "Scheduled Lambda Execution" --ref main -f environment=staging
```

### 5.2 Production Environment

```bash
# Deploy to production (requires approval)
gh workflow run "Terraform Deployment" --ref main -f environment=prod

# Set up daily schedule (production only)
# The workflow includes automatic scheduling for production
```

## 📊 Step 6: Monitoring and Maintenance

### 6.1 CloudWatch Monitoring

**Key Metrics to Monitor:**
- Lambda function duration and errors
- Step Functions execution success rate
- S3 storage usage and access patterns
- API throttling and rate limits

**Alarms Configured:**
- Lambda function errors > 5%
- Step Functions execution failures
- S3 upload failures
- Memory usage > 80%

### 6.2 Automated Maintenance

**Daily Operations:**
- Scheduled pipeline execution (6 AM UTC)
- Report generation and S3 upload
- Log rotation and cleanup
- Performance metrics collection

**Weekly Operations:**
- Old report cleanup (30-day retention)
- Cost analysis and optimization
- Security audit and updates

### 6.3 Manual Monitoring Commands

```bash
# Check recent executions
aws stepfunctions list-executions --state-machine-arn [STATE_MACHINE_ARN] --max-items 10

# View CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/aws-ssm-fetcher"

# Check S3 storage usage
aws s3 ls s3://your-bucket-name --recursive --human-readable --summarize
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. OIDC Authentication Failures
**Symptoms:** GitHub Actions fail with authentication errors

**Solutions:**
```bash
# Verify OIDC provider exists
aws iam list-open-id-connect-providers

# Check role trust policy
aws iam get-role --role-name GithubActionsOIDC-aws-ssm-fetcher-Role
```

#### 2. Terraform State Lock Issues
**Symptoms:** Terraform deployment fails with state lock errors

**Solutions:**
```bash
# Force unlock (use carefully)
terraform force-unlock [LOCK_ID] -force

# Check DynamoDB lock table
aws dynamodb scan --table-name terraform-state-locks
```

#### 3. Lambda Function Timeouts
**Symptoms:** Step Functions show Lambda timeout errors

**Solutions:**
- Increase Lambda timeout in Terraform configuration
- Optimize data processing logic
- Implement pagination for large datasets

#### 4. Permission Denied Errors
**Symptoms:** Lambda functions fail with permission errors

**Solutions:**
```bash
# Verify IAM policies
aws iam list-attached-role-policies --role-name aws-ssm-fetcher-dev-lambda-role

# Check resource permissions
aws s3api get-bucket-policy --bucket your-bucket-name
```

### Getting Help

1. **GitHub Issues**: Report problems at https://github.com/jxman/aws-ssm-data-fetcher/issues
2. **CloudWatch Logs**: Check detailed error messages in AWS Console
3. **Terraform Logs**: Review GitHub Actions workflow logs for deployment issues
4. **AWS Documentation**: Consult AWS service-specific documentation

## 🔄 Continuous Deployment

### Automatic Deployments

The system is configured for automatic deployment on:

- **Code Changes**: Any push to `main` branch triggers tests and validation
- **Infrastructure Changes**: Terraform changes automatically deployed after approval
- **Scheduled Updates**: Daily pipeline execution with monitoring

### Manual Deployments

```bash
# Deploy specific commit to production
gh workflow run "Terraform Deployment" --ref [COMMIT_SHA] -f environment=prod

# Rollback to previous version (redeploy previous commit)
gh workflow run "Terraform Deployment" --ref [PREVIOUS_COMMIT] -f environment=prod
```

## 📈 Cost Optimization

### Expected Monthly Costs

**Development Environment:**
- Lambda executions: ~$2-5
- S3 storage: ~$1-2
- CloudWatch logs: ~$2-3
- **Total: ~$5-10/month**

**Production Environment:**
- Lambda executions: ~$10-20
- S3 storage: ~$2-5
- CloudWatch monitoring: ~$5-10
- **Total: ~$17-35/month**

### Cost Optimization Tips

1. **Adjust Lambda memory** based on actual usage
2. **Implement S3 lifecycle policies** for old reports
3. **Use CloudWatch log retention** policies
4. **Monitor and optimize** Step Functions executions

## ✅ Production Readiness Checklist

### Security
- [ ] OIDC authentication configured
- [ ] Least-privilege IAM policies applied
- [ ] S3 bucket encryption enabled
- [ ] CloudTrail logging enabled
- [ ] Security groups properly configured

### Reliability
- [ ] Dead letter queues configured
- [ ] Circuit breakers implemented
- [ ] Retry logic for transient failures
- [ ] Health checks and monitoring
- [ ] Backup and recovery procedures

### Performance
- [ ] Lambda functions optimized for memory/CPU
- [ ] S3 lifecycle policies configured
- [ ] CloudWatch monitoring active
- [ ] Cost optimization measures applied

### Compliance
- [ ] Data retention policies defined
- [ ] Access logging enabled
- [ ] Audit trail configured
- [ ] Change management process
- [ ] Documentation updated

---

## 🎉 Next Steps

After completing this deployment guide:

1. **Monitor the system** for 1-2 weeks to establish baselines
2. **Review costs** and optimize based on actual usage
3. **Set up alerts** for critical metrics and failures
4. **Document any customizations** or environment-specific changes
5. **Train team members** on monitoring and maintenance procedures

The AWS SSM Data Fetcher is now ready for production use with a complete CI/CD pipeline, comprehensive monitoring, and automated daily execution! 🚀