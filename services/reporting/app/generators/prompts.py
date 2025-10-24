"""Prompt templates for report generation"""

import json
from typing import Dict, Any
from app.generators.base import ReportContext


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
