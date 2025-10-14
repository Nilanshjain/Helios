# IAM Module - IRSA for EKS

Create IAM roles for Kubernetes service accounts using IRSA (IAM Roles for Service Accounts).

## What is IRSA?

IRSA allows Kubernetes pods to assume IAM roles without using instance profiles or access keys. Benefits:
- **Fine-grained permissions** per pod
- **No shared credentials** across pods
- **Automatic credential rotation**
- **Audit trail** in CloudTrail

## Architecture

```
┌─────────────────────────────────────────────┐
│            EKS Cluster                      │
│                                             │
│  ┌──────────────────────┐                  │
│  │  Pod                 │                  │
│  │  ┌────────────────┐  │                  │
│  │  │  Service       │  │                  │
│  │  │  Account       │──┼──────┐           │
│  │  └────────────────┘  │      │           │
│  └──────────────────────┘      │           │
└────────────────────────────────┼───────────┘
                                 │
                                 │ AssumeRoleWithWebIdentity
                                 │
                          ┌──────▼──────┐
                          │   OIDC      │
                          │  Provider   │
                          └──────┬──────┘
                                 │
                                 │ Validates token
                                 │
                          ┌──────▼──────┐
                          │  IAM Role   │
                          │  (Created   │
                          │   by this   │
                          │   module)   │
                          └──────┬──────┘
                                 │
                                 │ Grants permissions
                                 ▼
                          AWS Resources
                          (S3, RDS, etc.)
```

## Usage

### Basic IRSA Role for S3 Access

```hcl
module "reporting_irsa" {
  source = "./modules/iam"

  role_name        = "helios-reporting-s3-access"
  role_description = "Allow reporting service to write reports to S3"

  # IRSA configuration
  create_irsa_role   = true
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.cluster_oidc_issuer_url

  service_accounts = [{
    namespace = "helios-prod"
    name      = "reporting-service"
  }]

  # Grant S3 permissions
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  ]

  tags = {
    Terraform   = "true"
    Environment = "prod"
  }
}
```

### Role with Custom Inline Policy

```hcl
module "detection_irsa" {
  source = "./modules/iam"

  role_name = "helios-detection-rds-access"

  create_irsa_role   = true
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.cluster_oidc_issuer_url

  service_accounts = [{
    namespace = "helios-prod"
    name      = "detection-service"
  }]

  # Custom inline policy for specific S3 bucket and RDS
  inline_policies = {
    rds_and_s3_access = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "rds-db:connect"
          ]
          Resource = [
            "arn:aws:rds-db:us-east-1:123456789012:dbuser:${module.rds.db_instance_resource_id}/helios_app"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:ListBucket"
          ]
          Resource = [
            module.s3_reports.bucket_arn,
            "${module.s3_reports.bucket_arn}/*"
          ]
        }
      ]
    })
  }

  tags = var.tags
}
```

### Role for Multiple Service Accounts

```hcl
module "shared_irsa" {
  source = "./modules/iam"

  role_name = "helios-cloudwatch-access"

  create_irsa_role   = true
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.cluster_oidc_issuer_url

  # Multiple service accounts can use this role
  service_accounts = [
    {
      namespace = "helios-prod"
      name      = "ingestion-service"
    },
    {
      namespace = "helios-prod"
      name      = "detection-service"
    },
    {
      namespace = "helios-prod"
      name      = "reporting-service"
    }
  ]

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
  ]

  tags = var.tags
}
```

### Role with Custom Policy Resource

```hcl
module "s3_write_only" {
  source = "./modules/iam"

  role_name = "helios-s3-write-only"

  create_irsa_role   = true
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.cluster_oidc_issuer_url

  service_accounts = [{
    namespace = "helios-prod"
    name      = "backup-service"
  }]

  create_custom_policy      = true
  custom_policy_description = "Write-only access to helios-backups bucket"
  custom_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ]
      Resource = "arn:aws:s3:::helios-backups/*"
    }]
  })

  tags = var.tags
}
```

## Kubernetes Integration

After creating the IAM role with Terraform, annotate your Kubernetes service account:

### 1. Create Service Account

```yaml
# k8s/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: reporting-service
  namespace: helios-prod
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/helios-reporting-s3-access
```

