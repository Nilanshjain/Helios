# 01 - Understanding the Existing System

**Goal**: Understand how the current Helios system works before adding enhancements.

**Time**: 2-3 hours of exploration

**Prerequisites**: Docker running, system started (`docker-compose up -d`)

---

## 📁 Code Structure Overview

```
Helios/
├── services/
│   ├── ingestion/              # Go - HTTP API for event ingestion
│   │   ├── main.go             # Entry point
│   │   ├── handlers/           # HTTP request handlers
│   │   └── kafka/              # Kafka producer
│   │
│   ├── storage-writer/         # Go - Kafka → TimescaleDB
│   │   ├── main.go
│   │   └── writer/             # Batch DB writes
│   │
│   ├── detection/              # Python - ML anomaly detection
│   │   ├── app/
│   │   │   ├── ml/             # ⭐ ML models (YOUR FOCUS)
│   │   │   │   ├── anomaly_detector.py      # Isolation Forest
│   │   │   │   ├── feature_engineering.py   # 12 features
│   │   │   │   └── training.py              # Model training
│   │   │   ├── consumers/      # Kafka consumers
│   │   │   │   └── detection_consumer.py    # Main detection loop
│   │   │   └── core/           # Config, logging, database
│   │   └── main.py
│   │
│   └── reporting/              # Python - AI-powered reports
│       ├── app/
│       │   ├── generators/     # ⭐ Claude integration
│       │   │   ├── claude_generator.py      # LLM reports
│       │   │   ├── mock_generator.py        # Template reports
│       │   │   └── prompts.py               # Prompt engineering
│       │   ├── consumers/      # Kafka consumers
│       │   │   └── report_consumer.py       # Anomaly → Report
│       │   └── storage/        # Report storage
│       └── main.py
│
├── config/                     # Configuration files
│   ├── grafana/                # Dashboards
│   ├── prometheus/             # Metrics collection
│   └── timescaledb/            # Database schema
│
└── docker-compose.yml          # Orchestration (14 services)
```

---

## 🔄 Data Flow Walkthrough

### 1. **Event Ingestion** (`services/ingestion/`)

**What happens**: External services send logs via HTTP POST.

**Key File**: `services/ingestion/handlers/events.go:42`

```go
// Simplified from actual code
func HandleEvent(w http.ResponseWriter, r *http.Request) {
    // 1. Parse JSON event
    var event Event
    json.NewDecode(r.Body).Decode(&event)

    // 2. Validate required fields
    if event.Service == "" || event.Level == "" {
        http.Error(w, "Invalid event", 400)
        return
    }

    // 3. Produce to Kafka
    kafkaProducer.Send("events", event)

    // 4. Return 202 Accepted (fast response!)
    w.WriteHeader(202)
}
```

**Flow**:
```
HTTP POST /api/v1/events
  ↓
Parse JSON
  ↓
Validate
  ↓
Send to Kafka "events" topic
  ↓
Return 202 Accepted (21-27ms P99)
```

**Hands-On Exercise**:
```bash
# Send a test event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "service": "test-service",
    "level": "INFO",
    "message": "Test event",
    "metadata": {"latency_ms": 50}
  }'

# Check Kafka (should see your event)
docker exec -it helios-kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic events \
  --from-beginning \
  --max-messages 1
```

---

### 2. **Storage** (`services/storage-writer/`)

**What happens**: Events from Kafka are batched and written to TimescaleDB.

**Key File**: `services/storage-writer/writer/batch_writer.go:28`

```go
// Simplified
func (w *Writer) ProcessBatch(events []Event) {
    // Collect 100 events into batch
    batch := []Event{}

    for event := range eventChannel {
        batch = append(batch, event)

        if len(batch) >= 100 {
            // Write batch to database
            db.BulkInsert("events", batch)
            batch = []Event{}  // Reset
        }
    }
}
```

**Why batching?**
- Individual INSERT: 1000 events = 1000 DB round trips (slow!)
- Batch INSERT: 1000 events = 10 batches = 10 DB round trips (fast!)

**Database Schema** (`config/timescaledb/init.sql:15`):
```sql
CREATE TABLE events (
    time         TIMESTAMPTZ NOT NULL,
    service      TEXT NOT NULL,
    level        TEXT NOT NULL,
    message      TEXT,
    metadata     JSONB,       -- ⭐ Latency stored here!
    trace_id     TEXT,
    span_id      TEXT
);

-- Convert to hypertable (TimescaleDB magic for time-series)
SELECT create_hypertable('events', 'time');
```

**Hands-On Exercise**:
```bash
# Check if your event was stored
docker exec -it helios-timescaledb psql -U helios -d helios -c \
  "SELECT time, service, level, message FROM events
   WHERE service = 'test-service'
   ORDER BY time DESC LIMIT 5;"
```

