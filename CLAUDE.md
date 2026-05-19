# Helios Project Context for Claude Code

**Last Updated**: 2026-05-18
**Project**: Event-Driven Observability Platform with Real-Time ML Anomaly Detection

---

## Current Direction (2026-05-18)

This repository is being repositioned as a flagship **MLOps portfolio project** for ML Engineer / MLOps role applications. Plan file: `C:\Users\Nilansh\.claude\plans\okay-i-want-you-sleepy-moore.md`.

**Strategic decisions in effect:**
- Single ML algorithm in production: **Isolation Forest** (12 features). Ensemble / Prophet / 25-feature variants were deleted, not finished.
- **SHAP explainability** wired into the live detection pipeline (Phase 3).
- Evaluation on **two public labeled datasets**: NAB and SMD (Phase 2). Synthetic-only eval is the existing baseline, replaced.
- **Gemini 1.5 Flash** is the default LLM (Phase 3). `claude_generator.py` is kept as a configurable alternative — selectable via `REPORT_GENERATOR_MODE=gemini|claude|mock`.
- **Grafana is the UI** — the React frontend was deleted. Demo surface is Grafana dashboards.
- Public deployment: **Oracle Cloud Always Free** ARM VM, $0 budget (Phase 6).

When making changes, lean toward MLOps signals (eval rigor, model card, MLflow tracking, drift monitoring) over GenAI/frontend depth.

---

## Project Overview

Helios is a distributed microservices system that processes application logs in real-time, detects anomalies using an Isolation Forest ML model, and generates automated incident reports through an LLM (Gemini 1.5 Flash by default; Claude API as configurable alternative).

**Key Capabilities:**
- High-performance event ingestion (600-825 events/sec, P99 latency 21-27ms)
- Real-time anomaly detection with Isolation Forest ML model
- Event-driven architecture with Apache Kafka
- Time-series optimized storage with TimescaleDB
- LLM-powered incident report generation via Claude API
- Comprehensive monitoring with Prometheus and Grafana

---

## Architecture Summary

```
Event Sources → Ingestion (Go) → Kafka → [Storage Writer (Go) → TimescaleDB]
                                       → [Detection Consumer (Python) → ML Model → Anomaly Alerts]
                                       → [Reporting Consumer (Python) → Claude API → Reports]
```

**13 Docker Containers:**
1. **zookeeper** - Kafka coordination
2. **kafka** - Message broker (10 partitions, snappy compression)
3. **kafka-ui** - Topic monitoring (port 9000)
4. **timescaledb** - Time-series database (port 5433)
5. **prometheus** - Metrics collection (port 9090)
6. **grafana** - Visualization dashboards (port 3100) — primary UI
7. **ingestion** - Go HTTP API (port 8080, metrics 8081)
8. **storage-writer** - Kafka → DB consumer (Go)
9. **detection** - FastAPI service (port 8000)
10. **detection-consumer** - ML anomaly detection (Python)
11. **reporting** - FastAPI service (port 8002)
12. **reporting-consumer** - Report generation (Python)
13. **alertmanager** - Prometheus alerts (port 9094)

---

## Directory Structure

