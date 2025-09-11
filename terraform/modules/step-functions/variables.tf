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

variable "data_fetcher_arn" {
  description = "ARN of the data fetcher Lambda function"
  type        = string
}

variable "processor_arn" {
  description = "ARN of the processor Lambda function"
  type        = string
}

variable "json_csv_generator_arn" {
  description = "ARN of the JSON/CSV generator Lambda function"
  type        = string
}

variable "excel_generator_arn" {
  description = "ARN of the Excel generator Lambda function"
  type        = string
}

variable "report_orchestrator_arn" {
  description = "ARN of the report orchestrator Lambda function"
  type        = string
}

variable "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  type        = string
}

variable "events_role_arn" {
  description = "ARN of the CloudWatch Events execution role"
  type        = string
  default     = ""
}

variable "enable_scheduled_execution" {
  description = "Enable scheduled execution of the Step Function"
  type        = bool
  default     = false
}

variable "schedule_expression" {
  description = "CloudWatch Events rule schedule expression"
  type        = string
  default     = "rate(24 hours)"
}

variable "skip_validation" {
  description = "Skip Step Functions validation during deployment (temporary fix for IAM permissions)"
  type        = bool
  default     = false
}
