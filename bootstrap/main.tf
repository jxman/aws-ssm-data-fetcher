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

  project_name      = "aws-ssm-fetcher"
  github_repository = "jxman/aws-ssm-data-fetcher"
  tf_state_bucket   = "aws-ssm-fetcher-terraform-state-jxman" # Unique bucket name

  common_tags = {
    Project     = "aws-ssm-fetcher"
    Environment = "bootstrap"
    ManagedBy   = "terraform"
    Owner       = "jxman"
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

output "setup_commands" {
  description = "Commands to complete setup"
  value       = <<-EOT

    🔑 GitHub Repository Secrets Setup:

    1. Go to: https://github.com/jxman/aws-ssm-data-fetcher/settings/secrets/actions

    2. Add these Repository Secrets:
       AWS_ROLE_ARN = ${module.github_oidc.github_actions_role_arn}
       TF_STATE_BUCKET = aws-ssm-fetcher-terraform-state-jxman

    3. Create Environments (Settings → Environments):
       - dev (no protection)
       - staging (1 reviewer, develop branch only)
       - prod (2 reviewers, main branch only, 5min wait)

    4. Add the same secrets to each environment

    ✅ Next: Configure GitHub repository settings

  EOT
}