```
helios/
├── services/
│   ├── ingestion/              # Go ingestion service
│   │   ├── main.go             # HTTP server entry point
│   │   ├── consumer.go         # Kafka consumer for storage
│   │   ├── handlers/           # HTTP request handlers
│   │   │   └── event_handler.go
│   │   ├── config/             # Configuration management
│   │   │   └── config.go
│   │   ├── models/             # Event models
│   │   │   └── event.go
│   │   ├── kafka/              # Kafka producer wrapper
│   │   └── Dockerfile
│   │
│   ├── detection/              # Python ML detection service
│   │   ├── app/
│   │   │   ├── main.py         # FastAPI server
│   │   │   ├── consumers/      # Kafka consumer + metrics
│   │   │   │   ├── detection_consumer.py  # Main consumer loop
│   │   │   │   └── metrics.py
│   │   │   ├── ml/             # Feature extraction, model inference
│   │   │   │   ├── anomaly_detector.py
│   │   │   │   ├── feature_engineering.py  # 12-feature pipeline
│   │   │   │   └── training.py
│   │   │   ├── api/            # FastAPI endpoints
│   │   │   │   └── routes.py
│   │   │   └── core/           # Config, logging, database
│   │   │       ├── config.py
│   │   │       ├── logging.py
│   │   │       └── database.py
│   │   ├── models/             # Trained ML models (.pkl)
│   │   ├── tests/              # Unit tests
│   │   └── Dockerfile
│   │
│   └── reporting/              # Python LLM reporting service
│       ├── app/
│       │   ├── main.py         # FastAPI server
│       │   ├── consumers/      # Anomaly alert consumer
│       │   │   ├── report_consumer.py  # Main consumer loop
│       │   │   └── metrics.py
│       │   ├── generators/     # Report generation
│       │   │   ├── base.py
│       │   │   ├── claude_generator.py  # Anthropic Claude integration
│       │   │   ├── mock_generator.py    # Zero-cost testing
│       │   │   └── prompts.py           # Prompt engineering
│       │   ├── storage/        # Report storage
│       │   │   ├── filesystem.py
│       │   │   └── database.py
│       │   ├── utils/
│       │   │   └── pdf_generator.py     # Markdown → PDF
│       │   ├── api/            # FastAPI endpoints
│       │   │   └── routes.py
│       │   └── core/           # Config, logging, database
│       ├── tests/
│       └── Dockerfile
│
├── scripts/
│   ├── load_test.py                   # Async load testing (aiohttp)
│   ├── train_model.py                 # ML model training
│   ├── simulate_indian_scenarios.py   # Scenario-based event generation
│   ├── generate_demo_data.py          # Demo data generator
│   └── live_anomaly_generator.py      # Real-time anomaly simulation
│
├── config/
│   ├── prometheus/
│   │   ├── prometheus.yml             # Scrape configs
│   │   └── alertmanager.yml
│   ├── grafana/
│   │   ├── datasources/
│   │   │   └── datasources.yml
│   │   └── dashboards/
│   │       └── helios-master-dashboard.json
│   └── timescaledb/
│       └── init.sql                   # Database schema
│
├── models/
│   ├── isolation_forest.pkl           # Trained model (248KB)
│   ├── model_config.json              # Model metadata
│   └── training_metrics.json          # Training statistics
│
├── docs/
│   ├── 00-START-HERE.md               # Main entry point
│   ├── existing/                      # Current system docs
│   │   ├── ARCHITECTURE.md
│   │   ├── VERIFIED_METRICS.md
│   │   └── RUN_AND_TEST_GUIDE.md
│   ├── learning/                      # Enhancement tutorials
│   ├── reference/
│   │   └── CLAUDE.md                  # Claude API integration guide
│   └── README.md
│
├── docker-compose.yml                 # 13-service orchestration
└── README.md                          # Project overview
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Ingestion** | Go 1.21 | High-throughput, low-latency event processing |
| **Streaming** | Apache Kafka 3.6, Zookeeper 3.8 | Distributed message broker |
| **Storage** | TimescaleDB 2.13 (PostgreSQL 15) | Time-series optimized database |
| **Detection** | Python 3.11, scikit-learn 1.3.2 | ML pipeline, anomaly detection |
| **Reporting** | Python 3.11, Anthropic Claude API | LLM integration, report generation |
| **Monitoring** | Prometheus 2.47, Grafana 10.2 | Metrics collection, visualization |
| **Web Framework** | FastAPI (Python), Chi (Go) | REST APIs |
| **Containerization** | Docker 20.10, Docker Compose 2.0 | Multi-service orchestration |

---

## Key Files & Locations

### Configuration
- **Database Schema**: `config/timescaledb/init.sql` - Hypertables, indexes, continuous aggregates
- **Docker Compose**: `docker-compose.yml` - Service orchestration, environment variables
- **Prometheus Config**: `config/prometheus/prometheus.yml` - Scrape targets
- **Grafana Datasources**: `config/grafana/datasources/datasources.yml` - Prometheus + TimescaleDB

### Go Services (Ingestion)
- **Main Entry**: `services/ingestion/main.go` - HTTP server, Kafka producer initialization
- **Event Handler**: `services/ingestion/handlers/event_handler.go` - Single/batch event ingestion
- **Storage Consumer**: `services/ingestion/consumer.go` - Kafka → TimescaleDB writer
- **Config**: `services/ingestion/config/config.go` - Environment variable loading
- **Models**: `services/ingestion/models/event.go` - Event struct, validation

### Python Services (Detection)
- **API Server**: `services/detection/app/main.py` - FastAPI application
- **Detection Consumer**: `services/detection/app/consumers/detection_consumer.py` - Main consumer loop
- **Feature Engineering**: `services/detection/app/ml/feature_engineering.py` - 12-feature extraction
- **Anomaly Detector**: `services/detection/app/ml/anomaly_detector.py` - Isolation Forest wrapper
- **Config**: `services/detection/app/core/config.py` - Settings management
- **Database**: `services/detection/app/core/database.py` - PostgreSQL connection pool

### Python Services (Reporting)
- **API Server**: `services/reporting/app/main.py` - FastAPI application
- **Report Consumer**: `services/reporting/app/consumers/report_consumer.py` - Anomaly alert consumer
- **Claude Generator**: `services/reporting/app/generators/claude_generator.py` - Anthropic API integration
- **Prompts**: `services/reporting/app/generators/prompts.py` - Prompt engineering templates
- **PDF Generator**: `services/reporting/app/utils/pdf_generator.py` - Markdown to PDF conversion
- **Config**: `services/reporting/app/core/config.py` - Settings (API keys, mode)

### Testing & Scripts
- **Load Testing**: `scripts/load_test.py` - Async HTTP load testing with aiohttp
- **Model Training**: `scripts/train_model.py` - Isolation Forest training script
- **Demo Data**: `scripts/generate_demo_data.py` - SQL data population
- **Live Anomalies**: `scripts/live_anomaly_generator.py` - Real-time anomaly simulation

---

## Database Schema (TimescaleDB)

### Tables

#### 1. `events` (Hypertable)
```sql
CREATE TABLE events (
    time        TIMESTAMPTZ NOT NULL,
    service     TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    message     TEXT NOT NULL,
    metadata    JSONB,
    trace_id    TEXT,
    span_id     TEXT,
    host        TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);
