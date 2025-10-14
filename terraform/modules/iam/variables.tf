# IAM Module Variables

variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "role_description" {
  description = "Description of the IAM role"
  type        = string
  default     = ""
}

variable "create_irsa_role" {
  description = "Create IRSA role for EKS service account"
  type        = bool
  default     = true
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider (required for IRSA)"
  type        = string
  default     = ""
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider (required for IRSA)"
  type        = string
  default     = ""
}

variable "service_accounts" {
  description = "List of service accounts that can assume this role"
  type = list(object({
    namespace = string
    name      = string
  }))
  default = []
}

variable "assume_role_policy" {
  description = "Custom assume role policy (if not using IRSA)"
  type        = string
  default     = ""
}

variable "max_session_duration" {
  description = "Maximum session duration in seconds"
  type        = number
  default     = 3600
}

variable "managed_policy_arns" {
  description = "List of AWS managed policy ARNs to attach"
  type        = list(string)
  default     = []
}

variable "inline_policies" {
  description = "Map of inline policies (name => policy JSON)"
  type        = map(string)
  default     = {}
}

variable "create_custom_policy" {
  description = "Create a custom IAM policy"
  type        = bool
  default     = false
}

variable "custom_policy" {
  description = "Custom IAM policy JSON"
  type        = string
  default     = ""
}

variable "custom_policy_description" {
  description = "Description of the custom policy"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to IAM resources"
  type        = map(string)
  default     = {}
}
