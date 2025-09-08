# Development environment configuration
environment = "dev"
aws_region  = "us-east-1"
log_level   = "DEBUG"

# Monitoring configuration
enable_monitoring        = true
retention_days           = 7
enable_sns_notifications = false
sns_email                = ""

# Scheduling (disabled for dev)
enable_scheduled_execution = false
schedule_expression        = "rate(24 hours)"

# S3 configuration
s3_force_destroy = true # Allow destruction with objects for dev environment