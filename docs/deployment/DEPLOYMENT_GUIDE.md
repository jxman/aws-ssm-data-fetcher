# AWS Lambda Deployment Guide

This guide explains how to deploy the AWS SSM data fetcher as a Lambda function that runs daily and uploads data to S3.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Lambda Function │───▶│   S3 Bucket     │
│   (Daily Cron)  │    │  (Data Fetcher)  │    │  (Excel & JSON) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  SSM Parameters │
                       │ (AWS Services)  │
                       └─────────────────┘
```

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Python 3.9+** for local testing
3. **S3 bucket** for storing output files
4. **IAM permissions** for Lambda to access SSM and S3

## Step 1: Create S3 Bucket

```bash
# Create S3 bucket for data storage
aws s3 mb s3://your-aws-data-bucket

# Enable versioning (optional)
aws s3api put-bucket-versioning \
    --bucket your-aws-data-bucket \
    --versioning-configuration Status=Enabled
```

## Step 2: Create IAM Role for Lambda

Create `lambda-role-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/aws/service/global-infrastructure/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::your-aws-data-bucket/*"
        }
    ]
}
```

Create the IAM role:

```bash
# Create trust policy
cat > lambda-trust-policy.json << EOF
{
    "Version": "2012-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

# Create IAM role
aws iam create-role \
    --role-name AWSSSMDataFetcherRole \
    --assume-role-policy-document file://lambda-trust-policy.json

# Attach policy
aws iam put-role-policy \
    --role-name AWSSSMDataFetcherRole \
    --policy-name AWSSSMDataFetcherPolicy \
    --policy-document file://lambda-role-policy.json
```

## Step 3: Package Lambda Function

```bash
# Create deployment package
mkdir lambda-deployment
cp lambda_function.py lambda-deployment/
cd lambda-deployment

# Install dependencies
pip install pandas openpyxl -t .

# Create deployment package
zip -r ../aws-ssm-fetcher.zip .
cd ..
```

## Step 4: Deploy Lambda Function

```bash
# Create Lambda function
aws lambda create-function \
    --function-name aws-ssm-data-fetcher \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR-ACCOUNT-ID:role/AWSSSMDataFetcherRole \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://aws-ssm-fetcher.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment Variables='{
        "BUCKET_NAME": "your-aws-data-bucket"
    }'
```

## Step 5: Set Up Daily Schedule

Create EventBridge rule for daily execution:

```bash
# Create rule for daily execution at 6 AM UTC
aws events put-rule \
    --name aws-ssm-daily-fetch \
    --schedule-expression "cron(0 6 * * ? *)" \
    --description "Daily AWS SSM data fetch"

# Add Lambda as target
aws events put-targets \
    --rule aws-ssm-daily-fetch \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR-ACCOUNT-ID:function:aws-ssm-data-fetcher"

# Give EventBridge permission to invoke Lambda
aws lambda add-permission \
    --function-name aws-ssm-data-fetcher \
    --statement-id allow-eventbridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:YOUR-ACCOUNT-ID:rule/aws-ssm-daily-fetch
```

## Step 6: Test the Function

```bash
# Test manually
aws lambda invoke \
    --function-name aws-ssm-data-fetcher \
    --payload '{"bucket_name": "your-aws-data-bucket"}' \
    response.json

# Check response
cat response.json

# Verify files in S3
aws s3 ls s3://your-aws-data-bucket/aws-data/
```

## Output Files

The Lambda function will create two files in your S3 bucket daily:

- `aws-data/aws_regions_services.xlsx` - Excel format (5 comprehensive sheets)
- `aws-data/aws_regions_services.json` - JSON format with metadata
- Files are overwritten on each run to maintain consistent naming

## Monitoring

- **CloudWatch Logs**: Monitor function execution and errors
- **CloudWatch Metrics**: Track invocation count, duration, errors
- **S3 Events**: Optional notification when files are created

## Cost Estimation

For daily execution:
- **Lambda**: ~$0.20/month (512MB memory, 60-second execution)
- **S3**: ~$0.02/month for storage (small files)
- **CloudWatch Logs**: ~$0.50/month

Total: **~$0.72/month**

## Website Integration

To serve the data on a website:

1. **Static Website**: Host on S3 with CloudFront
2. **API Gateway**: Create REST API to serve JSON data
3. **CloudFront**: Add caching for better performance

Example CloudFront setup:

```bash
# Create CloudFront distribution for S3 bucket
aws cloudfront create-distribution \
    --distribution-config file://cloudfront-config.json
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check IAM role permissions
2. **Timeout**: Increase Lambda timeout (max 15 minutes)
3. **Memory Issues**: Increase Lambda memory allocation
4. **SSM Rate Limits**: Function includes built-in retry logic

### Debugging

```bash
# View recent logs
aws logs describe-log-streams \
    --log-group-name /aws/lambda/aws-ssm-data-fetcher \
    --order-by LastEventTime \
    --descending

# Get specific log stream
aws logs get-log-events \
    --log-group-name /aws/lambda/aws-ssm-data-fetcher \
    --log-stream-name LOG_STREAM_NAME
```

## Updates and Maintenance

To update the function:

```bash
# Update code
zip -r aws-ssm-fetcher-updated.zip lambda_function.py

# Deploy update
aws lambda update-function-code \
    --function-name aws-ssm-data-fetcher \
    --zip-file fileb://aws-ssm-fetcher-updated.zip
```

## Security Considerations

- **Least Privilege**: IAM role has minimal required permissions
- **VPC**: Consider running Lambda in VPC for additional security
- **Encryption**: Enable S3 bucket encryption
- **Access Logs**: Enable S3 access logging for audit trail