### 2. Use in Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reporting
  namespace: helios-prod
spec:
  template:
    spec:
      serviceAccountName: reporting-service  # Links to IRSA role
      containers:
      - name: app
        image: reporting:latest
        env:
        - name: AWS_REGION
          value: us-east-1
        - name: S3_BUCKET
          value: helios-reports
```

### 3. Terraform Output to Kubernetes

```hcl
# Output role ARN for Kubernetes annotation
output "reporting_role_arn" {
  value = module.reporting_irsa.role_arn
}

# Use in helm values or kubernetes manifests
resource "kubernetes_service_account" "reporting" {
  metadata {
    name      = "reporting-service"
    namespace = "helios-prod"
    annotations = {
      "eks.amazonaws.com/role-arn" = module.reporting_irsa.role_arn
    }
  }
}
```

## Common Patterns

### 1. S3 Read/Write Access

```hcl
module "s3_access" {
  source = "./modules/iam"
  # ... IRSA config

  inline_policies = {
    s3 = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect = "Allow"
        Action = ["s3:*"]
        Resource = [
          "arn:aws:s3:::my-bucket",
          "arn:aws:s3:::my-bucket/*"
        ]
      }]
    })
  }
}
```

### 2. RDS IAM Authentication

```hcl
module "rds_access" {
  source = "./modules/iam"
  # ... IRSA config

  inline_policies = {
    rds_connect = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["rds-db:connect"]
        Resource = "arn:aws:rds-db:us-east-1:123:dbuser:*/app_user"
      }]
    })
  }
}
```

### 3. Secrets Manager Access

```hcl
module "secrets_access" {
  source = "./modules/iam"
  # ... IRSA config

  inline_policies = {
    secrets = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:us-east-1:123:secret:helios/*"
      }]
    })
  }
}
```

### 4. SNS Publish Access

```hcl
module "sns_access" {
  source = "./modules/iam"
  # ... IRSA config

  inline_policies = {
    sns = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = "arn:aws:sns:us-east-1:123:helios-alerts"
      }]
    })
  }
}
```

## Testing IRSA

### From Pod

```bash
# Exec into pod
kubectl exec -it reporting-xyz -n helios-prod -- /bin/bash

# Check environment variables (injected by EKS)
echo $AWS_ROLE_ARN
echo $AWS_WEB_IDENTITY_TOKEN_FILE

# Test AWS access
aws sts get-caller-identity
# Should show the IRSA role ARN

# Test S3 access
aws s3 ls s3://helios-reports/
```

### Verify Token

```bash
# View the JWT token
kubectl exec -it reporting-xyz -n helios-prod -- cat $AWS_WEB_IDENTITY_TOKEN_FILE

# Decode token (base64)
kubectl exec -it reporting-xyz -n helios-prod -- cat $AWS_WEB_IDENTITY_TOKEN_FILE | cut -d'.' -f2 | base64 -d | jq
```

## Troubleshooting

### "User is not authorized to perform: sts:AssumeRoleWithWebIdentity"

**Cause**: Service account annotation is missing or incorrect

**Fix**:
```bash
kubectl annotate serviceaccount -n helios-prod reporting-service \
  eks.amazonaws.com/role-arn=arn:aws:iam::123:role/helios-reporting-s3-access
```

### "An error occurred (AccessDenied) when calling the PutObject operation"

**Cause**: IAM role doesn't have required permissions

**Fix**: Check inline_policies or managed_policy_arns includes S3 permissions

### "Token audience does not match"

**Cause**: OIDC condition in trust policy is incorrect

**Fix**: Verify service_accounts namespace and name match exactly

## Security Best Practices

1. **Principle of Least Privilege** - Only grant required permissions
2. **One role per service** - Don't share roles across different services
3. **Use conditions** - Restrict by resource tags, IP, etc.
4. **Regular audits** - Review IAM roles and permissions
5. **Avoid wildcards** - Use specific resource ARNs
6. **Monitor usage** - Enable CloudTrail for IAM events

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0.0 |

## Outputs

| Name | Description |
|------|-------------|
| role_arn | ARN of the IAM role (use for k8s annotation) |
| role_name | Name of the IAM role |

## Further Reading

- [EKS IRSA Documentation](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Kubernetes Service Accounts](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
