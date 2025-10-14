# RDS Module - TimescaleDB on PostgreSQL

Production-ready RDS PostgreSQL with TimescaleDB extension for time-series data workloads.

## What is TimescaleDB?

TimescaleDB is a PostgreSQL extension optimized for time-series data. It provides:
- **Automatic partitioning** (hypertables) for better query performance
- **Continuous aggregates** for real-time materialized views
- **Data retention policies** for automatic data cleanup
- **Time-series specific functions** for analysis

Perfect for storing and querying metrics, logs, and event data.

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                   Multi-AZ Deployment                 │
├───────────────────────────────────────────────────────┤
│                                                       │
│   ┌─────────────────┐        ┌─────────────────┐    │
│   │   Primary RDS   │        │  Standby RDS    │    │
│   │   (AZ-1a)       │◄──────►│   (AZ-1b)       │    │
│   │                 │ Sync   │                 │    │
│   │  TimescaleDB    │ Repl   │  TimescaleDB    │    │
│   │  PostgreSQL 15  │        │  PostgreSQL 15  │    │
│   └────────┬────────┘        └─────────────────┘    │
│            │                                         │
│            │ Automated Backups                       │
│            ▼                                         │
│   ┌─────────────────┐                               │
│   │   S3 Backups    │                               │
│   │  (7-day retention)                              │
│   └─────────────────┘                               │
│                                                       │
└───────────────────────────────────────────────────────┘
           │
           │ CloudWatch Monitoring
           ▼
  ┌──────────────────┐
  │  CloudWatch      │
  │  - CPU           │
  │  - Memory        │
  │  - Storage       │
  │  - Connections   │
  └──────────────────┘
```

## Features

### 1. **TimescaleDB Optimization**
- Pre-configured parameter group with TimescaleDB settings
- Memory allocation optimized for time-series workloads
- Connection pooling parameters
- Query performance tuning

### 2. **High Availability**
- Multi-AZ deployment with automatic failover
- Synchronous replication
- Automated backups with 7-day retention
- Point-in-time recovery (PITR)

### 3. **Security**
- Encryption at rest with KMS
- Encryption in transit (SSL/TLS)
- VPC isolation
- Security groups for access control
- Password stored in AWS Secrets Manager

### 4. **Monitoring & Alerts**
- Enhanced monitoring (60-second intervals)
- Performance Insights
- CloudWatch log exports
- Automated alarms for CPU, memory, storage, connections

### 5. **Auto-Scaling**
- Storage auto-scaling up to max_allocated_storage
- Automatic minor version upgrades

## Usage

```hcl
module "rds" {
  source = "./modules/rds"

  identifier     = "helios-prod-db"
  engine_version = "15.4"
  instance_class = "db.t3.medium"

  # Storage
  allocated_storage     = 100  # Initial 100 GB
  max_allocated_storage = 500  # Auto-scale up to 500 GB
  storage_type          = "gp3"
  storage_encrypted     = true

  # Database
  database_name   = "helios"
  master_username = "helios_admin"
  # master_password = null  # Auto-generated and stored in Secrets Manager

  # Network
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnet_ids
  allowed_security_group_ids = [module.eks.node_security_group_id]
  publicly_accessible        = false

  # High Availability
  multi_az = true

  # Backups
  backup_retention_period = 7
  backup_window           = "03:00-04:00"       # UTC
  maintenance_window      = "mon:04:00-mon:05:00"  # UTC

  # Monitoring
  monitoring_interval                   = 60
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  # Alarms
  create_cloudwatch_alarms = true
  alarm_cpu_threshold      = 80
  alarm_memory_threshold   = 536870912   # 512 MB
  alarm_storage_threshold  = 10737418240  # 10 GB

  # Security
  deletion_protection         = true
  skip_final_snapshot         = false
  create_db_password_secret   = true

  tags = {
    Terraform   = "true"
    Environment = "prod"
    Project     = "helios"
  }
}
```

## TimescaleDB Configuration

### Parameter Group Highlights

```hcl
# TimescaleDB extension
shared_preload_libraries = "timescaledb"

# Memory allocation (optimized for time-series)
shared_buffers = 25% of RAM
effective_cache_size = 50% of RAM
work_mem = 10 MB per operation

# Write performance
checkpoint_completion_target = 0.9
wal_buffers = 16 MB

# Query optimization
random_page_cost = 1.1  # SSD-optimized
effective_io_concurrency = 200
```

### After Deployment: Enable TimescaleDB

Connect to the database and run:

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create hypertable for events
CREATE TABLE events (
  time        TIMESTAMPTZ NOT NULL,
  service     TEXT NOT NULL,
  level       TEXT,
  message     TEXT,
  metadata    JSONB
);

SELECT create_hypertable('events', 'time');

-- Create continuous aggregate for 5-minute windows
CREATE MATERIALIZED VIEW events_5min
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('5 minutes', time) AS bucket,
  service,
  level,
  count(*) as event_count
FROM events
GROUP BY bucket, service, level;

-- Add refresh policy (auto-update every 5 minutes)
SELECT add_continuous_aggregate_policy('events_5min',
  start_offset => INTERVAL '1 hour',
  end_offset => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '5 minutes');

-- Add data retention policy (keep 30 days)
SELECT add_retention_policy('events', INTERVAL '30 days');
```

## Accessing the Database

### From EKS Pods

```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DB_HOST
          value: "helios-prod-db.abc123.us-east-1.rds.amazonaws.com"
        - name: DB_PORT
          value: "5432"
        - name: DB_NAME
          value: "helios"
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: rds-credentials
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: rds-credentials
              key: password
```

### Retrieve Password from Secrets Manager

