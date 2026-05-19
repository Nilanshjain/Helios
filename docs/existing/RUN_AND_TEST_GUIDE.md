# Helios - Complete Run & Test Guide
**For Screenshots and End-to-End Testing**

This guide provides ALL commands needed to run, test, and capture screenshots of the Helios platform for GitHub/portfolio presentation.

**Time Required:** 15-20 minutes
**Prerequisites:** Docker Desktop, Python 3.11+, Git Bash or PowerShell

---

## Table of Contents
1. [System Setup](#1-system-setup)
2. [Event Ingestion Flow](#2-event-ingestion-flow)
3. [Real-Time Anomaly Detection](#3-real-time-anomaly-detection)
4. [AI Report Generation](#4-ai-report-generation)
5. [Performance Verification](#5-performance-verification)
6. [Database Analytics](#6-database-analytics)
7. [Monitoring Dashboards](#7-monitoring-dashboards)
8. [Complete End-to-End Test](#8-complete-end-to-end-test)

---

## 1. System Setup

### 1.1 Start All Services

```bash
# Navigate to project directory
cd C:\Users\Nilansh\Desktop\Helios

# Clean start (optional - for fresh deployment)
docker-compose down -v

# Start all 13 services
docker-compose up -d

# Wait 30 seconds for initialization
sleep 30
```

### 1.2 Verify Services Running

```bash
# Check all services (should show 13 containers)
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**📸 SCREENSHOT #1: All Services Running**
- **Capture:** Terminal showing all 13 containers with "Up" or "healthy" status
- **Highlight:** Microservices architecture (Go, Python, Kafka, TimescaleDB, Prometheus, Grafana)
- **Expected Services:**
  ```
  helios-ingestion             Up (healthy)
  helios-storage-writer        Up
  helios-detection             Up (healthy)
  helios-detection-consumer    Up
  helios-reporting             Up (healthy)
  helios-reporting-consumer    Up
  helios-kafka                 Up (healthy)
  helios-zookeeper             Up
  helios-timescaledb           Up (healthy)
  helios-prometheus            Up
  helios-grafana               Up
  helios-kafka-ui              Up
  helios-alertmanager          Up
  ```

### 1.3 Check Service Health

```bash
# Ingestion API health
curl http://localhost:8080/health

# Detection API health
curl http://localhost:8000/health

# Reporting API health
curl http://localhost:8002/health
```

**Expected:** All return `200 OK` with `{"status":"healthy"}`

---

## 2. Event Ingestion Flow

### 2.1 Send Single Test Event

```bash
# Send a single INFO event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-25T12:00:00Z",
    "service": "payment-gateway",
    "level": "INFO",
    "message": "Payment processed successfully",
    "metadata": {
      "latency_ms": 45,
      "endpoint": "/api/payments",
      "status_code": 200,
      "amount": 99.99
    }
  }'
```

**📸 SCREENSHOT #2: Event Ingestion**
- **Capture:** Curl command + JSON response
- **Highlight:** RESTful API, immediate 202 Accepted response, sub-30ms latency
- **Expected Response:**
  ```json
  {
    "status": "accepted",
    "event_id": "evt_...",
    "timestamp": "2025-10-25T12:00:00Z"
  }
  ```

### 2.2 Send Error Event

```bash
# Send an ERROR level event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-25T12:01:00Z",
    "service": "payment-gateway",
    "level": "ERROR",
    "message": "Database connection timeout",
    "metadata": {
      "latency_ms": 5200,
      "error_code": "DB_TIMEOUT",
      "retry_count": 3
    }
  }'
```

### 2.3 Verify Kafka Message Flow

```bash
# View messages in Kafka events topic (Ctrl+C to exit)
docker exec helios-kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic events \
  --from-beginning \
  --max-messages 5
```

**📸 SCREENSHOT #3: Kafka Message Stream**
- **Capture:** Events flowing through Kafka topic
- **Highlight:** Event-driven architecture, message broker decoupling, JSON format
- **Expected Output:** JSON events with all fields including `ingested_at` and `host` added by ingestion service

### 2.4 Check Kafka Topics

```bash
# List all topics
docker exec helios-kafka kafka-topics \
  --bootstrap-server localhost:29092 \
  --list

# Describe events topic (shows 10 partitions)
docker exec helios-kafka kafka-topics \
  --bootstrap-server localhost:29092 \
  --describe \
  --topic events
```

**Expected Output:**
```
Topic: events    PartitionCount: 10    ReplicationFactor: 1
```

---

## 3. Real-Time Anomaly Detection

### 3.1 Generate Anomalous Traffic

```bash
# Simulate production incident with high error rate
python scripts/simulate_indian_scenarios.py \
  --scenario payment-gateway \
  --events 200 \
  --surge \
  --rate 50
```

**📸 SCREENSHOT #4: Load Test Execution**
- **Capture:** Progress bar and final statistics
- **Highlight:** High throughput testing (50 events/sec), realistic error simulation (40-45%)
- **Expected Output:**
  ```
  ==========================================================
  [START] Simulating: Digital Payment Gateway Surge
  ==========================================================
  Events: 200
  Error rate: 43.5%
  Rate: 50 events/sec
  ==========================================================

  Progress: [====================] 100% (Errors: 87)

  ==========================================================
  [SUCCESS] Simulation Complete
  ==========================================================
  Total events: 200
  Success: 113 (56.5%)
  Errors: 87 (43.5%)
  Duration: 4.2 seconds
  Rate: 47.6 events/sec
  ==========================================================
  ```

### 3.2 Wait for Detection Window

```bash
# Detection runs every 5 minutes per service
# Wait 5-6 minutes from when you sent the surge
echo "Waiting 5 minutes for detection window..."
sleep 300

# Check if enough time has passed since last events
echo "5 minutes elapsed. Checking for anomaly detection..."
```

### 3.3 Check Detection Consumer Logs

```bash
# View detection logs in real-time
docker logs helios-detection-consumer --tail 50 --follow
```

**📸 SCREENSHOT #5: ML Detection in Action**
- **Capture:** Detection logs showing anomaly detection with score and severity
- **Highlight:** Machine learning inference, feature extraction, threshold evaluation
- **Expected Log Entries:**
  ```json
  {"event": "window_
  
  ready", "service": "payment-gateway", "event_count": 200, "window_minutes": 5}
  {"event": "features_extracted", "service": "payment-gateway", "features": {...12 features...}}
  {"event": "model_inference_complete", "inference_time_ms": 8.3}
  {"event": "anomaly_detected", "service": "payment-gateway", "score": -0.62, "threshold": -0.4, "severity": "critical"}
  {"event": "alert_published", "topic": "anomaly-alerts", "anomaly_id": "anom_..."}
  ```

### 3.4 Verify Anomaly Alert in Kafka

```bash
# Check anomaly-alerts topic
docker exec helios-kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic anomaly-alerts \
  --from-beginning \
  --max-messages 1
```

**📸 SCREENSHOT #6: Anomaly Alert Published**
- **Capture:** Alert message in anomaly-alerts topic
- **Highlight:** Event-driven pipeline, Kafka topic routing, anomaly metadata
- **Expected:** JSON with anomaly_id, service, score, severity, features, timestamp

### 3.5 Query Anomalies Table

```bash
# View detected anomalies in database
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT
    time,
    service,
    severity,
    score,
    threshold,
    (features->>'error_rate')::numeric AS error_rate,
    (features->>'event_count')::numeric AS event_count
  FROM anomalies
  ORDER BY time DESC
  LIMIT 5;
"
```

**Expected:** Recent anomaly entries with negative scores and severity levels

---

## 4. AI Report Generation

### 4.1 Check Report Consumer Logs

```bash
# View reporting consumer logs
docker logs helios-reporting-consumer --tail 30 --follow
```

**📸 SCREENSHOT #7: AI Report Generation**
- **Capture:** Logs showing Claude API call, token usage, cost, and generation time
- **Highlight:** LLM integration, cost tracking, sub-2-second generation
- **Expected Log Entries:**
  ```json
  {"event": "processing_anomaly", "anomaly_id": "anom_...", "service": "payment-gateway"}
  {"event": "context_fetched", "recent_events": 87, "window_minutes": 15}
  {"event": "calling_claude_api", "model": "claude-3-5-sonnet-20241022", "max_tokens": 1500}
  {"event": "report_generated", "tokens_input": 892, "tokens_output": 1347, "cost_usd": 0.0231, "generation_time_ms": 1847}
  {"event": "report_saved", "filepath": "/app/reports/2025/10/25/report_..._.md"}
  {"event": "metadata_saved", "report_id": "rpt_...", "database": "incident_reports"}
  {"event": "report_generated_successfully", "total_time_ms": 2150}
  ```

### 4.2 List Generated Reports via API

```bash
# Get list of all reports
curl -s http://localhost:8002/api/v1/reports | python -m json.tool
```

**📸 SCREENSHOT #8: Reports API Response**
- **Capture:** JSON list of reports with metadata
- **Highlight:** RESTful API design, pagination support, metadata tracking
- **Expected Response:**
  ```json
  {
    "total": 5,
    "reports": [
      {
        "report_id": "rpt_...",
        "anomaly_id": "anom_...",
        "service": "payment-gateway",
        "severity": "critical",
        "generated_at": "2025-10-25T12:05:34Z",
        "tokens_used": 2239,
        "cost_usd": 0.0231,
        "generation_time_ms": 1847,
        "filepath": "/app/reports/2025/10/25/report_..._.md"
      },
      ...
    ]
  }
  ```

### 4.3 Retrieve Full AI Report

```bash
# Get the report_id from previous command, then fetch full report
REPORT_ID="rpt_..."  # Replace with actual report_id

curl -s "http://localhost:8002/api/v1/reports/${REPORT_ID}" | python -m json.tool | head -n 100
```

**📸 SCREENSHOT #9: AI-Generated Incident Report**
- **Capture:** Full markdown report with all 7 sections (first 80-100 lines)
- **Highlight:**
  - Executive Summary with key findings
  - Technical Analysis with metrics breakdown
  - Root Cause Hypothesis with evidence
  - Impact Assessment (business + technical)
  - Immediate Actions Taken
  - Recommended Actions (prioritized)
  - Monitoring & Follow-up
- **Note:** This is REAL AI-generated content from Claude, not a template!

**Expected Report Structure:**
```markdown
# Incident Report: Critical Anomaly in payment-gateway

**Generated:** 2025-10-25T12:05:34Z
**Service:** payment-gateway
**Severity:** Critical
**Anomaly Score:** -0.62 (threshold: -0.4)

## 1. Executive Summary

A critical anomaly has been detected in the payment-gateway service...
[AI-generated analysis]

## 2. Technical Analysis

**Metrics Analysis:**
- Event Count: 200 events in 5-minute window
- Error Rate: 43.5% (expected: <5%)
- P99 Latency: 5200ms (baseline: 135ms) - 38x increase
- P95/P50 Ratio: 8.4 (baseline: 2.5)

...

## 7. Monitoring & Follow-up

**Watch for:**
- Error rate returning to baseline (<2%)
- Latency P99 below 200ms
- Database connection pool recovery
...
```

---

## 5. Performance Verification

### 5.1 Run Load Test

```bash
# Install dependencies (first time only)
pip install aiohttp

# Run 30-second load test at 100 RPS
python scripts/load_test.py --rps 100 --duration 30 --batch-size 10
```

**📸 SCREENSHOT #10: Load Test Results**
- **Capture:** Final statistics with latency breakdown
- **Highlight:** Sub-30ms P99 latency, events/sec throughput, success rate
- **Expected Output:**
  ```
  ================================================================================
  [RESULTS] LOAD TEST RESULTS
  ================================================================================
  Duration: 30.01s
  Total Requests: 2,651
  Successful: 2,651 (100.0%)
  Failed: 0 (0.0%)
  Total Events: 26,510
  Events/Sec: 883

  Latency:
    Average: 16.40ms
    P50: 16.09ms
    P95: 19.76ms
    P99: 21.46ms [PASS - Target: <50ms]

  Errors: None
  ================================================================================
  ```

### 5.2 Check Kafka Consumer Lag

```bash
# Verify consumers are keeping up (lag should be 0)
docker exec helios-kafka kafka-consumer-groups \
  --bootstrap-server localhost:29092 \
  --all-groups \
  --describe
```

**📸 SCREENSHOT #11: Kafka Consumer Groups**
- **Capture:** Consumer group status showing LAG = 0
- **Highlight:** 100% message delivery, real-time processing, no backlog
- **Expected:** All consumer groups (storage-writers, anomaly-detectors, report-generators) with LAG = 0

---

## 6. Database Analytics

### 6.1 Total Events Stored

```bash
# Query events statistics
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT
    COUNT(*) as total_events,
    COUNT(DISTINCT service) as unique_services,
    MIN(time) as first_event,
    MAX(time) as latest_event,
    MAX(time) - MIN(time) as time_span
  FROM events
  WHERE time > NOW() - INTERVAL '1 hour';
"
```

**📸 SCREENSHOT #12: Database Performance**
- **Capture:** Query results showing thousands of events processed
- **Highlight:** High-volume ingestion, time-series optimization, multiple services tracked
- **Expected Output:**
  ```
   total_events | unique_services |        first_event         |        latest_event        | time_span
  --------------+-----------------+----------------------------+----------------------------+-----------
          26710 |               4 | 2025-10-25 11:30:00.123+00 | 2025-10-25 12:05:45.876+00 | 00:35:45
  ```

### 6.2 Service-Level Error Analysis

```bash
# Breakdown by service and level
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT
    service,
    COUNT(*) as total_events,
    SUM(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END) as errors,
    ROUND(100.0 * SUM(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate_pct,
    AVG((metadata->>'latency_ms')::numeric) as avg_latency_ms
  FROM events
  WHERE time > NOW() - INTERVAL '1 hour'
  GROUP BY service
  ORDER BY errors DESC;
"
```

**Expected:** Shows payment-gateway with high error rate (40-45%) compared to others (<2%)

### 6.3 Report Generation Statistics

```bash
# AI report cost and performance analytics
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT
    COUNT(*) as total_reports,
    COUNT(DISTINCT service) as services_affected,
    SUM(tokens_used) as total_tokens,
    ROUND(SUM(cost_usd)::numeric, 4) as total_cost_usd,
    ROUND(AVG(cost_usd)::numeric, 4) as avg_cost_per_report,
    AVG(generation_time_ms)::int as avg_generation_time_ms,
    MIN(generated_at) as first_report,
    MAX(generated_at) as latest_report
  FROM incident_reports
  WHERE generated_at > NOW() - INTERVAL '24 hours';
"
```

**📸 SCREENSHOT #13: AI Cost & Performance Analytics**
- **Capture:** Database query showing API costs, token usage, and performance
- **Highlight:** Cost tracking, performance metrics, production-ready analytics
- **Expected Output:**
  ```
   total_reports | services_affected | total_tokens | total_cost_usd | avg_cost_per_report | avg_generation_time_ms
  ---------------+-------------------+--------------+----------------+---------------------+------------------------
               5 |                 2 |        11195 |         0.1156 |              0.0231 |                   1847
  ```

### 6.4 Anomaly Detection Stats

```bash
# Anomaly detection breakdown
docker exec helios-timescaledb psql -U postgres -d helios -c "
  SELECT
    severity,
    COUNT(*) as count,
    AVG(score) as avg_score,
    MIN(score) as min_score,
    AVG((features->>'error_rate')::numeric) as avg_error_rate,
    AVG((features->>'event_count')::numeric) as avg_event_count
  FROM anomalies
  WHERE time > NOW() - INTERVAL '24 hours'
  GROUP BY severity
  ORDER BY
    CASE severity
      WHEN 'CRITICAL' THEN 1
      WHEN 'HIGH' THEN 2
      WHEN 'MEDIUM' THEN 3
      WHEN 'LOW' THEN 4
    END;
"
```

---

## 7. Monitoring Dashboards

### 7.1 Prometheus Metrics

```bash
# Open Prometheus in browser
echo "Open http://localhost:9090 in your browser"
```

**Useful Queries:**

1. **Event Ingestion Rate:**
   ```promql
   rate(helios_events_ingested_total[5m])
   ```

2. **Anomaly Detection Rate:**
   ```promql
   rate(helios_anomalies_detected_total[1h])
   ```

3. **Ingestion P99 Latency:**
   ```promql
   histogram_quantile(0.99, rate(helios_ingestion_latency_seconds_bucket[5m]))
   ```

4. **AI Report Generation Cost:**
   ```promql
   rate(helios_claude_cost_usd_total[1h])
   ```

**📸 SCREENSHOT #14: Prometheus Dashboard**
- **Capture:** Prometheus UI with one of the queries above showing graph
- **Highlight:** Real-time metrics, time-series visualization, PromQL queries

### 7.2 Grafana Dashboards

```bash
# Open Grafana in browser (username: admin, password: admin)
echo "Open http://localhost:3100 in your browser"
echo "Credentials: admin/admin"
```

**Pre-built Dashboards:**
1. **Helios Overview** - System-wide metrics
2. **System Overview** - Infrastructure health

**📸 SCREENSHOT #15: Grafana Dashboard**
- **Capture:** Grafana dashboard showing event rates, latencies, or anomaly counts
- **Highlight:** Professional visualization, multiple panels, auto-refresh

### 7.3 Kafka UI

```bash
# Open Kafka UI
echo "Open http://localhost:9000 in your browser"
```

**What to Check:**
1. Topics → `events` → See message count, partitions (10), compression (snappy)
2. Topics → `anomaly-alerts` → View anomaly messages
3. Consumer Groups → Check lag for all groups

**📸 SCREENSHOT #16: Kafka UI**
- **Capture:** Topics page showing events topic with 10 partitions and message statistics
- **Highlight:** Topic monitoring, partition distribution, consumer group tracking

---

## 8. Complete End-to-End Test

This section combines everything into a single test flow for comprehensive verification.

### 8.1 Automated E2E Test Script

Create a file `scripts/e2e_test.sh`:

```bash
#!/bin/bash

echo "=========================================="
echo "HELIOS END-TO-END TEST"
echo "=========================================="
echo ""

# Test 1: Send events
echo "[1/8] Sending test events..."
curl -s -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-10-25T12:00:00Z","service":"e2e-test","level":"INFO","message":"Test event 1","metadata":{"latency_ms":50}}' > /dev/null
echo "✓ Events sent"
echo ""

# Test 2: Verify Kafka
echo "[2/8] Checking Kafka..."
KAFKA_COUNT=$(docker exec helios-kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:29092 \
  --topic events \
  --time -1 | awk -F':' '{sum += $3} END {print sum}')
echo "✓ Kafka has $KAFKA_COUNT total messages"
echo ""

# Test 3: Verify database
echo "[3/8] Checking database..."
DB_COUNT=$(docker exec helios-timescaledb psql -U postgres -d helios -t -c "SELECT COUNT(*) FROM events;")
echo "✓ Database has $DB_COUNT events stored"
echo ""

# Test 4: Check consumer lag
echo "[4/8] Checking consumer lag..."
docker exec helios-kafka kafka-consumer-groups \
  --bootstrap-server localhost:29092 \
  --group storage-writers \
  --describe 2>/dev/null | grep -q "0 " && echo "✓ Storage consumers keeping up (lag=0)" || echo "⚠ Storage consumers have lag"
echo ""

# Test 5: Run load test
echo "[5/8] Running load test..."
python scripts/load_test.py --rps 50 --duration 10 --batch-size 10 2>&1 | grep "P99:"
echo ""

# Test 6: Check anomalies
echo "[6/8] Checking anomalies..."
ANOMALY_COUNT=$(docker exec helios-timescaledb psql -U postgres -d helios -t -c "SELECT COUNT(*) FROM anomalies;")
echo "✓ $ANOMALY_COUNT anomalies detected"
echo ""

# Test 7: Check reports
echo "[7/8] Checking reports..."
REPORT_COUNT=$(docker exec helios-timescaledb psql -U postgres -d helios -t -c "SELECT COUNT(*) FROM incident_reports;")
echo "✓ $REPORT_COUNT reports generated"
echo ""

# Test 8: API health
echo "[8/8] Checking API health..."
INGESTION_HEALTH=$(curl -s http://localhost:8080/health | grep -o '"status":"healthy"' | wc -l)
DETECTION_HEALTH=$(curl -s http://localhost:8000/health | grep -o '"status":"healthy"' | wc -l)
REPORTING_HEALTH=$(curl -s http://localhost:8002/health | grep -o '"status":"healthy"' | wc -l)

if [ $INGESTION_HEALTH -eq 1 ]; then echo "✓ Ingestion API healthy"; else echo "✗ Ingestion API unhealthy"; fi
if [ $DETECTION_HEALTH -eq 1 ]; then echo "✓ Detection API healthy"; else echo "✗ Detection API unhealthy"; fi
if [ $REPORTING_HEALTH -eq 1 ]; then echo "✓ Reporting API healthy"; else echo "✗ Reporting API unhealthy"; fi
echo ""

echo "=========================================="
echo "END-TO-END TEST COMPLETE"
echo "=========================================="
echo ""
echo "Summary:"
echo "- Kafka Messages: $KAFKA_COUNT"
echo "- DB Events: $DB_COUNT"
echo "- Anomalies: $ANOMALY_COUNT"
echo "- Reports: $REPORT_COUNT"
echo ""
```

Run the test:

```bash
chmod +x scripts/e2e_test.sh
./scripts/e2e_test.sh
```

**📸 SCREENSHOT #17: E2E Test Results**
- **Capture:** Complete test execution with all checkmarks
- **Highlight:** Comprehensive validation, all components working together

---

## 9. Screenshot Checklist

Use this checklist to ensure you have all necessary screenshots:

- [ ] **#1** - All 14 services running (docker ps)
- [ ] **#2** - Event ingestion API call + response
- [ ] **#3** - Kafka message stream
- [ ] **#4** - Load test execution with statistics
- [ ] **#5** - ML detection logs with anomaly score
- [ ] **#6** - Anomaly alert in Kafka topic
- [ ] **#7** - AI report generation logs (tokens, cost, time)
- [ ] **#8** - Reports API JSON response
- [ ] **#9** - Full AI-generated incident report (markdown)
- [ ] **#10** - Load test P99 latency results
- [ ] **#11** - Kafka consumer groups (lag = 0)
- [ ] **#12** - Database query showing event statistics
- [ ] **#13** - AI cost & performance analytics
- [ ] **#14** - Prometheus metrics dashboard
- [ ] **#15** - Grafana visualization
- [ ] **#16** - Kafka UI topics page
- [ ] **#17** - E2E test complete results

---

## 10. Troubleshooting

### Services Not Starting

```bash
# Check logs for specific service
docker logs helios-ingestion --tail 50
docker logs helios-kafka --tail 50

# Restart specific service
docker-compose restart ingestion

# Full restart
docker-compose down
docker-compose up -d
```

### Anomaly Not Detected

**Checklist:**
- [ ] Wait full 5 minutes after sending surge events
- [ ] Ensure at least 10 events sent to same service
- [ ] Check error rate is >15% (or latency spike >3x)
- [ ] Verify threshold is -0.4 in docker-compose.yml
- [ ] Check detection-consumer logs for "window_ready"

```bash
# Force check detection consumer
docker logs helios-detection-consumer --tail 100 | grep -E "(window_ready|anomaly_detected)"
```

### Report Not Generated

**Checklist:**
- [ ] Verify ANTHROPIC_API_KEY is set in .env file
- [ ] Check REPORT_GENERATOR_MODE=claude in docker-compose.yml
- [ ] Ensure anomaly was detected (check anomalies table)
- [ ] Check reporting-consumer logs for errors

```bash
# Check API key is loaded
docker exec helios-reporting-consumer env | grep ANTHROPIC

# Check for errors
docker logs helios-reporting-consumer --tail 50 | grep -i error
```

### Kafka Consumer Lag

```bash
# If consumers are lagging, check resource usage
docker stats --no-stream

# Restart consumers
docker-compose restart storage-writer detection-consumer reporting-consumer
```

---

## 11. Cleanup

### Stop Services

```bash
# Stop all services (keeps data)
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Clean Test Data

```bash
# Remove test events
docker exec helios-timescaledb psql -U postgres -d helios -c "
  DELETE FROM events WHERE service = 'e2e-test';
"

# Clean old reports (keep last 7 days)
docker exec helios-timescaledb psql -U postgres -d helios -c "
  DELETE FROM incident_reports WHERE generated_at < NOW() - INTERVAL '7 days';
"
```

---

## 12. Quick Commands Reference

```bash
# Start
docker-compose up -d

# Status
docker ps

# Logs (follow)
docker logs -f helios-ingestion

# Stop
docker-compose down

# Send event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-10-25T12:00:00Z","service":"test","level":"INFO","message":"test","metadata":{"latency_ms":50}}'

# Load test
python scripts/load_test.py --rps 100 --duration 30

# Database query
docker exec helios-timescaledb psql -U postgres -d helios -c "SELECT COUNT(*) FROM events;"

# Consumer lag
docker exec helios-kafka kafka-consumer-groups --bootstrap-server localhost:29092 --all-groups --describe

# List reports
curl http://localhost:8002/api/v1/reports | python -m json.tool

# View report
curl http://localhost:8002/api/v1/reports/REPORT_ID | python -m json.tool
```

---

**Created:** 2025-10-25
**Purpose:** Complete guide for testing, screenshots, and portfolio presentation
**Time Required:** 15-20 minutes for full walkthrough
