# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = concat([
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            for func_name in var.lambda_function_names : [
              "AWS/Lambda",
              "Duration",
              "FunctionName",
              func_name
            ]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Lambda Function Duration"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            for func_name in var.lambda_function_names : [
              "AWS/Lambda",
              "Errors",
              "FunctionName",
              func_name
            ]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Lambda Function Errors"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            for func_name in var.lambda_function_names : [
              "AWS/Lambda",
              "Invocations",
              "FunctionName",
              func_name
            ]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Lambda Function Invocations"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      }
      ], var.step_function_arn != "" ? [
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            [
              "AWS/States",
              "ExecutionsFailed",
              "StateMachineArn",
              var.step_function_arn
            ],
            [
              "AWS/States",
              "ExecutionsSucceeded",
              "StateMachineArn",
              var.step_function_arn
            ],
            [
              "AWS/States",
              "ExecutionsStarted",
              "StateMachineArn",
              var.step_function_arn
            ]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Step Functions Executions"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      }
    ] : [])
  })

}

# CloudWatch Alarms for Lambda Functions
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count = length(var.lambda_function_names)

  alarm_name          = "${var.project_name}-${var.environment}-${var.lambda_function_names[count.index]}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors lambda errors for ${var.lambda_function_names[count.index]}"
  alarm_actions       = var.enable_sns_notifications ? [aws_sns_topic.alarms[0].arn] : []

  dimensions = {
    FunctionName = var.lambda_function_names[count.index]
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-${var.lambda_function_names[count.index]}-errors-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count = length(var.lambda_function_names)

  alarm_name          = "${var.project_name}-${var.environment}-${var.lambda_function_names[count.index]}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "60000" # 1 minute
  alarm_description   = "This metric monitors lambda duration for ${var.lambda_function_names[count.index]}"
  alarm_actions       = var.enable_sns_notifications ? [aws_sns_topic.alarms[0].arn] : []

  dimensions = {
    FunctionName = var.lambda_function_names[count.index]
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-${var.lambda_function_names[count.index]}-duration-alarm"
  })
}

# CloudWatch Alarm for Step Functions
resource "aws_cloudwatch_metric_alarm" "step_function_failures" {
  count               = var.step_function_arn != "" ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-step-function-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors step function execution failures"
  alarm_actions       = var.enable_sns_notifications ? [aws_sns_topic.alarms[0].arn] : []

  dimensions = {
    StateMachineArn = var.step_function_arn
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-step-function-failures-alarm"
  })
}

# SNS Topic for alarms (optional)
resource "aws_sns_topic" "alarms" {
  count = var.enable_sns_notifications ? 1 : 0
  name  = "${var.project_name}-${var.environment}-alarms"

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-alarms"
  })
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.enable_sns_notifications && var.sns_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.sns_email
}

# Log retention is handled by individual Lambda modules

data "aws_region" "current" {}
