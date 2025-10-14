# S3 Module - Report Storage

Production-ready S3 bucket for storing AI-generated incident reports with lifecycle management and security best practices.

## Features

### 1. **Security**
- Encryption at rest (AES-256 or KMS)
- Block all public access
- Versioning enabled
- Access logging
- Bucket policies

### 2. **Cost Optimization**
- Lifecycle policies for automatic deletion
- Intelligent-Tiering for infrequent access
- Storage class transitions (STANDARD → GLACIER → DEEP_ARCHIVE)

### 3. **Monitoring**
- CloudWatch metrics for errors
- S3 event notifications
- Access logging

### 4. **Disaster Recovery**
- Cross-region replication (optional)
- Versioning for accidental deletions
- Point-in-time recovery

## Usage

### Basic Configuration

```hcl
module "s3_reports" {
  source = "./modules/s3"

  bucket_name       = "helios-prod-reports"
  enable_versioning = true

  # Lifecycle: Delete reports after 30 days
  lifecycle_rules = [{
    id      = "delete-old-reports"
    enabled = true
    prefix  = ""
    expiration = {
      days = 30
    }
  }]

  tags = {
    Terraform   = "true"
    Environment = "prod"
    Project     = "helios"
  }
}
```

### Advanced Configuration with Tiered Storage

```hcl
module "s3_reports" {
  source = "./modules/s3"

  bucket_name       = "helios-prod-reports"
  enable_versioning = true
  kms_master_key_id = aws_kms_key.s3.arn

  # Multi-tier lifecycle
  lifecycle_rules = [{
    id      = "intelligent-lifecycle"
    enabled = true
    prefix  = ""

    # Move to Glacier after 30 days
    transitions = [{
      days          = 30
      storage_class = "GLACIER"
    }, {
      # Move to Deep Archive after 90 days
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }]

    # Delete after 365 days
    expiration = {
      days = 365
    }

    # Delete old versions after 7 days
    noncurrent_version_expiration = {
      days = 7
    }
  }]

  # Enable access logging
  enable_logging      = true
  log_retention_days  = 30

  # Enable S3 Intelligent-Tiering
  enable_intelligent_tiering = true

  # Event notifications
  notification_topic_arn = aws_sns_topic.s3_events.arn

  tags = {
    Terraform   = "true"
    Environment = "prod"
    Project     = "helios"
  }
}
```

### With Cross-Region Replication

```hcl
# Create replication role
resource "aws_iam_role" "replication" {
  name = "s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# Destination bucket in another region
resource "aws_s3_bucket" "replica" {
  provider = aws.us-west-2
  bucket   = "helios-prod-reports-replica"
}

module "s3_reports" {
  source = "./modules/s3"

  bucket_name       = "helios-prod-reports"
  enable_versioning = true

  # Enable replication
  replication_configuration = {
    role_arn               = aws_iam_role.replication.arn
    destination_bucket_arn = aws_s3_bucket.replica.arn
    storage_class          = "STANDARD_IA"
  }

  tags = {
    Terraform   = "true"
    Environment = "prod"
  }
}
```

## Storage Classes & Costs

| Storage Class | Use Case | Cost (per GB/month) | Retrieval Time |
|--------------|----------|---------------------|----------------|
| STANDARD | Frequently accessed | $0.023 | Milliseconds |
| STANDARD_IA | Infrequently accessed | $0.0125 | Milliseconds |
| INTELLIGENT_TIERING | Unknown access | $0.023-0.0125* | Milliseconds |
| GLACIER | Archive, rarely accessed | $0.004 | 1-5 minutes |
| DEEP_ARCHIVE | Long-term archive | $0.00099 | 12 hours |

*Auto-optimizes between tiers

### Cost Example: 1000 Reports/Day, 1 MB Each

**Scenario 1: No Lifecycle (Keep Forever)**
```
Storage: 30 TB/year × $0.023 = $690/year
```

**Scenario 2: Delete After 30 Days**
```
Storage: 30 GB max × $0.023 = $0.69/month = $8.28/year
Savings: 98.8%
```

**Scenario 3: Tiered Storage (30 days STANDARD, 60 days GLACIER, delete)**
```
Month 1: 30 GB × $0.023 = $0.69
Month 2: 30 GB × $0.004 = $0.12
Total: $0.81/month = $9.72/year
Savings: 98.6% (with 60-day retention)
```

## Lifecycle Policy Examples

### 1. Simple Deletion After 30 Days

```hcl
lifecycle_rules = [{
  id      = "delete-old-reports"
  enabled = true
  expiration = {
    days = 30
  }
}]
```

### 2. Tiered Storage Before Deletion

```hcl
lifecycle_rules = [{
  id      = "tiered-lifecycle"
  enabled = true

  transitions = [{
    days          = 30
    storage_class = "STANDARD_IA"
  }, {
    days          = 90
    storage_class = "GLACIER"
  }]

  expiration = {
    days = 365
  }
}]
```

### 3. Different Policies by Prefix

```hcl
lifecycle_rules = [
  {
    id      = "critical-reports-long-retention"
    enabled = true
    prefix  = "critical/"
    expiration = {
      days = 365  # Keep critical reports for 1 year
    }
  },
  {
    id      = "standard-reports-short-retention"
    enabled = true
    prefix  = "standard/"
    expiration = {
      days = 30  # Keep standard reports for 30 days
    }
  }
]
```

### 4. Delete Old Versions

