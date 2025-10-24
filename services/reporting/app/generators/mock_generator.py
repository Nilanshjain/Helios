"""Mock report generator for development/testing without AI API costs"""

import time
from typing import Dict, Any
from app.core.logging import get_logger
from app.generators.base import ReportGenerator, ReportContext, ReportResult

logger = get_logger(__name__)


class MockGenerator(ReportGenerator):
    """
    Generate template-based mock reports for development and testing.
    No external API calls, zero cost, instant generation.
    """

    def __init__(self) -> None:
        """Initialize mock generator"""
        logger.info("mock_generator_initialized", mode="mock")

    def generate(self, context: ReportContext) -> ReportResult:
        """Generate a mock report from template"""
        start_time = time.time()

        anomaly = context.anomaly
        metrics = context.metrics
        events = context.events

        # Extract key data
        anomaly_id = anomaly.get('id', 'unknown')
        service = anomaly.get('service', 'unknown-service')
        anomaly_score = anomaly.get('anomaly_score', 0.0)
        detected_at = anomaly.get('detected_at', 'unknown')

        # Get key metrics
        error_rate = metrics.get('error_rate', 0.0)
        total_events = metrics.get('total_events', 0)
        avg_latency = metrics.get('avg_latency', 0.0)
        p99_latency = metrics.get('p99_latency', 0.0)

        # Determine severity based on anomaly score
        if anomaly_score < -0.8:
            severity = "Critical"
        elif anomaly_score < -0.7:
            severity = "High"
        elif anomaly_score < -0.5:
            severity = "Medium"
        else:
            severity = "Low"

        # Count error events
        error_count = sum(1 for e in events if e.get('level') in ['ERROR', 'CRITICAL'])

        # Generate mock report
        report_content = self._generate_mock_report(
            anomaly_id=anomaly_id,
            service=service,
            detected_at=detected_at,
            severity=severity,
            anomaly_score=anomaly_score,
            error_rate=error_rate,
            total_events=total_events,
            error_count=error_count,
            avg_latency=avg_latency,
            p99_latency=p99_latency,
        )

        report_id = f"mock_report_{anomaly_id}_{int(time.time())}"
        generation_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "mock_report_generated",
            report_id=report_id,
            time_ms=generation_time_ms,
        )

        return ReportResult(
            report_id=report_id,
            content=report_content,
            format="markdown",
            tokens_used=0,  # No tokens for mock
            cost_usd=0.0,   # No cost for mock
            generation_time_ms=generation_time_ms,
            metadata={
                "generator": "mock",
                "severity": severity,
                "service": service,
            },
        )

    def _generate_mock_report(
        self,
        anomaly_id: str,
        service: str,
        detected_at: str,
        severity: str,
        anomaly_score: float,
        error_rate: float,
        total_events: int,
        error_count: int,
        avg_latency: float,
        p99_latency: float,
    ) -> str:
        """Generate mock report template"""

        report = f"""# Incident Report: {anomaly_id}

**Generated**: {detected_at}
**Service**: `{service}`
**Severity**: {severity}
**Anomaly Score**: {anomaly_score:.3f}

---

## 1. Executive Summary

An anomaly was detected in the `{service}` service with a **{severity}** severity rating. The ML-powered detection system identified unusual patterns in system metrics that deviate significantly from normal baseline behavior.

**Key Findings:**
- Error rate elevated to {error_rate:.2%}
- {error_count} error events detected out of {total_events} total events
- Average latency: {avg_latency:.2f}ms
- P99 latency: {p99_latency:.2f}ms

---

## 2. Technical Analysis

### What Happened
The anomaly detection system identified abnormal behavior in the following metrics:

1. **Error Rate**: {error_rate:.2%} (threshold: normal < 5%)
2. **Event Volume**: {total_events} events in detection window
3. **Latency Metrics**:
   - Average: {avg_latency:.2f}ms
   - P99: {p99_latency:.2f}ms

### Timeline
- **Detection Time**: {detected_at}
- **Affected Service**: {service}
- **Anomaly Score**: {anomaly_score:.3f} (lower scores indicate higher anomaly)

---

## 3. Root Cause Hypothesis

Based on the detected patterns, possible root causes include:

**Most Likely:**
- Elevated error rate suggesting downstream service issues
- Potential database connection pool exhaustion
- Recent deployment or configuration change

**Evidence:**
- Anomaly score of {anomaly_score:.3f} indicates significant deviation
- Error rate {error_rate:.2%} exceeds normal baseline
- {error_count} error events clustered in time window

**Confidence Level**: Medium (automated analysis, requires human validation)

---

## 4. Impact Assessment

### Services Affected
- Primary: `{service}`
- Downstream: Unknown (requires investigation)

### User Impact
- **Estimated Impact**: {severity} severity
- **Error Rate**: {error_rate:.2%} of requests affected
- **Latency**: P99 at {p99_latency:.2f}ms may impact user experience

### Business Implications
- Service degradation detected
- Potential customer-facing impact
- SLA compliance may be affected

---

## 5. Immediate Actions Taken

The following automated actions have been executed:

1. ✅ Anomaly detected and logged
2. ✅ Incident report generated
3. ✅ On-call team notified (if Slack configured)
4. ⏳ Awaiting human investigation

**Current System State**: Under observation

---

## 6. Recommended Actions

### Immediate (Next 1 hour)
- [ ] Review service logs for the detection window
- [ ] Check recent deployments or config changes
- [ ] Verify downstream service health
- [ ] Assess if rollback is needed

### Short-term (Next 24-72 hours)
- [ ] Analyze root cause with application logs
- [ ] Review database connection pool metrics
- [ ] Check for memory leaks or resource exhaustion
- [ ] Update monitoring thresholds if needed

### Long-term (Next 1-4 weeks)
- [ ] Implement circuit breakers if not present
- [ ] Add more granular error tracking
- [ ] Review and optimize service architecture
- [ ] Conduct post-mortem analysis

---

## 7. Monitoring & Follow-up

### What to Monitor
- Error rate for `{service}` (target: < 1%)
- Latency metrics (P50, P95, P99)
- Resource utilization (CPU, memory, connections)
- Downstream service health

### When to Escalate
- Error rate > 10% for > 5 minutes
- P99 latency > 1000ms sustained
- Complete service outage
- Customer complaints increase

### Expected Resolution
- **Investigation**: 1-2 hours
- **Fix deployment**: 2-4 hours
- **Full resolution**: 4-8 hours

---

## Notes

⚠️ **This is a MOCK report generated by template for development purposes.**

For production deployments, configure Claude AI generator with `REPORT_GENERATOR_MODE=claude` and `ANTHROPIC_API_KEY` for detailed, AI-powered incident analysis.

---

*Report generated by Helios Observability Platform*
*Anomaly Detection System - Mock Generator v1.0*
"""

        return report

    def health_check(self) -> bool:
        """Mock generator is always healthy"""
        return True
