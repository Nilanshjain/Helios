"""
Generate realistic demo data for Helios dashboard demonstration.

This script populates the database with:
- Diverse microservices (14 services)
- Varied event levels and patterns
- Multiple anomalies with different severities
- Realistic timestamps over the past 7 days
"""

import psycopg2
import random
from datetime import datetime, timedelta
import json

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,  # Docker port mapping: 5433:5432
    'database': 'helios',
    'user': 'postgres',
    'password': 'postgres'
}

# Microservices in the system
SERVICES = [
    'api-gateway',
    'auth-service',
    'user-service',
    'order-service',
    'inventory-service',
    'payment-service',
    'notification-service',
    'analytics-service',
    'search-service',
    'recommendation-engine',
    'data-pipeline',
    'cache-service',
    'email-worker',
    'image-processor'
]

# Event levels with realistic distribution
LEVEL_DISTRIBUTION = {
    'DEBUG': 0.15,
    'INFO': 0.60,
    'WARN': 0.15,
    'ERROR': 0.08,
    'CRITICAL': 0.02
}

# Sample messages for realism
MESSAGES = {
    'DEBUG': [
        'Processing request with correlation_id: {}',
        'Cache hit for key: {}',
        'Query executed in {}ms',
        'Connection pool size: {}',
    ],
    'INFO': [
        'Request completed successfully',
        'User authenticated: {}',
        'Order created: {}',
        'Payment processed successfully',
        'Email sent to user {}',
        'Cache refreshed for endpoint {}',
        'Database migration completed',
        'Health check passed',
    ],
    'WARN': [
        'High memory usage detected: {}%',
        'Slow query detected: {}ms',
        'Rate limit approaching: {} requests/min',
        'Connection pool near capacity',
        'Cache miss rate elevated: {}%',
        'Retry attempt #{} for request',
    ],
    'ERROR': [
        'Failed to connect to database: {}',
        'Payment gateway timeout after {}ms',
        'Invalid request payload: {}',
        'User authentication failed for {}',
        'Email delivery failed: {}',
        'API rate limit exceeded',
        'Database query timeout',
        'Third-party API error: {}',
    ],
    'CRITICAL': [
        'Database connection pool exhausted',
        'Out of memory: {}% heap used',
        'Circuit breaker opened for {}',
        'Service unhealthy: failing health checks',
        'Disk space critical: {}% remaining',
        'SSL certificate expiring in {} days',
    ]
}

def get_random_message(level):
    """Get random message template for level"""
    template = random.choice(MESSAGES[level])
    # Fill in placeholders with random data
    if '{}' in template:
        if 'correlation_id' in template:
            return template.format(f'corr-{random.randint(10000, 99999)}')
        elif 'ms' in template:
            return template.format(random.randint(100, 5000))
        elif '%' in template:
            return template.format(random.randint(50, 95))
        elif 'user' in template.lower():
            return template.format(f'user_{random.randint(1000, 9999)}')
        elif 'Order' in template or 'order' in template:
            return template.format(f'ORD-{random.randint(100000, 999999)}')
        else:
            return template.format(f'value_{random.randint(1, 100)}')
    return template

def generate_metadata(service, level):
    """Generate realistic metadata for event"""
    metadata = {
        'environment': 'production',
        'region': random.choice(['us-east-1', 'us-west-2', 'eu-west-1']),
        'version': f'v{random.randint(1, 5)}.{random.randint(0, 20)}.{random.randint(0, 10)}',
    }

    # Add service-specific metadata
    if level in ['ERROR', 'CRITICAL']:
        metadata['error_code'] = f'ERR_{random.randint(1000, 9999)}'

    if 'payment' in service.lower():
        metadata['payment_method'] = random.choice(['credit_card', 'debit_card', 'paypal'])
        metadata['transaction_id'] = f'TXN-{random.randint(100000, 999999)}'

    if 'api' in service.lower() or 'gateway' in service.lower():
        metadata['endpoint'] = random.choice(['/api/v1/users', '/api/v1/orders', '/api/v1/payments'])
        metadata['http_method'] = random.choice(['GET', 'POST', 'PUT', 'DELETE'])
        metadata['status_code'] = random.choice([200, 201, 400, 404, 500]) if level == 'ERROR' else 200

    return metadata

