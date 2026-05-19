"""Prompt templates for report generation"""

import json
from typing import Dict, Any, List
from app.generators.base import ReportContext


def build_structured_prompt(context: ReportContext) -> str:
    """SHAP-aware prompt that asks the LLM to return JSON matching IncidentReport.

    Used by both ``GeminiGenerator`` (with ``response_schema``) and
    ``ClaudeGenerator`` (with an explicit "JSON only" instruction). The top
    SHAP features from the detection layer are injected into the prompt so
    the root-cause hypothesis can be grounded in concrete attributions
    instead of generic SRE boilerplate.
    """
    anomaly = context.anomaly
    metrics = context.metrics
    events = context.events
    top_features: List[Dict[str, Any]] = anomaly.get("top_features", []) or []

    feature_block_lines: list[str] = []
    if top_features:
        feature_block_lines.append("SHAP attributions (top features driving the anomaly score):")
        for f in top_features:
            direction = f.get("direction", "unknown")
            feature_block_lines.append(
                f"  - {f.get('name', '?')}: value={f.get('value', float('nan')):.3f}, "
                f"shap={f.get('shap', 0.0):+.3f} ({direction})"
            )
        feature_block_lines.append(
            "Negative SHAP pushes the IsolationForest score lower (more anomalous); "
            "positive SHAP pulls toward normal."
        )
    else:
        feature_block_lines.append(
            "No SHAP attributions available — reason from the raw feature dict below only."
        )
    shap_block = "\n".join(feature_block_lines)

    return f"""You are a senior SRE writing an incident report from ML-detected anomaly evidence.

## Anomaly evidence
- Incident ID: {anomaly.get('id', 'unknown')}
- Service: {anomaly.get('service', 'unknown')}
- Detected at: {anomaly.get('timestamp', 'unknown')}
- Severity: {anomaly.get('severity', 'unknown')}
- IsolationForest score: {anomaly.get('score', 0):.3f} (threshold {anomaly.get('threshold', 0):.3f})

## Top contributing features
{shap_block}

## Window-level feature values
```json
{json.dumps(anomaly.get('features', {}), indent=2)}
```

## Aggregated service metrics during the window
{_format_metrics(metrics)}

## Sample events ({min(len(events), 10)} of {len(events)})
{_format_events(events[:10])}

## Required output
Respond with **JSON only** (no markdown fences, no commentary) matching this schema:

{{
  "incident_id": "{anomaly.get('id', 'unknown')}",
  "service": "{anomaly.get('service', 'unknown')}",
  "detected_at": "{anomaly.get('timestamp', 'unknown')}",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "confidence": 0.0-1.0,
  "executive_summary": "2-3 sentences for the oncall pager.",
  "root_cause_hypothesis": "Specific hypothesis explicitly referencing the top SHAP feature names by name.",
  "contributing_features": [
    {{"name": "<feature>", "value": <number>, "shap": <number>, "direction": "toward_anomaly|toward_normal"}}
  ],
  "recommended_actions": [
    {{"timeframe": "immediate|short_term|long_term", "action": "concrete step", "rationale": "evidence-grounded reason"}}
  ],
  "monitoring_checks": ["signal_or_metric_name_1", "..."]
}}

Constraints:
- The root_cause_hypothesis MUST reference at least one feature name from the SHAP block above.
- recommended_actions MUST include at least one item per timeframe.
- Severity MUST be one of LOW, MEDIUM, HIGH, CRITICAL (uppercase).
- Confidence is your honest estimate, not a fixed value.
- Do not invent metrics that aren't in the evidence."""


