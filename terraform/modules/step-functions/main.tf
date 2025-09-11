# Step Functions State Machine
resource "aws_sfn_state_machine" "main" {
  count    = var.skip_validation ? 0 : 1
  name     = "${var.project_name}-${var.environment}-pipeline"
  role_arn = var.lambda_execution_role_arn

  definition = jsonencode({
    Comment = "AWS SSM Data Fetcher Pipeline"
    StartAt = "DataFetcher"
    States = {
      DataFetcher = {
        Type     = "Task"
        Resource = var.data_fetcher_arn
        Parameters = {
          "execution_id.$" = "$$.Execution.Name"
          "input.$"        = "$"
        }
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 6
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "FailureNotification"
            ResultPath  = "$.error"
          }
        ]
        Next = "ProcessorCheck"
      }

      ProcessorCheck = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.status"
            StringEquals = "success"
            Next         = "Processor"
          }
        ]
        Default = "FailureNotification"
      }

      Processor = {
        Type     = "Task"
        Resource = var.processor_arn
        Parameters = {
          "execution_id.$"  = "$$.Execution.Name"
          "input.$"         = "$"
          "data_location.$" = "$.data_location"
        }
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 6
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "FailureNotification"
            ResultPath  = "$.error"
          }
        ]
        Next = "JsonCsvGeneratorCheck"
      }

      JsonCsvGeneratorCheck = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.status"
            StringEquals = "success"
            Next         = "JsonCsvGenerator"
          }
        ]
        Default = "FailureNotification"
      }

      JsonCsvGenerator = {
        Type     = "Task"
        Resource = var.json_csv_generator_arn
        Parameters = {
          "execution_id.$"            = "$$.Execution.Name"
          "input.$"                   = "$"
          "processed_data_location.$" = "$.processed_data_location"
        }
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 6
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "FailureNotification"
            ResultPath  = "$.error"
          }
        ]
        Next = "JsonCsvCheck"
      }

      JsonCsvCheck = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.statusCode"
            NumericEquals = 200
            Next          = "ExcelGenerator"
          }
        ]
        Default = "FailureNotification"
      }

      ExcelGenerator = {
        Type     = "Task"
        Resource = var.excel_generator_arn
        Parameters = {
          "execution_id.$" = "$$.Execution.Name"
          "summary.$"      = "$.summary"
        }
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 6
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "FailureNotification"
            ResultPath  = "$.error"
          }
        ]
        Next = "ExcelCheck"
      }

      ExcelCheck = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.statusCode"
            NumericEquals = 200
            Next          = "ReportOrchestrator"
          }
        ]
        Default = "FailureNotification"
      }

      ReportOrchestrator = {
        Type     = "Task"
        Resource = var.report_orchestrator_arn
        Parameters = {
          "execution_id.$" = "$$.Execution.Name"
          "summary.$"      = "$.summary"
        }
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 6
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "FailureNotification"
            ResultPath  = "$.error"
          }
        ]
        Next = "SuccessNotification"
      }

      SuccessNotification = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.notifications.arn
          Subject  = "${var.project_name} Pipeline Success"
          Message = {
            "execution_id.$" = "$$.Execution.Name"
            "status"         = "completed"
            "reports.$"      = "$.reports"
            "timestamp.$"    = "$$.State.EnteredTime"
          }
        }
        End = true
      }

      FailureNotification = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.notifications.arn
          Subject  = "${var.project_name} Pipeline Failure"
          Message = {
            "execution_id.$" = "$$.Execution.Name"
            "status"         = "failed"
            "error.$"        = "$.error"
            "timestamp.$"    = "$$.State.EnteredTime"
          }
        }
        End = true
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions_logs.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-step-functions"
  })

  depends_on = [
    aws_cloudwatch_log_group.step_functions_logs
  ]
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions_logs" {
  name              = "/aws/stepfunctions/${var.project_name}-${var.environment}-pipeline"
  retention_in_days = 14

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-step-functions-logs"
  })
}

# SNS Topic for notifications
resource "aws_sns_topic" "notifications" {
  name = "${var.project_name}-${var.environment}-notifications"

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-notifications"
  })
}

# SNS Topic Policy
resource "aws_sns_topic_policy" "notifications" {
  arn = aws_sns_topic.notifications.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.notifications.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

# Optional: CloudWatch Events rule for scheduled execution
resource "aws_cloudwatch_event_rule" "schedule" {
  count               = var.enable_scheduled_execution && !var.skip_validation ? 1 : 0
  name                = "${var.project_name}-${var.environment}-schedule"
  description         = "Scheduled execution for ${var.project_name}"
  schedule_expression = var.schedule_expression

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-schedule"
  })
}

resource "aws_cloudwatch_event_target" "step_function" {
  count     = var.enable_scheduled_execution && !var.skip_validation ? 1 : 0
  rule      = aws_cloudwatch_event_rule.schedule[0].name
  target_id = "StepFunctionTarget"
  arn       = aws_sfn_state_machine.main[0].arn
  role_arn  = var.events_role_arn

  input = jsonencode({
    scheduled = true
    timestamp = timestamp()
  })
}