---

### 3. **Anomaly Detection** (`services/detection/`) ⭐ **MOST IMPORTANT**

This is where the ML magic happens! Let's break it down step-by-step.

#### **Step 3a: Detection Consumer Loop**

**File**: `services/detection/app/consumers/detection_consumer.py:86`

```python
def start(self):
    """Main loop - consumes events from Kafka"""
    while True:
        # Poll Kafka for new messages
        messages = self.consumer.poll(timeout_ms=1000, max_records=500)

        for message in messages:
            event = message.value  # JSON event
            self._process_event(event)
```

**What it does**: Continuously reads events from Kafka topic `events`.

---

#### **Step 3b: Windowing (Group Events by Service)**

**File**: `services/detection/app/consumers/detection_consumer.py:131`

```python
def _process_event(self, event: Dict):
    service = event.get("service", "unknown")

    # Create window for this service if doesn't exist
    if service not in self.windows:
        self.windows[service] = deque(maxlen=1000)  # Last 1000 events
        self.last_check[service] = datetime.now()

    # Add event to window
    self.windows[service].append(event)

    # Check if 5 minutes passed since last detection
    time_since_last = (datetime.now() - self.last_check[service]).seconds

    if time_since_last >= 300:  # 5 minutes
        self._run_detection(service)  # ⭐ Run ML model!
        self.last_check[service] = datetime.now()
```

**Key Concept**: Events are grouped by **service** into **5-minute windows**.

**Example**:
```
Service: "api-gateway"
Events in last 5 min: [event1, event2, ..., event150]
  ↓
Feature extraction: Convert 150 events → 12 numbers
  ↓
ML model: Is this window anomalous?
```

---

#### **Step 3c: Feature Extraction** ⭐ **CRITICAL TO UNDERSTAND**

**File**: `services/detection/app/ml/feature_engineering.py:49`

```python
def extract_features(self, events: List[Dict]) -> np.ndarray:
    """Convert list of events into 12 numbers for ML model"""

    df = pd.DataFrame(events)  # Convert to pandas for analysis

    # Feature 1-2: Event counts
    event_count = len(df)
    error_rate = len(df[df['level'].isin(['ERROR', 'CRITICAL'])]) / event_count

    # Feature 3-6: Latency statistics
    latencies = self._extract_latencies(df)  # From metadata
    p50_latency = np.percentile(latencies, 50)  # Median
    p95_latency = np.percentile(latencies, 95)
    p99_latency = np.percentile(latencies, 99)
    latency_std = np.std(latencies)  # Spread

    # Feature 7: Time of day
    hour_of_day = datetime.now().hour  # 0-23

    # Feature 8-9: Ratios (engineered features)
    p95_p50_ratio = p95_latency / (p50_latency + 1)
    p99_p95_ratio = p99_latency / (p95_latency + 1)

    # Feature 10-12: Log-scaled versions
    error_count = event_count * error_rate
    log_event_count = np.log1p(event_count)
    log_error_rate = np.log1p(error_rate * 1000)

    # Return as 1x12 array
    return np.array([
        event_count, error_rate, p50_latency, p95_latency,
        p99_latency, latency_std, hour_of_day, p95_p50_ratio,
        p99_p95_ratio, error_count, log_event_count, log_error_rate
    ]).reshape(1, -1)
```

**Current Features** (12 total):
| # | Feature | What It Measures | Why It Matters |
|---|---------|------------------|----------------|
| 1 | `event_count` | Total events in 5min | High volume spike? |
| 2 | `error_rate` | % ERROR/CRITICAL | More errors than normal? |
| 3 | `p50_latency_ms` | Median latency | Typical request speed |
| 4 | `p95_latency_ms` | 95th percentile | Most requests are this fast or faster |
| 5 | `p99_latency_ms` | 99th percentile | Slowest 1% of requests |
| 6 | `latency_std` | Standard deviation | How spread out are latencies? |
| 7 | `hour_of_day` | 0-23 | Time-based patterns |
| 8 | `p95_p50_ratio` | P95/P50 ratio | Tail latency behavior |
| 9 | `p99_p95_ratio` | P99/P95 ratio | Extreme tail behavior |
| 10 | `error_count` | Absolute errors | Raw error volume |
| 11 | `log_event_count` | Log-scaled volume | For high volume services |
| 12 | `log_error_rate` | Log-scaled errors | Helps detect small changes |

