variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "log_level" {
  description = "Log level for Lambda functions"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

variable "enable_monitoring" {
  description = "Enable enhanced CloudWatch monitoring and alarms"
  type        = bool
  default     = true
}

variable "retention_days" {
  description = "CloudWatch logs retention in days"
  type        = number
  default     = 14

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.retention_days)
    error_message = "Retention days must be a valid CloudWatch logs retention period."
  }
}

variable "sns_email" {
  description = "Email address for SNS notifications (optional)"
  type        = string
  default     = ""
}

variable "schedule_expression" {
  description = "CloudWatch Events rule schedule expression for automated runs"
  type        = string
  default     = "rate(24 hours)" # Run daily
}

variable "enable_scheduled_execution" {
  description = "Enable scheduled execution of the Step Function"
  type        = bool
  default     = false
}

variable "s3_force_destroy" {
  description = "Allow Terraform to destroy S3 bucket with objects (use with caution)"
  type        = bool
  default     = false
}

variable "enable_sns_notifications" {
  description = "Enable SNS notifications for alarms"
  type        = bool
  default     = false
}
