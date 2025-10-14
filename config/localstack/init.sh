#!/bin/bash

echo "============================================"
echo "Initializing LocalStack AWS Resources"
echo "============================================"

# Wait for LocalStack to be fully ready
sleep 5

# Set AWS endpoint and credentials
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# S3 Buckets
echo "Creating S3 buckets..."
awslocal s3 mb s3://helios-reports || echo "Bucket helios-reports already exists"
awslocal s3 mb s3://helios-terraform-state || echo "Bucket helios-terraform-state already exists"
awslocal s3 mb s3://helios-logs || echo "Bucket helios-logs already exists"

# Enable versioning on reports bucket
awslocal s3api put-bucket-versioning \
  --bucket helios-reports \
  --versioning-configuration Status=Enabled

# Add lifecycle policy for old reports (delete after 30 days)
awslocal s3api put-bucket-lifecycle-configuration \
  --bucket helios-reports \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "delete-old-reports",
      "Status": "Enabled",
      "Expiration": {"Days": 30},
      "Filter": {"Prefix": ""}
    }]
  }'

# IAM Roles
echo "Creating IAM roles..."

# Lambda execution role
awslocal iam create-role \
  --role-name helios-lambda-execution-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' || echo "Role helios-lambda-execution-role already exists"

# Attach policies to Lambda role
awslocal iam attach-role-policy \
  --role-name helios-lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

awslocal iam attach-role-policy \
  --role-name helios-lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# EKS service role
awslocal iam create-role \
  --role-name helios-eks-cluster-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "eks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' || echo "Role helios-eks-cluster-role already exists"

# EKS node role
awslocal iam create-role \
  --role-name helios-eks-node-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' || echo "Role helios-eks-node-role already exists"

# Service account role for pods
awslocal iam create-role \
  --role-name helios-pod-execution-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "eks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' || echo "Role helios-pod-execution-role already exists"

# Attach S3 access to pod role
awslocal iam attach-role-policy \
  --role-name helios-pod-execution-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

echo "============================================"
echo "LocalStack initialization complete!"
echo "============================================"
echo ""
echo "S3 Buckets created:"
awslocal s3 ls
echo ""
echo "IAM Roles created:"
awslocal iam list-roles --query 'Roles[?contains(RoleName, `helios`)].RoleName' --output table
echo ""
echo "Access LocalStack at: http://localhost:4566"
echo "Use AWS CLI with: aws --endpoint-url=http://localhost:4566"
echo "Or use awslocal wrapper: awslocal s3 ls"
echo "============================================"
