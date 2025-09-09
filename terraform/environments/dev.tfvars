# Development environment configuration
environment = "dev"
aws_region  = "us-east-1"
log_level   = "DEBUG"

# Monitoring configuration
enable_monitoring        = true
retention_days           = 7
enable_sns_notifications = false
sns_email                = ""

# EventBridge scheduling (disabled for dev)
eventbridge_enabled             = false
eventbridge_schedule_expression = "cron(0 6 * * ? *)" # Daily at 6 AM UTC (when enabled)

# S3 configuration
s3_force_destroy = true # Allow destruction with objects for dev environment
