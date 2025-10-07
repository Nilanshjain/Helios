# Helios Infrastructure - Terraform Configuration
# Provisions AWS resources for production deployment

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # State backend (uncomment for production)
  # backend "s3" {
  #   bucket         = "helios-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "helios-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Helios"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Nilansh Jain"
    }
  }
}

# ============================================================================
# VARIABLES
# ============================================================================

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "helios"
}

# ============================================================================
# VPC MODULE (Network infrastructure)
# ============================================================================

module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = "10.0.0.0/16"

  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  public_subnets     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets    = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

# ============================================================================
# EKS MODULE (Kubernetes cluster)
# ============================================================================

module "eks" {
  source = "./modules/eks"

  project_name = var.project_name
  environment  = var.environment

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  cluster_version = "1.28"

  node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 5
      instance_types = ["t3.medium"]
    }
  }
}

# ============================================================================
# RDS MODULE (TimescaleDB)
# ============================================================================

module "rds" {
  source = "./modules/rds"

  project_name = var.project_name
  environment  = var.environment

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.medium"

  allocated_storage     = 100
  max_allocated_storage = 500

  db_name  = "helios"
  username = "postgres"

  backup_retention_period = 7
  multi_az                = true
}

# ============================================================================
# LAMBDA MODULE (Report generation)
# ============================================================================

module "lambda" {
  source = "./modules/lambda"

  project_name = var.project_name
  environment  = var.environment

  function_name = "helios-report-generator"
  runtime       = "python3.11"
  handler       = "lambda_function.lambda_handler"
  timeout       = 60
  memory_size   = 512

  source_dir = "../../services/reporting"

  environment_variables = {
    DB_HOST       = module.rds.endpoint
    DB_NAME       = "helios"
    REPORT_S3_BUCKET = aws_s3_bucket.reports.id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }
}

# ============================================================================
# S3 BUCKET (Incident reports storage)
# ============================================================================

resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-incident-reports-${var.environment}"

  tags = {
    Name = "Helios Incident Reports"
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = module.lambda.function_arn
}

output "s3_bucket_name" {
  description = "S3 bucket for reports"
  value       = aws_s3_bucket.reports.id
}

# ============================================================================
# NOTES
# ============================================================================

# To deploy:
# 1. Initialize: terraform init
# 2. Plan: terraform plan
# 3. Apply: terraform apply
# 4. Destroy: terraform destroy (caution!)
