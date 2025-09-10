variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (prod)"
  type        = string
}

variable "step_function_arn" {
  description = "ARN of the Step Functions state machine to trigger"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "schedule_expression" {
  description = "Schedule expression for EventBridge rule (cron or rate)"
  type        = string
  default     = "cron(0 6 * * ? *)" # Daily at 6 AM UTC
}

variable "enabled" {
  description = "Whether the EventBridge rule should be enabled"
  type        = bool
  default     = true
}