def insert_events(conn, num_events=10000):
    """Insert realistic events over the past 7 days"""
    cursor = conn.cursor()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    print(f"Generating {num_events} events from {start_time} to {end_time}...")

    events = []
    for i in range(num_events):
        # Random timestamp within the past 7 days
        time_offset = random.random() * 7 * 24 * 60 * 60  # seconds
        timestamp = end_time - timedelta(seconds=time_offset)

        # Select service and level with realistic distribution
        service = random.choice(SERVICES)
        level = random.choices(
            list(LEVEL_DISTRIBUTION.keys()),
            weights=list(LEVEL_DISTRIBUTION.values())
        )[0]

        message = get_random_message(level)
        metadata = generate_metadata(service, level)

        # Generate host
        host = f'{service}-pod-{random.randint(1, 5)}'

        # Random trace IDs for some events
        trace_id = f'trace-{random.randint(100000, 999999)}' if random.random() > 0.7 else None
        span_id = f'span-{random.randint(100000, 999999)}' if trace_id else None

        events.append((
            timestamp,
            service,
            level,
            message,
            json.dumps(metadata),
            trace_id,
            span_id,
            host,
            timestamp + timedelta(milliseconds=random.randint(1, 50))  # ingested_at
        ))

        if (i + 1) % 1000 == 0:
            print(f"  Generated {i + 1}/{num_events} events...")

    # Bulk insert
    print("Inserting events into database...")
    cursor.executemany("""
        INSERT INTO events (time, service, level, message, metadata, trace_id, span_id, host, ingested_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, events)

    conn.commit()
    print(f"√ Successfully inserted {num_events} events")
    cursor.close()

def insert_anomalies(conn, num_anomalies=15):
    """Insert diverse anomalies with realistic patterns"""
    cursor = conn.cursor()

    print(f"\nGenerating {num_anomalies} anomalies...")

    severities = {
        'CRITICAL': 0.20,
        'HIGH': 0.35,
        'MEDIUM': 0.30,
        'LOW': 0.10,
        'INFO': 0.05
    }

    anomalies = []
    for i in range(num_anomalies):
        severity = random.choices(
            list(severities.keys()),
            weights=list(severities.values())
        )[0]

        service = random.choice(SERVICES)
        timestamp = datetime.now() - timedelta(
            hours=random.randint(1, 168)  # Past week
        )

        # Generate realistic feature values based on severity
        if severity in ['CRITICAL', 'HIGH']:
            features = {
                'cpu_usage': random.uniform(0.85, 0.99),
                'memory_usage': random.uniform(0.80, 0.95),
                'error_rate': random.uniform(0.30, 0.70),
                'latency_ms': random.uniform(2000, 8000),
                'request_rate': random.uniform(500, 2000)
            }
            score = random.uniform(-0.95, -0.75)
            confidence = random.uniform(0.85, 0.98)
        elif severity == 'MEDIUM':
            features = {
                'cpu_usage': random.uniform(0.65, 0.85),
                'memory_usage': random.uniform(0.60, 0.80),
                'error_rate': random.uniform(0.15, 0.30),
                'latency_ms': random.uniform(1000, 2000),
                'request_rate': random.uniform(300, 500)
            }
            score = random.uniform(-0.75, -0.60)
            confidence = random.uniform(0.70, 0.85)
        else:
            features = {
                'cpu_usage': random.uniform(0.50, 0.65),
                'memory_usage': random.uniform(0.45, 0.60),
                'error_rate': random.uniform(0.05, 0.15),
                'latency_ms': random.uniform(500, 1000),
                'request_rate': random.uniform(100, 300)
            }
            score = random.uniform(-0.60, -0.50)
            confidence = random.uniform(0.60, 0.75)

        is_resolved = random.random() > 0.4  # 60% resolved
        resolved_at = timestamp + timedelta(hours=random.randint(1, 24)) if is_resolved else None

        anomalies.append((
            f'anomaly_{service}_{int(timestamp.timestamp())}',
            timestamp,
            service,
            score,
            -0.7,  # threshold
            severity,
            json.dumps(features),
            confidence,
            is_resolved,
            resolved_at
        ))

    cursor.executemany("""
        INSERT INTO anomalies (anomaly_id, time, service, score, threshold, severity, features, confidence, is_resolved, resolved_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (anomaly_id) DO NOTHING
    """, anomalies)

    conn.commit()
    print(f"√ Successfully inserted {num_anomalies} anomalies")
    cursor.close()

def insert_reports(conn, num_reports=20):
    """Insert AI-generated incident reports"""
    cursor = conn.cursor()

    print(f"\nGenerating {num_reports} incident reports...")

    # Get anomaly IDs
    cursor.execute("SELECT anomaly_id, service, severity FROM anomalies ORDER BY time DESC LIMIT %s", (num_reports,))
    anomalies = cursor.fetchall()

    reports = []
    for anomaly_id, service, severity in anomalies:
        timestamp = datetime.now() - timedelta(hours=random.randint(1, 168))
        report_id = f'report_{anomaly_id}'

        # Realistic token usage and costs
        tokens = random.randint(1500, 4000)
        cost = tokens * 0.000003  # $3 per 1M tokens (Claude 3.5 Sonnet)
        generation_time = random.randint(3000, 8000)  # ms

        markdown_path = f'{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{report_id}.markdown'
        pdf_path = f'{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{report_id}.pdf'

        # Sample markdown content
        content = f"""# Incident Report: {anomaly_id}

## Executive Summary
Anomaly detected in {service} with {severity} severity.

## Technical Analysis
- Service: {service}
- Severity: {severity}
- Detection Time: {timestamp.isoformat()}

## Recommendations
1. Investigate resource usage patterns
2. Review recent deployments
3. Monitor for similar patterns

---
Generated by Claude AI
"""

        reports.append((
            report_id,
            anomaly_id,
            service,
            severity,
            markdown_path,
            pdf_path,
            content,
            tokens,
            cost,
            generation_time,
            'claude-3-5-sonnet-20241022',
            timestamp,
            len(content.encode('utf-8'))
        ))

    cursor.executemany("""
        INSERT INTO incident_reports
        (report_id, anomaly_id, service, severity, markdown_path, pdf_path, content, tokens_used, cost_usd, generation_time_ms, model, generated_at, size_bytes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (report_id) DO NOTHING
    """, reports)

    conn.commit()
    print(f"√ Successfully inserted {num_reports} reports")
    cursor.close()

def main():
    """Main execution"""
    print("=" * 60)
    print("Helios Demo Data Generator")
    print("=" * 60)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("√ Connected to database\n")

        # Generate data
        insert_events(conn, num_events=15000)  # 15K events
        insert_anomalies(conn, num_anomalies=25)  # 25 anomalies
        insert_reports(conn, num_reports=25)  # 25 reports

        # Show stats
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM anomalies")
        anomaly_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM incident_reports")
        report_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT service) FROM events")
        service_count = cursor.fetchone()[0]

        print("\n" + "=" * 60)
        print("Database Statistics:")
        print("=" * 60)
        print(f"Total Events:      {event_count:,}")
        print(f"Total Anomalies:   {anomaly_count}")
        print(f"Total Reports:     {report_count}")
        print(f"Active Services:   {service_count}")
        print("=" * 60)

        cursor.close()
        conn.close()
        print("\n√ Demo data generation complete!")

    except Exception as e:
        print(f"X Error: {e}")
        raise

if __name__ == '__main__':
    main()