```
- **Chunk Interval**: 1 day
- **Indexes**: service+time, level+time, trace_id, metadata (GIN)
- **Compression**: Enabled (7 days old)
- **Retention**: 30 days

#### 2. `anomalies` (Hypertable)
```sql
CREATE TABLE anomalies (
    time         TIMESTAMPTZ NOT NULL,
    anomaly_id   TEXT NOT NULL,
    service      TEXT NOT NULL,
    score        DOUBLE PRECISION NOT NULL,
    threshold    DOUBLE PRECISION NOT NULL DEFAULT -0.7,
    severity     TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    features     JSONB NOT NULL,
    confidence   DOUBLE PRECISION,
    is_resolved  BOOLEAN DEFAULT FALSE,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```
- **Chunk Interval**: 7 days
- **Indexes**: service+time, severity+time, unresolved
- **Compression**: Enabled (14 days old)
- **Retention**: 90 days

#### 3. `incident_reports` (Regular Table)
```sql
CREATE TABLE incident_reports (
    id                  SERIAL PRIMARY KEY,
    report_id           TEXT UNIQUE NOT NULL,
    anomaly_id          TEXT NOT NULL,
    service             TEXT NOT NULL,
    severity            TEXT NOT NULL,
    content             TEXT NOT NULL,
    filepath            TEXT,
    pdf_path            TEXT,
    tokens_used         INTEGER DEFAULT 0,
    cost_usd            DOUBLE PRECISION DEFAULT 0.0,
    generation_time_ms  DOUBLE PRECISION DEFAULT 0.0,
    model               TEXT,
    generated_at        TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### Continuous Aggregates
- **event_metrics_1m**: 1-minute rollups (event count, latencies, error rates)
- **event_metrics_5m**: 5-minute rollups (for ML features)
- **event_metrics_1h**: 1-hour rollups (for dashboards)

---

## ML Model Details

### Isolation Forest
- **Model File**: `models/isolation_forest.pkl` (248KB)
- **Algorithm**: Scikit-learn Isolation Forest
- **Training Data**: Synthetic time-series (7 days, 5-minute intervals)
- **Contamination**: 5% (expected anomaly rate)
- **Threshold**: -0.16 (current), -0.4 to -0.7 (configurable)

### Feature Engineering (12 Features)
**File**: `services/detection/app/ml/feature_engineering.py`

1. `event_count` - Total events in window
2. `error_rate` - Percentage of ERROR/CRITICAL events
3. `p50_latency_ms` - Median latency
4. `p95_latency_ms` - 95th percentile latency
5. `p99_latency_ms` - 99th percentile latency
6. `latency_std` - Latency standard deviation
7. `hour_of_day` - Temporal feature (0-23)
8. `p95_p50_ratio` - Latency distribution skew
9. `p99_p95_ratio` - Extreme tail behavior
10. `error_count` - Absolute error count
11. `log_event_count` - Log-scaled event volume
12. `log_error_rate` - Log-scaled error rate

### Detection Flow
```
Event → Add to Service Window → Check Timer (every N minutes)
  → Extract Features → ML Inference → Anomaly Score
  → If score < threshold → Publish to anomaly-alerts topic
  → Store in DB + Update Metrics
```

---

## Kafka Topics

### 1. `events` (Main Event Stream)
- **Partitions**: 10
- **Replication**: 1
- **Compression**: Snappy
- **Retention**: 168 hours (7 days)
- **Consumer Groups**:
  - `storage-writers` - Write to TimescaleDB
  - `anomaly-detectors` - ML detection

### 2. `anomaly-alerts` (Detected Anomalies)
- **Partitions**: 10
- **Replication**: 1
- **Consumer Groups**:
  - `reporting-service` - Generate incident reports

---

## API Endpoints

### Ingestion Service (Port 8080)
- `GET /health` - Health check
- `GET /ready` - Readiness probe
- `POST /api/v1/events` - Ingest single event
- `POST /api/v1/events/batch` - Ingest event batch

**Metrics**: Port 8081 (`/metrics`)

### Detection Service (Port 8000)
- `GET /health` - Health check
- `GET /api/v1/predict` - On-demand anomaly detection
- `GET /api/v1/model/info` - Model metadata

**Metrics**: Port 8001 (`/metrics`)

### Reporting Service (Port 8002)
- `GET /health` - Health check
- `POST /api/v1/reports/generate` - Generate report
- `GET /api/v1/reports/{report_id}` - Fetch report
- `GET /api/v1/reports` - List reports

**Metrics**: Port 8003 (`/metrics`)

### Kafka UI (Port 9000)
- `http://localhost:9000` - Web interface for topic monitoring

### Prometheus (Port 9090)
- `http://localhost:9090` - Metrics query interface

### Grafana (Port 3100)
- `http://localhost:3100` - Visualization dashboards (admin/admin)

---

## Environment Variables

### Ingestion Service
```bash
KAFKA_BROKERS=kafka:29092
KAFKA_TOPIC=events
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=helios
DB_USER=postgres
DB_PASSWORD=postgres
LOG_LEVEL=info
METRICS_PORT=8081
```

### Detection Service
```bash
KAFKA_BROKERS=kafka:29092
KAFKA_EVENTS_TOPIC=events
KAFKA_ALERTS_TOPIC=anomaly-alerts
KAFKA_CONSUMER_GROUP=anomaly-detectors
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=helios
DB_USER=postgres
DB_PASSWORD=postgres
MODEL_PATH=/app/models/isolation_forest.pkl
ANOMALY_THRESHOLD=-0.16
WINDOW_SIZE_MINUTES=1
MIN_EVENTS_PER_WINDOW=3
API_PORT=8000
METRICS_PORT=8001
LOG_LEVEL=INFO
```

### Reporting Service
```bash
# Report Generator (default: gemini)
REPORT_GENERATOR_MODE=gemini  # gemini | claude | mock

# Gemini (default, free tier — get from https://aistudio.google.com)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
GEMINI_MAX_TOKENS=1500
GEMINI_TEMPERATURE=0.3

# Claude (alternative; only needed if REPORT_GENERATOR_MODE=claude)
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CLAUDE_MAX_TOKENS=1500
CLAUDE_TEMPERATURE=0.3

# Kafka
KAFKA_BROKERS=kafka:29092
KAFKA_ALERTS_TOPIC=anomaly-alerts
KAFKA_CONSUMER_GROUP=reporting-service

# Database
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=helios
DB_USER=postgres
DB_PASSWORD=postgres

# API
API_PORT=8002
METRICS_PORT=8003
LOG_LEVEL=INFO

# Storage
REPORTS_STORAGE_PATH=/app/reports
REPORTS_RETENTION_DAYS=30
```

---

## Prometheus Metrics

### Ingestion Service
- `helios_events_ingested_total{service, level, status}` - Total events ingested
- `helios_ingestion_latency_seconds{endpoint}` - Ingestion latency histogram
- `helios_kafka_producer_errors_total` - Kafka producer errors

### Detection Service
- `helios_events_processed_total{service, status}` - Events processed
- `helios_anomalies_detected_total{service, severity}` - Anomalies detected
- `helios_detection_latency_seconds` - Detection processing time
- `helios_window_size{service}` - Current window size per service

### Reporting Service
- `helios_reports_generated_total{service, severity, generator}` - Reports generated
- `helios_report_generation_latency_seconds` - Report generation time
- `helios_claude_tokens_used_total` - Total tokens consumed
- `helios_claude_cost_usd_total` - Total API cost in USD

---

## Common Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# View logs
docker logs helios-ingestion -f
docker logs helios-detection-consumer -f
docker logs helios-reporting-consumer -f

# Restart service
docker-compose restart ingestion

# Stop all
docker-compose down

# Rebuild specific service
docker-compose up -d --build ingestion
```

### Database Operations
```bash
# Connect to TimescaleDB
docker exec -it helios-timescaledb psql -U postgres -d helios

# Query events
SELECT service, level, COUNT(*)
FROM events
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY service, level;

# Query anomalies
SELECT * FROM anomalies
WHERE time > NOW() - INTERVAL '24 hours'
ORDER BY time DESC
LIMIT 10;

# Check continuous aggregates
SELECT * FROM event_metrics_5m
WHERE bucket > NOW() - INTERVAL '1 hour';
```

### Kafka Operations
```bash
# List topics
docker exec helios-kafka kafka-topics --bootstrap-server localhost:29092 --list

# Consumer group lag
docker exec helios-kafka kafka-consumer-groups \
  --bootstrap-server localhost:29092 \
  --group anomaly-detectors \
  --describe

# Consume events (tail)
docker exec helios-kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic events \
  --from-beginning \
  --max-messages 10
```

### Testing
```bash
# Send test event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-24T10:00:00Z",
    "service": "api-gateway",
    "level": "INFO",
    "message": "Request processed",
    "metadata": {"latency_ms": 45}
  }'

# Run load test
cd scripts
python load_test.py --rps 100 --duration 30 --batch-size 10

# Train model
cd services/detection
python -m app.ml.training
```

---

## Known Issues & Limitations

### Current Issues
1. **Batch Endpoint Reliability**: 30-45% failure rate on `/api/v1/events/batch` due to transient 404 errors
2. **Single-Instance Deployment**: Services not horizontally scaled yet
3. **ML Model Evaluation**: Phase 2 adds NAB + SMD public-dataset evaluation (replacing synthetic-only)
4. **SHAP Explainability**: Wired in via Phase 3 (was previously dead code)
5. **Feature Drift Detection**: Added in Phase 4 (PSI-based)

### Performance Limits
- **Tested Throughput**: 600-825 events/sec (production systems: 100K-1M e/s)
- **Latency**: P99 21-27ms (meets <50ms target)
- **Detection Latency**: <10ms ML inference time

---

## Development Workflow

### Adding New Features
1. **Update Database Schema**: Modify `config/timescaledb/init.sql`
2. **Update Models**: Add/modify structs in `services/*/models/`
3. **Update API Handlers**: Implement in `services/*/handlers/` or `services/*/api/routes.py`
4. **Add Metrics**: Define in Prometheus metrics section
5. **Update Docker Compose**: Add environment variables if needed
6. **Test**: Use load testing scripts, verify in Grafana

### Debugging Tips
- **Check Logs**: `docker logs <container> -f --tail 100`
- **Prometheus Metrics**: Query at `http://localhost:9090`
- **Kafka UI**: Monitor topics at `http://localhost:9000`
- **Database**: Connect with `docker exec -it helios-timescaledb psql -U postgres -d helios`
- **Health Checks**: `curl http://localhost:8080/health`

---

## Security Considerations

### API Keys
- **Never commit**: `.env` files, API keys to git
- **Use environment variables**: `ANTHROPIC_API_KEY`, `DB_PASSWORD`
- **Check `.gitignore`**: Ensure `.env`, `*.env` excluded

### Database
- **Default Credentials**: `postgres/postgres` (change in production)
- **Port Exposure**: TimescaleDB on 5433 (bind to localhost in production)
- **SQL Injection**: Parameterized queries used throughout

### Kafka
- **No Authentication**: Default setup (add SASL in production)
- **No Encryption**: Plaintext (add SSL/TLS in production)

---

## Cost Management

### LLM API (Reporting)
- **Default**: Gemini 1.5 Flash — free tier (1500 req/day, 1M TPM), $0 for the demo
- **Alternative**: Claude 3.5 Sonnet — $0.02-0.05 per report (Input: $3/1M, Output: $15/1M)
- **Mock Mode**: `REPORT_GENERATOR_MODE=mock` for zero-cost local development
- **Switching**: Set `REPORT_GENERATOR_MODE=gemini|claude|mock` env var
- **Token + cost tracking**: Prometheus metrics emitted for both providers

### Infrastructure (Docker)
- **Local Development**: Free
- **Cloud Deployment**: ~$100-200/month (AWS/GCP)
  - t3.medium instances (3x): ~$75/month
  - TimescaleDB managed: ~$50/month
  - Kafka managed: ~$100/month

---

## Future Enhancements (out of current scope)

- **Alert Integrations**: PagerDuty, Slack, email notifications
- **Advanced ML**: LSTM/autoencoder for temporal sequence detection
- **Kubernetes**: Helm charts for horizontal scaling
- **Multi-region**: Kafka cluster deployment
- **Automated retraining pipeline** with labeled production incidents

---

## Git Status (Current)

**Branch**: master
**Working Directory Changes**:
- Modified: `docker-compose.yml`, database configs, reporting service
- Deleted: Old Terraform configs, LocalStack setup, deprecated dashboards
- Untracked: New docs, frontend scaffold, demo scripts

**Recent Commits**:
- `176e53d` - Professional README with architecture diagrams
- `f6c187f` - Critical bug fixes, ML components
- `7389c57` - Documentation consolidation

---

## Quick Reference

### Start System
```bash
docker-compose up -d
# Wait 30 seconds for initialization
docker ps  # Should show 14 containers
```

### Verify System
```bash
# Check Kafka
docker exec helios-kafka kafka-topics --bootstrap-server localhost:29092 --list

# Check Database
docker exec helios-timescaledb psql -U postgres -d helios -c "SELECT COUNT(*) FROM events;"

# Check Consumer Lag
docker exec helios-kafka kafka-consumer-groups --bootstrap-server localhost:29092 --group anomaly-detectors --describe
```

### Send Test Data
```bash
python scripts/load_test.py --rps 50 --duration 10
```

### Monitor
- Kafka UI: http://localhost:9000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3100 (admin/admin)

---

## When Working on Specific Components

### Go Services (Ingestion/Storage)
- **Main Files**: `services/ingestion/main.go`, `consumer.go`, `handlers/event_handler.go`
- **Build**: `docker-compose up -d --build ingestion`
- **Test**: Send curl requests to port 8080
- **Metrics**: Check port 8081/metrics

### Python ML (Detection)
- **Main Files**: `app/consumers/detection_consumer.py`, `app/ml/feature_engineering.py`
- **Model**: `models/isolation_forest.pkl`
- **Train**: `python -m app.ml.training`
- **Test**: Monitor logs for "anomaly_detected" events
- **Metrics**: Check port 8001/metrics

### Python Reporting (LLM Integration)
- **Main Files**: `app/consumers/report_consumer.py`, `app/generators/gemini_generator.py` (default), `app/generators/claude_generator.py` (alternative)
- **API Keys**: `GEMINI_API_KEY` (default, free tier) or `ANTHROPIC_API_KEY` (if `REPORT_GENERATOR_MODE=claude`)
- **Mock Mode**: `REPORT_GENERATOR_MODE=mock` for testing — first-class citizen, not a fallback
- **Structured Output**: Both generators target the same Pydantic `IncidentReport` schema (see `app/generators/structured_output.py`)
- **Test**: Trigger anomaly, check `/app/reports` volume
- **Metrics**: Check port 8003/metrics

### Database Schema
- **Schema File**: `config/timescaledb/init.sql`
- **Apply Changes**: `docker-compose down && docker volume rm helios-timescaledb-data && docker-compose up -d`
- **Query**: `docker exec -it helios-timescaledb psql -U postgres -d helios`

### UI (Grafana, not a custom frontend)
- **Primary UI**: Grafana at `http://localhost:3100`
- **Dashboards**: `config/grafana/dashboards/helios-master-dashboard.json` (operational view) and `model-health.json` (model monitoring — added in Phase 4)
- A React frontend previously scaffolded under `frontend/` was deleted in Phase 1 (it referenced hook files that didn't exist; not worth completing for an MLOps-focused project)

---

## Important Context for Claude Code

### When Making Changes
1. **Always check dependencies**: Services depend on Kafka and TimescaleDB being ready
2. **Update metrics**: Add Prometheus metrics for new features
3. **Update docker-compose.yml**: Add environment variables for new configs
4. **Test thoroughly**: Use load testing scripts before committing
5. **Update documentation**: Keep this file and README.md in sync

### Common Patterns
- **Error Handling**: All services use structured logging (zerolog for Go, Python logging)
- **Health Checks**: Every service has `/health` endpoint
- **Metrics**: Prometheus metrics on separate port (8081, 8001, 8003)
- **Configuration**: Environment variables loaded from docker-compose.yml
- **Kafka Messages**: JSON serialized with timestamp, service as partition key

### Code Style
- **Go**: Standard Go formatting (gofmt), use zerolog for logging
- **Python**: Black formatting, type hints, docstrings
- **SQL**: Uppercase keywords, snake_case identifiers
- **Docker**: Multi-stage builds for smaller images

---

This document provides comprehensive context for Claude Code to assist with development, debugging, and enhancement of the Helios observability platform.
