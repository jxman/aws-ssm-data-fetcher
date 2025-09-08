# Production environment configuration
environment = "prod"
aws_region  = "us-east-1"
log_level   = "WARNING"

# Monitoring configuration
enable_monitoring        = true
retention_days           = 30
enable_sns_notifications = true
sns_email                = "production-alerts@example.com" # Update with actual email

# Scheduling (enabled for production)
enable_scheduled_execution = true
schedule_expression        = "rate(24 hours)" # Daily execution

# S3 configuration
s3_force_destroy = false # Protect production data