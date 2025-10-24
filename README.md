# Helios

**Event-Driven Observability Platform with Real-Time ML Anomaly Detection**

A distributed microservices system that processes application logs in real-time, detects anomalies using Machine Learning (Isolation Forest), and generates automated incident reports through LLM integration.

[![Go](https://img.shields.io/badge/Go-1.21-00ADD8?logo=go&logoColor=white)](https://golang.org/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org/)
[![Kafka](https://img.shields.io/badge/Kafka-3.6-231F20?logo=apache-kafka&logoColor=white)](https://kafka.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-20.10-2496ED?logo=docker&logoColor=white)](https://docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

Helios is an observability platform designed to monitor microservices infrastructure by ingesting event logs, detecting anomalies through unsupervised machine learning, and generating actionable incident reports. The system processes events in real-time with sub-30ms P99 latency and maintains 100% message delivery guarantees through Kafka streaming.

**Key Features:**
- High-performance event ingestion with Go-based goroutine concurrency
- Real-time anomaly detection using Isolation Forest with 12-feature engineering pipeline
- Event-driven architecture with Apache Kafka (10 partitions, snappy compression)
- Time-series optimized storage with TimescaleDB hypertables
- LLM-powered incident report generation via Anthropic Claude API
- Comprehensive monitoring with Prometheus and Grafana
- Multi-language microservices architecture (Go for throughput, Python for ML/AI)

---

## Architecture

### System Overview

```
                                    HELIOS PLATFORM
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  ┌────────────────┐                                                     │
│  │ Event Sources  │  Microservices, Applications, Infrastructure        │
│  └────────┬───────┘                                                     │
│           │                                                              │
│           │ HTTP POST /api/v1/events                                    │
│           ↓                                                              │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │           INGESTION SERVICE (Go 1.21)                   │            │
│  │  • Goroutine-based concurrency                          │            │
│  │  • Batch processing endpoints                           │            │
│  │  • Request validation & transformation                  │            │
│  │  • P99 Latency: 21-27ms                                 │            │
│  └────────────────────────┬────────────────────────────────┘            │
│                           │                                              │
│                           │ Produce                                      │
│                           ↓                                              │
│  ┌────────────────────────────────────────────────────────────┐         │
│  │              APACHE KAFKA MESSAGE BROKER                   │         │
│  │  Topic: events                                             │         │
│  │  • 10 Partitions (horizontal scaling)                      │         │
│  │  • Snappy compression                                      │         │
│  │  • Replication factor: 1                                   │         │
│  │  • Consumer groups: storage, detection, reporting          │         │
│  └──────────┬──────────────────────────┬──────────────────────┘         │
│             │                          │                                 │
│             │ Consume                  │ Consume                         │
│             ↓                          ↓                                 │
│  ┌──────────────────────┐   ┌─────────────────────────────────────┐    │
│  │  STORAGE WRITER (Go) │   │   DETECTION CONSUMER (Python 3.11)  │    │
│  │  • Batch inserts     │   │   • Isolation Forest ML Model        │    │
│  │  • Error handling    │   │   • 12-feature extraction pipeline   │    │
│  │  • Transaction mgmt  │   │   • 5-minute sliding windows         │    │
│  └──────────┬───────────┘   │   • Min 10 events per window         │    │
│             │                │   • Inference time: <10ms            │    │
│             ↓                └──────────────┬───────────────────────┘    │
│  ┌──────────────────────────────────┐      │                            │
│  │  TIMESCALEDB (PostgreSQL Ext)    │      │ Produce (if anomaly)       │
│  │  • Hypertables (time-partitioned)│      ↓                            │
│  │  • 5 optimized indexes            │   ┌─────────────────────────┐    │
│  │  • Continuous aggregates          │   │ Topic: anomaly-alerts   │    │
│  │  • Compression policies           │   └──────────┬──────────────┘    │
│  └──────────────────────────────────┘              │                    │
│                                                     │ Consume            │
│                                                     ↓                    │
│                                          ┌──────────────────────────────┐│
│                                          │ REPORTING CONSUMER (Python)  ││
│                                          │ • Anthropic Claude API       ││
│                                          │ • Context-aware prompts      ││
│                                          │ • Incident report generation ││
│                                          │ • Filesystem storage         ││
│                                          └──────────────────────────────┘│
│                                                                          │
│  ┌────────────────────────────────────────────────────────────┐         │
│  │              MONITORING STACK                              │         │
│  │  • Prometheus (metrics collection)                         │         │
│  │  • Grafana (visualization dashboards)                      │         │
│  │  • Kafka UI (topic monitoring)                             │         │
│  └────────────────────────────────────────────────────────────┘         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. EVENT INGESTION FLOW
   ─────────────────────
   Client Request → Ingestion Service (validation) → Kafka Producer
        ↓
   Response: 202 Accepted (15-27ms)


2. STORAGE FLOW
   ────────────
   Kafka Topic (events) → Storage Writer Consumer → TimescaleDB
        ↓                       ↓                        ↓
   Message consumed        Batch insert           Hypertable storage
   (partition 0-9)         (100 events/batch)     (time-indexed)


3. DETECTION FLOW
   ──────────────
   Kafka Topic (events) → Detection Consumer → Feature Extraction (12 features)
        ↓                        ↓                       ↓
   Window buffer          Process 5-min window    Isolation Forest inference
   (per service)          (min 10 events)         (<10ms prediction)
                                                        ↓
                                                   Anomaly score < -0.7?
                                                        ↓
                                                   Publish to anomaly-alerts


4. REPORTING FLOW
   ──────────────
   Kafka Topic (anomaly-alerts) → Reporting Consumer → Claude API
        ↓                               ↓                    ↓
   Anomaly metadata              Build context prompt   Generate report
                                                             ↓
                                                     Store to filesystem
```

### Component Details

#### Ingestion Service (Go)
- **Concurrency**: Goroutine-per-request model
- **Endpoints**: `/api/v1/events` (single), `/api/v1/events/batch` (bulk)
- **Processing**: JSON validation, timestamp normalization, metadata enrichment
- **Performance**: P99 latency 21-27ms, throughput 600-825 events/sec (tested)

#### Apache Kafka
- **Topics**: `events` (raw logs), `anomaly-alerts` (detected anomalies)
- **Partitioning**: Hash-based on service name (10 partitions per topic)
- **Compression**: Snappy codec (50-70% size reduction)
- **Consumer Groups**: Independent processing with offset management

#### TimescaleDB
- **Schema**: Hypertable on `time` column (automatic time-based partitioning)
- **Indexes**: time DESC, service+time, level+time, trace_id, metadata (GIN)
- **Retention**: Configurable compression and retention policies
- **Aggregates**: Pre-computed 5-minute rollups for analytics

#### ML Detection (Python)
- **Model**: Isolation Forest (scikit-learn 1.3.2)
- **Training**: Synthetic time-series data (7 days, 5-minute intervals)
- **Features**: 12 engineered features including error rates, latency percentiles, temporal patterns
- **Window**: 5-minute sliding windows per service
- **Threshold**: Anomaly score < -0.7

#### Reporting Service (Python)
- **LLM**: Anthropic Claude API (claude-3-5-sonnet)
- **Mode**: Production (API) or Mock (testing without costs)
- **Prompts**: Structured with anomaly metadata, service context, event samples
- **Output**: JSON reports with severity, root cause analysis, recommendations

---

## Technology Stack

| Layer | Technologies | Purpose |
|-------|-------------|---------|
| **Ingestion** | Go 1.21 | High-throughput, low-latency event processing |
| **Streaming** | Apache Kafka 3.6, Zookeeper 3.8 | Distributed message broker, event backbone |
| **Storage** | TimescaleDB 2.13 (PostgreSQL 15) | Time-series optimized relational database |
| **Detection** | Python 3.11, scikit-learn 1.3.2 | Machine learning pipeline, anomaly detection |
| **Reporting** | Python 3.11, Anthropic Claude API | LLM integration, incident report generation |
| **Monitoring** | Prometheus 2.47, Grafana 10.2 | Metrics collection, visualization dashboards |
| **Orchestration** | Docker 20.10, Docker Compose 2.0 | Containerization, multi-service management |

---

## Performance Metrics

### Verified Test Results (October 2025)

**Test Environment**: Docker Compose, Windows 11, 16GB RAM, Local development

| Component | Metric | Value | Target | Status |
|-----------|--------|-------|--------|--------|
| **Ingestion** | P99 Latency | 21-27ms | <50ms | Pass |
| **Ingestion** | P95 Latency | 20-22ms | <50ms | Pass |
| **Ingestion** | P50 Latency | 15-16ms | <30ms | Pass |
| **Ingestion** | Throughput | 600-825 e/s | Tested | Verified |
| **Kafka** | Message Delivery | 100% (0 lag) | 100% | Pass |
| **Kafka** | Total Processed | 70,900+ messages | - | Verified |
| **Database** | Events Stored | 25,590+ | - | Verified |
| **Database** | Write Success | 100% | 100% | Pass |
| **ML Model** | Load Time | <100ms | <1s | Pass |
| **ML Model** | Inference Time | <10ms | <50ms | Pass |

### ML Feature Engineering Pipeline

The detection system extracts 12 features from event windows:

1. **event_count** - Total events in window
2. **error_rate** - Percentage of ERROR/CRITICAL level events
3. **p50_latency_ms** - Median latency
4. **p95_latency_ms** - 95th percentile latency
5. **p99_latency_ms** - 99th percentile latency
6. **latency_std** - Latency standard deviation
7. **hour_of_day** - Temporal feature (0-23)
8. **p95_p50_ratio** - Latency distribution skew indicator
9. **p99_p95_ratio** - Extreme tail behavior indicator
10. **error_count** - Absolute error count (event_count × error_rate)
11. **log_event_count** - Log-scaled event volume (handles spikes)
12. **log_error_rate** - Log-scaled error rate (handles rate changes)

---

## Quick Start

### Prerequisites

- Docker Desktop 20.10+ with Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- Python 3.11+ (for load testing)
- 10GB free disk space

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/helios.git
cd helios

# Start all services
docker-compose up -d

# Verify services (should show 14 containers)
docker ps
```

### Send Test Event

```bash
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-24T10:00:00Z",
    "service": "api-gateway",
    "level": "INFO",
    "message": "Request processed successfully",
    "metadata": {
      "latency_ms": 45,
      "endpoint": "/api/users",
      "status_code": 200
    }
  }'
```

**Expected Response**: `HTTP 202 Accepted`

### Run Load Test

```bash
# Install dependencies (first time only)
pip install aiohttp

# Execute 30-second load test at 100 RPS
python scripts/load_test.py --rps 100 --duration 30 --batch-size 10
```

**Expected Output**:
```
[RESULTS] LOAD TEST RESULTS
Duration: 30.01s
Total Events: 18,540
Events/Sec: 618
P99 Latency: 21.46ms [PASS]
```

### Verify System

```bash
# Check database storage
docker exec helios-timescaledb psql -U postgres -d helios \
  -c "SELECT COUNT(*) as total_events FROM events;"

# Check Kafka consumer lag
docker exec helios-kafka kafka-consumer-groups \
  --bootstrap-server localhost:29092 \
  --group anomaly-detectors \
  --describe
```

**Expected**: Total events > 0, Consumer LAG = 0

---

## Project Structure

```
helios/
├── services/
│   ├── ingestion/              # Go ingestion service
│   │   ├── main.go
│   │   ├── handlers/           # HTTP request handlers
│   │   ├── kafka/              # Kafka producer wrapper
│   │   └── Dockerfile
│   │
│   ├── detection/              # Python ML detection service
│   │   ├── app/
│   │   │   ├── consumers/      # Kafka consumer + metrics
│   │   │   ├── ml/             # Feature extraction, model inference
│   │   │   └── api/            # FastAPI endpoints
│   │   ├── models/             # Trained ML models
│   │   └── Dockerfile
│   │
│   ├── reporting/              # Python LLM reporting service
│   │   ├── app/
│   │   │   ├── consumers/      # Anomaly alert consumer
│   │   │   ├── generators/     # Claude API integration
│   │   │   └── api/            # FastAPI endpoints
│   │   └── Dockerfile
│   │
│   └── storage/                # Go database writer
│       ├── consumer.go
│       ├── database/
│       └── Dockerfile
│
├── scripts/
│   ├── load_test.py                   # Async load testing tool
│   ├── train_model.py                 # ML model training script
│   └── simulate_indian_scenarios.py   # Scenario-based event generation
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml             # Scrape configurations
│   └── grafana/
│       └── dashboards/                # Pre-built dashboards
│
├── models/
│   ├── isolation_forest.pkl           # Trained model (248KB)
│   ├── model_config.json              # Model metadata
│   └── training_metrics.json          # Training statistics
│
├── docs/
│   ├── QUICKSTART.md                  # Setup guide
│   ├── TESTING.md                     # Testing procedures
│   ├── ARCHITECTURE.md                # System design details
│   ├── METRICS.md                     # Performance benchmarks
│   ├── RESUME.md                      # Resume bullet points
│   └── GITHUB_SETUP.md                # Video recording guide
│
├── docker-compose.yml                 # 14-service orchestration
└── README.md                          # This file
```

---

## Monitoring

### Access Dashboards

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| Kafka UI | http://localhost:9000 | None | Topic monitoring, message inspection |
| Prometheus | http://localhost:9090 | None | Metrics querying, target health |
| Grafana | http://localhost:3000 | admin/admin | Visualization dashboards |

### Key Prometheus Metrics

- `helios_events_processed_total` - Events consumed by detection service
- `helios_anomalies_detected_total` - Anomaly detection count
- `helios_window_size` - Current window size per service
- `http_request_duration_seconds` - Ingestion latency histogram
- `kafka_publish_duration_seconds` - Kafka producer latency

---

## Testing

### Load Testing

```bash
# Basic test (30 seconds at 100 RPS)
python scripts/load_test.py --rps 100 --duration 30

# Extended test (60 seconds at 150 RPS)
python scripts/load_test.py --rps 150 --duration 60 --clients 10

# Single-event endpoint (no batching)
python scripts/load_test.py --rps 50 --no-batch
```

### Integration Testing

```bash
# Verify Kafka topics
docker exec helios-kafka kafka-topics \
  --bootstrap-server localhost:29092 \
  --list

# Query recent events
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT service, COUNT(*) as count
  FROM events
  WHERE time > NOW() - INTERVAL '1 hour'
  GROUP BY service;"

# Check detection consumer logs
docker logs helios-detection-consumer --tail 20

# Verify consumer group status
docker exec helios-kafka kafka-consumer-groups \
  --bootstrap-server localhost:29092 \
  --group anomaly-detectors \
  --describe
```

---

## Development Notes

### Design Decisions

**Go for Ingestion**: Chosen for native concurrency (goroutines), low memory overhead, and compiled performance. Alternative considered: Node.js (rejected due to higher memory usage).

**Python for ML/AI**: Required for scikit-learn ecosystem and LLM SDK support. Go lacks mature ML libraries.

**Kafka over Alternatives**: Selected for message durability, replay capability, and horizontal scaling via partitions. Alternatives considered: RabbitMQ (lacks native partitioning), Redis Streams (limited persistence).

**TimescaleDB over InfluxDB**: Provides full PostgreSQL compatibility (JSONB, transactions, complex queries) while adding time-series optimizations. InfluxDB has limited query language.

### Known Limitations

1. **Batch Endpoint Reliability**: 30-45% failure rate due to transient 404 errors (under investigation)
2. **Single-Instance Deployment**: Currently not horizontally scaled (designed for but not implemented)
3. **ML Model Evaluation**: Precision/recall not measured (requires labeled test dataset)
4. **Throughput**: 600-825 e/s tested (production systems handle 100K-1M e/s)

### Future Enhancements

- Kubernetes deployment with Helm charts for horizontal scaling
- Labeled anomaly dataset for model evaluation (precision, recall, F1 score)
- Alert integrations (PagerDuty, Slack, email notifications)
- Web UI for anomaly investigation and report viewing
- Advanced ML models (LSTM for temporal sequence detection)
- Multi-region Kafka cluster deployment
- Automated model retraining pipeline

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Apache Kafka for distributed streaming platform
- TimescaleDB for time-series PostgreSQL extension
- scikit-learn for machine learning library
- Anthropic for Claude LLM API
- Prometheus and Grafana for monitoring infrastructure

---

**Built with Go, Kafka, Python, and TimescaleDB**
