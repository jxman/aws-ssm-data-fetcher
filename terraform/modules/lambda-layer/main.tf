# Create zip file for shared layer
data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../lambda_functions/shared_layer"
  output_path = "${path.root}/../lambda_functions/shared_layer.zip"
}

# Lambda layer for shared modules
resource "aws_lambda_layer_version" "shared_layer" {
  filename                 = data.archive_file.layer_zip.output_path
  layer_name               = "${var.project_name}-${var.environment}-shared-layer"
  source_code_hash         = data.archive_file.layer_zip.output_base64sha256
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Shared modules for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [data.archive_file.layer_zip]
}