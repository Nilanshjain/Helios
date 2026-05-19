# Day 1: Learning & System Understanding (6 hours)

**Goal**: Deeply understand the existing Helios system before enhancing it
**Time**: 6 hours (can split across 2 days if needed)
**Deliverable**: Comprehensive understanding of current codebase + notes

---

## Morning: Deep Dive Learning (3-4 hours)

### Part 1: Read Documentation (2 hours)

#### 1. Read `01-EXISTING-SYSTEM.md` (1 hour)
- [ ] Understand data flow: events → Kafka → detection → reports
- [ ] Study the 12 current features
- [ ] Review detection consumer logic
- [ ] Understand how anomalies trigger reports

**Key Questions to Answer**:
- How does an event get from ingestion to anomaly detection?
- What are the 12 features and why was each chosen?
- How is the anomaly threshold determined?
- What happens when an anomaly is detected?

#### 2. Read `02-ML-FUNDAMENTALS.md` (1 hour)
- [ ] Understand Isolation Forest algorithm
- [ ] Learn why unsupervised learning is used
- [ ] Grasp the isolation concept
- [ ] Understand StandardScaler importance

**Key Questions to Answer**:
- Why does Isolation Forest work for anomaly detection?
- What does the anomaly score represent?
- Why must we scale features?
- What does contamination parameter control?

### Part 2: Watch Videos (30 min)

#### Recommended Videos
1. **StatQuest: Isolation Forest** (15 min)
   - Search YouTube: "StatQuest Isolation Forest"
   - Best visual explanation of how it works

2. **Your System Walkthrough** (15 min)
   - Review the Helios architecture diagram in README
   - Trace data flow from curl command to report generation

---

## Afternoon: Hands-On Exploration (2-3 hours)

### Part 1: Start the System (30 min)

```bash
# Navigate to project
cd C:\Users\Nilansh\Desktop\Helios

# Start all services
docker-compose up -d

# Wait 30 seconds for initialization
timeout /t 30

# Verify all 14 containers are running
docker-compose ps

# Check logs for errors
docker-compose logs helios-detection-consumer --tail 20
docker-compose logs helios-reporting-consumer --tail 20
```

**Success Criteria**:
- [ ] All 14 containers show "Up"
- [ ] No error messages in logs
- [ ] Kafka UI accessible at http://localhost:9000

### Part 2: Send Test Events (30 min)

#### Send Normal Event
```bash
curl -X POST http://localhost:8080/api/v1/events ^
  -H "Content-Type: application/json" ^
  -d "{\"timestamp\": \"2025-10-24T10:00:00Z\", \"service\": \"api-gateway\", \"level\": \"INFO\", \"message\": \"Request processed\", \"metadata\": {\"latency_ms\": 45, \"endpoint\": \"/api/users\", \"status_code\": 200}}"
```

