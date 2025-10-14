# EKS Module

Production-ready Amazon EKS (Elastic Kubernetes Service) module with managed node groups and IRSA support.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     EKS Control Plane                      │
│                  (Managed by AWS)                          │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  API Server  │  │  etcd        │  │  Scheduler   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │         OIDC Identity Provider (IRSA)            │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────┬───────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┬────────────────┐
    │                         │                │
    ▼                         ▼                ▼
┌─────────┐             ┌─────────┐      ┌─────────┐
│ Node    │             │ Node    │      │ Node    │
│ Group 1 │             │ Group 2 │      │ Group 3 │
│ (AZ-1a) │             │ (AZ-1b) │      │ (AZ-1c) │
│         │             │         │      │         │
│ EC2     │             │ EC2     │      │ EC2     │
│ ┌─────┐ │             │ ┌─────┐ │      │ ┌─────┐ │
│ │ Pod │ │             │ │ Pod │ │      │ │ Pod │ │
│ └─────┘ │             │ └─────┘ │      │ └─────┘ │
└─────────┘             └─────────┘      └─────────┘
```

## Features

### 1. **Managed Control Plane**
- Fully managed by AWS
- Multi-AZ high availability
- Automatic version updates
- CloudWatch logging integration

### 2. **Managed Node Groups**
- Auto Scaling Groups (ASG)
- Automatic AMI patching
- Support for Spot and On-Demand instances
- Node labels and taints

### 3. **IRSA (IAM Roles for Service Accounts)**
- OIDC provider for pod-level IAM roles
- Fine-grained permissions per pod
- No need for instance profiles

### 4. **Security**
- Dedicated security groups for control plane and nodes
- Secrets encryption at rest (KMS)
- Network policies support
- Private API endpoint option

### 5. **Observability**
- Control plane logs to CloudWatch
- Metrics integration with Prometheus
- Container Insights support

## Usage

```hcl
module "eks" {
  source = "./modules/eks"

  cluster_name    = "helios-prod-cluster"
  cluster_version = "1.28"

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids

  # Control plane access
  cluster_endpoint_private_access      = true
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"]

  # CloudWatch logging
  cluster_enabled_log_types              = ["api", "audit", "authenticator"]
  cloudwatch_log_group_retention_in_days = 7

  # Node groups
  node_groups = {
    general = {
      desired_size    = 3
      max_size        = 6
      min_size        = 2
      max_unavailable = 1

      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"  # or "SPOT" for cost savings
      disk_size      = 50
      ami_type       = "AL2_x86_64"

      labels = {
        workload = "general"
      }

      taints = []

      tags = {
        NodeGroup = "general"
      }
    }
  }

