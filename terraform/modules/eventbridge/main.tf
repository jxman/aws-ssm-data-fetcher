# EventBridge rule for scheduling AWS SSM data fetcher pipeline
resource "aws_cloudwatch_event_rule" "daily_execution" {
  name                = "${var.project_name}-${var.environment}-daily-execution"
  description         = "Trigger AWS SSM data fetcher pipeline daily at 6 AM UTC"
  schedule_expression = var.schedule_expression
  state               = var.enabled ? "ENABLED" : "DISABLED"

  tags = merge(var.common_tags, {
    Name        = "${var.project_name}-${var.environment}-daily-execution"
    Description = "EventBridge rule for AWS SSM data fetcher scheduled execution"
  })
}

# EventBridge target for Step Functions
resource "aws_cloudwatch_event_target" "step_function" {
  count     = var.step_function_arn != "" ? 1 : 0
  rule      = aws_cloudwatch_event_rule.daily_execution.name
  target_id = "StepFunctionTarget"
  arn       = var.step_function_arn
  role_arn  = aws_iam_role.eventbridge_step_functions[0].arn

  # Input with proper JSON structure for Step Functions
  input = jsonencode({
    source       = "eventbridge-scheduled"
    environment  = var.environment
    timestamp    = "$${aws.events.scheduled-time}"
    execution_id = "eventbridge-$${aws.events.event.id}"
  })
}

# IAM role for EventBridge to invoke Step Functions
resource "aws_iam_role" "eventbridge_step_functions" {
  count = var.step_function_arn != "" ? 1 : 0
  name  = "${var.project_name}-${var.environment}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name        = "${var.project_name}-${var.environment}-eventbridge-role"
    Description = "IAM role for EventBridge to invoke Step Functions"
  })
}

# IAM policy for EventBridge to invoke Step Functions
resource "aws_iam_role_policy" "eventbridge_step_functions" {
  count = var.step_function_arn != "" ? 1 : 0
  name  = "${var.project_name}-${var.environment}-eventbridge-policy"
  role  = aws_iam_role.eventbridge_step_functions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = var.step_function_arn
      }
    ]
  })
}
