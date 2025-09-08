output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.name
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = aws_iam_role.step_functions_execution.arn
}

output "step_functions_role_name" {
  description = "Name of the Step Functions execution role"
  value       = aws_iam_role.step_functions_execution.name
}

output "events_role_arn" {
  description = "ARN of the CloudWatch Events execution role"
  value       = aws_iam_role.events_execution.arn
}

output "events_role_name" {
  description = "Name of the CloudWatch Events execution role"
  value       = aws_iam_role.events_execution.name
}
