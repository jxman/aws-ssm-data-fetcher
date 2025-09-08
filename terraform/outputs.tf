output "s3_bucket_name" {
  description = "Name of the S3 bucket for cache and outputs"
  value       = module.s3_storage.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3_storage.bucket_arn
}

output "lambda_data_fetcher_arn" {
  description = "ARN of the data fetcher Lambda function"
  value       = module.lambda_data_fetcher.function_arn
}

output "lambda_processor_arn" {
  description = "ARN of the processor Lambda function"
  value       = module.lambda_processor.function_arn
}

output "lambda_report_generator_arn" {
  description = "ARN of the report generator Lambda function"
  value       = module.lambda_report_generator.function_arn
}

output "lambda_layer_arn" {
  description = "ARN of the shared Lambda layer"
  value       = module.lambda_layer.layer_arn
}

output "step_function_arn" {
  description = "ARN of the Step Functions state machine"
  value       = module.step_functions.state_machine_arn
}

output "step_function_name" {
  description = "Name of the Step Functions state machine"
  value       = module.step_functions.state_machine_name
}

output "cloudwatch_dashboard_url" {
  description = "URL to the CloudWatch dashboard"
  value       = module.cloudwatch.dashboard_url
}

output "iam_lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.iam.lambda_execution_role_arn
}

output "iam_step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = module.iam.step_functions_role_arn
}

# Useful information for CLI and local development
output "deployment_info" {
  description = "Information for deployment and testing"
  value = {
    environment   = var.environment
    aws_region    = var.aws_region
    s3_bucket     = module.s3_storage.bucket_name
    step_function = module.step_functions.state_machine_name
    lambda_functions = {
      data_fetcher     = module.lambda_data_fetcher.function_name
      processor        = module.lambda_processor.function_name
      report_generator = module.lambda_report_generator.function_name
    }
  }
}
