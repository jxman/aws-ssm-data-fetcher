variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (fixed to prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = var.environment == "prod"
    error_message = "This deployment only supports production environment."
  }
}

variable "log_level" {
  description = "Log level for Lambda functions (production default)"
  type        = string
  default     = "WARNING"

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
  description = "CloudWatch logs retention in days (production default)"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.retention_days)
    error_message = "Retention days must be a valid CloudWatch logs retention period."
  }
}

variable "sns_email" {
  description = "Email address for SNS notifications (required for production)"
  type        = string
  default     = "production-alerts@example.com"
}

variable "eventbridge_schedule_expression" {
  description = "EventBridge schedule expression for automated pipeline execution"
  type        = string
  default     = "cron(0 6 * * ? *)" # Daily at 6 AM UTC
}

variable "eventbridge_enabled" {
  description = "Enable EventBridge scheduled execution of the Step Function"
  type        = bool
  default     = true
}

variable "s3_force_destroy" {
  description = "Allow Terraform to destroy S3 bucket with objects (use with caution)"
  type        = bool
  default     = false
}

variable "enable_sns_notifications" {
  description = "Enable SNS notifications for alarms (production default)"
  type        = bool
  default     = true
}
