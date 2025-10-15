# Helios - Real-Time Anomaly Detection & Incident Reporting

[![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go)](https://go.dev/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org/)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-3.5+-231F20?style=flat&logo=apache-kafka)](https://kafka.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Cloud-native observability platform combining high-throughput event ingestion, ML-based anomaly detection, and AI-powered incident reporting.

## Overview

Helios automates monitoring and incident response for distributed systems by processing 50,000 events/second, detecting anomalies with 95% precision, and generating incident reports in under 2 seconds.

**Key Features:**
- Event ingestion with Go + Apache Kafka (50K events/sec)
- Real-time ML anomaly detection using Isolation Forest
- AI-generated incident reports with root cause analysis
- Production-ready infrastructure with Terraform + Kubernetes

## Architecture

```
Applications → Go API → Kafka → TimescaleDB
                         ↓
                    ML Detection → Reports
```

**Components:**
- **Ingestion**: Go microservice with Kafka integration
- **Storage**: TimescaleDB for time-series data
- **Detection**: Python service with Isolation Forest ML
- **Reporting**: Lambda + Claude API for incident reports
- **Monitoring**: Prometheus + Grafana dashboards

## Quick Start

### Prerequisites
- Docker Desktop 20.10+
- Docker Compose 2.0+

### Setup

```bash
# Clone repository
git clone https://github.com/Nilanshjain/Helios.git
cd Helios

# Start services
docker-compose up -d

# Verify services
docker-compose ps

# Access dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

### Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Ingestion API | `http://localhost:8080` | Event ingestion |
| Grafana | `http://localhost:3000` | Monitoring dashboards |
| Prometheus | `http://localhost:9090` | Metrics |
| TimescaleDB | `localhost:5432` | Database |

## Performance

| Metric | Result |
|--------|--------|
| Throughput | 49,750 events/sec |
| P99 Latency | 423ms |
| ML Precision | 95.8% |
| ML Recall | 87.5% |
| Report Generation | 1.85s avg |

## Tech Stack

**Backend:** Go, Python (FastAPI), Apache Kafka, TimescaleDB
**ML/AI:** scikit-learn (Isolation Forest), Claude API
**Infrastructure:** Docker, Kubernetes, Terraform, AWS (Lambda, S3, EKS)
**Monitoring:** Prometheus, Grafana

## Project Structure

```
Helios/
├── services/
│   ├── ingestion/      # Go event ingestion
│   ├── detection/      # Python ML detection
│   └── reporting/      # Lambda reporting
├── terraform/          # Infrastructure as Code
├── k8s/                # Kubernetes manifests
├── config/             # Configurations
├── scripts/            # Utility scripts
└── docker-compose.yml  # Local development
```

## Configuration

Create `.env` file:

```bash
# Kafka
KAFKA_BROKERS=localhost:9092

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=helios
DB_USER=postgres
DB_PASSWORD=your_password

# Claude API (optional for reporting)
ANTHROPIC_API_KEY=your_api_key
```

## Testing

```bash
# ML model training
cd scripts && python train_model.py

# Load testing
cd tests/load && ./run_load_test.sh
```

## Documentation

- [Architecture Details](docs/ARCHITECTURE.md)
- [AWS Infrastructure](docs/AWS_INFRASTRUCTURE.md)
- [Testing Guide](docs/TESTING.md)
- [Interview Prep](docs/RESUME_PROJECT_SUMMARY.md)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

**Nilansh Jain**
📧 nilanshjain0306@gmail.com
🔗 [GitHub](https://github.com/Nilanshjain) • [LinkedIn](https://linkedin.com/in/nilansh-jain)

---

⭐ Star this repository if you find it useful!
