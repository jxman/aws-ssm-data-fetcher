# Staging environment configuration
environment    = "staging"
aws_region     = "us-east-1"
log_level      = "INFO"

# Monitoring configuration
enable_monitoring         = true
retention_days           = 14
enable_sns_notifications = true
sns_email               = "your-email@example.com"  # Update with actual email

# Scheduling (enabled for staging testing)
enable_scheduled_execution = true
schedule_expression       = "rate(12 hours)"  # Twice daily for testing

# S3 configuration
s3_force_destroy = false  # Protect staging data