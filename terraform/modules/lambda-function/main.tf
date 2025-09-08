# Create zip file for Lambda function
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.source_path
  output_path = "${var.source_path}.zip"
  excludes = [
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    "tests"
  ]
}

# Lambda function
resource "aws_lambda_function" "main" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-${var.function_name}"
  role             = var.function_role
  handler          = var.handler
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size
  architectures    = ["x86_64"]

  layers = var.lambda_layer_arn != "" ? [var.lambda_layer_arn] : []

  environment {
    variables = var.environment_variables
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-${var.function_name}"
  })

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    data.archive_file.lambda_zip
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-${var.function_name}-logs"
  })
}

# Dead Letter Queue for failed executions
resource "aws_sqs_queue" "dlq" {
  name                       = "${var.project_name}-${var.environment}-${var.function_name}-dlq"
  message_retention_seconds  = 1209600 # 14 days
  visibility_timeout_seconds = var.timeout * 6

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-${var.function_name}-dlq"
  })
}

# Lambda function event source mapping (if needed)
# resource "aws_lambda_event_source_mapping" "main" {
#   count                  = var.event_source_arn != "" ? 1 : 0
#   event_source_arn       = var.event_source_arn
#   function_name          = aws_lambda_function.main.arn
#   starting_position      = var.starting_position
#   batch_size             = var.batch_size
#   maximum_batching_window_in_seconds = var.maximum_batching_window_in_seconds
# }

# Lambda permission for Step Functions
resource "aws_lambda_permission" "allow_step_functions" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "states.amazonaws.com"
}

# Lambda alias for versioning
resource "aws_lambda_alias" "main" {
  name             = var.environment
  description      = "Alias for ${var.environment} environment"
  function_name    = aws_lambda_function.main.function_name
  function_version = aws_lambda_function.main.version

  lifecycle {
    ignore_changes = [function_version]
  }
}