  tags = {
    Terraform   = "true"
    Environment = "prod"
    Project     = "helios"
  }
}
```

## Node Group Configuration

### Multiple Node Groups Example

```hcl
node_groups = {
  # General purpose workloads
  general = {
    desired_size   = 3
    max_size       = 10
    min_size       = 2
    instance_types = ["t3.medium"]
    capacity_type  = "ON_DEMAND"
    labels = {
      workload = "general"
    }
  }

  # Compute-intensive workloads
  compute = {
    desired_size   = 2
    max_size       = 5
    min_size       = 1
    instance_types = ["c5.2xlarge"]
    capacity_type  = "SPOT"  # Save ~70% costs
    labels = {
      workload = "compute-intensive"
    }
    taints = [{
      key    = "workload"
      value  = "compute"
      effect = "NoSchedule"
    }]
  }
}
```

### Spot Instances for Cost Savings

```hcl
node_groups = {
  spot = {
    desired_size   = 3
    max_size       = 10
    min_size       = 1
    instance_types = ["t3.medium", "t3a.medium", "t2.medium"]  # Multiple types for better availability
    capacity_type  = "SPOT"
    labels = {
      "node.kubernetes.io/lifecycle" = "spot"
    }
  }
}
```

**Savings**: ~70% compared to On-Demand instances

## EKS Add-ons

This module automatically installs essential add-ons:

### 1. **VPC CNI** (Amazon VPC Container Network Interface)
- Provides pod networking
- Assigns VPC IP addresses to pods
- Supports network policies

### 2. **CoreDNS**
- Cluster DNS server
- Service discovery
- DNS-based load balancing

### 3. **kube-proxy**
- Network proxy on each node
- Implements Kubernetes Service abstraction
- Load balances traffic to pods

## IRSA (IAM Roles for Service Accounts)

Enable fine-grained IAM permissions for pods:

```hcl
# 1. Create IAM role for a specific service account
resource "aws_iam_role" "reporting_service" {
  name = "helios-reporting-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = module.eks.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:helios-prod:reporting-service"
          "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

# 2. Attach policies
resource "aws_iam_role_policy_attachment" "reporting_s3" {
  role       = aws_iam_role.reporting_service.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# 3. Annotate Kubernetes service account
# kubectl annotate serviceaccount -n helios-prod reporting-service \
#   eks.amazonaws.com/role-arn=arn:aws:iam::ACCOUNT_ID:role/helios-reporting-service-role
```

## Accessing the Cluster

### Configure kubectl

```bash
# Get cluster credentials
aws eks update-kubeconfig \
  --region us-east-1 \
  --name helios-prod-cluster

# Verify connection
kubectl get nodes
kubectl get pods --all-namespaces
```

### Using Terraform Outputs

```bash
# Get cluster endpoint
terraform output -raw cluster_endpoint

# Get OIDC provider ARN
terraform output -raw oidc_provider_arn
```

## Cluster Auto-Scaling

The module configures node groups with scaling parameters, but you need to deploy Cluster Autoscaler:

```yaml
# cluster-autoscaler.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    spec:
      containers:
      - image: registry.k8s.io/autoscaling/cluster-autoscaler:v1.28.0
        name: cluster-autoscaler
        command:
          - ./cluster-autoscaler
          - --cloud-provider=aws
          - --namespace=kube-system
          - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/helios-prod-cluster
```

## Cost Optimization

| Strategy | Monthly Savings | Trade-off |
|----------|----------------|-----------|
| Use Spot instances | ~$60 (70% off) | Possible interruptions |
| Reduce node count (min_size=1) | ~$30 | Less availability |
| Use t3a instead of t3 | ~$5 (10% off) | AMD CPUs |
| Disable control plane logs | ~$5 | Less observability |
| **Total Potential Savings** | **~$100/month** | |

### Recommended Cost-Optimized Configuration

```hcl
node_groups = {
  general = {
    desired_size   = 2  # Lower than production
    max_size       = 4
    min_size       = 1  # Scale to zero during low usage
    instance_types = ["t3a.medium"]  # AMD instances (cheaper)
    capacity_type  = "SPOT"          # 70% savings
  }
}

cluster_enabled_log_types              = ["api"]  # Only essential logs
cloudwatch_log_group_retention_in_days = 3        # Shorter retention
```

## Testing with LocalStack

LocalStack has limited EKS support. For local testing, use **kind** or **minikube**:

```bash
# Using kind (Kubernetes in Docker)
kind create cluster --name helios-local

# Deploy your manifests
kubectl apply -f k8s/
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0.0 |

## Outputs

| Name | Description |
|------|-------------|
| cluster_endpoint | EKS cluster endpoint |
| cluster_certificate_authority_data | CA certificate for kubectl |
| oidc_provider_arn | OIDC provider ARN for IRSA |
| node_iam_role_arn | IAM role ARN for nodes |

## Best Practices

1. **Use private API endpoint** in production
2. **Enable all control plane logs** for audit trail
3. **Use IRSA** instead of instance profiles
4. **Deploy multiple node groups** for different workloads
5. **Use Spot instances** for non-critical workloads
6. **Enable secrets encryption** with KMS
7. **Keep Kubernetes version** up to date

## Monitoring

### View Control Plane Logs

```bash
# CloudWatch Logs Insights
aws logs tail /aws/eks/helios-prod-cluster/cluster --follow
```

### Check Node Group Health

```bash
kubectl get nodes
kubectl describe node <node-name>
```

### View Add-on Status

```bash
aws eks describe-addon \
  --cluster-name helios-prod-cluster \
  --addon-name vpc-cni
```

## Troubleshooting

### Nodes Not Joining Cluster

1. Check security groups allow communication
2. Verify IAM role has required policies
3. Check node group logs in EC2 console

### Pods Can't Pull Images

1. Ensure nodes have ECR pull permissions
2. Check if using private ECR registry
3. Verify VPC has internet access (NAT gateway)

### IRSA Not Working

1. Verify OIDC provider is created
2. Check service account annotation
3. Ensure IAM role trust policy is correct
