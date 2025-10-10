# Helios Reporting Service

AI-powered incident report generation using GPT-4 or local LLMs.

## Features

- Automated incident report generation from anomalies
- GPT-4 integration with prompt engineering
- Context aggregation from TimescaleDB
- Report storage with versioning
- Slack notification integration
- Token usage tracking and cost optimization
- Mock mode for development without API costs

## Architecture

```
Anomaly Alerts (Kafka) → Report Generator → GPT-4 API → Report Storage
                               ↓
                        Context Fetcher (TimescaleDB)
                               ↓
                        Slack Notification
```

## Quick Start

### Development Mode (No API Key Required)

```bash
# Use mock generator (no OpenAI API key needed)
docker-compose up -d reporting

# Reports will use template-based generation
```

### Production Mode (GPT-4)

```bash
# Set OpenAI API key
export OPENAI_API_KEY=sk-...

# Start service
docker-compose up -d reporting
```

## Configuration

Environment variables:

```bash
# Generator Mode
REPORT_GENERATOR_MODE=openai  # or 'mock'
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.3

# Kafka
KAFKA_BROKERS=kafka:9092
KAFKA_ALERTS_TOPIC=anomaly-alerts
KAFKA_CONSUMER_GROUP=report-generators

# Database
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=helios

# Storage
REPORTS_STORAGE_PATH=/app/reports
REPORTS_RETENTION_DAYS=30

# Slack (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_ENABLED=true
```

## API Endpoints

```bash
# Health check
GET /health

# List reports
GET /api/v1/reports?limit=10&service=payment-service

# Get specific report
GET /api/v1/reports/{report_id}

# Regenerate report
POST /api/v1/reports/{anomaly_id}/regenerate

# Get metrics
GET /metrics
```

## Report Structure

Generated reports include:

1. **Executive Summary** - High-level incident overview
2. **Impact Assessment** - Affected services and user impact
3. **Root Cause Analysis** - Likely causes based on evidence
4. **Timeline** - Event sequence
5. **Recommended Actions** - Immediate, short-term, and long-term steps
6. **Supporting Data** - Metrics, logs, and graphs

## Prompt Engineering

The service uses carefully engineered prompts for high-quality reports:

- Context-aware prompts with recent events
- Token-optimized context summaries
- Structured output format
- Technical depth appropriate for SRE teams

## Testing

```bash
# Run tests
pytest

# Test with mock data
python -m app.test_generator

# Benchmark report generation
python -m app.benchmark
```

## Metrics

Prometheus metrics:

- `helios_reports_generated_total` - Total reports generated
- `helios_report_generation_latency_seconds` - Generation time
- `helios_openai_tokens_used_total` - OpenAI tokens consumed
- `helios_openai_cost_usd_total` - Estimated API costs
- `helios_report_errors_total` - Generation failures

## Performance

- Report Generation: <3 seconds (GPT-4)
- Report Generation: <100ms (mock mode)
- Token Usage: 800-1200 tokens/report
- Cost: ~$0.03-0.05 per report (GPT-4)
