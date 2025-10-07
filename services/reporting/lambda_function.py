"""
Helios Incident Report Generator - AWS Lambda Function

Generates AI-powered incident reports from anomaly alerts using GPT-4.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")

# Configuration from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
S3_BUCKET = os.getenv("REPORT_S3_BUCKET", "helios-incident-reports")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "helios")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def lambda_handler(event: Dict, context: any) -> Dict[str, any]:
    """
    AWS Lambda handler function.

    Triggered by Kafka anomaly-alerts topic via Lambda Event Source Mapping.

    Args:
        event: Lambda event containing Kafka records
        context: Lambda context object

    Returns:
        Response dictionary with status and metadata
    """
    logger.info(f"Received event with {len(event.get('records', {}))} records")

    try:
        # Parse Kafka records
        anomalies = []
        for topic_partition, records in event.get("records", {}).items():
            for record in records:
                # Decode base64-encoded Kafka message
                message_value = record.get("value", "")
                decoded_message = json.loads(message_value)
                anomalies.append(decoded_message)

        logger.info(f"Processed {len(anomalies)} anomalies")

        # Generate report for each anomaly
        reports_generated = []
        for anomaly in anomalies:
            try:
                report = generate_incident_report(anomaly)
                reports_generated.append(report)
            except Exception as e:
                logger.error(f"Failed to generate report for anomaly: {e}", exc_info=True)
                continue

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reports generated successfully",
                "anomalies_processed": len(anomalies),
                "reports_generated": len(reports_generated),
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "details": str(e),
            }),
        }


def generate_incident_report(anomaly: Dict) -> Dict[str, any]:
    """
    Generate AI-powered incident report from anomaly data.

    Args:
        anomaly: Anomaly data from detection service

    Returns:
        Dictionary containing report data and metadata
    """
    logger.info(f"Generating report for anomaly: {anomaly.get('id')}")

    # Extract anomaly details
    service = anomaly.get("service", "unknown")
    timestamp = anomaly.get("timestamp")
    score = anomaly.get("score", 0.0)
    severity = anomaly.get("severity", "UNKNOWN")

    # Fetch contextual data
    context = fetch_context_data(service, timestamp)

    # Build GPT-4 prompt
    prompt = build_prompt(anomaly, context)

    # Generate report using GPT-4
    report_content = call_gpt4_api(prompt)

    # Create report metadata
    report_id = f"{service}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    report_data = {
        "report_id": report_id,
        "anomaly_id": anomaly.get("id"),
        "service": service,
        "timestamp": timestamp,
        "severity": severity,
        "score": score,
        "content": report_content,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Store report in S3
    store_report_s3(report_id, report_content, service)

    # Store metadata in RDS (TODO: implement database storage)
    # store_report_metadata(report_data)

    logger.info(f"Report generated successfully: {report_id}")

    return report_data


def fetch_context_data(service: str, timestamp: str) -> Dict[str, any]:
    """
    Fetch contextual data from TimescaleDB for report generation.

    Args:
        service: Service name
        timestamp: Anomaly timestamp

    Returns:
        Dictionary with context data (events, metrics, deployments)
    """
    # TODO: Implement database queries
    # For now, return mock data

    logger.info(f"Fetching context for service={service}, timestamp={timestamp}")

    return {
        "recent_events": [],
        "error_logs": [],
        "metrics": {
            "event_count": 0,
            "error_rate": 0.0,
            "avg_latency": 0.0,
            "p99_latency": 0.0,
        },
        "deployments": [],
        "correlated_services": [],
    }


def build_prompt(anomaly: Dict, context: Dict) -> str:
    """
    Build GPT-4 prompt for incident report generation.

    Args:
        anomaly: Anomaly data
        context: Contextual data from database

    Returns:
        Formatted prompt string
    """
    service = anomaly.get("service", "unknown")
    timestamp = anomaly.get("timestamp", "unknown")
    score = anomaly.get("score", 0.0)
    severity = anomaly.get("severity", "UNKNOWN")
    features = anomaly.get("features", [])

    metrics = context.get("metrics", {})

    prompt = f"""
You are a senior Site Reliability Engineer analyzing a production incident.

**ANOMALY DETECTED:**
- Service: {service}
- Detected At: {timestamp}
- Severity: {severity}
- Anomaly Score: {score:.3f} (threshold: -0.7)

**METRICS AT TIME OF ANOMALY:**
- Event Count: {metrics.get('event_count', 'N/A')}
- Error Rate: {metrics.get('error_rate', 0):.2%}
- Average Latency: {metrics.get('avg_latency', 0):.0f}ms
- P99 Latency: {metrics.get('p99_latency', 0):.0f}ms

