# Multi-Layer Lambda Architecture
# This module creates two specialized layers to resolve size/dependency conflicts

# Build script execution for core layer
resource "null_resource" "build_core_layer" {
  triggers = {
    requirements_hash = filesha256("${path.root}/../lambda_functions/core_layer/requirements.txt")
    modules_hash      = sha256(join("", [for f in fileset("${path.root}/../lambda_functions/core_layer/python", "**") : filesha256("${path.root}/../lambda_functions/core_layer/python/${f}")]))
  }

  provisioner "local-exec" {
    working_dir = "${path.root}/../lambda_functions"
    command     = "chmod +x scripts/build_multi_layer_packages.sh && ./scripts/build_multi_layer_packages.sh"
  }
}

# Core layer with lightweight dependencies
resource "aws_lambda_layer_version" "core_layer" {
  filename                 = "${path.root}/../lambda_functions/core_layer/core_layer.zip"
  layer_name               = "${var.project_name}-${var.environment}-core-layer"
  source_code_hash         = filebase64sha256("${path.root}/../lambda_functions/core_layer/core_layer.zip")
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Core lightweight dependencies and app modules for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [null_resource.build_core_layer]
}

# Heavy data layer with pandas, numpy, openpyxl
resource "aws_lambda_layer_version" "heavy_data_layer" {
  count = fileexists("${path.root}/../lambda_functions/heavy_data_layer/requirements.txt") ? 1 : 0

  filename                 = "${path.root}/../lambda_functions/heavy_data_layer/heavy_data_layer.zip"
  layer_name               = "${var.project_name}-${var.environment}-heavy-data-layer"
  source_code_hash         = filebase64sha256("${path.root}/../lambda_functions/heavy_data_layer/heavy_data_layer.zip")
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Heavy data processing dependencies (pandas, numpy, openpyxl) for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [null_resource.build_core_layer]
}
