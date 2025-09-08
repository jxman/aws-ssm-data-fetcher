output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.main.arn
}

output "state_machine_name" {
  description = "Name of the Step Functions state machine"
  value       = aws_sfn_state_machine.main.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS notification topic"
  value       = aws_sns_topic.notifications.arn
}

output "sns_topic_name" {
  description = "Name of the SNS notification topic"
  value       = aws_sns_topic.notifications.name
}

output "log_group_name" {
  description = "Name of the Step Functions log group"
  value       = aws_cloudwatch_log_group.step_functions_logs.name
}

output "log_group_arn" {
  description = "ARN of the Step Functions log group"
  value       = aws_cloudwatch_log_group.step_functions_logs.arn
}

output "schedule_rule_arn" {
  description = "ARN of the CloudWatch Events rule (if enabled)"
  value       = var.enable_scheduled_execution ? aws_cloudwatch_event_rule.schedule[0].arn : null
}

output "schedule_rule_name" {
  description = "Name of the CloudWatch Events rule (if enabled)"
  value       = var.enable_scheduled_execution ? aws_cloudwatch_event_rule.schedule[0].name : null
}
