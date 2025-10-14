# LocalStack Configuration

LocalStack provides a fully functional local AWS cloud stack for cost-free testing and development.

## What Gets Created

### S3 Buckets
- `helios-reports` - Stores AI-generated incident reports with versioning enabled
- `helios-terraform-state` - Terraform state backend
- `helios-logs` - Application logs and CloudWatch logs

### IAM Roles
- `helios-lambda-execution-role` - For Lambda functions (report generation)
- `helios-eks-cluster-role` - For EKS cluster management
- `helios-eks-node-role` - For EKS worker nodes
- `helios-pod-execution-role` - For Kubernetes pods to access S3

## Usage

### 1. Start LocalStack with Docker Compose
```bash
docker-compose up -d localstack

# Check status
docker-compose ps localstack

# View logs
docker-compose logs -f localstack
```

### 2. Configure AWS CLI for LocalStack
```bash
# Install awslocal wrapper (recommended)
pip install awscli-local

# Or configure AWS CLI manually
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

### 3. Test S3 Operations
```bash
# List buckets
awslocal s3 ls

# Upload a file
echo "test report" > report.json
awslocal s3 cp report.json s3://helios-reports/

# List files in bucket
awslocal s3 ls s3://helios-reports/

# Download file
awslocal s3 cp s3://helios-reports/report.json ./downloaded-report.json
```

### 4. Test IAM Operations
```bash
# List roles
awslocal iam list-roles

# Get role details
awslocal iam get-role --role-name helios-lambda-execution-role

# List attached policies
awslocal iam list-attached-role-policies --role-name helios-lambda-execution-role
```

### 5. Use with Terraform
```bash
# Configure Terraform to use LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_ENDPOINT_URL=http://localhost:4566

# Initialize Terraform
cd terraform
terraform init

# Plan (will use LocalStack)
terraform plan

# Apply to LocalStack (not real AWS)
terraform apply
```

## Environment Variables

The following environment variables are pre-configured in docker-compose.yml:

```yaml
AWS_DEFAULT_REGION: us-east-1
AWS_ACCESS_KEY_ID: test
AWS_SECRET_ACCESS_KEY: test
```

## Enabled Services

LocalStack is configured with the following AWS services:
- **S3** - Object storage for reports
- **Lambda** - Serverless functions for AI report generation
- **IAM** - Identity and access management
- **STS** - Security Token Service
- **CloudWatch** - Metrics and logs
- **EventBridge** - Event-driven architecture

## Persistence

LocalStack is configured with persistence enabled. Data persists in the `helios-localstack-data` Docker volume even when the container is restarted.

To clear all data:
```bash
docker-compose down
docker volume rm helios-localstack-data
docker-compose up -d localstack
```

## Accessing LocalStack

- **Gateway**: http://localhost:4566
- **Health Check**: http://localhost:4566/_localstack/health
- **Dashboard** (Pro only): http://localhost:4566/_localstack/dashboard

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs localstack

# Common issue: Docker socket access
# On Windows, enable Docker Desktop's "Expose daemon on tcp://localhost:2375"
```

### Services not responding
```bash
# Verify health
curl http://localhost:4566/_localstack/health

# Restart container
docker-compose restart localstack
```

### AWS CLI errors
```bash
# Ensure using LocalStack endpoint
aws --endpoint-url=http://localhost:4566 s3 ls

# Or use awslocal wrapper (handles endpoint automatically)
awslocal s3 ls
```

## Cost Comparison

| Component | AWS Cost (Monthly) | LocalStack Cost |
|-----------|-------------------|-----------------|
| S3 Storage (10 GB) | ~$0.23 | **$0** |
| Lambda (1M requests) | ~$0.20 | **$0** |
| IAM | Free | **$0** |
| CloudWatch Logs | ~$5 | **$0** |
| **Total** | **~$5.43/month** | **$0** |

## Next Steps

1. Test S3 upload/download with your reporting service
2. Deploy Lambda functions to LocalStack
3. Run Terraform against LocalStack for infrastructure validation
4. Use LocalStack for CI/CD testing without AWS costs
