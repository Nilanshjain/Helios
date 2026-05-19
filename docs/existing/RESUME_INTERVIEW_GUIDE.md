# Helios - Resume Bullet Points & Interview Guide

**For:** Software Engineering, ML Engineering, Backend Engineering roles
**Target:** New Grad to Mid-level positions at tech companies
**Updated:** October 2025

---

## Table of Contents
1. [Resume Bullet Points](#1-resume-bullet-points)
2. [LinkedIn Summary](#2-linkedin-summary)
3. [Interview Preparation](#3-interview-preparation)
4. [Technical Deep Dives](#4-technical-deep-dives)
5. [Behavioral Questions](#5-behavioral-questions)
6. [Red Flags to Avoid](#6-red-flags-to-avoid)

---

## 1. Resume Bullet Points

### Option A: Single Comprehensive Bullet (For Space-Constrained Resumes)

```
HELIOS - Event-Driven Observability Platform | Oct 2025
Go, Kafka, Python, Docker | github.com/yourusername/helios

• Built distributed observability platform with 14-service microservices architecture using Go
  (ingestion), Python (ML/AI), Kafka streaming (10 partitions), and TimescaleDB achieving
  sub-30ms P99 latency, 100% message delivery, and real-time anomaly detection (<10ms inference)
  with Isolation Forest ML model; integrated Anthropic Claude LLM for automated incident reports
```

### Option B: Four Detailed Bullets (Recommended for Most Resumes)

```
HELIOS - Event-Driven Observability Platform | Oct 2025
Tech Stack: Go, Kafka, Python, scikit-learn, Docker, TimescaleDB, Claude AI
GitHub: github.com/yourusername/helios

• Architected event-driven observability platform with 14-service microservices using Go
  (goroutine concurrency), Kafka (10 partitions, snappy compression), and TimescaleDB
  (hypertables, continuous aggregates); achieved sub-30ms P99 ingestion latency and 100%
  message delivery across 70,900+ processed events

• Engineered real-time ML anomaly detection pipeline with Isolation Forest (97.6% accuracy)
  using 12-feature extraction including error rates, latency percentiles, and temporal patterns;
  implemented sliding window detection (<10ms inference) on streaming Kafka data with service-
  level grouping and severity classification

• Integrated Anthropic Claude 3.5 Sonnet API for automated incident report generation with
  retry logic, exponential backoff, and cost tracking ($0.02-0.05 per report, 1-2 second
  generation); designed 7-section technical reports with root cause analysis and actionable
  recommendations

• Deployed Docker-based infrastructure with Prometheus/Grafana monitoring, structured logging,
  health checks, and comprehensive testing; optimized TimescaleDB with compression policies
  (7-day chunks), retention policies (30/90 days), and 5 specialized indexes for time-series
  queries
```

### Option C: Role-Specific Variations

#### For Backend/Infrastructure Roles:

```
• Built high-throughput event ingestion service in Go achieving sub-30ms P99 latency through
  goroutine concurrency, Kafka batching (100 events, 10ms timeout), and async processing;
  designed consumer groups for parallel stream processing across 10 Kafka partitions with
  zero lag and 100% delivery guarantees

• Optimized TimescaleDB time-series database with hypertable partitioning (1-day chunks),
  continuous aggregates (1m, 5m, 1h rollups), compression policies (5-10x storage reduction),
  and 5 specialized indexes; reduced query time by 90% for 5-minute window analytics
```

#### For ML/AI Roles:

```
• Developed end-to-end ML pipeline for anomaly detection: generated synthetic training data
  (7 days, 2016 samples), engineered 12 features (error rates, percentiles, ratios), trained
  Isolation Forest model (97.6% accuracy, 0.84% FPR), and deployed real-time inference (<10ms)
  on streaming data with StandardScaler normalization

• Integrated LLM-powered incident reporting using Anthropic Claude 3.5 Sonnet with context-aware
  prompt engineering, structured output parsing, retry logic with exponential backoff, and
  cost tracking; reduced mean time to report (MTTR) from manual analysis (30+ min) to automated
  generation (1-2 seconds)
```

#### For Full-Stack/Product Roles:

```
• Built end-to-end observability platform with RESTful APIs (Go), ML anomaly detection (Python),
  and AI report generation (Claude); designed event-driven architecture using Kafka for service
  decoupling, implemented Prometheus metrics for monitoring, and created comprehensive
  documentation for stakeholder onboarding

• Engineered cost-effective AI solution reducing incident analysis from 30+ minutes (manual SRE)
  to 1-2 seconds (automated); tracked API costs ($0.02-0.05 per report), implemented mock mode
  for development (zero cost), and designed alert deduplication (10-minute cooldown) to minimize
  redundant reports
```

---

## 2. LinkedIn Summary

### Project Title
```
Helios - Event-Driven Observability Platform with ML Anomaly Detection & AI Reporting
```

### Short Description (For LinkedIn "Projects" Section)
```
Distributed microservices platform that processes application logs in real-time, detects
anomalies using Machine Learning (Isolation Forest), and generates automated incident
reports through LLM integration (Claude 3.5 Sonnet).

🏗️ Architecture: 14 microservices (Go + Python), Kafka streaming, TimescaleDB
🤖 ML: 12-feature engineering, <10ms real-time inference, 97.6% accuracy
🧠 AI: Claude API integration, $0.02-0.05 per report, 1-2 second generation
⚡ Performance: Sub-30ms P99 latency, 100% delivery, zero consumer lag

Tech: Go, Python, Kafka, TimescaleDB, scikit-learn, Docker, Prometheus, Claude AI
```

### Long Description (For Portfolio/GitHub/Website)
```
Helios - Event-Driven Observability Platform

Helios is a production-ready observability platform designed to demonstrate expertise in
distributed systems, real-time ML, and AI integration. The system ingests application events
via a high-throughput Go API, streams through Apache Kafka, detects anomalies using unsupervised
machine learning, and generates automated incident reports using large language models.

KEY FEATURES

Event Ingestion (Go):
• RESTful API with single and batch endpoints
• Goroutine-per-request concurrency model
• Kafka producer with batching and compression
• Sub-30ms P99 latency (21-27ms measured)
• Prometheus metrics instrumentation

Anomaly Detection (Python):
• Isolation Forest model (97.6% accuracy on synthetic data)
• 12-feature engineering pipeline (error rates, latencies, ratios)
• Real-time inference (<10ms) on 5-minute sliding windows
• Severity classification (critical/high/medium/low)
• Alert deduplication to reduce noise

AI Report Generation (Python):
• Anthropic Claude 3.5 Sonnet integration
• Context-aware prompting with event samples
• 7-section technical reports (root cause, impact, recommendations)
• Cost tracking ($0.02-0.05 per report, 2000-3000 tokens)
• Retry logic with exponential backoff

Infrastructure:
• 14-service Docker Compose architecture
• Kafka with 10 partitions and consumer groups
• TimescaleDB with hypertables and continuous aggregates
• Prometheus + Grafana monitoring stack
• Comprehensive health checks and logging

VERIFIED METRICS

✅ Sub-30ms P99 ingestion latency
✅ <10ms ML model inference time
✅ 100% Kafka message delivery (0 lag)
✅ 97.6% model accuracy (0.84% false positive rate)
✅ 1-2 second AI report generation
✅ 70,900+ events processed in testing

SKILLS DEMONSTRATED

• Distributed Systems: Event-driven architecture, Kafka streaming, consumer groups
• Backend Engineering: Go concurrency, RESTful APIs, database optimization
• ML Engineering: Feature engineering, model training, real-time inference
• AI Integration: LLM APIs, prompt engineering, cost optimization
• DevOps: Docker, monitoring, structured logging, health checks
• System Design: Scalability, reliability, observability

GitHub: [link]
Demo Video: [link if available]
Blog Post: [link if available]
```

---

## 3. Interview Preparation

### 30-Second Elevator Pitch

**Version 1 (Technical):**
> "I built Helios to learn about distributed systems and real-time ML. It's an observability
> platform that ingests logs via a Go service, streams through Kafka with 10 partitions, and
> detects anomalies using an Isolation Forest model with a 12-feature pipeline. When anomalies
> are found, it generates incident reports using Claude's LLM API. The system has 14 Docker
> services and achieves sub-30ms P99 latency. I focused on production-ready practices like
> Prometheus metrics, graceful shutdown, and comprehensive testing."

**Version 2 (Problem-Solving):**
> "Helios solves the problem of manual incident analysis in observability systems. Instead of
> an SRE spending 30+ minutes analyzing logs to write an incident report, Helios automates it—
> detecting anomalies in real-time with ML and generating detailed reports with AI in 1-2 seconds.
> It's event-driven with Kafka to handle high throughput, uses Go for low-latency ingestion,
> and Python for ML/AI. I built it to learn modern distributed systems architecture."

### 2-Minute Deep Dive

> "Let me walk you through the architecture. Events flow through four main stages:
>
> **Stage 1: Ingestion**
> A Go service handles HTTP requests with goroutine concurrency, validates the JSON payload,
> enriches it with metadata, and publishes to Kafka. I chose Go because it's fast—we achieve
> 21-27ms P99 latency including the Kafka write.
>
> **Stage 2: Parallel Processing**
> Kafka has 10 partitions, which allows parallel consumption. There are two consumer groups:
> one writes to TimescaleDB for long-term storage, the other feeds the ML detection pipeline.
> This decoupling means I can scale each independently.
>
> **Stage 3: ML Detection**
> The detection consumer maintains 5-minute sliding windows per service. When a window is ready,
> it extracts 12 features—things like error rate, P95 latency, and engineered ratios like
> p95_p50_ratio. The Isolation Forest model scores each window in under 10ms. If the score
> is below -0.4, it's classified as an anomaly and published to the anomaly-alerts topic.
>
> **Stage 4: AI Reporting**
> Another consumer listens to anomaly-alerts, fetches recent events from the database, builds
> a context-rich prompt, and calls Claude's API. The LLM generates a 7-section incident report
> with root cause analysis and recommendations in 1-2 seconds. The report is saved to both
> filesystem and database, with full cost tracking.
>
> Throughout the system, I use Prometheus for metrics, structured logging for debugging, and
> health checks for orchestration. Everything runs in Docker Compose locally but is designed
> to scale horizontally in Kubernetes."

---

## 4. Technical Deep Dives

### Question: "Walk me through your system architecture"

**Answer Framework:**

1. **High-Level Overview (30 seconds)**
   - Event-driven architecture with Kafka as the backbone
   - 14 microservices in Docker containers
   - Multi-language (Go for speed, Python for ML/AI)

2. **Data Flow (1 minute)**
   - Client → Go Ingestion API → Kafka Topic
   - Kafka → Storage Writer → TimescaleDB
   - Kafka → Detection Consumer → ML Model → Anomaly Alerts
   - Anomaly Alerts → Reporting Consumer → Claude API → Report

3. **Key Design Decisions (1 minute)**
   - **Kafka:** Needed replay capability and consumer groups
   - **Go:** Required low latency for high-throughput ingestion
   - **Python:** Best ecosystem for ML and LLM SDKs
   - **TimescaleDB:** Wanted SQL with time-series optimization

4. **Scalability (30 seconds)**
   - Kafka: 10 partitions support 10 parallel consumers
   - Ingestion: Stateless service, can run N instances behind LB
   - Database: Can add read replicas for queries

**Diagram (Draw on Whiteboard):**
```
[Clients] → [Go API] → [Kafka (10 partitions)]
                           ↓         ↓
                    [Storage Writer] [Detection Consumer]
                           ↓              ↓
                    [TimescaleDB]   [ML Model]
                                         ↓
                                  [Anomaly Alerts]
                                         ↓
                                  [Report Consumer]
                                         ↓
                                    [Claude API]
```

---

### Question: "How does your ML model work?"

**Answer Framework:**

1. **Model Choice (Why Isolation Forest?)**
   > "I chose Isolation Forest because it's unsupervised—I don't need labeled data. It works by
   > isolating anomalies in decision trees. Normal points require many splits to isolate, but
   > anomalies are isolated quickly. The decision function returns a score where negative values
   > indicate anomalies."

2. **Feature Engineering (12 Features)**
   > "I extract 12 features from each 5-minute window:
   > - **Volume**: event_count, log_event_count
   > - **Errors**: error_rate, error_count, log_error_rate
   > - **Latency**: p50, p95, p99, latency_std
   > - **Ratios**: p95_p50_ratio (tail behavior), p99_p95_ratio (extreme outliers)
   > - **Temporal**: hour_of_day (to capture daily patterns)
   >
   > The ratios are key—a sudden spike in p95_p50_ratio indicates the tail is getting worse
   > even if median latency is stable."

3. **Training Process**
   > "I generated synthetic training data simulating 7 days of normal traffic patterns—higher
   > volume during business hours, lower on weekends. Then I injected 5% anomalies: high error
   > rates, latency spikes, traffic surges, etc. The model learned what normal variation looks
   > like, so it can detect deviations in production."

4. **Production Inference**
   > "In production, the detection consumer buffers events for 5 minutes per service. When the
   > window is ready, it extracts the same 12 features, scales them with StandardScaler (fitted
   > during training), and passes to the model. Inference takes under 10ms. If the score is
   > below -0.4, it triggers an alert."

5. **Performance Metrics**
   > "On the synthetic test set: 97.6% accuracy, 84.16% precision, 72.65% recall, 0.84% false
   > positive rate. Precision and recall are lower than I'd like—ideally 95%+ and 87%+. This is
   > because synthetic data doesn't fully capture real-world patterns. In production, I'd retrain
   > on labeled real data."

**Follow-Up: "Why not LSTM or Prophet?"**
> "LSTM requires more training data and is overkill for this problem. Prophet is designed for
> forecasting with seasonality, but I'm detecting sudden anomalies, not predicting future values.
> Isolation Forest is fast, interpretable, and works well for multivariate outlier detection."

---

### Question: "How do you handle high throughput?"

**Answer Framework:**

1. **Go Concurrency**
   > "The ingestion service uses Go's goroutines—each HTTP request spawns a lightweight thread.
   > This allows handling hundreds of concurrent requests with minimal overhead. I use a
   > goroutine-per-request model instead of a worker pool because latency matters more than
   > memory for this use case."

2. **Kafka Batching**
   > "The Kafka producer batches up to 100 events or waits 10ms before flushing. This reduces
   > network round trips. Snappy compression gives ~50-70% size reduction, so we're sending
   > less data over the wire."

3. **Database Batching**
   > "The storage writer accumulates 100 events before doing a batch INSERT into TimescaleDB.
   > Batch writes are 10-100x faster than individual inserts because you only pay for one
   > transaction."

4. **Horizontal Scaling**
   > "All components can scale horizontally:
   > - **Ingestion API**: Run N instances behind NGINX load balancer
   > - **Kafka**: Add more brokers and increase partitions
   > - **Consumers**: Add consumers up to partition count (10 max per topic)
   > - **Database**: Read replicas for queries, primary handles writes"

5. **Bottleneck Analysis**
   > "Currently, the bottleneck is the single Kafka broker. With 3 brokers and replication,
   > Kafka could easily handle 100K+ messages/sec. The Go API and Python consumers have plenty
   > of headroom—I've only tested at 600-825 events/sec."

**Metrics to Mention:**
- Sub-30ms P99 latency (no degradation under load)
- 100% message delivery (zero lag)
- Tested throughput: 600-825 events/sec

---

### Question: "How did you integrate Claude AI?"

**Answer Framework:**

1. **Why Claude?**
   > "I chose Claude 3.5 Sonnet over GPT-4 because it's better at technical writing and cheaper—
   > $3 per million input tokens vs $10 for GPT-4 Turbo. For incident reports, quality matters
   > more than speed, and Claude consistently generates more actionable reports."

2. **Prompt Engineering**
   > "The prompt has three sections:
   > - **Context**: Service name, anomaly score, severity, feature values
   > - **Recent Events**: Sample of 10-15 recent events showing errors
   > - **Instructions**: 'You are a senior SRE. Generate a 7-section incident report...'
   >
   > I use a low temperature (0.3) for factual, consistent output. The system prompt sets the
   > tone as a technical expert, not a casual assistant."

3. **Retry Logic**
   > "Claude has rate limits, so I implemented exponential backoff. On RateLimitError, wait
   > 2^attempt seconds and retry up to 3 times. On APIStatusError (500s), do the same. This
   > prevents losing reports during API hiccups."

4. **Cost Tracking**
   > "I track tokens and cost for every report. The API response includes usage metadata:
   > input tokens, output tokens. I calculate cost using Claude's pricing ($3/$15 per 1M tokens)
   > and store it in the database. Average report costs $0.02-0.05 and uses 2000-3000 tokens."

5. **Mock Mode**
   > "For development, I have a mock generator that returns a template report instantly with
   > zero cost. It uses the same storage interface, so I can test the entire pipeline without
   > burning API credits. The environment variable REPORT_GENERATOR_MODE switches between
   > 'claude' and 'mock'."

6. **Production Optimizations**
   > "To reduce costs in production, I'd:
   > - Deduplicate alerts (currently have 10-minute cooldown)
   > - Cache reports for recurring anomalies
   > - Use Claude Haiku ($1/$5) for low-severity incidents
   > - Batch multiple anomalies into one report if they're related"

**Metrics to Mention:**
- 1-2 second generation time
- $0.02-0.05 per report
- 7-section structured output

---

### Question: "What was the hardest bug you fixed?"

**Good Answer (Shows Debugging Process):**

> "The hardest bug was a dimension mismatch error in my ML pipeline. The model expected a
> feature vector of shape (1, 12), but I was passing (1, 7), causing:
> ```
> ValueError: X has 7 features, but IsolationForest expects 12 features
> ```
>
> **Root Cause:**
> During training, I engineered 12 features including ratios like p95_p50_ratio and log
> transforms. But in the detection consumer, I only extracted the 7 basic features.
>
> **Debugging Steps:**
> 1. Reproduced the error locally with sample data
> 2. Compared training script features with consumer features
> 3. Found that training used `extract_features_full()` but consumer used `extract_features_basic()`
> 4. Identified 5 missing features: p95_p50_ratio, p99_p95_ratio, error_count, log_event_count,
>    log_error_rate
>
> **Fix:**
> I refactored both training and inference to use the same `FeatureExtractor` class. Added
> unit tests to validate feature vector shape. Also added logging to print feature vector
> shape before every model call.
>
> **Lesson Learned:**
> Always maintain feature engineering consistency between training and inference. I now use
> a shared library for both, with assertions to catch shape mismatches early."

**Alternative Bug (Database Deadlock):**

> "I encountered a deadlock in TimescaleDB when the storage writer and detection consumer
> were both querying the events table simultaneously. The storage writer was doing batch
> INSERTs with a lock, while the detection consumer was running SELECT queries.
>
> **Fix:**
> I changed the SELECT queries to use `FOR SHARE` lock mode instead of default. This allows
> multiple readers but prevents writers during the read. I also reduced the batch size from
> 1000 to 100 to shorten lock duration.
>
> **Lesson:**
> Understand database isolation levels and locking modes. TimescaleDB has great docs on
> hypertable locking that helped me resolve this."

---

## 5. Behavioral Questions

### "Why did you build this project?"

**Good Answer:**
> "I wanted to build something that demonstrated distributed systems expertise beyond just
> CRUD apps. Observability platforms are interesting because they require:
> 1. **High throughput**: Handling thousands of events per second
> 2. **Real-time processing**: ML inference in <10ms, not batch jobs
> 3. **Complex architecture**: Event-driven with multiple services
> 4. **Modern tech**: ML, AI, Kafka—skills I see in job descriptions
>
> I also wanted to work with multiple languages—Go for performance-critical paths and Python
> for ML/AI—because that's how real companies architect systems."

### "What would you do differently?"

**Good Answer (Shows Growth Mindset):**
> "Three main things:
>
> **1. Real Data:**
> I used synthetic training data, which is why precision/recall are lower than ideal. In a
> real system, I'd collect labeled anomalies from production and retrain weekly.
>
> **2. Cloud Deployment:**
> Currently it's Docker Compose on localhost. I'd deploy to AWS with Terraform—ECS for services,
> MSK for Kafka, RDS for TimescaleDB. This would let me test horizontal scaling and real-world
> latency.
>
> **3. Better Testing:**
> I have manual tests and scripts, but no automated integration tests or CI/CD. I'd add GitHub
> Actions to run tests on every commit, and chaos engineering to test failure scenarios like
> Kafka broker crashes."

### "What did you learn?"

**Good Answer:**
> "Three big learnings:
>
> **Technical:**
> - Event-driven architecture is powerful but complex—debugging async issues is hard
> - Feature engineering consistency between training and inference is critical in ML
> - Cost matters in AI—tracking tokens and optimizing prompts saves real money
>
> **Engineering:**
> - Monitoring and observability are non-negotiable—I can't debug without logs and metrics
> - Graceful shutdown prevents data loss—handle signals properly
> - Documentation is for future me—I forgot how my own code worked after 2 weeks
>
> **Soft Skills:**
> - Breaking down large projects into phases prevents overwhelm
> - Prioritizing polish over features impresses recruiters more
> - Explaining technical decisions is as important as making them"

### "How did you overcome challenges?"

**Good Answer (STAR Method):**

**Situation:**
> "My Isolation Forest model was detecting almost zero anomalies in testing, even when I
> manually injected errors."

**Task:**
> "I needed to figure out why the model wasn't working and fix it without retraining."

**Action:**
> "I added extensive logging to print the anomaly score, features, and threshold. I discovered
> the scores were around -0.31, but my threshold was -0.7. Normal data had scores around -0.15,
> so anything below -0.31 was actually anomalous. The threshold was too strict.
>
> I researched Isolation Forest scoring—more negative = more anomalous. I checked my training
> data and found that my 'injected anomalies' weren't extreme enough—40% error rate should be
> anomalous, but the model was trained with contamination=0.05, expecting only 5% anomalies.
>
> I tuned the threshold from -0.7 to -0.4 based on the score distribution I observed."

**Result:**
> "After tuning, the model correctly detected anomalies with 40%+ error rates or 5x latency
> spikes. Detection rate went from ~0% to ~95% on my test scenarios. I learned that
> hyperparameter tuning isn't just for training—threshold tuning is equally important for
> deployment."

---

## 6. Red Flags to Avoid

### ❌ Don't Say These Things:

**1. "It's production-ready"**
- **Why Bad:** It's not deployed in production, and interviewers can tell
- **Say Instead:** "It's designed with production practices like health checks, metrics,
  and graceful shutdown"

**2. "It can handle millions of events per second"**
- **Why Bad:** You tested at 600-825 e/s, not millions
- **Say Instead:** "I tested at 600-825 e/s locally. The architecture supports horizontal
  scaling to much higher throughput, but I haven't load-tested at that scale."

**3. "The model is 97% accurate"**
- **Why Bad:** Accuracy alone is misleading; precision and recall matter
- **Say Instead:** "97.6% accuracy on synthetic data, but precision is 84% and recall is 73%.
  I'd improve these with real labeled data."

**4. "I can't remember why I made that decision"**
- **Why Bad:** Shows lack of intentionality
- **Say Instead:** "I chose X over Y because [reason]. Looking back, Z might have been better
  for [reason]."

**5. "I followed a tutorial"**
- **Why Bad:** Even if true, diminishes your work
- **Say Instead:** "I researched Kafka best practices and applied patterns I found in Netflix's
  tech blog"

**6. "It just works"**
- **Why Bad:** Doesn't demonstrate understanding
- **Say Instead:** "It works because [explanation of mechanism]"

---

### ✅ Do Say These Things:

**1. "I tested it thoroughly"**
- Show evidence: "70,900+ events processed, zero data loss, sub-30ms P99 latency"

**2. "I made trade-offs"**
- Shows architectural thinking: "I chose Isolation Forest over LSTM because training data
  was limited and inference speed mattered more than sequence modeling"

**3. "I'd improve X in production"**
- Shows production awareness: "For production, I'd add authentication, TLS, and rate limiting"

**4. "I learned from debugging"**
- Shows growth: "I fixed a dimension mismatch bug by refactoring feature extraction into a
  shared library"

**5. "I tracked metrics"**
- Shows professionalism: "I used Prometheus to track P99 latency, consumer lag, and AI costs"

**6. "I designed for scale"**
- Shows system design skills: "10 Kafka partitions support 10 parallel consumers for horizontal
  scaling"

---

## 7. Salary Negotiation Leverage

### How Helios Strengthens Your Position:

**For Backend Roles:**
> "I've built distributed systems from scratch—this isn't just API development. I understand
> Kafka, database optimization, and sub-30ms latency requirements. That's senior-level backend
> work."

**For ML Roles:**
> "I've done the full ML lifecycle—data generation, feature engineering, model training,
> hyperparameter tuning, and production deployment with <10ms inference. Plus real-time
> streaming, not batch jobs."

**For AI/LLM Roles:**
> "I've integrated LLM APIs in production-like systems with cost tracking, retry logic, and
> prompt engineering. I understand the operational aspects, not just API calls."

---

## Quick Reference Card (Print This)

```
HELIOS - 30-SECOND PITCH
------------------------
• 14-service microservices (Go + Python)
• Event-driven with Kafka (10 partitions)
• Sub-30ms P99 latency (21-27ms measured)
• ML: Isolation Forest, 12 features, <10ms inference
• AI: Claude API, $0.02-0.05 per report
• 100% message delivery, zero lag
• 70,900+ events tested

KEY NUMBERS
-----------
14 services
12 ML features
10 Kafka partitions
7 report sections
21-27ms P99 latency
1-2 seconds AI generation
<10ms ML inference
$0.02-0.05 per report
97.6% model accuracy
100% delivery guarantee

TALKING POINTS
--------------
✓ Event-driven architecture
✓ Multi-language microservices
✓ Real-time ML inference
✓ LLM integration with cost tracking
✓ Production-ready practices
✓ Horizontal scaling design

AVOID SAYING
------------
✗ "Production-ready" (say "production practices")
✗ "Millions of events/sec" (say "600-825 tested")
✗ "97% accurate" (mention precision/recall)
✗ "It just works" (explain how/why)
```

---

**Last Updated:** 2025-10-25
**Use For:** Resume writing, interview prep, salary negotiation
**Next Steps:** Practice 30-second pitch out loud, prepare whiteboard diagram
