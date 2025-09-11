output "dashboard_url" {
  description = "URL to the CloudWatch dashboard"
  value       = "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "alarm_topic_arn" {
  description = "ARN of the SNS topic for alarms"
  value       = var.enable_sns_notifications ? aws_sns_topic.alarms[0].arn : null
}

output "lambda_error_alarms" {
  description = "Names of Lambda error alarms"
  value       = aws_cloudwatch_metric_alarm.lambda_errors[*].alarm_name
}

output "lambda_duration_alarms" {
  description = "Names of Lambda duration alarms"
  value       = aws_cloudwatch_metric_alarm.lambda_duration[*].alarm_name
}

output "step_function_failure_alarm" {
  description = "Name of Step Functions failure alarm"
  value       = var.step_function_arn != "" ? aws_cloudwatch_metric_alarm.step_function_failures[0].alarm_name : null
}
