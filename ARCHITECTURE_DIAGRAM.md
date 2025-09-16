# AWS SSM Data Fetcher - Architecture Overview

## System Architecture

This system is a serverless AWS infrastructure designed to collect, process, and generate reports from AWS Systems Manager (SSM) Parameter Store data across all AWS regions and services.

## ASCII Architecture Diagram

```
                            ┌─────────────────┐
                            │   EventBridge   │
                            │ (Daily Schedule) │
                            └─────────────────┘
                                      │ Triggers daily at 6 AM UTC
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AWS Step Functions                                    │
│                     (aws-ssm-fetcher-prod-pipeline)                            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   Data Fetcher  │───▶│   Processor     │───▶│ JSON/CSV Gen    │             │
│  │ (Collect SSM    │    │ (Process &      │    │ (Create JSON    │             │
│  │  Parameters)    │    │  Transform)     │    │  & CSV Reports) │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│           │                       │                       │                    │
│           ▼                       ▼                       ▼                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   Excel Gen     │◀───│ Report Orch     │◀───│      SNS        │             │
│  │ (Create Excel   │    │ (Coordinate     │    │ (Success/Fail   │             │
│  │   Reports)      │    │  Final Reports) │    │ Notifications)  │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      S3 Bucket  │    │   CloudWatch    │    │     Lambda      │
│ (Data Storage   │    │ (Monitoring &   │    │  Shared Layer   │
│  & Reports)     │    │    Logging)     │    │ (Dependencies)  │
│                 │    │                 │    │                 │
│ • Raw Data      │    │ • Function Logs │    │ • pandas        │
│ • Processed     │    │ • Step Functions│    │ • numpy         │
│ • Cache         │    │ • Dashboards    │    │ • openpyxl      │
│ • Reports       │    │ • Alarms        │    │ • pytz          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Component Details

### Core Services

#### 1. **EventBridge Rule**
- **Purpose**: Scheduled trigger for daily execution
- **Schedule**: Daily at 6 AM UTC (configurable)
- **Target**: Step Functions State Machine

#### 2. **Step Functions State Machine**
- **Name**: `aws-ssm-fetcher-prod-pipeline`
- **Purpose**: Orchestrates the entire data collection and processing workflow
- **States**:
  - Data Fetcher → Processor → JSON/CSV Generator → Excel Generator → Report Orchestrator
  - Success/Failure SNS notifications
  - Error handling with retries and exponential backoff

#### 3. **Lambda Functions** (5 total)

##### **Data Fetcher Lambda**
- **Runtime**: Python 3.11
- **Memory**: 1024 MB (1 GB)
- **Timeout**: 15 minutes
- **Purpose**: Collect SSM parameters from all AWS regions
- **Outputs**: Raw data stored in S3

##### **Processor Lambda**
- **Runtime**: Python 3.11
- **Memory**: 3008 MB (3 GB)
- **Timeout**: 15 minutes
- **Purpose**: Process and transform raw SSM data
- **Libraries**: pandas, numpy for data manipulation

##### **JSON/CSV Generator Lambda**
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 5 minutes
- **Purpose**: Generate JSON and CSV reports with EST timezone
- **Features**: Multiple CSV sheets, statistics, metadata

##### **Excel Generator Lambda**
- **Runtime**: Python 3.11
- **Memory**: 1024 MB (1 GB)
- **Timeout**: 5 minutes
- **Purpose**: Generate Excel reports with formatting
- **Features**: Multiple sheets, color coding, charts

##### **Report Orchestrator Lambda**
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 5 minutes
- **Purpose**: Coordinate final report generation and cleanup

#### 4. **Lambda Shared Layer**
- **Purpose**: Common dependencies for all Lambda functions
- **Libraries**: pandas, numpy, openpyxl, pytz, boto3
- **Benefits**: Reduced deployment package size, consistent versions

#### 5. **S3 Bucket**
- **Purpose**: Centralized data and report storage
- **Structure**:
  - `raw-data/`: SSM parameter data by execution
  - `processed-data/`: Transformed data
  - `cache/`: Temporary processing cache
  - `reports/`: Final JSON, CSV, Excel reports

#### 6. **CloudWatch**
- **Log Groups**: Individual groups for each Lambda function + Step Functions
- **Dashboards**: Performance monitoring for all components
- **Alarms**: Error rate, duration, and failure notifications
- **Retention**: 14 days for Step Functions, configurable for Lambda

#### 7. **SNS Topic**
- **Purpose**: Success/failure notifications
- **Integration**: Step Functions publishes to SNS
- **Notifications**: Email alerts for pipeline status

### IAM & Security

#### **IAM Roles**
- **Lambda Execution Role**: Permissions for S3, CloudWatch, SNS, SSM
- **Step Functions Role**: Permissions to invoke Lambda functions and publish to SNS
- **EventBridge Role**: Permissions to trigger Step Functions

#### **GitHub OIDC Integration** (CI/CD)
- **Purpose**: Secure deployment without long-lived credentials
- **Components**:
  - OIDC Identity Provider
  - GitHub-specific IAM role with repository restrictions
  - Deployment policy with least-privilege access

## Data Flow

1. **Scheduled Trigger**: EventBridge triggers Step Functions daily
2. **Data Collection**: Data Fetcher Lambda queries SSM across all regions
3. **Processing**: Processor Lambda transforms raw data into structured format
4. **Report Generation**: Multiple generators create different report formats
5. **Orchestration**: Report Orchestrator coordinates final steps
6. **Storage**: All outputs stored in S3 with organized structure
7. **Monitoring**: CloudWatch captures metrics, logs, and sends alerts
8. **Notifications**: SNS sends success/failure notifications

## Key Features

### **Serverless & Scalable**
- No server management required
- Automatic scaling based on demand
- Pay-per-use pricing model

### **Robust Error Handling**
- Exponential backoff retry logic
- State machine error catching
- SNS failure notifications
- Detailed CloudWatch logging

### **Multi-Format Reporting**
- JSON: Comprehensive data with metadata
- CSV: Multiple sheets for analysis
- Excel: Formatted reports with visualizations
- EST timezone support throughout

### **Monitoring & Observability**
- CloudWatch dashboards for all components
- Log aggregation and analysis
- Performance metrics and alarms
- Execution history and debugging

### **Security & Compliance**
- IAM least-privilege access
- Encrypted S3 storage
- VPC compatibility (if needed)
- GitHub OIDC for secure CI/CD

## Deployment

The infrastructure is deployed using:
- **Terraform**: Infrastructure as Code
- **GitHub Actions**: CI/CD pipeline with OIDC authentication
- **Modular Design**: Reusable Terraform modules for each component
- **Environment Isolation**: Separate configurations for dev/staging/prod

## Cost Optimization

- **Appropriate Memory Allocation**: Right-sized for each function's needs
- **Efficient Scheduling**: Daily execution minimizes unnecessary runs
- **S3 Lifecycle Policies**: Automated cleanup of old data
- **CloudWatch Log Retention**: Limited retention periods
- **Shared Layer**: Reduces individual deployment package sizes
