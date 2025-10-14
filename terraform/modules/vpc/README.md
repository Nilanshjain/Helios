# VPC Module

Production-ready VPC module for AWS EKS deployment with multi-AZ architecture.

## Architecture

This module creates a highly available VPC with the following components:

### Network Topology
```
┌─────────────────────────────────────────────────────────────┐
│                         VPC (10.0.0.0/16)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   AZ-1a     │  │   AZ-1b     │  │   AZ-1c     │         │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤         │
│  │  Public     │  │  Public     │  │  Public     │         │
│  │  Subnet     │  │  Subnet     │  │  Subnet     │         │
│  │ 10.0.0.0/24 │  │ 10.0.1.0/24 │  │ 10.0.2.0/24 │         │
│  │             │  │             │  │             │         │
│  │ [NAT GW]    │  │ [NAT GW]    │  │ [NAT GW]    │         │
│  │             │  │             │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│        │                 │                 │                │
│        └─────────────────┴─────────────────┘                │
│                         │                                   │
│                  [Internet Gateway]                         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Private    │  │  Private    │  │  Private    │         │
│  │  Subnet     │  │  Subnet     │  │  Subnet     │         │
│  │ 10.0.3.0/24 │  │ 10.0.4.0/24 │  │ 10.0.5.0/24 │         │
│  │             │  │             │  │             │         │
│  │ [EKS Nodes] │  │ [EKS Nodes] │  │ [EKS Nodes] │         │
│  │             │  │             │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components Created

1. **VPC** - /16 CIDR block with DNS support enabled
2. **Public Subnets** - 3 subnets (one per AZ) for load balancers and NAT gateways
3. **Private Subnets** - 3 subnets (one per AZ) for EKS worker nodes
4. **Internet Gateway** - Public internet access for public subnets
5. **NAT Gateways** - Outbound internet access for private subnets (one per AZ)
6. **Route Tables** - Public and private routing configuration
7. **VPC Flow Logs** - Network traffic monitoring (optional)

## Usage

```hcl
module "vpc" {
  source = "./modules/vpc"

  project_name       = "helios"
  environment        = "prod"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  cluster_name       = "helios-prod-cluster"

  # Cost optimization: Use single NAT gateway instead of one per AZ
  single_nat_gateway = false  # Set to true to save ~$64/month

  # Network monitoring
  enable_flow_logs          = true
  flow_logs_retention_days  = 7

  tags = {
    Terraform   = "true"
    Environment = "prod"
    Project     = "helios"
  }
}
```

## Features

### Multi-AZ High Availability
- Deploys across 3 availability zones
- Ensures resilience against AZ failures
- Required for production EKS deployments

### EKS-Ready Tagging
- Automatic subnet tagging for EKS integration
- `kubernetes.io/role/elb` for public subnets (external load balancers)
- `kubernetes.io/role/internal-elb` for private subnets (internal load balancers)
- `kubernetes.io/cluster/{cluster_name}` for cluster association

### Cost Optimization Options

#### Single NAT Gateway Mode
```hcl
single_nat_gateway = true
```
**Savings**: ~$64/month (reduces from 3 NAT gateways to 1)
**Trade-off**: No NAT gateway redundancy across AZs

#### Disable NAT Gateway (LocalStack/Dev)
```hcl
enable_nat_gateway = false
```
**Savings**: ~$96/month (free for LocalStack)
**Trade-off**: No internet access from private subnets

### Network Monitoring

VPC Flow Logs capture network traffic for:
- Security analysis
- Troubleshooting connectivity issues
- Compliance requirements

## Outputs

The module provides these outputs for use by other modules:

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC ID |
| `vpc_cidr` | VPC CIDR block |
| `public_subnet_ids` | List of public subnet IDs |
| `private_subnet_ids` | List of private subnet IDs |
| `nat_gateway_ids` | List of NAT Gateway IDs |
| `nat_gateway_public_ips` | NAT Gateway public IPs |

## Cost Breakdown

### Production Configuration (3 AZs, 3 NAT Gateways)
- **VPC**: $0/month (free)
- **NAT Gateway**: $32.40/gateway × 3 = $97.20/month
- **NAT Gateway Data Processing**: ~$0.045/GB
- **VPC Flow Logs**: ~$0.50/GB ingested
- **Total (minimal traffic)**: ~$100/month

### Cost-Optimized Configuration (Single NAT Gateway)
- **NAT Gateway**: $32.40/month
- **Total (minimal traffic)**: ~$35/month

### LocalStack (Development)
- **All components**: $0/month

## Testing with LocalStack

```bash
# Start LocalStack
docker-compose up -d localstack

# Configure Terraform for LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# Test VPC creation
cd terraform
terraform init
terraform plan
terraform apply

# Verify VPC created in LocalStack
awslocal ec2 describe-vpcs
awslocal ec2 describe-subnets
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0.0 |

## Best Practices

1. **Always use multiple AZs** for production (minimum 3)
2. **Enable VPC Flow Logs** for security and troubleshooting
3. **Use private subnets** for EKS worker nodes
4. **Tag subnets properly** for EKS auto-discovery
5. **Consider single NAT gateway** for non-production to reduce costs

## Subnet Sizing Guide

Default configuration uses /24 subnets (254 IPs each):
- **Public subnets**: Sufficient for load balancers and NAT gateways
- **Private subnets**: Supports ~200 pods per subnet (with EKS secondary CIDR)

For larger clusters, consider /20 subnets (4094 IPs each).
