# 📋 HELIOS LEARNING CENTER - COMPLETE DOCUMENTATION PLAN

This document lists ALL files in the learning center, their status, and outlines for files yet to be created.

**Last Updated**: October 29, 2025

---

## 📊 Documentation Status

| Category | Total Files | ✅ Created | ⏳ Pending |
|----------|-------------|-----------|-----------|
| **Root** | 2 | 2 | 0 |
| **Existing** | 6 | 6 | 0 |
| **Learning** | 6 | 3 | 3 |
| **Implementation** | 12 | 0 | 12 |
| **Reference** | 4 | 0 | 4 |
| **Diagrams** | 4 | 0 | 4 |
| **TOTAL** | **34** | **11** | **23** |

**Progress**: 32% complete

---

## ✅ COMPLETED FILES

### Root Level
- ✅ `00-START-HERE.md` - Main entry point with learning roadmap
- ✅ `DOCUMENTATION-PLAN.md` - This file (meta-documentation)

### Existing Folder (Archived Current Docs)
- ✅ `ARCHITECTURE.md` - Current system deep dive
- ✅ `RUN_AND_TEST_GUIDE.md` - Testing guide
- ✅ `VERIFIED_METRICS.md` - Current performance numbers
- ✅ `KNOWN_ISSUES.md` - Current bugs and issues
- ✅ `GITHUB_ENHANCEMENT.md` - Portfolio optimization tips
- ✅ `RESUME_INTERVIEW_GUIDE.md` - Interview preparation

### Learning Folder (Concept Docs)
- ✅ `01-EXISTING-SYSTEM.md` - Comprehensive code walkthrough
- ✅ `03-PROPHET-FORECASTING.md` - Time-series forecasting with Prophet
- ✅ `04-SHAP-EXPLAINABILITY.md` - Explainable AI with SHAP

---

## ⏳ PENDING FILES (To Be Created)

### Learning Folder

#### `02-ML-FUNDAMENTALS.md`
**Purpose**: Deep dive into Isolation Forest algorithm
**Time**: 2-3 hours reading
**Outline**:
```markdown
# 02 - ML Fundamentals: Isolation Forest

## What is Anomaly Detection?
- Supervised vs. Unsupervised learning
- Why unsupervised for our use case

## How Isolation Forest Works
- Decision tree basics
- The isolation concept (purple elephant analogy)
- Training: Building random trees
- Inference: Counting splits to isolate
- Anomaly score interpretation

## Why Isolation Forest?
- Fast training and inference
- No labeled data needed
- Handles high-dimensional data
- Comparison with other algorithms (One-Class SVM, LOF, Autoencoder)

## StandardScaler (Feature Normalization)
- Why scale features?
- How StandardScaler works
- Impact on model performance

## Hands-On Exercise
- Train IF on toy dataset
- Visualize decision boundaries
- Understand contamination parameter

## Common Pitfalls
- Feature scaling forgotten
- Contamination too high/low
- Training on anomalous data

## Quiz & Checklist
```

---

#### `05-ENSEMBLE-METHODS.md`
**Purpose**: Learn how to combine multiple ML algorithms
**Time**: 2 hours reading
**Outline**:
```markdown
# 05 - Ensemble Methods for Better Detection

## Why Ensemble > Single Algorithm?
- Diversity of detection methods
- Reducing false positives
- Increasing confidence

## Voting Strategies
- Majority voting (2 out of 3)
- Weighted voting (IF: 50%, Prophet: 50%)
- Confidence scoring based on agreement

## Combining IF + Prophet
- When each algorithm excels
- Handling disagreements
- Algorithm-specific strengths

## Implementation Patterns
- Parallel prediction
- Result aggregation
- Confidence calculation

## Examples from Industry
- DataDog: Multi-algorithm ensemble
- AWS CloudWatch: Statistical + ML
- Dynatrace: Causal AI + forecasting

## Hands-On Exercise
- Implement simple 2-model ensemble
- Test on synthetic anomalies
- Compare single vs. ensemble performance

## Quiz & Checklist
```

---

