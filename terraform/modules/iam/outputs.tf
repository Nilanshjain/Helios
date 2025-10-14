# IAM Module Outputs

output "role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.this.name
}

output "role_id" {
  description = "ID of the IAM role"
  value       = aws_iam_role.this.id
}

output "role_unique_id" {
  description = "Stable and unique string identifying the role"
  value       = aws_iam_role.this.unique_id
}

output "custom_policy_arn" {
  description = "ARN of the custom policy (if created)"
  value       = var.create_custom_policy ? aws_iam_policy.custom[0].arn : null
}

output "custom_policy_id" {
  description = "ID of the custom policy (if created)"
  value       = var.create_custom_policy ? aws_iam_policy.custom[0].id : null
}