**Hands-On Exercise**:
```python
# Try extracting features from sample events
events = [
    {"service": "api", "level": "INFO", "metadata": {"latency_ms": 50}},
    {"service": "api", "level": "ERROR", "metadata": {"latency_ms": 200}},
    {"service": "api", "level": "INFO", "metadata": {"latency_ms": 45}},
]

extractor = FeatureExtractor()
features = extractor.extract_features(events)
print(features)  # Should see [3, 0.333, 50, ...] (12 numbers)
```

---

#### **Step 3d: ML Model (Isolation Forest)**

**File**: `services/detection/app/ml/anomaly_detector.py:115`

```python
def predict(self, events: List[Dict]) -> Dict:
    """Given window of events, predict if anomalous"""

    # 1. Extract features (12 numbers)
    features = self.feature_extractor.extract_features(events)

    # 2. Normalize features (StandardScaler)
    features_scaled = self.scaler.transform(features)

    # 3. Get anomaly score from Isolation Forest
    score = self.model.decision_function(features_scaled)[0]

    # 4. Threshold check
    is_anomaly = score < self.threshold  # Currently -0.7

    # 5. Calculate severity
    severity = self._calculate_severity(score, features[0])

    return {
        'is_anomaly': is_anomaly,
        'score': score,  # Lower = more anomalous
        'severity': severity,  # critical/high/medium/low
        'features': features[0].tolist()
    }
```

**How Isolation Forest Works** (Simple Explanation):

1. **Training Phase**: Learn what "normal" looks like
   - Given 2000+ historical windows
   - Build trees that try to isolate each point
   - Normal points: hard to isolate (many splits needed)
   - Anomalies: easy to isolate (few splits needed)

2. **Inference Phase**: Check if new window is normal
   - Extract features from new 5-min window
   - How many splits to isolate it?
   - Few splits = anomaly, many splits = normal

**Analogy**:
- Finding a purple elephant in a zoo = easy to isolate (anomaly!)
- Finding a specific grey elephant = hard to isolate (normal)

**Anomaly Score**:
- **Normal**: score = -0.3 to 0.2 (higher is more normal)
- **Anomaly**: score < -0.7 (lower is more anomalous)

**Hands-On Exercise**:
```bash
# Check if model file exists
ls -lh services/detection/models/

# Train a new model (optional)
docker exec -it helios-detection python -m app.ml.training
```

---

#### **Step 3e: Anomaly Alert → Kafka**

**File**: `services/detection/app/consumers/detection_consumer.py:200`

```python
def _handle_anomaly(self, service, result, events):
    """When anomaly detected, create alert and publish"""

    alert = {
        'id': f"anomaly_{service}_{int(time.time())}",
        'timestamp': datetime.now().isoformat(),
        'service': service,
        'severity': result['severity'],
        'score': result['score'],
        'features': dict(zip(feature_names, result['features'])),
        'window_size': len(events),
    }

    # Store in database
    db.insert('anomalies', alert)

    # Publish to Kafka "anomaly-alerts" topic
    kafka_producer.send('anomaly-alerts', alert)
```

**Flow Summary**:
```
150 events in 5-min window
  ↓
Extract 12 features
  ↓
Isolation Forest predict
  ↓
Score = -0.85 (< -0.7 threshold)
  ↓
ANOMALY DETECTED!
  ↓
Publish to "anomaly-alerts" Kafka topic
```

---

### 4. **AI Report Generation** (`services/reporting/`)

**What happens**: Anomaly alerts trigger Claude 3.5 Sonnet to generate incident reports.

**File**: `services/reporting/app/consumers/report_consumer.py:79`

```python
def _process_anomaly(self, anomaly: dict):
    """Given anomaly alert, generate detailed report"""

    # 1. Fetch context from database
    context = self._fetch_context(anomaly)
    # context includes:
    #   - Last 500 events around anomaly time
    #   - Aggregated metrics (error rate, latencies)
    #   - Recent anomalies for same service

    # 2. Build prompt for Claude
    prompt = build_incident_report_prompt(context)

    # 3. Call Claude API
    report = claude_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    # 4. Save report (filesystem + database)
    save_report(report.content, anomaly_id)
```

**Prompt Structure** (`services/reporting/app/generators/prompts.py:41`):
```markdown
You are analyzing a production incident...

## Incident Overview
- Anomaly Score: -0.85
- Service: api-gateway
- Time: 2025-10-29 14:32:15

## System Metrics
- Error Rate: 12.3% (baseline: 2.1%)
- P99 Latency: 450ms (baseline: 120ms)
- Event Count: 1,245

## Sample Events
[Shows ERROR logs]

## Your Task
Generate incident report with:
1. Executive Summary
2. Root Cause Analysis
3. Recommended Actions
...
```