#### `06-FEATURE-ENGINEERING.md`
**Purpose**: Master creating informative features from raw data
**Time**: 3 hours reading + practice
**Outline**:
```markdown
# 06 - Feature Engineering for Anomaly Detection

## What Makes a Good Feature?
- Discriminative power
- Stable computation
- Domain relevance
- Low correlation (avoid redundancy)

## Current 12 Features (Review)
- Detailed explanation of each
- Why each feature matters
- How each is computed

## New 13 Features (To Add)
### Infrastructure Metrics (6 features)
1. avg_cpu_usage - Resource contention
2. max_cpu_usage - Peak load
3. avg_memory_usage - Memory pressure
4. max_memory_usage - Memory spikes
5. cpu_memory_correlation - Resource correlation
6. resource_pressure_score - Combined metric

### Database Metrics (4 features)
7. avg_db_connection_usage - Connection pool health
8. max_db_connection_usage - Pool exhaustion
9. avg_db_query_p99 - Query performance
10. db_slow_query_ratio - Slow query detection

### Cache Metrics (2 features)
11. avg_cache_hit_rate - Cache effectiveness
12. cache_miss_spike - Sudden cache degradation

### Dependency Metrics (1 feature)
13. downstream_error_rate - Upstream service health

## Feature Correlation
- Why correlation matters
- Realistic correlation patterns
  - High CPU → High latency
  - Low cache hits → High latency
  - DB saturation → Errors

## Synthetic Data with Realistic Features
- Scenario-based generation
- Feature correlation implementation
- Validation techniques

## Feature Extraction Code Walkthrough
- Metadata structure
- Extraction helpers
- Error handling

## Hands-On Exercise
- Design 3 custom features
- Extract from sample events
- Validate feature quality

## Quiz & Checklist
```

---

### Implementation Folder (Daily Guides)

#### `DAY-01-SETUP.md`
**Purpose**: Learning day + environment setup
**Outline**:
```markdown
# Day 1: Learning & Setup (6 hours)

## Morning: Learning (3 hours)
- [ ] Read 01-EXISTING-SYSTEM.md
- [ ] Read 02-ML-FUNDAMENTALS.md
- [ ] Watch recommended videos:
  - StatQuest: Isolation Forest (15 min)
  - System walkthrough of current code

## Afternoon: Hands-On Exploration (3 hours)
- [ ] Start all Docker services
- [ ] Send test events
- [ ] Query database
- [ ] Trigger anomaly
- [ ] Read generated report
- [ ] Study feature_engineering.py code
- [ ] Study anomaly_detector.py code

## Success Criteria
- [ ] Understand data flow end-to-end
- [ ] Can explain all 12 current features
- [ ] Know where each component lives in code
- [ ] Completed self-quiz in learning docs

## Evening Prep (30 min)
- [ ] Preview DAY-02-DATA-GENERATOR.md
- [ ] Install any missing Python packages
- [ ] Sketch out data generator design

## Deliverable
- Notes on current system understanding
- Questions for clarification
```

---

#### `DAY-02-DATA-GENERATOR.md`
**Purpose**: Build RealisticDataGenerator with 5 scenarios
**Outline**:
```markdown
# Day 2: Realistic Data Generator (6 hours)

## Learning Objectives
- Understand feature correlation
- Model realistic failure scenarios
- Generate time-based patterns

## Morning: Design (2 hours)
### 5 Failure Scenarios
1. **normal** - 1-3% errors, normal latency, balanced resources
2. **deployment_spike** - 15% errors for 30min, high CPU, high DB connections
3. **database_slowdown** - High latency, normal errors, slow queries, DB saturation
4. **cache_miss_storm** - High latency, high memory, low cache hit rate
5. **cascading_failure** - 25% errors, very high CPU/memory, downstream failures

### Feature Correlation Matrix
- CPU ↔ Memory: +0.7 correlation
- CPU ↔ Latency: +0.6 correlation
- DB connections ↔ Latency: +0.8 correlation
- Cache misses ↔ Latency: +0.7 correlation

## Afternoon: Implementation (3 hours)
### File: `services/detection/app/ml/realistic_data_generator.py`

**Class Structure**:
```python
class RealisticDataGenerator:
    def __init__(self, days=30, events_per_window=100)
    def generate(self) -> List[List[Dict]]
    def _pick_scenario(self, hour, deployment_schedule)
    def _generate_window(self, scenario, hour_of_day)
    def _generate_event(self, scenario, hour)
    def _generate_deployment_schedule(self)
    def _is_peak_hour(self, hour)