**RECENT ERROR LOGS:**
{format_error_logs(context.get('error_logs', []))}

**RECENT DEPLOYMENTS:**
{format_deployments(context.get('deployments', []))}

**CORRELATED SERVICES:**
{', '.join(context.get('correlated_services', ['None']))}

Generate a detailed incident report with the following structure:

## Executive Summary
Brief one-paragraph overview of the incident and its impact.

## Impact Assessment
- Affected components and dependencies
- Estimated user impact (if applicable)
- Business metrics affected

## Technical Analysis
- Root cause hypothesis (most likely explanation based on evidence)
- Supporting evidence from logs, metrics, and traces
- Timeline of events leading to the anomaly

## Recommended Actions
1. **Immediate**: Actions to mitigate the issue right now
2. **Short-term**: Investigation steps to confirm root cause
3. **Long-term**: Preventive measures to avoid recurrence

Be specific, technical, and actionable. Focus on evidence-based analysis.
"""

    return prompt


def call_gpt4_api(prompt: str) -> str:
    """
    Call OpenAI GPT-4 API to generate report.

    Args:
        prompt: Formatted prompt string

    Returns:
        Generated report content
    """
    # TODO: Implement actual OpenAI API call
    # For now, return mock report

    logger.info("Calling GPT-4 API")

    # Mock report for demonstration
    mock_report = """
## Executive Summary
An anomaly was detected in the payment-service showing elevated latency and error rates.
The issue appears to be related to database connection timeouts affecting checkout operations.

## Impact Assessment
- Affected Components: payment-service, checkout API
- Estimated User Impact: ~5% of checkout attempts failing
- Business Metrics: Conversion rate decreased by 3-5%

## Technical Analysis
**Root Cause Hypothesis**: Database connection pool exhaustion

**Supporting Evidence**:
- P99 latency increased from 200ms to 5000ms
- Error logs show "connection timeout" messages
- Recent deployment (v1.2.3) introduced new query patterns

**Timeline**:
- 10:30 AM: Deployment of v1.2.3
- 10:45 AM: Gradual increase in latency observed
- 11:00 AM: Anomaly detected by ML model

## Recommended Actions

### Immediate
1. Rollback to v1.2.2 to restore service
2. Increase database connection pool size temporarily
3. Monitor error rates and latency after rollback

### Short-term
1. Review database queries introduced in v1.2.3
2. Analyze slow query logs for optimization opportunities
3. Load test v1.2.3 in staging environment

### Long-term
1. Implement database connection pool monitoring alerts
2. Add pre-deployment load testing gate
3. Review and optimize ORM query patterns
4. Consider read replica for heavy read operations
"""

    logger.info("Report generated (using mock data)")

    return mock_report


def store_report_s3(report_id: str, content: str, service: str) -> str:
    """
    Store incident report in S3.

    Args:
        report_id: Unique report identifier
        content: Report content (Markdown)
        service: Service name

    Returns:
        S3 object key
    """
    object_key = f"{service}/{report_id}.md"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=content,
            ContentType="text/markdown",
            Metadata={
                "report_id": report_id,
                "service": service,
                "generated_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"Report stored in S3: s3://{S3_BUCKET}/{object_key}")
        return object_key

    except Exception as e:
        logger.error(f"Failed to store report in S3: {e}", exc_info=True)
        raise


def format_error_logs(error_logs: List[Dict]) -> str:
    """Format error logs for prompt"""
    if not error_logs:
        return "No recent error logs available"

    formatted = []
    for log in error_logs[:5]:  # Limit to 5 most recent
        formatted.append(f"- [{log.get('timestamp')}] {log.get('message')}")

    return "\n".join(formatted)


def format_deployments(deployments: List[Dict]) -> str:
    """Format deployment information for prompt"""
    if not deployments:
        return "No recent deployments"

    formatted = []
    for deployment in deployments[:3]:  # Limit to 3 most recent
        formatted.append(
            f"- {deployment.get('version')} deployed at {deployment.get('timestamp')}"
        )

    return "\n".join(formatted)


# For local testing
if __name__ == "__main__":
    # Mock event for testing
    test_event = {
        "records": {
            "anomaly-alerts-0": [
                {
                    "value": json.dumps({
                        "id": "test-anomaly-001",
                        "service": "payment-service",
                        "timestamp": datetime.utcnow().isoformat(),
                        "score": -0.85,
                        "severity": "HIGH",
                        "features": [1000, 0.15, 500, 1200, 2500, 350, 10],
                    })
                }
            ]
        }
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
