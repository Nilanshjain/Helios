# S3 Module - Report Storage with Lifecycle Management

# S3 Bucket for Reports
resource "aws_s3_bucket" "reports" {
  bucket = var.bucket_name

  tags = merge(
    var.tags,
    {
      Name = var.bucket_name
    }
  )
}

# Enable versioning
resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_master_key_id != null ? "aws:kms" : "AES256"
      kms_master_key_id = var.kms_master_key_id
    }
    bucket_key_enabled = var.kms_master_key_id != null ? true : false
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rules
resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  count  = length(var.lifecycle_rules) > 0 ? 1 : 0
  bucket = aws_s3_bucket.reports.id

  dynamic "rule" {
    for_each = var.lifecycle_rules

    content {
      id     = rule.value.id
      status = rule.value.enabled ? "Enabled" : "Disabled"

      filter {
        prefix = lookup(rule.value, "prefix", "")
      }

      dynamic "expiration" {
        for_each = lookup(rule.value, "expiration", null) != null ? [rule.value.expiration] : []

        content {
          days                         = lookup(expiration.value, "days", null)
          expired_object_delete_marker = lookup(expiration.value, "expired_object_delete_marker", null)
        }
      }

      dynamic "transition" {
        for_each = lookup(rule.value, "transitions", [])

        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }

      dynamic "noncurrent_version_expiration" {
        for_each = lookup(rule.value, "noncurrent_version_expiration", null) != null ? [rule.value.noncurrent_version_expiration] : []

        content {
          noncurrent_days = noncurrent_version_expiration.value.days
        }
      }

      dynamic "noncurrent_version_transition" {
        for_each = lookup(rule.value, "noncurrent_version_transitions", [])

        content {
          noncurrent_days = noncurrent_version_transition.value.days
          storage_class   = noncurrent_version_transition.value.storage_class
        }
      }
    }
  }
}

# Logging bucket (if enabled)
resource "aws_s3_bucket" "logs" {
  count  = var.enable_logging ? 1 : 0
  bucket = "${var.bucket_name}-logs"

  tags = merge(
    var.tags,
    {
      Name = "${var.bucket_name}-logs"
    }
  )
}

resource "aws_s3_bucket_versioning" "logs" {
  count  = var.enable_logging ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  count  = var.enable_logging ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  count  = var.enable_logging ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle for logs bucket (auto-delete old logs)
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  count  = var.enable_logging ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = var.log_retention_days
    }
  }
}

# Enable logging on reports bucket
resource "aws_s3_bucket_logging" "reports" {
  count  = var.enable_logging ? 1 : 0
  bucket = aws_s3_bucket.reports.id

  target_bucket = aws_s3_bucket.logs[0].id
  target_prefix = "reports-access-logs/"
}

# CORS configuration (if needed for direct browser uploads)
resource "aws_s3_bucket_cors_configuration" "reports" {
  count  = length(var.cors_rules) > 0 ? 1 : 0
  bucket = aws_s3_bucket.reports.id

  dynamic "cors_rule" {
    for_each = var.cors_rules

    content {
      allowed_headers = cors_rule.value.allowed_headers
      allowed_methods = cors_rule.value.allowed_methods
      allowed_origins = cors_rule.value.allowed_origins
      expose_headers  = lookup(cors_rule.value, "expose_headers", null)
      max_age_seconds = lookup(cors_rule.value, "max_age_seconds", null)
    }
  }
}

# Bucket policy
resource "aws_s3_bucket_policy" "reports" {
  count  = var.bucket_policy != null ? 1 : 0
  bucket = aws_s3_bucket.reports.id
  policy = var.bucket_policy
}

# CloudWatch metric filter for monitoring
resource "aws_cloudwatch_log_metric_filter" "s3_errors" {
  count          = var.enable_cloudwatch_metrics ? 1 : 0
  name           = "${var.bucket_name}-errors"
  log_group_name = "/aws/s3/${var.bucket_name}"

  pattern = "[... , request_uri, ... , status_code=4*, ... ]"

  metric_transformation {
    name      = "S3Errors"
    namespace = "CustomMetrics/S3"
    value     = "1"
  }
}

# Event notification to SNS (optional)
resource "aws_s3_bucket_notification" "reports" {
  count  = var.notification_topic_arn != null ? 1 : 0
  bucket = aws_s3_bucket.reports.id

  topic {
    topic_arn = var.notification_topic_arn
    events    = ["s3:ObjectCreated:*"]
  }
}

# Intelligent-Tiering configuration (cost optimization)
resource "aws_s3_bucket_intelligent_tiering_configuration" "reports" {
  count  = var.enable_intelligent_tiering ? 1 : 0
  bucket = aws_s3_bucket.reports.id
  name   = "EntireBucket"

  status = "Enabled"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# Replication configuration (for disaster recovery)
resource "aws_s3_bucket_replication_configuration" "reports" {
  count  = var.replication_configuration != null ? 1 : 0
  bucket = aws_s3_bucket.reports.id
  role   = var.replication_configuration.role_arn

  rule {
    id     = "replicate-all"
    status = "Enabled"

    filter {
      prefix = ""
    }

    destination {
      bucket        = var.replication_configuration.destination_bucket_arn
      storage_class = lookup(var.replication_configuration, "storage_class", "STANDARD")

      dynamic "encryption_configuration" {
        for_each = lookup(var.replication_configuration, "kms_key_id", null) != null ? [1] : []

        content {
          replica_kms_key_id = var.replication_configuration.kms_key_id
        }
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.reports]
}