```

### Key Implementation Details
- Time-based traffic patterns (peak 3x baseline)
- Correlated feature generation
- Deployment schedule (every 3 days at 2am)
- Scenario probabilities

## Evening: Testing & Validation (1 hour)
- [ ] Generate 30 days of data
- [ ] Visualize feature distributions
- [ ] Check correlation matrix
- [ ] Validate scenarios appear correctly

## Success Criteria
- [ ] 30 days = 8,640 windows generated
- [ ] All 5 scenarios present
- [ ] Features are correlated (check correlation matrix)
- [ ] Peak hours have 3x traffic
- [ ] Can distinguish normal vs. anomaly visually

## Deliverable
- `realistic_data_generator.py` (~300-400 lines)
- Test script showing generated data
```

---

#### `DAY-03-FEATURES.md` through `DAY-12-DOCUMENTATION.md`
**Similar structure for each day** - Will create on demand as you progress.

Brief outlines:

- **DAY-03**: Extend `feature_engineering.py` to 25 features
- **DAY-04**: Implement `prophet_detector.py` and train models
- **DAY-05**: Build `ensemble_detector.py` with weighted voting
- **DAY-06-07**: Create `evaluate_model.py`, train all models, generate metrics
- **DAY-08**: Add `explainability.py` with SHAP integration
- **DAY-09**: Update `prompts.py` to include SHAP in Claude reports
- **DAY-10**: Create Grafana dashboard JSON with ML metrics
- **DAY-11**: Build simple explainability UI (HTML + Chart.js or React)
- **DAY-12**: Update README, record demo video, final polish

---

### Reference Folder

#### `API-REFERENCE.md`
**Purpose**: Quick lookup for all REST endpoints
**Outline**:
```markdown
# API Reference

## Ingestion Service (Port 8080)

### POST /api/v1/events
Single event ingestion
- Request body: Event JSON
- Response: 202 Accepted
- Example: curl command

### POST /api/v1/events/batch
Batch event ingestion
- Request body: Array of events
- Response: 202 Accepted
- Example: curl command

### GET /health
Health check
### GET /ready
Readiness probe

## Reporting Service (Port 8082)

### GET /api/v1/reports
List all reports

### GET /api/v1/reports/{report_id}
Get specific report

### POST /api/v1/reports/{anomaly_id}/regenerate
Regenerate report for anomaly

### GET /metrics
Prometheus metrics

## Explainability UI (Port 3000)

### GET /
Main dashboard

### GET /api/v1/anomalies/latest
Get latest anomaly with SHAP values
```

---

#### `CODE-NAVIGATION.md`
**Purpose**: "Where do I find X?" guide
**Outline**:
```markdown
# Code Navigation Guide

## Common Questions

**Q: Where is feature extraction?**
A: `services/detection/app/ml/feature_engineering.py:49`

**Q: Where is the ML model trained?**
A: `services/detection/app/ml/training.py:191` (synthetic data) or line 131 (database)

**Q: Where does anomaly detection run?**
A: `services/detection/app/consumers/detection_consumer.py:162`

**Q: Where are anomaly alerts created?**
A: `services/detection/app/consumers/detection_consumer.py:211`

**Q: Where is the Claude prompt built?**
A: `services/reporting/app/generators/prompts.py:8`

**Q: Where is the database schema?**
A: `config/timescaledb/init.sql:15`

**Q: Where are Docker services defined?**
A: `docker-compose.yml`

## File Index by Function

### ML Pipeline
- Feature extraction: `feature_engineering.py`
- Model definition: `anomaly_detector.py`
- Training: `training.py`
- Detection loop: `detection_consumer.py`
- Prophet (new): `prophet_detector.py`
- Ensemble (new): `ensemble_detector.py`
- SHAP (new): `explainability.py`

### API Endpoints
- Ingestion: `services/ingestion/handlers/events.go`
- Reporting: `services/reporting/app/api/routes.py`

### Configuration
- Database: `config/timescaledb/init.sql`
- Prometheus: `config/prometheus/prometheus.yml`
- Grafana: `config/grafana/provisioning/`

[... complete index...]
```