**Hands-On Exercise**:
```bash
# Check generated reports
docker exec -it helios-reporting ls -lh /app/reports/

# Read latest report
docker exec -it helios-reporting cat /app/reports/*.markdown | head -50
```

---

## 🧪 Complete Test: Trigger Anomaly End-to-End

Let's cause an anomaly and watch it flow through the system!

### Step 1: Generate High Error Rate Traffic
```bash
# Send 100 events with 50% error rate (way above normal 2%)
for i in {1..100}; do
  level=$(( RANDOM % 2 == 0 ? "ERROR" : "INFO" ))
  curl -X POST http://localhost:8080/api/v1/events \
    -H "Content-Type: application/json" \
    -d "{
      \"service\": \"test-anomaly\",
      \"level\": \"$level\",
      \"message\": \"Load test $i\",
      \"metadata\": {\"latency_ms\": $((RANDOM % 200 + 100))}
    }"
done
```

### Step 2: Watch Detection Consumer Logs
```bash
docker logs -f helios-detection | grep -E "anomaly_detected|test-anomaly"
```

**Expected Output** (after ~5 minutes):
```
anomaly_detected service=test-anomaly severity=high score=-0.92
```

### Step 3: Check Anomaly Database
```bash
docker exec -it helios-timescaledb psql -U helios -d helios -c \
  "SELECT time, service, severity, score
   FROM anomalies
   WHERE service = 'test-anomaly'
   ORDER BY time DESC LIMIT 1;"
```

### Step 4: Watch Report Generation
```bash
docker logs -f helios-reporting-consumer | grep -E "report_generated|test-anomaly"
```

### Step 5: Read Generated Report
```bash
# Find report file
docker exec helios-reporting ls -lt /app/reports/ | head -2

# Read it
docker exec helios-reporting cat /app/reports/report_anomaly_test-anomaly_*.markdown
```

---

## 🎯 Understanding Checklist

After completing this guide, you should be able to answer:

**Architecture**:
- [ ] What are the 7 main components?
- [ ] How do events flow from ingestion to report?
- [ ] Why use Kafka instead of direct DB writes?

**ML Pipeline**:
- [ ] What are the 12 current features?
- [ ] How does Isolation Forest detect anomalies?
- [ ] What does the anomaly score mean?
- [ ] How are events grouped into windows?

**Code Navigation**:
- [ ] Where is feature extraction code?
- [ ] Where is the ML model trained?
- [ ] Where are anomaly alerts created?
- [ ] Where is the Claude prompt built?

**Hands-On**:
- [ ] Can you send an event via curl?
- [ ] Can you query events from the database?
- [ ] Can you trigger an anomaly?
- [ ] Can you read generated reports?

---

## 🔍 Key Files to Study

Before moving to Day 2, thoroughly read these files:

### Must Read:
1. `services/detection/app/ml/feature_engineering.py` - **Understand all 12 features**
2. `services/detection/app/ml/anomaly_detector.py` - **How IF works**
3. `services/detection/app/consumers/detection_consumer.py` - **Main loop**
4. `services/reporting/app/generators/prompts.py` - **Claude prompting**

### Good to Read:
5. `config/timescaledb/init.sql` - Database schema
6. `docker-compose.yml` - Service orchestration
7. `services/ingestion/handlers/events.go` - Event ingestion

---

## 📝 Self-Quiz

Test your understanding:

1. **Q**: If I send 200 events with 50% error rate to service "api", when will anomaly detection run?
   - **A**: After 5 minutes from last check, the detection consumer will extract features from those 200 events and run Isolation Forest.

2. **Q**: What's the difference between P50, P95, and P99 latency?
   - **A**: P50 = median (50% faster), P95 = 95% faster, P99 = 99% faster. P99 shows tail latency.

3. **Q**: Why is `error_rate` a feature but also `log_error_rate`?
   - **A**: Log scaling helps model detect proportional changes. 1%→2% (small absolute change but 100% relative change).

4. **Q**: What does an anomaly score of -0.9 mean?
   - **A**: Very anomalous (< -0.7 threshold). The window's features are very different from training data.

5. **Q**: How many algorithms are currently used for detection?
   - **A**: Just 1 - Isolation Forest. (You'll add Prophet later!)

---

## ➡️ Next Steps

Once you can answer the quiz questions and understand the flow:

1. ✅ Mark Day 1 complete
2. ➡️ Read `02-ML-FUNDAMENTALS.md` to deepen Isolation Forest understanding
3. ➡️ Read `03-PROPHET-FORECASTING.md` to learn what you'll add
4. ➡️ Start `implementation/DAY-02-DATA-GENERATOR.md`

---

*Confused about something? Re-read that section. Draw diagrams. Run the code with print statements. Understanding this deeply is critical for interviews!*
