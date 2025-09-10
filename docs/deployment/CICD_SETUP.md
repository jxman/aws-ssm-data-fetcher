# 🔄 CI/CD Pipeline Setup Guide

## Overview

This document provides comprehensive instructions for setting up the complete CI/CD pipeline for the AWS SSM Data Fetcher project using GitHub Actions. The pipeline includes automated testing, security scanning, infrastructure deployment, and scheduled execution.

## 🏗️ Pipeline Architecture

### Workflow Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflows                 │
├─────────────────────────────────────────────────────────────┤
│  📋 Test & Validate     │  🚀 Terraform Deploy  │  ⏰ Scheduled │
│  ┌─────────────────┐   │  ┌─────────────────┐   │  ┌─────────┐ │
│  │ • Unit Tests    │   │  │ • Build Packages│   │  │ • Daily │ │
│  │ • Lambda Build  │   │  │ • Deploy Infra  │   │  │ • Manual│ │
│  │ • Security Scan │   │  │ • Test Deploy   │   │  │ • Monitor│ │
│  │ • Code Quality  │   │  │ • Outputs       │   │  │ • Notify│ │
│  └─────────────────┘   │  └─────────────────┘   │  └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │      AWS Infrastructure      │
                  │ Step Functions • Lambda     │
                  │ S3 • CloudWatch • SNS      │
                  └─────────────────────────────┘
```

## 🔧 Prerequisites Setup

### 1. AWS OIDC Configuration

First, set up OIDC authentication for secure, keyless access to AWS:

```bash
# Create OIDC provider (if not exists)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role for GitHub Actions
aws iam create-role \
  --role-name GitHubActions-AWSSSMFetcher-Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          },
          "StringLike": {
            "token.actions.githubusercontent.com:sub": "repo:YOUR-USERNAME/aws_serivce_lambda:*"
          }
        }
      }
    ]
  }'

# Attach necessary policies
aws iam attach-role-policy \
  --role-name GitHubActions-AWSSSMFetcher-Role \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

### 2. S3 Backend Setup

Create S3 bucket for Terraform state:

```bash
# Create state bucket
aws s3 mb s3://your-terraform-state-bucket-name

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket-name \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket your-terraform-state-bucket-name \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'
```

### 3. GitHub Repository Secrets

Set up these repository secrets in GitHub:
- Go to `Settings > Secrets and variables > Actions`

```bash
# Required secrets
AWS_ROLE_ARN=arn:aws:iam::ACCOUNT:role/GitHubActions-AWSSSMFetcher-Role
TF_STATE_BUCKET=your-terraform-state-bucket-name
```

### 4. GitHub Environments

Create environments in GitHub (`Settings > Environments`):

#### **Development Environment**
- **Name**: `dev`
- **Protection rules**: None (allow any branch)
- **Environment secrets**: None additional required

#### **Staging Environment**
- **Name**: `staging`
- **Protection rules**:
  - Required reviewers: 1 person
  - Restrict to `develop` branch
- **Environment secrets**: Same as repository secrets

#### **Production Environment**
- **Name**: `prod`
- **Protection rules**:
  - Required reviewers: 2 people
  - Restrict to `main` branch
  - Deployment timer: 5 minutes
- **Environment secrets**: Same as repository secrets

## 📋 Workflow Details

### 1. Test and Validate Workflow

**Trigger**: Every push/PR
**Purpose**: Comprehensive validation

#### Features:
- **Unit & Integration Tests**: Complete test suite validation
- **Lambda Package Building**: Verify packages build and size limits
- **Code Quality**: Black, isort, flake8, mypy checks
- **Security Scanning**: Bandit security analysis
- **Documentation Validation**: Ensure docs are complete
- **Terraform Validation**: Format and configuration checks

### 2. Terraform Deploy Workflow

**Trigger**: Push to main/develop, manual dispatch
**Purpose**: Infrastructure deployment

#### Features:
- **Multi-Environment**: Automatic environment detection
- **Security Scanning**: TFSec security analysis
- **Lambda Package Building**: Fresh package building
- **Terraform Operations**: Plan, apply, destroy
- **Infrastructure Testing**: Post-deployment validation
- **PR Comments**: Automatic plan comments on PRs

#### Branch Mapping:
- `main` branch → `prod` environment (auto-deploy)
- `develop` branch → `staging` environment (plan only)
- Other branches → `dev` environment (plan only)

### 3. Scheduled Execution Workflow

**Trigger**: Daily schedule, manual dispatch
**Purpose**: Automated data collection

#### Features:
- **Scheduled Execution**: Daily at 6 AM UTC
- **Manual Trigger**: On-demand execution with environment selection
- **Monitoring**: Real-time execution monitoring
- **Results Handling**: Success/failure notifications
- **Report Management**: Automatic cleanup of old reports

## 🚀 Deployment Process

