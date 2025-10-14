# S3 Module Variables

variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "enable_versioning" {
  description = "Enable versioning on the bucket"
  type        = bool
  default     = true
}

variable "kms_master_key_id" {
  description = "KMS key ID for bucket encryption (null for AES256)"
  type        = string
  default     = null
}

variable "enable_logging" {
  description = "Enable access logging"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Number of days to retain access logs"
  type        = number
  default     = 30
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules for the bucket"
  type = list(object({
    id      = string
    enabled = bool
    prefix  = optional(string)
    expiration = optional(object({
      days                         = optional(number)
      expired_object_delete_marker = optional(bool)
    }))
    transitions = optional(list(object({
      days          = number
      storage_class = string
    })))
    noncurrent_version_expiration = optional(object({
      days = number
    }))
    noncurrent_version_transitions = optional(list(object({
      days          = number
      storage_class = string
    })))
  }))
  default = []
}

variable "cors_rules" {
  description = "List of CORS rules for the bucket"
  type = list(object({
    allowed_headers = list(string)
    allowed_methods = list(string)
    allowed_origins = list(string)
    expose_headers  = optional(list(string))
    max_age_seconds = optional(number)
  }))
  default = []
}

variable "bucket_policy" {
  description = "Bucket policy JSON"
  type        = string
  default     = null
}

variable "enable_cloudwatch_metrics" {
  description = "Enable CloudWatch metrics for S3 errors"
  type        = bool
  default     = false
}

variable "notification_topic_arn" {
  description = "SNS topic ARN for S3 event notifications"
  type        = string
  default     = null
}

variable "enable_intelligent_tiering" {
  description = "Enable S3 Intelligent-Tiering for cost optimization"
  type        = bool
  default     = false
}

variable "replication_configuration" {
  description = "Replication configuration for disaster recovery"
  type = object({
    role_arn                 = string
    destination_bucket_arn   = string
    storage_class            = optional(string)
    kms_key_id               = optional(string)
  })
  default = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