```hcl
lifecycle_rules = [{
  id      = "clean-old-versions"
  enabled = true

  noncurrent_version_expiration = {
    days = 7  # Delete old versions after 7 days
  }
}]
```

## Access Patterns

### From Lambda Function

```python
import boto3
import json

s3 = boto3.client('s3')

# Upload report
def upload_report(report_id, report_data):
    s3.put_object(
        Bucket='helios-prod-reports',
        Key=f'reports/{report_id}.json',
        Body=json.dumps(report_data),
        ContentType='application/json',
        ServerSideEncryption='AES256'
    )

# Download report
def download_report(report_id):
    response = s3.get_object(
        Bucket='helios-prod-reports',
        Key=f'reports/{report_id}.json'
    )
    return json.loads(response['Body'].read())

# List reports
def list_reports(prefix='reports/'):
    response = s3.list_objects_v2(
        Bucket='helios-prod-reports',
        Prefix=prefix
    )
    return [obj['Key'] for obj in response.get('Contents', [])]
```

### From Kubernetes Pod (with IRSA)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: reporting-service
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/helios-reporting-s3-access

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reporting
spec:
  template:
    spec:
      serviceAccountName: reporting-service
      containers:
      - name: app
        env:
        - name: S3_BUCKET
          value: "helios-prod-reports"
```

### From AWS CLI

```bash
# Upload report
aws s3 cp report.json s3://helios-prod-reports/reports/2025-10-15-001.json

# Download report
aws s3 cp s3://helios-prod-reports/reports/2025-10-15-001.json ./report.json

# List reports
aws s3 ls s3://helios-prod-reports/reports/

# Sync directory
aws s3 sync ./reports/ s3://helios-prod-reports/reports/
```

## Monitoring

### CloudWatch Metrics

```bash
# View S3 metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name NumberOfObjects \
  --dimensions Name=BucketName,Value=helios-prod-reports Name=StorageType,Value=AllStorageTypes \
  --start-time 2025-10-01T00:00:00Z \
  --end-time 2025-10-15T00:00:00Z \
  --period 86400 \
  --statistics Average
```

### S3 Inventory

Enable S3 Inventory for detailed reporting:

```hcl
resource "aws_s3_bucket_inventory" "reports" {
  bucket = module.s3_reports.bucket_id
  name   = "weekly-inventory"

  included_object_versions = "All"

  schedule {
    frequency = "Weekly"
  }

  destination {
    bucket {
      format     = "CSV"
      bucket_arn = module.s3_reports.bucket_arn
      prefix     = "inventory"
    }
  }
}
```

## Security Best Practices

### 1. Block Public Access

The module automatically blocks all public access. Never disable this for production.

### 2. Encryption at Rest

Always enable encryption:

```hcl
# Use AWS managed keys (default)
kms_master_key_id = null

# Or use customer managed KMS key
kms_master_key_id = aws_kms_key.s3.arn
```

### 3. Bucket Policy for Least Privilege

```hcl
data "aws_iam_policy_document" "bucket_policy" {
  statement {
    sid    = "AllowReportingServiceAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.reporting_service.arn]
    }

    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket"
    ]

    resources = [
      module.s3_reports.bucket_arn,
      "${module.s3_reports.bucket_arn}/*"
    ]
  }

  # Deny unencrypted uploads
  statement {
    sid    = "DenyUnencryptedObjectUploads"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:PutObject"]

    resources = ["${module.s3_reports.bucket_arn}/*"]

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["AES256", "aws:kms"]
    }
  }
}

module "s3_reports" {
  # ... other config
  bucket_policy = data.aws_iam_policy_document.bucket_policy.json
}
```

### 4. Access Logging

Enable logging to track all access:

```hcl
enable_logging     = true
log_retention_days = 90  # Keep logs for 90 days
```

## Testing with LocalStack

```bash
# Start LocalStack
docker-compose up -d localstack

# Create bucket
awslocal s3 mb s3://helios-reports

# Upload test file
echo '{"test": "report"}' > test-report.json
awslocal s3 cp test-report.json s3://helios-reports/

# List files
awslocal s3 ls s3://helios-reports/

# Download file
awslocal s3 cp s3://helios-reports/test-report.json ./downloaded.json
```

## Troubleshooting

### Access Denied Errors

1. Check bucket policy allows the IAM role
2. Verify IRSA annotation on service account
3. Ensure IAM role has trust policy for OIDC provider
4. Check KMS key policy if using KMS encryption

### Lifecycle Rules Not Working

1. Check rule is enabled: `status = "Enabled"`
2. Verify prefix matches your objects
3. Wait 24 hours for rules to take effect
4. Check CloudWatch metrics for lifecycle transitions

### High Costs

1. Review storage class distribution
2. Check if lifecycle rules are working
3. Enable Intelligent-Tiering
4. Reduce retention period
5. Delete unnecessary old versions

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0.0 |

## Outputs

| Name | Description |
|------|-------------|
| bucket_id | Bucket name |
| bucket_arn | Bucket ARN |
| bucket_regional_domain_name | Regional domain name for SDK access |

## Best Practices

1. **Always enable encryption** (AES-256 or KMS)
2. **Block public access** (enabled by default)
3. **Enable versioning** for accidental deletion protection
4. **Use lifecycle policies** to control costs
5. **Enable access logging** for security auditing
6. **Use Intelligent-Tiering** for unknown access patterns
7. **Enable replication** for critical data
8. **Set retention policies** based on compliance requirements
9. **Use IRSA** for pod access instead of instance profiles
10. **Monitor costs** with CloudWatch and S3 Analytics
