output "layer_arn" {
  description = "ARN of the Lambda layer"
  value       = aws_lambda_layer_version.shared_layer.arn
}

output "layer_version" {
  description = "Version of the Lambda layer"
  value       = aws_lambda_layer_version.shared_layer.version
}

output "layer_name" {
  description = "Name of the Lambda layer"
  value       = aws_lambda_layer_version.shared_layer.layer_name
}