### Automatic Deployment Flow

1. **Developer pushes to `develop`**:
   - Tests run automatically
   - Terraform plan generated for staging
   - Manual approval required for staging deployment

2. **PR merged to `main`**:
   - All tests must pass
   - Security scans must pass
   - Automatic deployment to production
   - Infrastructure testing validates deployment

3. **Production monitoring**:
   - CloudWatch dashboards available
   - Scheduled executions run daily
   - Notifications on failures

### Manual Deployment

Use GitHub Actions UI for manual deployments:

1. Go to `Actions > Terraform Deployment`
2. Click `Run workflow`
3. Select:
   - Environment: `dev`, `staging`, or `prod`
   - Action: `plan`, `apply`, or `destroy`
4. Click `Run workflow`

## 🔒 Security Features

### 1. OIDC Authentication
- No long-lived AWS keys
- Role-based access with repository restrictions
- Automatic token rotation

### 2. Security Scanning
- **TFSec**: Terraform security analysis
- **Bandit**: Python security linting
- **TruffleHog**: Secret detection
- **CodeCov**: Code coverage tracking

### 3. Environment Protection
- **Production**: Requires 2 reviewers + 5-minute delay
- **Staging**: Requires 1 reviewer
- **Development**: No restrictions

### 4. Access Control
- Branch protection rules
- Required status checks
- Signed commits (optional)

## 📊 Monitoring & Observability

### 1. Workflow Monitoring
- **GitHub Actions**: Built-in workflow monitoring
- **Step Summaries**: Detailed execution reports
- **Notifications**: Email notifications on failures

### 2. Infrastructure Monitoring
- **CloudWatch Dashboards**: Real-time metrics
- **CloudWatch Alarms**: Automated alerting
- **SNS Notifications**: Email/SMS alerts

### 3. Execution Tracking
- **Step Functions**: Visual workflow monitoring
- **Lambda Logs**: Detailed execution logs
- **S3 Reports**: Generated report tracking

## 🛠️ Customization Options

### 1. Schedule Modification
Edit `.github/workflows/scheduled-execution.yml`:
```yaml
schedule:
  # Run daily at 6:00 UTC - modify as needed
  - cron: '0 6 * * *'
```

### 2. Environment Variables
Add environment-specific variables in workflow files:
```yaml
env:
  CUSTOM_SETTING: value
  LOG_LEVEL: DEBUG
```

### 3. Notification Channels
Add Slack/Teams notifications:
```yaml
- name: Notify Slack
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## 🧪 Testing the Pipeline

### 1. Test Workflows Locally
Use [act](https://github.com/nektos/act) for local testing:
```bash
# Install act
brew install act

# Test workflows locally
act -j test
act -j terraform --secret-file .secrets
```

### 2. Validate Configuration
```bash
# Test deployment script
./deploy.sh --help

# Validate Terraform
cd terraform && terraform validate

# Test Lambda packages
cd lambda_functions && ./scripts/build_packages.sh
```

## 🔧 Troubleshooting

### Common Issues

#### 1. OIDC Authentication Failures
```bash
# Verify OIDC provider exists
aws iam list-open-id-connect-providers

# Check role trust policy
aws iam get-role --role-name GitHubActions-AWSSSMFetcher-Role
```

#### 2. Terraform State Issues
```bash
# Check state bucket access
aws s3 ls s3://your-terraform-state-bucket-name

# Verify state file
terraform state list
```

#### 3. Lambda Package Size Issues
```bash
# Check package sizes
cd lambda_functions
ls -lh *.zip */deployment_package.zip

# Rebuild with optimization
./scripts/build_packages.sh
```

#### 4. Permission Issues
- Verify IAM role has sufficient permissions
- Check environment protection rules
- Ensure secrets are properly configured

### Debugging Steps

1. **Check GitHub Actions logs**:
   - Go to `Actions` tab in repository
   - Click on failed workflow
   - Review detailed logs

2. **Check AWS CloudWatch**:
   - Review Lambda function logs
   - Check Step Functions execution history
   - Monitor CloudWatch dashboards

3. **Validate Terraform state**:
   - Check S3 state bucket
   - Review Terraform outputs
   - Verify resource creation

## 📚 Additional Resources

### Documentation Links
- [Terraform Infrastructure Guide](TERRAFORM_INFRASTRUCTURE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Project README](../../README.md)

### AWS Documentation
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Step Functions](https://docs.aws.amazon.com/step-functions/)
- [Lambda Functions](https://docs.aws.amazon.com/lambda/)

### GitHub Actions
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Environment Protection](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)

---

This CI/CD pipeline provides a production-ready, secure, and automated deployment system for the AWS SSM Data Fetcher project. The combination of comprehensive testing, security scanning, and automated deployment ensures reliable and safe delivery of infrastructure and code changes.
