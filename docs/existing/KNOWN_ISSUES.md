# Known Issues - Helios Observability Platform

## Critical Issues Requiring Investigation

### 1. Isolation Forest Anomaly Score Sign Flip After Model Reload

**Issue ID:** HELIOS-ML-001
**Severity:** High
**Status:** Under Investigation
**Discovered:** 2025-10-26

#### Description

The Isolation Forest ML model exhibits inconsistent behavior where anomaly scores flip from negative to positive values after the detection consumer is restarted, even when analyzing the same event patterns.

#### Observed Behavior

**Before Consumer Restart:**
- Anomaly scores: **-0.17 to -0.20** (negative values)
- Detection threshold: **-0.32**
- Behavior: Events scored as "normal" because scores were above threshold
- Example: `payment-gateway-backup` with 53% error rate scored **-0.198** (severity: critical, but `is_anomaly: false`)

**After Consumer Restart (with same events):**
- Anomaly scores: **+0.09 to +0.13** (positive values)
- Detection threshold: **-0.16** (updated)
- Behavior: Events scored as "normal" with positive scores
- Example: Same service with similar patterns scored **+0.095** (severity: low, `is_anomaly: false`)

#### Technical Details

**Detection Consumer Configuration:**
```yaml
ANOMALY_THRESHOLD: -0.32  # Later changed to -0.16
WINDOW_SIZE_MINUTES: 1
MIN_EVENTS_PER_WINDOW: 3
CONTAMINATION: 0.05
MODEL_PATH: /app/models/isolation_forest.pkl
```

**Event Pattern:**
- Service: `payment-gateway-backup`
- Events in window: 15-60 events
- Error rate: 53.33% (8 ERROR/CRITICAL out of 15 total events)
- Expected: Should trigger anomaly detection
- Actual: Scored as non-anomalous

**Log Evidence:**
```json
// Before restart
{"service": "payment-gateway-backup", "is_anomaly": false, "score": -0.1980191032187918, "severity": "critical"}

// After restart (same event patterns)
{"service": "payment-gateway-backup", "is_anomaly": false, "score": 0.09587324962720323, "severity": "low"}
```

#### Root Cause Analysis (In Progress)

**Hypotheses:**

1. **Sklearn Version Mismatch**
   - Model may have been trained with different sklearn version than runtime
   - Isolation Forest `score_samples()` implementation changed between versions
   - Sign convention: Some versions return negative scores (lower = more anomalous), others positive

2. **Feature Engineering Inconsistency**
   - Features extracted during training may differ from runtime feature extraction
   - Possible missing/additional features causing dimension mismatch
   - Feature scaling not persisted with model

3. **Model Serialization Issue**
   - Pickle serialization may not preserve all model state
   - Random state or tree structure corruption during save/load
   - Volume mount timing issues causing incomplete model file reads

4. **Training Data Distribution**
   - Model trained on recent "normal" data that includes high error rates
   - What appears anomalous (53% errors) is actually "normal" in training distribution
   - Contamination parameter (0.05) may be too low for this use case

#### Impact

**Business Impact:**
- ❌ Anomaly detection system is non-functional
- ❌ Critical incidents (53% error rate) go undetected
- ❌ No automated incident reports generated
- ❌ Screenshot demo for recruiters cannot show ML detection in action

**Technical Impact:**
- Threshold tuning is ineffective (scores change sign unpredictably)
- Cannot reliably demonstrate real-time anomaly detection
- Reporting pipeline never triggers (depends on anomaly alerts)

#### Reproduction Steps

1. Start Helios platform with fresh containers
2. Train ML model: `curl -X POST http://localhost:8000/api/v1/train`
3. Start detection consumer: `docker-compose up -d detection-consumer`
4. Inject mixed events (80% INFO, 20% ERROR)
5. Observe scores: Record score values (likely negative)
6. Restart detection consumer: `docker-compose restart detection-consumer`
7. Inject same event pattern
8. Observe scores: Values flip to positive

#### Workaround (Temporary)

For demonstration purposes:
1. Use **high anomaly injection** (95% error rate) to force detection
2. **Manual API trigger**: Call detection API directly with test data
3. **Mock mode**: Use `REPORT_GENERATOR_MODE=mock` (already enabled)

#### Recommended Fixes

**Short-term (for demo):**
1. ✅ Switch to 95% error rate simulation
2. ✅ Document issue for future fix
3. ⚠️ Lower threshold to 0.0 and use positive scores
4. ⚠️ Use absolute value: `abs(score) > threshold`

**Long-term (production-ready):**
1. 🔧 **Upgrade sklearn**: Pin to latest stable version, retrain model
2. 🔧 **Feature engineering audit**: Document exact features, add validation
3. 🔧 **Model versioning**: Add metadata to model file (sklearn version, feature schema, training date)
4. 🔧 **Score normalization**: Convert all scores to consistent 0-1 range
5. 🔧 **Alternative algorithm**: Consider LSTM autoencoder or Prophet for time-series anomaly detection
6. 🔧 **Dynamic thresholding**: Use percentile-based thresholds instead of fixed values
7. 🔧 **Integration tests**: Add tests that verify score sign consistency across restarts

#### Related Files

- `services/detection/app/ml/anomaly_detector.py` - ML model implementation
- `services/detection/app/consumers/detection_consumer.py:150` - Threshold comparison logic
- `services/detection/requirements.txt` - Sklearn version specification
- `docker-compose.yml:224` - ANOMALY_THRESHOLD configuration

#### Testing Checklist (When Fixed)

- [ ] Train model on known dataset with labeled anomalies
- [ ] Verify score sign consistency before/after consumer restart
- [ ] Test with 0%, 25%, 50%, 75%, 100% error rates
- [ ] Confirm threshold actually filters anomalies correctly
- [ ] Validate anomaly alerts published to Kafka topic
- [ ] End-to-end test: anomaly → detection → alert → report → PDF

#### Additional Notes

This issue blocks the primary value proposition of Helios: **real-time ML-powered anomaly detection with AI-generated reports**. Without reliable anomaly detection, the reporting pipeline never triggers.

**Current workaround for screenshots:** Generate 95% error rate to force any model variant to detect anomalies, or use direct API calls to generate reports manually.

---

## Minor Issues

### 2. TimescaleDB Datasource YAML Provisioning Not Working in Grafana

**Issue ID:** HELIOS-VIZ-001
**Severity:** Medium
**Status:** Workaround Implemented

#### Description
Grafana datasources provisioned via YAML for PostgreSQL/TimescaleDB connections pass health checks but queries never execute in dashboards.

**Workaround:** Manually add "TimescaleDB-Direct" datasource through Grafana UI.

**Impact:** Requires manual setup step for database metrics panels.

---

### 3. Storage Writer Event Lag

**Issue ID:** HELIOS-STORAGE-001
**Severity:** Low
**Status:** Observed, Needs Monitoring

#### Description
Events sent to ingestion API may take 5-10 seconds to appear in TimescaleDB, especially after burst traffic (150+ events in <10 seconds).

**Observed:** 150 ERROR/CRITICAL events for `payment-gateway` sent via API did not appear in database query after 15 seconds.

**Hypothesis:**
- Kafka consumer batch timeout (1000ms) causes processing delay
- Database connection pool saturation during bursts
- Transaction commit timing

**Impact:** Minor - affects only immediate query results, data eventually persists.

---

**Last Updated:** 2025-10-26
**Maintainer:** Engineering Team
