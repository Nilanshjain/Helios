# Global Variables
variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "helios"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

# VPC Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# EKS Variables
variable "eks_cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "eks_node_instance_types" {
  description = "Instance types for EKS nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "eks_node_desired_size" {
  description = "Desired number of nodes"
  type        = number
  default     = 3
}

variable "eks_node_min_size" {
  description = "Minimum number of nodes"
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Maximum number of nodes"
  type        = number
  default     = 6
}

# RDS Variables
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 100
}

variable "rds_database_name" {
  description = "Database name"
  type        = string
  default     = "helios"
}

variable "rds_master_username" {
  description = "Master username"
  type        = string
  default     = "helios_admin"
}
