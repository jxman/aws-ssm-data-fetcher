variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}

variable "lambda_function_names" {
  description = "List of Lambda function names to monitor"
  type        = list(string)
}

variable "step_function_arn" {
  description = "ARN of the Step Functions state machine"
  type        = string
}

variable "enable_sns_notifications" {
  description = "Enable SNS notifications for alarms"
  type        = bool
  default     = false
}

variable "sns_email" {
  description = "Email address for SNS notifications"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch logs retention in days"
  type        = number
  default     = 14
}
