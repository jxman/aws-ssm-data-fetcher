# Use pre-built shared layer zip (built by build_packages.sh)
data "archive_file" "layer_zip" {
  type        = "zip"
  source_file = "${path.root}/../lambda_functions/shared_layer/layer.zip"
  output_path = "${path.root}/../lambda_functions/shared_layer_terraform.zip"
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
