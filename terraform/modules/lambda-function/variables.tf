variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "function_role" {
  description = "ARN of the IAM role for Lambda function"
  type        = string
}

variable "lambda_layer_arn" {
  description = "ARN of the Lambda layer"
  type        = string
  default     = ""
}

variable "source_path" {
  description = "Path to the Lambda function source code"
  type        = string
}

variable "handler" {
  description = "Lambda function handler"
  type        = string
}

variable "runtime" {
  description = "Lambda function runtime"
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 1024
}

variable "environment_variables" {
  description = "Environment variables for Lambda function"
  type        = map(string)
  default     = {}
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}

variable "log_retention_days" {
  description = "CloudWatch logs retention in days"
  type        = number
  default     = 14
}

variable "subnet_ids" {
  description = "List of subnet IDs for VPC configuration"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "List of security group IDs for VPC configuration"
  type        = list(string)
  default     = []
}

# Optional variables for event source mapping
variable "event_source_arn" {
  description = "ARN of the event source (e.g., SQS, Kinesis)"
  type        = string
  default     = ""
}

variable "starting_position" {
  description = "Starting position for event source mapping"
  type        = string
  default     = "LATEST"
}

variable "batch_size" {
  description = "Maximum number of items to retrieve in a single batch"
  type        = number
  default     = 10
}

variable "maximum_batching_window_in_seconds" {
  description = "Maximum amount of time to gather records before invoking the function"
  type        = number
  default     = 0
}
