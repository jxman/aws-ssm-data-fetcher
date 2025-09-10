# Production environment configuration
environment = "prod"
aws_region  = "us-east-1"
log_level   = "WARNING"

# Monitoring configuration
enable_monitoring        = true
retention_days           = 30
enable_sns_notifications = true
sns_email                = "production-alerts@example.com" # Update with actual email

# EventBridge scheduling (enabled for production)
eventbridge_enabled             = true
eventbridge_schedule_expression = "cron(0 6 * * ? *)" # Daily at 6 AM UTC

# S3 configuration
s3_force_destroy = false # Protect production data
