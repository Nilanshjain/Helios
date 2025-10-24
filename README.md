# Helios ☀️

> **Event-Driven Observability Platform with Real-Time ML Anomaly Detection**

A distributed system that processes application logs, detects anomalies using Machine Learning, and generates automated incident reports with LLM integration.

[![Go](https://img.shields.io/badge/Go-1.21-00ADD8?logo=go)](https://golang.org/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org/)
[![Kafka](https://img.shields.io/badge/Kafka-3.6-231F20?logo=apache-kafka)](https://kafka.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-20.10-2496ED?logo=docker)](https://docker.com/)

---

## 🎯 What is Helios?

Helios monitors microservices in real-time, detects anomalies with ML (Isolation Forest), and generates AI-powered incident reports—similar to Datadog but self-hosted.

**Key Features**:
- 🚀 **Sub-30ms P99 latency** for event ingestion
- 🤖 **ML detection** with 12-feature pipeline
- ⚡ **Kafka streaming** (100% delivery, 0 lag)
- 📊 **TimescaleDB** with hypertables
- 🧠 **Claude LLM** for incident reports
- 🌐 **14 Docker services** (Go + Python)

---

## 📋 Quick Start

```bash
# Clone and start
git clone https://github.com/yourusername/helios.git
cd helios
docker-compose up -d

# Send test event
curl -X POST http://localhost:8080/api/v1/events   -H "Content-Type: application/json"   -d '{"timestamp":"2025-10-24T10:00:00Z","service":"api","level":"INFO","message":"Test"}'

# Run load test
python scripts/load_test.py --rps 100 --duration 30
```

**📖 Full Guide**: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

---

## 🏗️ Architecture

```
Events → Go Ingestion → Kafka → Storage Writer → TimescaleDB
                          ↓
                    Detection Consumer (ML) → Anomaly Alerts
                          ↓
                    Reporting Consumer (LLM) → Incident Reports

Monitoring: Prometheus + Grafana
```

**Components**:
- **Ingestion** (Go): Goroutine concurrency, P99 21-27ms
- **Kafka**: 10 partitions, snappy compression, 100% delivery
- **Detection** (Python): Isolation Forest, 12 features, 5-min windows
- **Database**: TimescaleDB hypertables + 5 indexes
- **Reporting** (Python): Claude API integration

**📖 Detailed Design**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 💻 Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Languages** | Go 1.21, Python 3.11 |
| **Streaming** | Apache Kafka 3.6 |
| **Database** | TimescaleDB 2.13 |
| **ML/AI** | Scikit-learn, Claude API |
| **Monitoring** | Prometheus, Grafana |
| **Orchestration** | Docker Compose (14 services) |

---

## 📊 Performance Metrics

**Verified** (October 2025, Docker Compose):

| Component | Metric | Value | Status |
|-----------|--------|-------|--------|
| **Ingestion** | P99 Latency | 21-27ms | ✅ <50ms |
| **Ingestion** | Throughput | 600-825 e/s | ✅ Tested |
| **Kafka** | Delivery Rate | 100% (0 lag) | ✅ Perfect |
| **Kafka** | Messages | 70,900+ | ✅ Verified |
| **Database** | Events Stored | 25,590+ | ✅ Verified |
| **ML Model** | Inference | <10ms | ✅ <50ms |

**📖 Full Metrics**: [`docs/METRICS.md`](docs/METRICS.md)

---

## 🔬 ML Detection

**Model**: Isolation Forest (Unsupervised)

**Features** (12 total):
- Event count, error rate
- P50/P95/P99 latency + std dev
- Hour of day (temporal)
- Latency ratios (P95/P50, P99/P95)
- Log-scaled metrics

**Process**:
- 5-minute sliding windows per service
- Min 10 events for significance
- <10ms inference time

---

## 🛠️ Services

| Service | Port | Purpose |
|---------|------|---------|
| **Ingestion** | 8080 | HTTP API (Go) |
| **Kafka** | 9092 | Message broker |
| **TimescaleDB** | 5433 | Time-series DB |
| **Kafka UI** | 9000 | Topic monitoring |
| **Prometheus** | 9090 | Metrics |
| **Grafana** | 3000 | Dashboards |
| + 8 more | - | Detection, reporting, storage |

---

## 📂 Project Structure

```
helios/
├── services/
│   ├── ingestion/          # Go service
│   ├── detection/          # Python ML
│   ├── reporting/          # Python LLM
│   └── storage/            # Go DB writer
├── scripts/
│   ├── load_test.py        # Performance testing
│   └── train_model.py      # ML training
├── docs/
│   ├── QUICKSTART.md       # Get started
│   ├── TESTING.md          # Testing guide
│   ├── ARCHITECTURE.md     # System design
│   ├── METRICS.md          # Performance data
│   ├── RESUME.md           # Bullet points
│   └── GITHUB_SETUP.md     # Video recording
└── docker-compose.yml      # 14 services
```

---

## 🧪 Testing

```bash
# Load test
python scripts/load_test.py --rps 100 --duration 30

# Check database
docker exec helios-timescaledb psql -U postgres -d helios   -c "SELECT COUNT(*) FROM events;"

# Verify Kafka
docker exec helios-kafka kafka-consumer-groups   --bootstrap-server localhost:29092   --group anomaly-detectors --describe
```

**📖 Full Guide**: [`docs/TESTING.md`](docs/TESTING.md)

---

## 📈 Monitoring

| Service | URL | Credentials |
|---------|-----|-------------|
| Kafka UI | http://localhost:9000 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |

---

## 🎓 What I Learned

- Event-driven architecture with Kafka
- Multi-language microservices (Go + Python)
- Real-time ML on streaming data
- Time-series database optimization
- Feature engineering consistency
- Docker orchestration (14 services)

**Key Challenges**:
1. Feature dimension mismatch (7→12 features)
2. Snappy codec compatibility
3. Sliding window detection design

---

## 📝 Documentation

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) - Get started in 5 minutes
- [`docs/TESTING.md`](docs/TESTING.md) - Testing procedures
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - System design
- [`docs/METRICS.md`](docs/METRICS.md) - Performance metrics
- [`docs/RESUME.md`](docs/RESUME.md) - Resume bullet points
- [`docs/GITHUB_SETUP.md`](docs/GITHUB_SETUP.md) - Video recording guide

---

## 🚀 Future Enhancements

- [ ] Horizontal scaling (Kubernetes)
- [ ] ML model evaluation (precision/recall)
- [ ] Alerting integration (PagerDuty, Slack)
- [ ] Web UI for anomaly investigation
- [ ] Cloud deployment (AWS ECS/EKS)

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

<div align="center">

**Built with Go, Kafka, Python, and TimescaleDB**

⭐ Star if helpful!

</div>