- [ ] Received 202 Accepted response
- [ ] Event appears in Kafka UI (http://localhost:9000)

#### Send Anomalous Event (High Latency)
```bash
curl -X POST http://localhost:8080/api/v1/events ^
  -H "Content-Type: application/json" ^
  -d "{\"timestamp\": \"2025-10-24T10:01:00Z\", \"service\": \"api-gateway\", \"level\": \"ERROR\", \"message\": \"Request timeout\", \"metadata\": {\"latency_ms\": 5000, \"endpoint\": \"/api/users\", \"status_code\": 500}}"
```

- [ ] Event sent successfully
- [ ] Check if it triggers anomaly (may need more events to reach min_events_per_window)

#### Run Mini Load Test
```bash
python scripts/load_test.py --rps 50 --duration 10
```

- [ ] Load test completes without errors
- [ ] Events visible in Kafka
- [ ] P99 latency reported

### Part 3: Query Database (30 min)

#### Connect to TimescaleDB
```bash
docker exec -it helios-timescaledb psql -U postgres -d helios
```

#### Check Event Count
```sql
SELECT COUNT(*) as total_events FROM events;
SELECT service, COUNT(*) as count FROM events GROUP BY service;
```

- [ ] See events from your tests
- [ ] Understand table structure

#### Check Anomalies (if any)
```sql
SELECT * FROM anomalies ORDER BY time DESC LIMIT 5;
```

- [ ] Understand anomaly table structure
- [ ] See score, severity, features columns

#### Check Continuous Aggregates
```sql
SELECT * FROM event_metrics_5m
WHERE bucket > NOW() - INTERVAL '1 hour'
ORDER BY bucket DESC
LIMIT 10;
```

- [ ] See pre-computed metrics
- [ ] Understand how features are derived

Exit psql: `\q`

### Part 4: Trigger Anomaly (1 hour)

#### Generate Anomaly Scenario
Create file `test_anomaly.py`:

```python
import requests
import time
from datetime import datetime

# Send burst of high-latency errors
for i in range(20):
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "payment-service",
        "level": "ERROR",
        "message": f"Database timeout {i}",
        "metadata": {
            "latency_ms": 4500 + (i * 50),
            "endpoint": "/checkout",
            "status_code": 500,
            "error_code": "DB_TIMEOUT"
        }
    }

    response = requests.post(
        "http://localhost:8080/api/v1/events",
        json=event
    )
    print(f"{i+1}/20 - {response.status_code}")
    time.sleep(0.5)

print("\nWait 1 minute for detection window to process...")
time.sleep(60)

print("Check anomalies table for detections!")
```

Run:
```bash
python test_anomaly.py
```

#### Verify Anomaly Detected
```bash
# Check detection logs
docker logs helios-detection-consumer --tail 50 | findstr "anomaly"

# Check database
docker exec helios-timescaledb psql -U postgres -d helios ^
  -c "SELECT time, service, severity, score FROM anomalies ORDER BY time DESC LIMIT 5;"

# Check if report was generated
docker logs helios-reporting-consumer --tail 50
```

**Success Criteria**:
- [ ] Anomaly appears in database
- [ ] Detection consumer logged "anomaly_detected"
- [ ] Report consumer generated a report
- [ ] Report file exists in reporting volume

---

## Evening: Code Study (1-2 hours)

### Part 1: Study Feature Engineering (30 min)

**File**: `services/detection/app/ml/feature_engineering.py`

Read the file and answer:

1. **How many features are extracted?**
   <details><summary>Answer</summary>12 features</details>

2. **How is error_rate calculated?**
   <details><summary>Answer</summary>Count of ERROR/CRITICAL events divided by total events</details>

3. **What happens if latency metadata is missing?**
   <details><summary>Answer</summary>Latency features default to 0.0</details>

4. **Why is log_event_count used instead of raw count?**
   <details><summary>Answer</summary>Log scaling handles large spikes better (1000 → 6.9, 10000 → 9.2)</details>

- [ ] Can explain each of the 12 features
- [ ] Understand how features are extracted from events

### Part 2: Study Anomaly Detector (30 min)

**File**: `services/detection/app/ml/anomaly_detector.py`

Read the file and answer:

1. **What parameters are used for IsolationForest?**
   <details><summary>Answer</summary>contamination, n_estimators, max_samples, random_state</details>

2. **How is severity determined?**
   <details><summary>Answer</summary>Based on score: < -0.9 = CRITICAL, < -0.7 = HIGH, < -0.5 = MEDIUM, else LOW</details>

3. **What is returned by the predict() method?**
   <details><summary>Answer</summary>Dict with is_anomaly, score, threshold, severity, confidence, features, feature_names</details>

- [ ] Understand model initialization
- [ ] Understand training process
- [ ] Understand prediction flow

### Part 3: Study Detection Consumer (30 min)

**File**: `services/detection/app/consumers/detection_consumer.py`

Read the file and answer:

1. **How are events grouped?**
   <details><summary>Answer</summary>By service name, stored in separate windows (deque)</details>

2. **When is detection triggered?**
   <details><summary>Answer</summary>Every WINDOW_SIZE_MINUTES after last check</details>

3. **What is MIN_EVENTS_PER_WINDOW?**
   <details><summary>Answer</summary>Minimum events required to run detection (default: 3-10)</details>

4. **How are anomalies deduplicated?**
   <details><summary>Answer</summary>Alert cache with cooldown period (default: 10 minutes)</details>

- [ ] Understand consumer loop
- [ ] Understand window management
- [ ] Understand anomaly handling

---

## Self-Assessment Quiz

Test your understanding:

### Architecture
1. What are the 5 main components of Helios?
   <details><summary>Answer</summary>Ingestion, Kafka, Storage, Detection, Reporting</details>

2. What database is used and why?
   <details><summary>Answer</summary>TimescaleDB - time-series optimized PostgreSQL</details>

3. How many Kafka topics exist?
   <details><summary>Answer</summary>2: events, anomaly-alerts</details>

### ML Pipeline
4. What ML algorithm is currently used?
   <details><summary>Answer</summary>Isolation Forest (scikit-learn)</details>

5. How many features are extracted from events?
   <details><summary>Answer</summary>12 features</details>

6. What is the anomaly detection threshold?
   <details><summary>Answer</summary>-0.16 (configurable via ANOMALY_THRESHOLD)</details>

### Data Flow
7. Trace the path of an event from ingestion to report.
   <details><summary>Answer</summary>
   1. HTTP POST → Ingestion service
   2. Kafka produce → events topic
   3. Detection consumer → extracts features → ML inference
   4. If anomaly → Kafka produce → anomaly-alerts topic
   5. Reporting consumer → generates report via Claude
   6. Report saved to filesystem + database
   </details>

---

## Deliverables

By end of Day 1, you should have:

### 1. Running System
- [ ] All 14 Docker containers running
- [ ] Can send events successfully
- [ ] Can query database
- [ ] Can view Kafka topics

### 2. Notes Document
Create `my_notes/day01_understanding.md`:

```markdown
# Day 1 Notes: System Understanding

## Data Flow Diagram (in my words)
[Your diagram/description]

## 12 Current Features
1. event_count - [why it matters]
2. error_rate - [why it matters]
...

## Key Code Locations
- Feature extraction: services/detection/app/ml/feature_engineering.py:49
- Detection logic: [location]
- Report generation: [location]

## Questions/Clarifications Needed
- [Any unclear concepts]

## What I Learned
- [Key insights]
```

### 3. Answered Quiz Questions
- [ ] All architecture questions answered correctly
- [ ] All ML pipeline questions answered correctly
- [ ] Can trace data flow end-to-end

### 4. Tomorrow's Prep
- [ ] Previewed DAY-02-DATA-GENERATOR.md
- [ ] Understand goal: generate 30 days of realistic data
- [ ] Sketched out 5 failure scenarios

---

## Troubleshooting

### Docker containers not starting
```bash
# Check Docker Desktop is running
docker ps

# Check disk space
docker system df

# Restart Docker Desktop
# Then try: docker-compose up -d
```

### Can't connect to database
```bash
# Check container is running
docker ps | findstr timescaledb

# Check logs
docker logs helios-timescaledb --tail 20

# Wait 30 seconds for initialization
timeout /t 30
```

### Load test fails
```bash
# Install dependencies
pip install aiohttp

# Try with lower RPS
python scripts/load_test.py --rps 10 --duration 5
```

---

## Optional Bonus Tasks

If you finish early:

### 1. Explore Grafana
- Open http://localhost:3100 (admin/admin)
- View existing dashboards
- Understand metrics being tracked

### 2. Explore Prometheus
- Open http://localhost:9090
- Query: `helios_events_processed_total`
- Query: `helios_anomalies_detected_total`

### 3. Read Claude Integration
- File: `services/reporting/app/generators/claude_generator.py`
- Understand how reports are generated
- Look at prompt engineering in `prompts.py`

---

## Success Criteria

You're ready for Day 2 when you can:

- [ ] Explain Helios architecture to a friend (pretend they're interviewing you)
- [ ] Describe how Isolation Forest works (purple elephant analogy)
- [ ] List and explain all 12 current features
- [ ] Trace an event from curl command to incident report
- [ ] Run the system and trigger an anomaly
- [ ] Read and understand the key Python files (feature_engineering, anomaly_detector, detection_consumer)

---

## Time Tracking

Log your actual time spent:

- [ ] Documentation reading: ___ hours
- [ ] Hands-on exploration: ___ hours
- [ ] Code study: ___ hours
- [ ] Total: ___ hours

**Note**: It's OK to take 7-8 hours total. Understanding deeply is more important than speed!

---

## Next Steps

**Tomorrow**: DAY-02-DATA-GENERATOR.md
You'll build a `RealisticDataGenerator` that creates 30 days of synthetic events with:
- 5 realistic failure scenarios
- Correlated features (high CPU → high latency)
- Time-based patterns (peak hours, deployment windows)
- 25 features (13 new + 12 existing)

**Tonight's Homework** (15 min):
- Preview DAY-02 guide
- Sketch out the 5 scenarios on paper
- Think about how CPU and latency might correlate

---

**Congratulations on completing Day 1! You now have a solid foundation to build upon. Rest up and get ready to generate realistic data tomorrow!**
