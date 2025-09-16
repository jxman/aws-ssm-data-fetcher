# Multi-Layer Lambda Architecture
# This module creates two specialized layers to resolve size/dependency conflicts

# Core layer with lightweight dependencies and app modules
data "archive_file" "core_layer_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../lambda_functions/core_layer"
  output_path = "${path.root}/../lambda_functions/core_layer_terraform.zip"
}

resource "aws_lambda_layer_version" "core_layer" {
  filename                 = data.archive_file.core_layer_zip.output_path
  layer_name               = "${var.project_name}-${var.environment}-core-layer"
  source_code_hash         = data.archive_file.core_layer_zip.output_base64sha256
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Core dependencies and app modules for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [data.archive_file.core_layer_zip]
}

# Heavy data layer with pandas, numpy, openpyxl (only requirements.txt)
data "archive_file" "heavy_data_layer_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../lambda_functions/heavy_data_layer"
  output_path = "${path.root}/../lambda_functions/heavy_data_layer_terraform.zip"
}

resource "aws_lambda_layer_version" "heavy_data_layer" {
  count = fileexists("${path.root}/../lambda_functions/heavy_data_layer/requirements.txt") ? 1 : 0

  filename                 = data.archive_file.heavy_data_layer_zip.output_path
  layer_name               = "${var.project_name}-${var.environment}-heavy-data-layer"
  source_code_hash         = data.archive_file.heavy_data_layer_zip.output_base64sha256
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Heavy data processing dependencies for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [data.archive_file.heavy_data_layer_zip]
}