---

#### `METRICS-GLOSSARY.md`
**Purpose**: Explain every metric used
**Outline**:
```markdown
# Metrics Glossary

## Performance Metrics

**P50 Latency** (Median)
- Definition: 50% of requests are faster than this
- Good value: < 100ms
- Alert threshold: > 500ms
- Why it matters: Represents typical user experience

**P95 Latency** (95th Percentile)
- Definition: 95% of requests faster
- Good value: < 200ms
- Alert threshold: > 1000ms
- Why it matters: Most users have this experience or better

**P99 Latency** (99th Percentile)
- Definition: 99% of requests faster
- Good value: < 500ms
- Alert threshold: > 2000ms
- Why it matters: Tail latency for power users

## ML Metrics

**Precision**
- Definition: Of all anomalies detected, how many were real?
- Formula: True Positives / (True Positives + False Positives)
- Target: > 85%
- Impact: Low precision = too many false alarms

**Recall**
- Definition: Of all real anomalies, how many did we detect?
- Formula: True Positives / (True Positives + False Negatives)
- Target: > 80%
- Impact: Low recall = missing real incidents

**F1 Score**
- Definition: Harmonic mean of precision and recall
- Formula: 2 * (Precision * Recall) / (Precision + Recall)
- Target: > 85%
- Why it matters: Balanced measure

**False Positive Rate**
- Definition: % of normal windows incorrectly flagged
- Formula: False Positives / (False Positives + True Negatives)
- Target: < 10%
- Impact: Alert fatigue

## SHAP Metrics

**SHAP Value**
- Definition: Feature contribution to prediction
- Range: -∞ to +∞
- Negative: Pushes toward anomaly
- Positive: Pushes toward normal
- Interpretation: Larger absolute value = more important

[... complete glossary...]
```

---

#### `COMMANDS-CHEATSHEET.md`
**Purpose**: Quick reference for common commands
**Outline**:
```markdown
# Commands Cheatsheet

## Docker

# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f [service-name]
docker-compose logs -f helios-detection

# Restart service
docker-compose restart helios-detection

# Check status
docker-compose ps

## Kafka

# List topics
docker exec helios-kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# Read from topic
docker exec helios-kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic events \
  --from-beginning \
  --max-messages 10

# Produce test message
docker exec -it helios-kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic events

## TimescaleDB

# Connect to database
docker exec -it helios-timescaledb psql -U helios -d helios

# Query events
docker exec helios-timescaledb psql -U helios -d helios -c \
  "SELECT COUNT(*) FROM events;"

# Query anomalies
docker exec helios-timescaledb psql -U helios -d helios -c \
  "SELECT time, service, severity FROM anomalies ORDER BY time DESC LIMIT 10;"

## Python

# Train model
docker exec helios-detection python -m app.ml.training

# Run tests
docker exec helios-detection pytest tests/

# Install package
docker exec helios-detection pip install shap

## Testing

# Send test event
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"service":"test","level":"INFO","message":"test"}'

# Batch events
curl -X POST http://localhost:8080/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d '[{"service":"test","level":"ERROR","message":"error1"},
       {"service":"test","level":"ERROR","message":"error2"}]'

# Get reports
curl http://localhost:8082/api/v1/reports

[... complete cheatsheet...]
```

---

### Diagrams Folder

#### `current-architecture.png`
**Purpose**: Visual diagram of existing system
**Content**:
- 7 components (ingestion, kafka, storage, timescaledb, detection, reporting, monitoring)
- Data flow arrows
- Technology labels

**Creation Method**: Use draw.io, Excalidraw, or similar tool

---

