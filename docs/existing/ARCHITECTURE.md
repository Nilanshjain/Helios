# Helios Architecture - Deep Dive

This document provides a comprehensive overview of Helios' system architecture, design decisions, and technical implementation details.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Technology Choices](#technology-choices)
5. [Scalability Considerations](#scalability-considerations)
6. [Security & Reliability](#security--reliability)
7. [Performance Optimizations](#performance-optimizations)

---

## System Overview

Helios is a **distributed, event-driven observability platform** designed to:
- Ingest high-volume application logs/events
- Store time-series data efficiently
- Detect anomalies using unsupervised Machine Learning
- Generate automated incident reports using Large Language Models

### Design Principles

1. **Event-Driven**: Loose coupling between services via message broker
2. **Polyglot**: Right language for the right job (Go for speed, Python for ML/AI)
3. **Scalable**: Horizontal scaling via Kafka partitions and consumer groups
4. **Observable**: Built-in metrics and monitoring at every layer
5. **Time-Series Optimized**: Specialized database for temporal queries

---

## Component Architecture

### 1. Ingestion Service (Go)

**Purpose**: High-throughput, low-latency event ingestion

**Technology**: Go 1.21
- **Why Go**: Native concurrency (goroutines), low memory overhead, compiled performance

**Key Features**:
- Goroutine-per-request concurrency model
- Batch endpoint for bulk ingestion (10 events/request)
- Kafka producer with async publishing
- Prometheus metrics instrumentation

**API Endpoints**:
```
POST /api/v1/events        - Single event ingestion
POST /api/v1/events/batch  - Batch ingestion (array of events)
GET  /health               - Health check
GET  /metrics              - Prometheus metrics
```

**Event Schema**:
```json
{
  "timestamp": "2025-10-24T10:00:00Z",
  "service": "api-gateway",
  "level": "ERROR|WARN|INFO|DEBUG|CRITICAL",
  "message": "Request failed",
  "metadata": {
    "latency_ms": 150,
    "endpoint": "/api/users",
    "status_code": 500
  },
  "trace_id": "trace_abc123",
  "span_id": "span_def456"
}
```

**Performance Characteristics**:
- **P99 Latency**: 21-27ms (including Kafka publish)
- **Concurrency**: ~50-100 concurrent goroutines
- **Throughput**: 600-700 events/sec (local testing)

**Code Structure**:
```
services/ingestion/
├── main.go              # Entry point, HTTP server setup
├── handlers/
│   └── event_handler.go # Request handling, validation
├── kafka/
│   └── producer.go      # Kafka producer wrapper
├── models/
│   └── event.go         # Event struct definitions
└── Dockerfile
```

---

### 2. Kafka Message Broker

**Purpose**: Decoupled, scalable message streaming

**Technology**: Apache Kafka 3.6 + Zookeeper

**Topics**:
```
events          - Raw event stream (all ingested events)
anomaly-alerts  - Detected anomalies (published by detection service)
```

**Configuration**:
- **Partitions**: 10 per topic (supports horizontal scaling)
- **Replication Factor**: 1 (single-node, production would use 3)
- **Compression**: Snappy (balance between speed and compression ratio)
- **Retention**: 7 days (configurable)
- **Acknowledgment**: all (wait for leader + replicas)

**Consumer Groups**:
```
storage-writers     - Writes events to TimescaleDB
anomaly-detectors   - ML detection pipeline
reporting-service   - Report generation from anomalies
```

**Why Kafka**:
- ✅ High throughput (millions of messages/sec)
- ✅ Durable message storage (replay capability)
- ✅ Consumer groups (independent processing of same stream)
- ✅ Horizontal scalability (add partitions, add consumers)
- ✅ Industry standard (used by LinkedIn, Uber, Netflix)

**Performance**:
- **Message Delivery**: 100% (0 lag measured)
- **Messages Processed**: 70,900+ in testing
- **Partition Distribution**: Even across 10 partitions

---

### 3. Storage Writer (Go)

**Purpose**: Persist events to time-series database

**Technology**: Go 1.21 + Kafka Consumer + PostgreSQL driver

**Responsibilities**:
- Consumes from `events` topic
- Batch writes to TimescaleDB (configurable batch size)
- Error handling and retry logic

**Code Structure**:
```
services/storage/
├── consumer.go          # Kafka consumer loop
├── database/
│   └── timescale.go     # TimescaleDB connection, batch insert
└── Dockerfile
```

**Write Strategy**:
- Batch writes (default: 100 events per transaction)
- Prepared statements for performance
- Error events logged to separate error topic (future enhancement)

---

### 4. TimescaleDB (Time-Series Database)

**Purpose**: Optimized storage for time-series event data

**Technology**: TimescaleDB 2.13 (PostgreSQL extension)

**Schema**:
```sql
CREATE TABLE events (
    time        TIMESTAMPTZ NOT NULL,
    service     TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('DEBUG','INFO','WARN','ERROR','CRITICAL')),
    message     TEXT NOT NULL,
    metadata    JSONB,
    trace_id    TEXT,
    span_id     TEXT,
    host        TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable (TimescaleDB magic)
SELECT create_hypertable('events', 'time');
```

**Indexes**:
```sql
-- Time-series queries (most common)
CREATE INDEX idx_events_time ON events (time DESC);

-- Service-specific queries
CREATE INDEX idx_events_service_time ON events (service, time DESC);

-- Error filtering
CREATE INDEX idx_events_level_time ON events (level, time DESC)
WHERE level IN ('ERROR', 'CRITICAL');

-- Distributed tracing
CREATE INDEX idx_events_trace_id ON events (trace_id)
WHERE trace_id IS NOT NULL;

-- JSON field searches
CREATE INDEX idx_events_metadata_gin ON events USING GIN (metadata);
```

**Continuous Aggregates** (pre-computed rollups):
```sql
-- 5-minute aggregated metrics per service
CREATE MATERIALIZED VIEW events_5min AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    service,
    COUNT(*) as event_count,
    COUNT(*) FILTER (WHERE level IN ('ERROR', 'CRITICAL')) as error_count,
    AVG((metadata->>'latency_ms')::float) as avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::float) as p95_latency_ms
FROM events
GROUP BY bucket, service;
```

**Why TimescaleDB**:
- ✅ Automatic data partitioning by time
- ✅ Native time-series functions (time_bucket, first, last)
- ✅ Continuous aggregates (automatic rollups)
- ✅ Full PostgreSQL compatibility (JSONB, indexes, transactions)
- ✅ Compression (10x storage savings on old data)

**Performance**:
- **Events Stored**: 25,590+ in testing
- **Write Throughput**: Kept up with 700 events/sec
- **Query Performance**: Sub-100ms for 5-minute windows

---

### 5. Detection Service - ML Pipeline (Python)

**Purpose**: Real-time anomaly detection on streaming events

**Technology**: Python 3.11 + Scikit-learn + Kafka Consumer

#### Architecture

```
Kafka Consumer
     ↓
Event Buffering (5-minute sliding windows per service)
     ↓
Feature Extraction (12 features)
     ↓
ML Inference (Isolation Forest)
     ↓
Anomaly Threshold (-0.7)
     ↓
Publish to anomaly-alerts topic
```

#### Feature Engineering Pipeline

**12 Features Extracted**:

1. **event_count** - Total events in window
2. **error_rate** - Percentage of ERROR/CRITICAL events
3. **p50_latency_ms** - Median latency
4. **p95_latency_ms** - 95th percentile latency
5. **p99_latency_ms** - 99th percentile latency
6. **latency_std** - Latency standard deviation
7. **hour_of_day** - Temporal pattern (0-23)
8. **p95_p50_ratio** - Latency tail indicator (high = outliers)
9. **p99_p95_ratio** - Extreme tail indicator
10. **error_count** - Absolute error count (event_count * error_rate)
11. **log_event_count** - Log-scaled event count (handles volume spikes)
12. **log_error_rate** - Log-scaled error rate (handles rate spikes)

**Code**:
```python
def extract_features(events):
    event_count = len(events)
    error_rate = count_errors(events) / event_count

    latencies = extract_latencies(events)
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)

    # Engineered features
    p95_p50_ratio = p95 / (p50 + 1)  # Avoid div by zero
    p99_p95_ratio = p99 / (p95 + 1)
    error_count = event_count * error_rate
    log_event_count = np.log1p(event_count)
    log_error_rate = np.log1p(error_rate * 1000)

    return [event_count, error_rate, p50, p95, p99, latency_std,
            hour_of_day, p95_p50_ratio, p99_p95_ratio,
            error_count, log_event_count, log_error_rate]
```

#### ML Model: Isolation Forest

**Algorithm**: Isolation Forest (Unsupervised Anomaly Detection)

**Why Isolation Forest**:
- ✅ **No labeled data needed** - Learns normal behavior from data
- ✅ **Fast inference** - O(log n) prediction time
- ✅ **Effective for outliers** - Isolates rare events
- ✅ **Works with multi-dimensional features** - Handles 12 features

**Training Process**:
```python
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Train on 7 days of synthetic normal data
model = IsolationForest(
    contamination=0.05,      # Expect 5% anomalies
    n_estimators=100,        # 100 decision trees
    max_samples='auto',
    random_state=42
)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(training_features)
model.fit(X_scaled)
```

**Inference**:
```python
# Extract features from window
features = feature_extractor.extract_features(events)

# Scale and predict
features_scaled = scaler.transform(features)
anomaly_score = model.decision_function(features_scaled)[0]

# Classify
is_anomaly = anomaly_score < THRESHOLD  # -0.7
```

**Detection Logic**:
- **Sliding Windows**: 5-minute windows per service
- **Trigger**: Every 5 minutes per service (time-based)
- **Min Events**: Require ≥10 events for statistical significance
- **Threshold**: -0.7 (lower = more anomalous)

**Performance**:
- **Model Size**: 248KB (pickled)
- **Load Time**: <100ms
- **Inference Time**: <10ms per window
- **Verified**: Model loads and runs predictions (sklearn warnings confirm)

---

### 6. Reporting Service - LLM Integration (Python)

**Purpose**: Generate human-readable incident reports from anomalies

**Technology**: Python 3.11 + Anthropic Claude API + Kafka Consumer

#### Architecture

```
Kafka Consumer (anomaly-alerts topic)
     ↓
Report Generator (Mock or Claude API)
     ↓
Prompt Engineering (context, events, scores)
     ↓
Claude LLM API Call
     ↓
Store Report (filesystem or S3)
```

#### Prompt Engineering

**Template**:
```python
prompt = f"""
You are an SRE analyzing an anomaly in the {service} service.

ANOMALY DETAILS:
- Service: {service}
- Detection Time: {timestamp}
- Anomaly Score: {score:.3f} (threshold: -0.7)
- Events in Window: {event_count}
- Error Rate: {error_rate:.1%}
- P99 Latency: {p99_latency_ms:.0f}ms

RECENT EVENTS:
{format_events(recent_events)}

Please provide:
1. Severity assessment (Critical/High/Medium/Low)
2. Probable root cause
3. Impact analysis
4. Recommended actions

Format as structured incident report.
"""
```

**Claude API Configuration**:
```python
import anthropic

client = anthropic.Anthropic(api_key=os.environ['CLAUDE_API_KEY'])

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    temperature=0.3,  # Lower = more factual
    messages=[{"role": "user", "content": prompt}]
)
```

**Mock Mode** (for testing without API costs):
```python
def generate_mock_report(anomaly):
    return {
        "report_id": generate_id(),
        "service": anomaly['service'],
        "severity": "HIGH",
        "summary": f"Anomaly detected in {anomaly['service']}",
        "error_rate": anomaly['error_rate'],
        "recommendations": [
            "Check service logs for errors",
            "Verify database connectivity",
            "Review recent deployments"
        ]
    }
```

**Storage**:
- **Filesystem**: `/app/reports/{timestamp}_{service}.json`
- **Future**: S3 bucket, database, ticketing system integration

---

### 7. Monitoring Stack

#### Prometheus (Metrics Collection)

**Scrape Targets**:
```yaml
scrape_configs:
  - job_name: 'ingestion'
    static_configs:
      - targets: ['ingestion:8081']

  - job_name: 'detection'
    static_configs:
      - targets: ['detection:8001']

  - job_name: 'reporting'
    static_configs:
      - targets: ['reporting:8003']
```

**Key Metrics**:

**Ingestion**:
- `http_requests_total` - Request counter by endpoint, method, status
- `http_request_duration_seconds` - Latency histogram
- `kafka_publish_duration_seconds` - Kafka producer latency

**Detection**:
- `helios_events_processed` - Events consumed by service, status
- `helios_window_size` - Current window size per service
- `helios_anomalies_detected` - Anomaly counter
- `helios_detection_latency` - ML inference time

**Reporting**:
- `helios_reports_generated` - Report counter
- `helios_report_generation_latency` - LLM API call time

#### Grafana (Visualization)

**Potential Dashboards**:

1. **Ingestion Overview**
   - Request rate (RPS)
   - Latency (P50/P95/P99)
   - Error rate
   - Kafka publish latency

2. **Detection Pipeline**
   - Events processed per service
   - Anomalies detected timeline
   - Window sizes
   - ML inference time

3. **System Health**
   - CPU/Memory per service
   - Kafka consumer lag
   - Database query time
   - Disk usage

---

## Data Flow

### 1. Normal Event Flow (No Anomaly)

```
1. Client → POST /api/v1/events
   ├─ Ingestion validates event
   └─ Returns 202 Accepted

2. Ingestion → Kafka Producer
   ├─ Serializes to JSON
   ├─ Compresses with snappy
   └─ Publishes to 'events' topic (partition by service hash)

3. Kafka → Storage Writer Consumer
   ├─ Consumes event
   ├─ Batches 100 events
   └─ INSERT INTO TimescaleDB

4. Kafka → Detection Consumer
   ├─ Consumes event
   ├─ Adds to service window (5-min buffer)
   ├─ Checks if 5 minutes elapsed
   └─ IF NO: continue buffering

Total Latency: 15-25ms (ingestion → storage)
```

### 2. Anomaly Detection Flow

```
1. Detection Consumer → 5 minutes elapsed
   ├─ Check window size ≥ 10 events
   └─ Extract 12 features

2. Feature Extraction
   ├─ Calculate error rate, latencies, counts
   └─ Engineer ratios, log transforms

3. ML Inference
   ├─ Load Isolation Forest model
   ├─ Scale features (StandardScaler)
   ├─ model.decision_function(features)
   └─ Compare score to threshold (-0.7)

4. IF ANOMALY DETECTED:
   ├─ Create anomaly alert JSON
   ├─ Publish to 'anomaly-alerts' topic
   └─ Log to Prometheus metrics

5. Reporting Consumer → Receives alert
   ├─ Generate prompt with context
   ├─ Call Claude API (or mock)
   ├─ Parse response
   └─ Store report to filesystem

Total Latency: 5 minutes (window) + 2-5 seconds (LLM)
```

### 3. Query Flow (User Queries Historical Data)

```
1. User → Grafana Dashboard
   ↓
2. Grafana → Prometheus Query
   ├─ PromQL: rate(http_requests_total[5m])
   └─ Prometheus returns time-series

3. Grafana → TimescaleDB Query (optional)
   ├─ SQL: SELECT * FROM events WHERE time > NOW() - INTERVAL '1 hour'
   ├─ Uses time-based index
   └─ Returns events

4. Grafana → Renders charts
```

---

## Technology Choices

### Why Go for Ingestion?

**Requirements**: High throughput, low latency, concurrent request handling

**Go Advantages**:
- ✅ Native concurrency (goroutines = lightweight threads)
- ✅ Compiled binary (fast startup, small footprint)
- ✅ Strong standard library (net/http, encoding/json)
- ✅ Easy deployment (single binary, no runtime dependencies)
- ✅ Industry adoption (Docker, Kubernetes, Prometheus all use Go)

**Alternatives Considered**:
- **Node.js**: Good concurrency but higher memory usage
- **Java**: Powerful but heavyweight (JVM, startup time)
- **Rust**: Excellent performance but steeper learning curve

### Why Python for ML/Reporting?

**Requirements**: ML libraries, data processing, LLM integration

**Python Advantages**:
- ✅ Best ML ecosystem (scikit-learn, pandas, numpy)
- ✅ LLM SDK support (Anthropic, OpenAI official libraries)
- ✅ Fast prototyping and iteration
- ✅ Rich data processing tools

**Alternatives Considered**:
- **Go**: Limited ML libraries, no native LLM SDKs
- **Java**: Verbose, ML libraries less mature than Python

### Why Kafka vs Alternatives?

**Requirements**: Message durability, replay capability, horizontal scaling

**Kafka Advantages**:
- ✅ Industry standard (proven at scale)
- ✅ Message persistence (can replay from any offset)
- ✅ Consumer groups (multiple independent consumers)
- ✅ Partitioning for horizontal scaling
- ✅ Rich ecosystem (Kafka Streams, Connect, UI tools)

**Alternatives Considered**:
- **RabbitMQ**: Simpler but less scalable, no native partitioning
- **Redis Streams**: Fast but limited persistence, smaller ecosystem
- **AWS SQS/SNS**: Cloud-native but vendor lock-in, no replay

### Why TimescaleDB vs Alternatives?

**Requirements**: Time-series optimization, SQL compatibility, JSONB support

**TimescaleDB Advantages**:
- ✅ Full PostgreSQL (SQL, transactions, JSONB, indexes)
- ✅ Automatic time-based partitioning (hypertables)
- ✅ Continuous aggregates (pre-computed rollups)
- ✅ Compression (10x savings on old data)
- ✅ Easy migration from PostgreSQL

**Alternatives Considered**:
- **InfluxDB**: Purpose-built for time-series but limited query language
- **Elasticsearch**: Powerful search but higher resource usage
- **ClickHouse**: Extremely fast but less SQL-compatible

---

## Scalability Considerations

### Current Limitations (Single-Node Deployment)

- **Ingestion**: Single Go instance (600-700 e/s)
- **Kafka**: Single broker (no replication)
- **Database**: Single TimescaleDB instance
- **Consumers**: Single instance per consumer group

### Horizontal Scaling Strategy

#### 1. Ingestion Service

**Current**: 1 instance behind Docker network

**Scaled**: Multiple instances behind load balancer

```
Internet
   ↓
[Load Balancer - NGINX/HAProxy]
   ↓  ↓  ↓
[Ingestion 1] [Ingestion 2] [Ingestion 3]
   ↓  ↓  ↓
       Kafka
```

**Configuration**:
- Round-robin load balancing
- Health check endpoint: `/health`
- Each instance produces to same Kafka topic

**Expected Throughput**: 2,000-3,000 e/s with 3 instances

#### 2. Kafka Cluster

**Current**: 1 broker, 10 partitions per topic

**Scaled**: 3 brokers, 30 partitions per topic

```
Zookeeper Ensemble (3 nodes)
   ↓  ↓  ↓
[Kafka Broker 1] [Kafka Broker 2] [Kafka Broker 3]
   Partitions:      Partitions:      Partitions:
   0, 3, 6, 9       1, 4, 7, 10      2, 5, 8, 11
```

**Configuration**:
- Replication factor: 3 (no data loss)
- Min in-sync replicas: 2
- Partitions: 30 (10 partitions × 3 replicas)

**Expected Throughput**: 100K+ messages/sec

#### 3. Consumer Groups

**Current**: 1 consumer per group (processes all 10 partitions)

**Scaled**: Multiple consumers per group (1 consumer per partition)

```
Kafka Topic: events (10 partitions)
   ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓
   [Detection Consumer Group]
    C1 C2 C3 C4 C5 C6 C7 C8 C9 C10
    ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓
       All write to same database
```

**Configuration**:
- 10 consumers = 1 per partition (max parallelism)
- Consumer group ID: `anomaly-detectors`
- Kafka automatically balances partitions

**Expected Processing**: 10x throughput (parallel processing)

#### 4. TimescaleDB

**Current**: Single instance

**Scaled**: Streaming replication + read replicas

```
Primary (Write)
   ↓
[WAL Streaming]
   ↓  ↓
Replica 1  Replica 2 (Read-only)
```

**Configuration**:
- Primary: All writes (ingestion, consumers)
- Replicas: All reads (Grafana, analytics)
- Continuous aggregates: Pre-computed on primary

**Alternative**: TimescaleDB Cloud (managed multi-node)

---

## Security & Reliability

### Current Security Posture

**Production Gaps** (expected for demo project):
- ❌ No authentication on ingestion API (public endpoint)
- ❌ No TLS/SSL (HTTP, not HTTPS)
- ❌ No API rate limiting
- ❌ Kafka has no ACLs (any consumer can read any topic)
- ❌ Database credentials in plaintext (docker-compose.yml)

### Production-Ready Security Checklist

#### 1. API Security

```yaml
# Add JWT authentication
POST /api/v1/events
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# Add rate limiting (per API key)
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1635724800

# Add TLS
https://ingestion.helios.com/api/v1/events
```

#### 2. Kafka Security

```properties
# Enable SASL/SCRAM authentication
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=...

# Enable ACLs
bin/kafka-acls.sh --add --allow-principal User:ingestion \
  --operation Write --topic events
```

#### 3. Database Security

```bash
# Use secrets management (Vault, AWS Secrets Manager)
DB_PASSWORD=$(vault kv get -field=password secret/timescale)

# Enable SSL connection
postgresql://user:pass@db:5432/helios?sslmode=require

# Rotate credentials regularly
```

### Reliability Features

#### 1. Kafka Durability

```properties
# Producer config (ingestion service)
acks=all                    # Wait for all replicas
retries=3                   # Retry failed sends
max.in.flight.requests=1    # Ensure ordering

# Topic config
min.insync.replicas=2       # Min replicas before accepting write
```

#### 2. Consumer Error Handling

```python
# Detection consumer
try:
    process_event(event)
except Exception as e:
    logger.error("processing_failed", error=str(e))
    # Don't commit offset (retry on restart)
    # OR publish to dead-letter queue
    producer.send('dlq-events', event)
```

#### 3. Database Transactions

```python
# Storage writer
with connection.begin():
    cursor.executemany(
        "INSERT INTO events (...) VALUES (...)",
        batch_events
    )
    # Auto-commit on success, rollback on exception
```

---

## Performance Optimizations

### 1. Ingestion Service

**Batch Endpoint**:
```go
// Instead of 1 event = 1 Kafka message
// Batch: 10 events = 1 Kafka message

// Reduces network overhead by 10x
// Latency: ~15ms (vs 10 sequential sends = 100ms+)
```

**Goroutine Pooling** (future):
```go
// Current: goroutine-per-request (unlimited)
// Optimized: Worker pool with bounded goroutines

pool := workerpool.New(1000) // Max 1000 workers
pool.Submit(func() {
    handleEvent(event)
})
```

### 2. Kafka Configuration

**Compression**:
```properties
compression.type=snappy  # 50-70% size reduction
# Alternatives: lz4 (faster), zstd (better compression)
```

**Batching**:
```properties
linger.ms=10           # Wait 10ms to batch messages
batch.size=16384       # Max 16KB batch size
# Reduces network calls by batching small messages
```

### 3. TimescaleDB Optimizations

**Hypertable Partitioning**:
```sql
-- Automatic time-based partitioning
-- Default: 7-day chunks
SELECT set_chunk_time_interval('events', INTERVAL '1 day');

-- Queries only scan relevant chunks
-- Query: WHERE time > NOW() - INTERVAL '1 hour'
-- Scans: 1 chunk (today) instead of all data
```

**Continuous Aggregates** (pre-computation):
```sql
-- Instead of expensive GROUP BY on millions of rows
SELECT service, COUNT(*) FROM events
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY service;

-- Query pre-computed aggregate (instant)
SELECT service, SUM(event_count) FROM events_5min
WHERE bucket > NOW() - INTERVAL '24 hours'
GROUP BY service;
```

**Compression** (future):
```sql
-- Compress chunks older than 7 days
SELECT add_compression_policy('events', INTERVAL '7 days');

-- 10x storage savings, decompress on read (still fast)
```

### 4. ML Detection Optimizations

**Model Caching**:
```python
# Load model once at startup (not per-inference)
model = load_model('/app/models/isolation_forest.pkl')

# Inference: <10ms (vs ~100ms if reloading each time)
```

**Feature Pre-computation** (future):
```python
# Instead of extracting features from raw events each time,
# compute rolling aggregates in real-time

# Example: Maintain running P95 latency with t-digest algorithm
from tdigest import TDigest
digest = TDigest()
for event in stream:
    digest.update(event['latency'])
p95 = digest.percentile(95)  # O(1) instead of O(n log n)
```

---

## Future Enhancements

### Phase 2: Production Readiness

- [ ] Add authentication & authorization (JWT, API keys)
- [ ] Enable TLS/SSL for all connections
- [ ] Implement rate limiting (Redis-based)
- [ ] Add dead-letter queues for failed processing
- [ ] Health checks for all services
- [ ] Structured logging with correlation IDs

### Phase 3: Scalability

- [ ] Kubernetes deployment (Helm charts)
- [ ] Horizontal pod autoscaling (HPA)
- [ ] Multi-region Kafka cluster
- [ ] TimescaleDB read replicas
- [ ] CDN for static assets (if adding UI)

### Phase 4: Advanced Features

- [ ] Web UI for anomaly investigation
- [ ] Advanced ML models (LSTM for sequences)
- [ ] Alerting integrations (PagerDuty, Slack, email)
- [ ] Anomaly correlation (cross-service detection)
- [ ] Custom detection rules (user-defined thresholds)
- [ ] Model retraining pipeline (continuous learning)

---

## Appendix: Key Metrics Summary

### Measured Performance

| Component | Metric | Value | Target |
|-----------|--------|-------|--------|
| Ingestion | P99 Latency | 21-27ms | <50ms ✅ |
| Ingestion | Throughput | 600-700 e/s | Tested |
| Kafka | Message Delivery | 100% | 100% ✅ |
| Kafka | Consumer Lag | 0 | 0 ✅ |
| Detection | Model Load Time | <100ms | <1s ✅ |
| Detection | Inference Time | <10ms | <50ms ✅ |
| Database | Write Throughput | 700+ e/s | Tested ✅ |
| Database | Events Stored | 25,590 | N/A |

### Resource Usage (Docker Compose)

| Service | CPU | Memory | Disk |
|---------|-----|--------|------|
| Ingestion | ~5% | ~50MB | Minimal |
| Kafka | ~10% | ~512MB | ~1GB |
| TimescaleDB | ~15% | ~256MB | ~500MB |
| Detection | ~5% | ~150MB | Minimal |
| Reporting | ~5% | ~150MB | Minimal |
| **Total** | **~40%** | **~1.1GB** | **~1.5GB** |

---

## References

- **Kafka Documentation**: https://kafka.apache.org/documentation/
- **TimescaleDB Docs**: https://docs.timescale.com/
- **Isolation Forest Paper**: https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf
- **Go Concurrency Patterns**: https://go.dev/blog/pipelines
- **Anthropic Claude API**: https://docs.anthropic.com/

---

**Last Updated**: October 24, 2025
