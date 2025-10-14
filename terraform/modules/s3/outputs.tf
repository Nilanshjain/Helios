# S3 Module Outputs

output "bucket_id" {
  description = "The name of the bucket"
  value       = aws_s3_bucket.reports.id
}

output "bucket_arn" {
  description = "The ARN of the bucket"
  value       = aws_s3_bucket.reports.arn
}

output "bucket_domain_name" {
  description = "The bucket domain name"
  value       = aws_s3_bucket.reports.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "The bucket regional domain name"
  value       = aws_s3_bucket.reports.bucket_regional_domain_name
}

output "bucket_region" {
  description = "The AWS region this bucket resides in"
  value       = aws_s3_bucket.reports.region
}

output "logs_bucket_id" {
  description = "The name of the logs bucket"
  value       = var.enable_logging ? aws_s3_bucket.logs[0].id : null
}

output "logs_bucket_arn" {
  description = "The ARN of the logs bucket"
  value       = var.enable_logging ? aws_s3_bucket.logs[0].arn : null
}
