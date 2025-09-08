output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role"
  value       = aws_iam_role.github_actions_role.arn
}

output "github_actions_role_name" {
  description = "Name of the GitHub Actions IAM role"
  value       = aws_iam_role.github_actions_role.name
}

output "github_actions_policy_arn" {
  description = "ARN of the GitHub Actions IAM policy"
  value       = aws_iam_policy.github_actions_policy.arn
}