```bash
# Get database credentials
aws secretsmanager get-secret-value \
  --secret-id helios-prod-db-master-password \
  --query SecretString \
  --output text | jq -r '.password'
```

### Connect with psql

```bash
# Get connection details
export DB_HOST=$(terraform output -raw db_instance_address)
export DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id helios-prod-db-master-password \
  --query SecretString --output text | jq -r '.password')

# Connect
psql "postgresql://helios_admin:$DB_PASSWORD@$DB_HOST:5432/helios"
```

## Cost Optimization

### Production vs Development Configurations

**Production (High Availability)**
```hcl
instance_class   = "db.t3.medium"   # $0.068/hr = ~$50/month
multi_az         = true              # 2x cost = ~$100/month
allocated_storage = 100              # 100 GB gp3 = $8/month
Total: ~$108/month
```

**Development (Cost-Optimized)**
```hcl
instance_class   = "db.t3.micro"    # $0.017/hr = ~$12/month
multi_az         = false             # Single AZ
allocated_storage = 20               # 20 GB gp3 = $1.60/month
Total: ~$14/month
```

**Savings**: ~$94/month (87% reduction)

### Additional Cost Optimizations

1. **Use t3 instances** (burstable) instead of m5/r5
2. **Disable Multi-AZ** for non-production
3. **Reduce backup_retention_period** to 1 day
4. **Disable Performance Insights** in dev
5. **Use gp2 instead of gp3** (minor savings)

## CloudWatch Alarms

The module creates 4 automated alarms:

| Alarm | Threshold | Action |
|-------|-----------|--------|
| High CPU | 80% for 10 min | Alert |
| Low Memory | < 512 MB free | Alert |
| Low Storage | < 10 GB free | Alert |
| High Connections | > 80% of max | Alert |

Configure SNS topic for notifications:

```hcl
resource "aws_sns_topic" "alerts" {
  name = "rds-alerts"
}

module "rds" {
  # ... other configuration
  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

## Performance Tuning

### Query Performance

```sql
-- Check slow queries
SELECT
  substring(query, 1, 100) AS short_query,
  calls,
  total_exec_time,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan AS index_scans,
  idx_tup_read AS tuples_read,
  idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

### Connection Pooling

For applications with many connections, use **PgBouncer** or **Amazon RDS Proxy**:

```bash
# Example: Using PgBouncer in Kubernetes
kubectl apply -f pgbouncer-deployment.yaml
```

## Monitoring

### Key Metrics to Watch

1. **CPU Utilization** - Should stay < 70% on average
2. **Freeable Memory** - Should stay > 1 GB
3. **Database Connections** - Should stay < 80% of max_connections
4. **Storage Space** - Monitor growth rate
5. **Read/Write IOPS** - Ensure within provisioned limits
6. **Read/Write Latency** - P99 should be < 10ms for SSD

### Performance Insights

Access via AWS Console:
1. RDS → Your instance → Performance Insights
2. View top SQL queries, wait events, database load

## Backup & Recovery

### Automated Backups

- Daily backups during backup_window
- Retained for backup_retention_period days
- Stored in S3 (encrypted)
- Enable PITR (Point-in-Time Recovery)

### Manual Snapshots

```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier helios-prod-db \
  --db-snapshot-identifier helios-prod-db-manual-2025-10-15

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier helios-prod-db-restored \
  --db-snapshot-identifier helios-prod-db-manual-2025-10-15
```

### Point-in-Time Recovery

```bash
# Restore to specific time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier helios-prod-db \
  --target-db-instance-identifier helios-prod-db-restored \
  --restore-time 2025-10-15T12:00:00Z
```

## Troubleshooting

### High CPU Usage

1. Check slow queries in pg_stat_statements
2. Add missing indexes
3. Optimize queries
4. Consider upgrading instance class

### Connection Limit Reached

1. Check current connections: `SELECT count(*) FROM pg_stat_activity;`
2. Kill idle connections
3. Implement connection pooling (PgBouncer/RDS Proxy)
4. Increase max_connections parameter

### Storage Full

1. Check table/index sizes
2. Run VACUUM to reclaim space
3. Drop unused indexes
4. Implement data retention policies
5. Increase allocated_storage

### Slow Queries

1. Enable pg_stat_statements extension
2. Analyze slow queries
3. Add appropriate indexes
4. Consider partitioning large tables

## Migration from Docker Compose

```bash
# 1. Dump existing data
docker exec helios-timescaledb pg_dump -U postgres helios > backup.sql

# 2. Get RDS endpoint
export RDS_HOST=$(terraform output -raw db_instance_address)
export RDS_PASSWORD=$(terraform output -raw db_instance_password)

# 3. Restore to RDS
psql "postgresql://helios_admin:$RDS_PASSWORD@$RDS_HOST:5432/helios" < backup.sql

# 4. Update application configs to use RDS endpoint
kubectl set env deployment/ingestion DB_HOST=$RDS_HOST
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0.0 |
| random | >= 3.5.0 |

## Outputs

| Name | Description |
|------|-------------|
| db_instance_endpoint | Connection endpoint (host:port) |
| db_instance_address | Database hostname |
| db_password_secret_arn | Secrets Manager ARN for credentials |
| connection_string | PostgreSQL connection string |

## Best Practices

1. **Always enable Multi-AZ** in production
2. **Enable encryption at rest** with KMS
3. **Store passwords in Secrets Manager**
4. **Enable deletion protection** for production
5. **Set appropriate backup retention** (7-30 days)
6. **Monitor with CloudWatch alarms**
7. **Use Performance Insights** to identify bottlenecks
8. **Implement connection pooling** for high-traffic apps
9. **Regular VACUUM and ANALYZE** for query performance
10. **Test backup/restore procedures** periodically
