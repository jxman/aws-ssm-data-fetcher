# 🚀 GitHub Repository & CI/CD Setup Guide

This guide will help you set up a GitHub repository with complete CI/CD pipelines for the AWS SSM Data Fetcher project.

## 📋 Prerequisites

- AWS Account with administrative access
- GitHub account
- AWS CLI configured locally
- Terraform installed locally (>= 1.5.0)

## 🔧 Step 1: Create GitHub Repository

### 1.1 Create Repository
```bash
# Option 1: Using GitHub CLI
gh repo create your-username/aws-ssm-data-fetcher --public --description "AWS SSM Data Fetcher - Serverless Lambda Architecture"

# Option 2: Create manually on GitHub.com
# Then clone: git clone https://github.com/your-username/aws-ssm-data-fetcher.git
```

### 1.2 Initialize Repository
```bash
cd aws-ssm-data-fetcher

# Copy your existing project files
cp -r /path/to/your/current/project/* .

# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit: AWS SSM Data Fetcher serverless architecture"
git branch -M main
git push -u origin main

# Create develop branch for development workflows
git checkout -b develop
git push -u origin develop
```

## 🔐 Step 2: Set Up AWS OIDC Authentication

### 2.1 Create Terraform State Bucket
```bash
# Create S3 bucket for Terraform state (replace with unique name)
aws s3 mb s3://your-terraform-state-bucket-name --region us-east-1

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

### 2.2 Deploy OIDC Infrastructure
Create a temporary Terraform configuration to bootstrap OIDC:

**bootstrap/main.tf:**
```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "github_oidc" {
  source = "../terraform/modules/github-oidc"

  project_name       = "aws-ssm-fetcher"
  github_repository  = "your-username/aws-ssm-data-fetcher"  # Replace with your repo
  tf_state_bucket    = "your-terraform-state-bucket-name"   # Replace with your bucket

  common_tags = {
    Project     = "aws-ssm-fetcher"
    Environment = "bootstrap"
    ManagedBy   = "terraform"
  }
}

output "github_actions_role_arn" {
  description = "ARN for GitHub Actions authentication"
  value       = module.github_oidc.github_actions_role_arn
}

output "oidc_provider_arn" {
  description = "OIDC Provider ARN"
  value       = module.github_oidc.oidc_provider_arn
}
```

Deploy OIDC infrastructure:
```bash
mkdir bootstrap
cd bootstrap

# Create the main.tf file above
# Then deploy:
terraform init
terraform plan
terraform apply

# Note the output ARNs - you'll need them for GitHub secrets
export GITHUB_ROLE_ARN=$(terraform output -raw github_actions_role_arn)
echo "GitHub Actions Role ARN: $GITHUB_ROLE_ARN"
```

## ⚙️ Step 3: Configure GitHub Repository Settings

### 3.1 Set Up Repository Secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these **Repository Secrets**:
```
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/GithubActionsOIDC-aws-ssm-fetcher-Role
TF_STATE_BUCKET=your-terraform-state-bucket-name
```

### 3.2 Create Environments
Go to your GitHub repository → Settings → Environments

Create these environments with protection rules:

#### Development Environment
- **Name**: `dev`
- **Protection Rules**: None (allow all branches)

#### Staging Environment
- **Name**: `staging`
- **Protection Rules**:
  - Required reviewers: 1
  - Restrict to `develop` branch

#### Production Environment
- **Name**: `prod`
- **Protection Rules**:
  - Required reviewers: 2
  - Restrict to `main` branch
  - Wait timer: 5 minutes

### 3.3 Environment Secrets
For each environment, add the same secrets:
```
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/GithubActionsOIDC-aws-ssm-fetcher-Role
TF_STATE_BUCKET=your-terraform-state-bucket-name
```

## 📁 Step 4: Update Project Configuration

### 4.1 Update Terraform Configuration
Edit `terraform/main.tf` to include the OIDC module:

```hcl
# Add this module to your main.tf
module "github_oidc" {
  source = "./modules/github-oidc"