def build_incident_report_prompt(context: ReportContext) -> str:
    """
    Build a comprehensive prompt for Claude to generate an incident report.

    Args:
        context: ReportContext with anomaly, events, metrics, and recent_anomalies

    Returns:
        Formatted prompt string for LLM
    """

    anomaly = context.anomaly
    events = context.events
    metrics = context.metrics
    recent_anomalies = context.recent_anomalies

    # Format anomaly details
    anomaly_id = anomaly.get('id', 'unknown')
    detection_time = anomaly.get('detected_at', 'unknown')
    anomaly_score = anomaly.get('anomaly_score', 0)
    service_name = anomaly.get('service', 'unknown')
    window_start = anomaly.get('window_start', 'unknown')
    window_end = anomaly.get('window_end', 'unknown')

    # Format metrics
    metrics_summary = _format_metrics(metrics)

    # Format events sample
    events_sample = _format_events(events[:10])  # First 10 events

    # Format recent anomaly patterns
    recent_pattern = _format_recent_anomalies(recent_anomalies)

    prompt = f"""You are analyzing a production incident detected by our ML-powered anomaly detection system.

## Incident Overview
- **Incident ID**: {anomaly_id}
- **Detection Time**: {detection_time}
- **Anomaly Score**: {anomaly_score:.3f}
- **Affected Service**: {service_name}
- **Time Window**: {window_start} to {window_end}

## System Metrics During Incident
{metrics_summary}

## Sample Events (First 10)
{events_sample}

## Recent Anomaly Context
{recent_pattern}

## Your Task
Generate a comprehensive incident report with the following sections:

### 1. Executive Summary
- Brief overview (2-3 sentences)
- Severity assessment (Critical/High/Medium/Low)
- Primary impact

### 2. Technical Analysis
- What happened (technical details)
- Key metrics that deviated from normal
- Timeline of the incident

### 3. Root Cause Hypothesis
- Most likely root cause(s)
- Evidence supporting your hypothesis
- Confidence level

### 4. Impact Assessment
- Services affected
- User impact (estimated)
- Business implications

### 5. Immediate Actions Taken
- What was done to mitigate
- Current system state

### 6. Recommended Actions
**Immediate (Next 1 hour):**
- Action items to stabilize the system

**Short-term (Next 24-72 hours):**
- Investigation steps
- Monitoring improvements

**Long-term (Next 1-4 weeks):**
- Preventive measures
- System improvements

### 7. Monitoring & Follow-up
- What to monitor
- When to escalate
- Expected resolution time

Keep the report technical but clear. Use markdown formatting. Be specific and actionable."""

    return prompt


def _format_metrics(metrics: Dict[str, Any]) -> str:
    """Format metrics dictionary into readable text"""
    if not metrics:
        return "No metrics available"

    lines = []
    for key, value in metrics.items():
        # Format key to be more readable
        readable_key = key.replace('_', ' ').title()

        # Format value based on type
        if isinstance(value, float):
            formatted_value = f"{value:.2f}"
        elif isinstance(value, int):
            formatted_value = f"{value:,}"
        else:
            formatted_value = str(value)

        lines.append(f"- **{readable_key}**: {formatted_value}")

    return "\n".join(lines)


def _format_events(events: list) -> str:
    """Format events list into readable text"""
    if not events:
        return "No events available"

    lines = []
    for i, event in enumerate(events, 1):
        timestamp = event.get('timestamp', 'N/A')
        level = event.get('level', 'INFO')
        service = event.get('service', 'unknown')
        message = event.get('message', 'No message')

        # Truncate long messages
        if len(message) > 100:
            message = message[:97] + "..."

        lines.append(f"{i}. [{timestamp}] {level} - {service}: {message}")

    return "\n".join(lines)


def _format_recent_anomalies(recent_anomalies: list) -> str:
    """Format recent anomalies into readable text"""
    if not recent_anomalies:
        return "No recent anomalies detected in the past 24 hours."

    lines = [f"Detected {len(recent_anomalies)} anomalies in the past 24 hours:\n"]

    for i, anomaly in enumerate(recent_anomalies[:5], 1):  # Show up to 5 recent
        detected_at = anomaly.get('detected_at', 'N/A')
        service = anomaly.get('service', 'unknown')
        score = anomaly.get('anomaly_score', 0)

        lines.append(f"{i}. [{detected_at}] {service} - Score: {score:.3f}")

    if len(recent_anomalies) > 5:
        lines.append(f"\n... and {len(recent_anomalies) - 5} more")

    return "\n".join(lines)
