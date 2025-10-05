# Use pre-built shared layer zip directly (built by build_packages.sh)
resource "aws_lambda_layer_version" "shared_layer" {
  filename                 = "${path.root}/../lambda_functions/shared_layer/layer.zip"
  layer_name               = "${var.project_name}-${var.environment}-shared-layer"
  source_code_hash         = filebase64sha256("${path.root}/../lambda_functions/shared_layer/layer.zip")
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]

  description = "Shared modules for ${var.project_name} Lambda functions"

  lifecycle {
    create_before_destroy = true
  }
}
