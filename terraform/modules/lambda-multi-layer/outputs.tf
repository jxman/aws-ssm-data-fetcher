output "core_layer_arn" {
  description = "ARN of the core layer with lightweight dependencies"
  value       = aws_lambda_layer_version.core_layer.arn
}

output "core_layer_version" {
  description = "Version of the core layer"
  value       = aws_lambda_layer_version.core_layer.version
}

output "heavy_data_layer_arn" {
  description = "ARN of the heavy data layer (if created)"
  value       = length(aws_lambda_layer_version.heavy_data_layer) > 0 ? aws_lambda_layer_version.heavy_data_layer[0].arn : null
}

output "heavy_data_layer_version" {
  description = "Version of the heavy data layer (if created)"
  value       = length(aws_lambda_layer_version.heavy_data_layer) > 0 ? aws_lambda_layer_version.heavy_data_layer[0].version : null
}

# Convenience outputs for different function types
output "lightweight_function_layers" {
  description = "Layer ARNs for functions that only need core dependencies"
  value       = [aws_lambda_layer_version.core_layer.arn]
}

output "heavy_function_layers" {
  description = "Layer ARNs for functions that need both core and heavy data dependencies"
  value = length(aws_lambda_layer_version.heavy_data_layer) > 0 ? [
    aws_lambda_layer_version.core_layer.arn,
    aws_lambda_layer_version.heavy_data_layer[0].arn
  ] : [aws_lambda_layer_version.core_layer.arn]
}
