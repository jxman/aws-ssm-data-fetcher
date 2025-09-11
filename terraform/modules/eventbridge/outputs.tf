output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_execution.arn
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_execution.name
}

output "eventbridge_rule_id" {
  description = "ID of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_execution.id
}

output "eventbridge_iam_role_arn" {
  description = "ARN of the IAM role used by EventBridge"
  value       = var.step_function_arn != "" ? aws_iam_role.eventbridge_step_functions[0].arn : null
}

output "eventbridge_iam_role_name" {
  description = "Name of the IAM role used by EventBridge"
  value       = var.step_function_arn != "" ? aws_iam_role.eventbridge_step_functions[0].name : null
}

output "schedule_expression" {
  description = "Schedule expression used by the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_execution.schedule_expression
}
