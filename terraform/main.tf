terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # backend "s3" {
  #   # Configure backend in terraform init
  #   # bucket = "your-terraform-state-bucket"
  #   # key    = "aws-ssm-fetcher/terraform.tfstate"
  #   # region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-ssm-fetcher"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources for current AWS account and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local variables
locals {
  project_name = "aws-ssm-fetcher"
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.name

  common_tags = {
    Project     = local.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# S3 Bucket for cache and outputs
module "s3_storage" {
  source = "./modules/s3"

  project_name = local.project_name
  environment  = var.environment
  common_tags  = local.common_tags
}

# IAM roles and policies for Lambda functions
module "iam" {
  source = "./modules/iam"

  project_name = local.project_name
  environment  = var.environment
  common_tags  = local.common_tags

  s3_bucket_arn = module.s3_storage.bucket_arn
}

# Lambda shared layer
module "lambda_layer" {
  source = "./modules/lambda-layer"

  project_name = local.project_name
  environment  = var.environment
  common_tags  = local.common_tags
}

# Lambda functions
module "lambda_data_fetcher" {
  source = "./modules/lambda-function"

  project_name     = local.project_name
  environment      = var.environment
  function_name    = "data-fetcher"
  function_role    = module.iam.lambda_execution_role_arn
  lambda_layer_arn = module.lambda_layer.layer_arn

  source_path = "../lambda_functions/data_fetcher"
  handler     = "lambda_function.lambda_handler"
  runtime     = "python3.11"
  timeout     = 900  # 15 minutes
  memory_size = 1024 # 1GB

  environment_variables = {
    S3_BUCKET        = module.s3_storage.bucket_name
    OUTPUT_S3_BUCKET = module.s3_storage.bucket_name
    CACHE_S3_BUCKET  = module.s3_storage.bucket_name
    S3_CACHE_BUCKET  = module.s3_storage.bucket_name
    CACHE_PREFIX     = "cache"
    LOG_LEVEL        = var.log_level
    ENVIRONMENT      = var.environment
  }

  common_tags = local.common_tags
}

module "lambda_processor" {
  source = "./modules/lambda-function"

  project_name     = local.project_name
  environment      = var.environment
  function_name    = "processor"
  function_role    = module.iam.lambda_execution_role_arn
  lambda_layer_arn = module.lambda_layer.layer_arn

  source_path = "../lambda_functions/processor"
  handler     = "lambda_function.lambda_handler"
  runtime     = "python3.11"
  timeout     = 900  # 15 minutes
  memory_size = 3008 # 3GB (for pandas/numpy processing)

  environment_variables = {
    S3_BUCKET        = module.s3_storage.bucket_name
    OUTPUT_S3_BUCKET = module.s3_storage.bucket_name
    CACHE_S3_BUCKET  = module.s3_storage.bucket_name
    S3_CACHE_BUCKET  = module.s3_storage.bucket_name
    CACHE_PREFIX     = "cache"
    LOG_LEVEL        = var.log_level
    ENVIRONMENT      = var.environment
  }

  common_tags = local.common_tags
}

module "lambda_report_generator" {
  source = "./modules/lambda-function"

  project_name     = local.project_name
  environment      = var.environment
  function_name    = "report-generator"
  function_role    = module.iam.lambda_execution_role_arn
  lambda_layer_arn = module.lambda_layer.layer_arn

  source_path = "../lambda_functions/report_generator"
  handler     = "lambda_function.lambda_handler"
  runtime     = "python3.11"
  timeout     = 600  # 10 minutes
  memory_size = 2048 # 2GB

  environment_variables = {
    S3_BUCKET        = module.s3_storage.bucket_name
    OUTPUT_S3_BUCKET = module.s3_storage.bucket_name
    CACHE_S3_BUCKET  = module.s3_storage.bucket_name
    S3_CACHE_BUCKET  = module.s3_storage.bucket_name
    OUTPUT_PREFIX    = "reports"
    LOG_LEVEL        = var.log_level
    ENVIRONMENT      = var.environment
  }

  common_tags = local.common_tags
}

# Step Functions for orchestration
module "step_functions" {
  source = "./modules/step-functions"

  project_name = local.project_name
  environment  = var.environment
  common_tags  = local.common_tags

  data_fetcher_arn     = module.lambda_data_fetcher.function_arn
  processor_arn        = module.lambda_processor.function_arn
  report_generator_arn = module.lambda_report_generator.function_arn

  lambda_execution_role_arn = module.iam.step_functions_role_arn
}

# CloudWatch monitoring
module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name = local.project_name
  environment  = var.environment
  common_tags  = local.common_tags

  lambda_function_names = [
    module.lambda_data_fetcher.function_name,
    module.lambda_processor.function_name,
    module.lambda_report_generator.function_name
  ]

  step_function_arn        = module.step_functions.state_machine_arn
  enable_sns_notifications = var.enable_sns_notifications
  sns_email                = var.sns_email
}
