# Scripts Directory

This directory contains utility scripts for managing and operating the AWS SSM Fetcher project.

## Manual Execution Script

### `manual_execution.sh`

**Purpose**: Manually trigger the AWS SSM Fetcher pipeline outside of the scheduled EventBridge execution.

**Features**:
- ✅ Automatically retrieves Step Function ARN from Terraform outputs
- ✅ Generates timestamped execution names
- ✅ Provides interactive confirmation before execution
- ✅ Shows real-time status and monitoring links
- ✅ Comprehensive error checking and validation
- ✅ Colorized output for better readability

**Prerequisites**:
- AWS CLI installed and configured
- Terraform installed
- Infrastructure deployed (terraform state available)
- Proper AWS permissions for Step Functions execution

**Usage**:
```bash
# From project root directory
./scripts/manual_execution.sh

# Or from scripts directory
cd scripts
./manual_execution.sh
```

**What it does**:
1. Validates AWS CLI and Terraform installation
2. Retrieves Step Function ARN from Terraform outputs
3. Generates unique execution name with timestamp
4. Creates appropriate input payload
5. Prompts for confirmation
6. Starts Step Function execution
7. Provides monitoring links and status information

**Sample Output**:
```
🚀 AWS SSM Fetcher Manual Execution
=================================================
📋 Getting Step Function ARN from Terraform...
✅ Step Function ARN: arn:aws:states:us-east-1:123456789012:stateMachine:aws-ssm-fetcher-prod-pipeline
✅ S3 Bucket: aws-ssm-fetcher-prod-123456789012-us-east-1

📝 Execution Details:
  Name: manual-execution-20250114-103045
  Timestamp: 2025-01-14T10:30:45Z

🤔 Do you want to start the manual execution? (y/N): y

🚀 Starting Step Function execution...
✅ Execution started successfully!

📊 Execution Details:
  ARN: arn:aws:states:us-east-1:123456789012:execution:aws-ssm-fetcher-prod-pipeline:manual-execution-20250114-103045

🔗 Monitoring Links:
  AWS Console: https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/[ARN]
  S3 Bucket: https://s3.console.aws.amazon.com/s3/buckets/aws-ssm-fetcher-prod-123456789012-us-east-1

📊 Current Status: RUNNING
⏳ Execution is running. This typically takes 5-15 minutes.
```

**Error Handling**:
- Validates AWS CLI installation
- Checks Terraform availability and state
- Verifies Step Function ARN retrieval
- Provides clear error messages with suggestions

**Security**:
- Uses existing AWS CLI credentials
- No hardcoded ARNs or sensitive information
- Follows principle of least privilege

## Directory Structure

```
scripts/
├── README.md                    # This documentation
└── manual_execution.sh          # Manual execution script
```

## Adding New Scripts

When adding new scripts to this directory:

1. **Make them executable**: `chmod +x script_name.sh`
2. **Add documentation**: Update this README with script details
3. **Follow naming convention**: Use descriptive names with underscores
4. **Include error handling**: Validate prerequisites and provide clear messages
5. **Use consistent output**: Follow the emoji and color scheme from existing scripts
6. **Test thoroughly**: Ensure scripts work in different environments

## Best Practices

- **Always validate prerequisites** before executing main functionality
- **Provide clear feedback** to users about what's happening
- **Include monitoring information** for long-running operations
- **Use relative paths** to support running from different directories
- **Handle errors gracefully** with informative messages
- **Follow the project's security practices** (no hardcoded credentials)