#### `enhanced-architecture.png`
**Purpose**: Diagram showing Prophet + SHAP additions
**Content**:
- All current components
- NEW: Prophet forecaster box
- NEW: SHAP explainer box
- NEW: Ensemble voting logic
- NEW: Explainability UI

---

#### `ensemble-flow.png`
**Purpose**: Detailed view of dual-algorithm ensemble
**Content**:
- Input: 25 features
- Split to: Isolation Forest + Prophet
- Voting logic (weighted)
- Confidence calculation
- Output: Anomaly decision

---

#### `shap-example.png`
**Purpose**: Sample SHAP waterfall chart
**Content**:
- Screenshot or recreation of SHAP visualization
- Shows top 5 features
- Demonstrates how to read the chart

---

## 🎯 Priority Order for Creation

Based on 12-day timeline:

### Week 1 (Days 1-7)
1. ✅ 00-START-HERE.md (done)
2. ✅ 01-EXISTING-SYSTEM.md (done)
3. ⏳ 02-ML-FUNDAMENTALS.md (needed for Day 1)
4. ✅ 03-PROPHET-FORECASTING.md (done - needed for Day 4)
5. ⏳ 06-FEATURE-ENGINEERING.md (needed for Days 2-3)
6. ⏳ 05-ENSEMBLE-METHODS.md (needed for Day 5)
7. ⏳ DAY-01 through DAY-07 implementation guides (as you progress)

### Week 2 (Days 8-12)
8. ✅ 04-SHAP-EXPLAINABILITY.md (done - needed for Day 8)
9. ⏳ DAY-08 through DAY-12 implementation guides (as you progress)
10. ⏳ Reference docs (helpful throughout, create as needed)
11. ⏳ Diagrams (create during Day 12 documentation)

---

## 📝 Template for New Docs

When creating implementation guides, use this structure:

```markdown
# Day X: [Title] ([Hours] hours)

## Learning Objectives
- What you'll learn today

## Morning/Afternoon/Evening Breakdown
- Time-boxed tasks

## Implementation Steps
1. Step-by-step guide
2. Code snippets
3. Expected outputs

## Success Criteria
- [ ] Checklist of deliverables
- [ ] Test results to verify

## Troubleshooting
- Common issues and fixes

## Deliverable
- Files created/modified
- Metrics achieved

## Next Steps
- Preview tomorrow's work
```

---

## 🔄 Update Process

As you create new files:

1. Create the file following the outline
2. Update this document's completion counts
3. Check off in Priority Order section
4. Commit changes to git

---

## 📈 Completion Tracking

Track your progress here:

### Learning Docs
- [x] 01-EXISTING-SYSTEM.md
- [ ] 02-ML-FUNDAMENTALS.md
- [x] 03-PROPHET-FORECASTING.md
- [x] 04-SHAP-EXPLAINABILITY.md
- [ ] 05-ENSEMBLE-METHODS.md
- [ ] 06-FEATURE-ENGINEERING.md

### Implementation Guides
- [ ] DAY-01-SETUP.md
- [ ] DAY-02-DATA-GENERATOR.md
- [ ] DAY-03-FEATURES.md
- [ ] DAY-04-PROPHET.md
- [ ] DAY-05-ENSEMBLE.md
- [ ] DAY-06-07-EVALUATION.md
- [ ] DAY-08-SHAP.md
- [ ] DAY-09-REPORTING.md
- [ ] DAY-10-GRAFANA.md
- [ ] DAY-11-UI.md
- [ ] DAY-12-DOCUMENTATION.md

### Reference Docs
- [ ] API-REFERENCE.md
- [ ] CODE-NAVIGATION.md
- [ ] METRICS-GLOSSARY.md
- [ ] COMMANDS-CHEATSHEET.md

### Diagrams
- [ ] current-architecture.png
- [ ] enhanced-architecture.png
- [ ] ensemble-flow.png
- [ ] shap-example.png

---

**Note**: This is a living document. Update as you create new files or change plans.

*You now have a complete blueprint for your learning center. Start with the high-priority files and create others on-demand as you progress through the 12-day plan!*
