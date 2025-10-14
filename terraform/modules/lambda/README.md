# Lambda Module

Deploy AWS Lambda functions with IAM roles, CloudWatch logging, and event triggers.

## Usage

### Basic Function

```hcl
module "report_generator" {
  source = "./modules/lambda"

  function_name = "helios-report-generator"
  description   = "Generate AI-powered incident reports"
  runtime       = "python3.11"
  handler       = "app.handler.lambda_handler"
  filename      = "lambda_function.zip"
  timeout       = 30
  memory_size   = 512

  environment_variables = {
    ANTHROPIC_API_KEY = var.anthropic_api_key
    S3_BUCKET         = module.s3.bucket_id
    DB_HOST           = module.rds.db_instance_address
  }

  tags = {
    Terraform   = "true"
    Environment = "prod"
  }
}
```

### Function with VPC Access

```hcl
module "lambda_with_vpc" {
  source = "./modules/lambda"

  function_name = "helios-db-function"
  runtime       = "python3.11"
  handler       = "index.handler"
  filename      = "function.zip"

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  # VPC functions need more memory and timeout
  memory_size = 1024
  timeout     = 60

  tags = var.tags
}
```

### Function with S3 Trigger

```hcl
module "s3_processor" {
  source = "./modules/lambda"

  function_name = "process-reports"
  runtime       = "python3.11"
  handler       = "index.handler"
  filename      = "processor.zip"

  s3_bucket_arns = [module.s3.bucket_arn]

  inline_policies = {
    s3_access = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${module.s3.bucket_arn}/*"
      }]
    })
  }

  tags = var.tags
}

# Configure S3 notification
resource "aws_s3_bucket_notification" "trigger" {
  bucket = module.s3.bucket_id

  lambda_function {
    lambda_function_arn = module.s3_processor.function_arn
    events              = ["s3:ObjectCreated:*"]
  }
}
```

### Function with CloudWatch Alarms

```hcl
resource "aws_sns_topic" "alerts" {
  name = "lambda-alerts"
}

module "monitored_lambda" {
  source = "./modules/lambda"

  function_name = "critical-function"
  runtime       = "python3.11"
  handler       = "index.handler"
  filename      = "function.zip"

  create_cloudwatch_alarms = true
  alarm_actions            = [aws_sns_topic.alerts.arn]
  alarm_error_threshold    = 5
  alarm_throttle_threshold = 1

  tags = var.tags
}
```

## Cost Optimization

### Free Tier
- **1M requests/month** free
- **400,000 GB-seconds** compute time free

### Pricing After Free Tier
- **Requests**: $0.20 per 1M requests
- **Compute**: $0.0000166667 per GB-second

### Example Costs

**Scenario: 100K requests/day, 512 MB, 2 seconds average**
```
Monthly requests: 3M
Monthly compute: 3M × 0.5 GB × 2s = 3M GB-seconds

Requests cost: (3M - 1M) × $0.20/1M = $0.40
Compute cost: (3M - 0.4M) × $0.0000166667 = $43.33
Total: ~$44/month
```

**Cost Optimization Tips**:
1. Reduce memory if possible (cost scales with memory)
2. Optimize code for faster execution
3. Use ARM64 architecture (20% cheaper)
4. Set appropriate timeout (avoid paying for hung functions)
5. Use provisioned concurrency only when needed

## Deployment Package

### Create Python ZIP

```bash
cd services/reporting
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda_function.zip .
cd ..
zip -g lambda_function.zip app/*.py
```

### With Dependencies Layer

```bash
# Create layer
mkdir python
pip install -r requirements.txt -t python/
zip -r layer.zip python

# Upload layer
aws lambda publish-layer-version \
  --layer-name helios-dependencies \
  --zip-file fileb://layer.zip \
  --compatible-runtimes python3.11

# Use in module
module "lambda" {
  # ... other config
  layers = ["arn:aws:lambda:us-east-1:123456789012:layer:helios-dependencies:1"]
}
```

## Testing with LocalStack

```bash
# Deploy to LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566

awslocal lambda create-function \
  --function-name test-function \
  --runtime python3.11 \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --handler index.handler \
  --zip-file fileb://function.zip

# Invoke function
awslocal lambda invoke \
  --function-name test-function \
  --payload '{"test": "data"}' \
  response.json

cat response.json
```

## Monitoring

### View Logs

```bash
# Get recent logs
aws logs tail /aws/lambda/helios-report-generator --follow

# Query logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/helios-report-generator \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"
```

### Metrics

```bash
# View invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=helios-report-generator \
  --start-time 2025-10-15T00:00:00Z \
  --end-time 2025-10-15T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

## Best Practices

1. **Set appropriate timeout** - Don't use max (900s) unless needed
2. **Right-size memory** - Use Lambda Power Tuning tool
3. **Use environment variables** - Never hardcode secrets
4. **Enable VPC only if needed** - Adds cold start latency
5. **Use layers for dependencies** - Faster deployments
6. **Monitor with alarms** - Catch errors early
7. **Set reserved concurrency** - Prevent runaway costs
8. **Use ARM64** - 20% cheaper, often faster
9. **Minimize package size** - Faster cold starts
10. **Use provisioned concurrency** - Only for latency-sensitive functions

## Troubleshooting

### Cold Starts
- Use provisioned concurrency ($$$)
- Reduce package size
- Use ARM64
- Keep functions warm with EventBridge

### Timeout Errors
- Increase timeout setting
- Optimize code
- Check VPC NAT gateway (if applicable)

### Permission Denied
- Check IAM role has required policies
- Verify resource-based policies
- Check VPC security groups

### Out of Memory
- Increase memory_size
- Check for memory leaks
- Monitor CloudWatch metrics