  project_name       = local.project_name
  github_repository  = "your-username/aws-ssm-data-fetcher"  # Replace with your repo
  tf_state_bucket    = "your-terraform-state-bucket-name"   # Replace with your bucket
  common_tags        = local.common_tags
}
```

### 4.2 Update Environment Files
Update `terraform/environments/*.tfvars` with your specific configurations:

**terraform/environments/dev.tfvars:**
```hcl
# Development environment configuration
environment    = "dev"
aws_region     = "us-east-1"
log_level      = "DEBUG"

# Monitoring configuration
enable_monitoring         = true
retention_days           = 7
enable_sns_notifications = false
sns_email               = ""

# Scheduling (disabled for dev)
enable_scheduled_execution = false
schedule_expression       = "rate(24 hours)"

# S3 configuration
s3_force_destroy = true  # Allow destruction with objects for dev environment
```

## 🔄 Step 5: Branch Strategy & Workflows

### 5.1 Branch Strategy
```
main (production)
├── staging
│   └── develop (development)
│       ├── feature/new-feature
│       └── hotfix/critical-fix
```

### 5.2 Workflow Triggers
- **Push to `develop`**: Deploy to dev environment
- **Push to `main`**: Deploy to production environment
- **Pull Request**: Run tests and Terraform plan
- **Manual**: Deploy to any environment with approval

### 5.3 Environment Promotion Flow
```
Dev → Staging → Production
```

## 🧪 Step 6: Test Your Setup

### 6.1 Test OIDC Authentication
Create a simple test workflow:

**.github/workflows/test-auth.yml:**
```yaml
name: Test OIDC Authentication
on:
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  test-auth:
    runs-on: ubuntu-latest
    steps:
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
        aws-region: us-east-1
        role-session-name: GitHubActions-Test

    - name: Test AWS Access
      run: |
        aws sts get-caller-identity
        echo "✅ OIDC authentication successful!"
```

### 6.2 Test Full Deployment
```bash
# Push to develop branch to trigger dev deployment
git checkout develop
git add .
git commit -m "Test: Initial GitHub Actions deployment"
git push origin develop

# Monitor the Actions tab in GitHub
```

## 📊 Step 7: Monitor and Maintain

### 7.1 GitHub Actions Monitoring
- Monitor workflow runs in the Actions tab
- Set up failure notifications
- Review deployment summaries

### 7.2 AWS Resource Monitoring
- Use CloudWatch dashboards created by Terraform
- Monitor costs in AWS Cost Explorer
- Set up billing alerts

### 7.3 Security Best Practices
- Regularly rotate OIDC thumbprints (GitHub publishes updates)
- Review IAM permissions quarterly
- Monitor CloudTrail logs for suspicious activity
- Enable AWS Config for compliance monitoring

## 🚨 Troubleshooting

### Common Issues

#### 1. OIDC Authentication Fails
```bash
# Check role trust policy
aws iam get-role --role-name GithubActionsOIDC-aws-ssm-fetcher-Role

# Verify OIDC provider exists
aws iam list-open-id-connect-providers
```

#### 2. Terraform State Lock Issues
```bash
# Check DynamoDB table for locks
aws dynamodb scan --table-name terraform-state-lock-aws-ssm-fetcher

# Manual unlock if needed (use with caution)
terraform force-unlock LOCK_ID
```

#### 3. Permission Denied Errors
- Check IAM policy permissions
- Verify resource naming matches patterns
- Review CloudTrail logs for specific denied actions

### Getting Help
1. Check GitHub Actions workflow logs
2. Review AWS CloudWatch logs
3. Check AWS CloudTrail for permission issues
4. Validate Terraform configuration with `terraform validate`

## 🎉 Next Steps

Once setup is complete:

1. **Deploy to Development**: Push to `develop` branch
2. **Test Functionality**: Use manual workflow dispatch to test all environments
3. **Set up Monitoring**: Configure alerts and dashboards
4. **Documentation**: Update team documentation with deployment procedures
5. **Training**: Train team members on the CI/CD workflows

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS OIDC for GitHub Actions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

---

## 🔒 Security Checklist

- [ ] OIDC provider configured with correct thumbprints
- [ ] IAM role has least-privilege permissions
- [ ] GitHub repository secrets are properly configured
- [ ] Environment protection rules are in place
- [ ] Terraform state bucket is encrypted and versioned
- [ ] AWS CloudTrail is enabled for audit logging
- [ ] Billing alerts are configured
- [ ] Team members have appropriate GitHub repository access

**✅ Setup Complete!** Your AWS SSM Data Fetcher now has enterprise-grade CI/CD with GitHub Actions! 🚀
