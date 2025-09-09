# Staging environment configuration
environment = "staging"
aws_region  = "us-east-1"
log_level   = "INFO"

# Monitoring configuration
enable_monitoring        = true
retention_days           = 14
enable_sns_notifications = true
sns_email                = "your-email@example.com" # Update with actual email

# EventBridge scheduling (enabled for staging testing)
eventbridge_enabled             = true
eventbridge_schedule_expression = "cron(0 6,18 * * ? *)" # Twice daily at 6 AM and 6 PM UTC

# S3 configuration
s3_force_destroy = false # Protect staging data
