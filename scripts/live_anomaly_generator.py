"""
Live Anomaly Generator for Demo
Inserts new anomalies every 4 minutes to keep the dashboard live
"""

import psycopg2
import random
import time
import json
from datetime import datetime

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'helios',
    'user': 'postgres',
    'password': 'postgres'
}

SERVICES = [
    'api-gateway', 'auth-service', 'user-service', 'order-service',
    'inventory-service', 'payment-service', 'notification-service',
    'analytics-service', 'search-service', 'recommendation-engine',
    'data-pipeline', 'cache-service', 'email-worker', 'image-processor'
]

SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

def insert_anomaly(conn):
    """Insert a single realistic anomaly"""
    cursor = conn.cursor()

    service = random.choice(SERVICES)
    severity = random.choice(SEVERITIES)
    timestamp = datetime.now()

    # Generate realistic features based on severity
    if severity in ['CRITICAL', 'HIGH']:
        features = {
            'cpu_usage': 0.85 + random.random() * 0.14,
            'memory_usage': 0.80 + random.random() * 0.15,
            'error_rate': 0.30 + random.random() * 0.40,
            'latency_ms': 2000 + random.random() * 6000,
            'request_rate': 500 + random.random() * 1500
        }
        score = -0.95 + random.random() * 0.20
        confidence = 0.85 + random.random() * 0.13
    elif severity == 'MEDIUM':
        features = {
            'cpu_usage': 0.65 + random.random() * 0.20,
            'memory_usage': 0.60 + random.random() * 0.20,
            'error_rate': 0.15 + random.random() * 0.15,
            'latency_ms': 1000 + random.random() * 1000,
            'request_rate': 300 + random.random() * 200
        }
        score = -0.75 + random.random() * 0.15
        confidence = 0.70 + random.random() * 0.15
    else:
        features = {
            'cpu_usage': 0.50 + random.random() * 0.15,
            'memory_usage': 0.45 + random.random() * 0.15,
            'error_rate': 0.05 + random.random() * 0.10,
            'latency_ms': 500 + random.random() * 500,
            'request_rate': 100 + random.random() * 200
        }
        score = -0.60 + random.random() * 0.10
        confidence = 0.60 + random.random() * 0.15

    anomaly_id = f'anomaly_live_{service}_{int(timestamp.timestamp())}'

    try:
        cursor.execute("""
            INSERT INTO anomalies (anomaly_id, time, service, score, threshold, severity, features, confidence, is_resolved, resolved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            anomaly_id,
            timestamp,
            service,
            score,
            -0.7,
            severity,
            json.dumps(features),
            confidence,
            False,  # New anomalies are unresolved
            None
        ))

        conn.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Inserted {severity} anomaly for {service} (ID: {anomaly_id})")
        return True
    except Exception as e:
        print(f"Error inserting anomaly: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def main():
    """Main loop - insert anomaly every 4 minutes"""
    print("=" * 60)
    print("Helios Live Anomaly Generator")
    print("=" * 60)
    print("Inserting new anomaly every 4 minutes...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"Connected to database at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print()

        # Insert first anomaly immediately
        insert_anomaly(conn)

        # Then insert every 4 minutes (240 seconds)
        while True:
            print(f"Waiting 4 minutes until next anomaly...")
            time.sleep(240)  # 4 minutes
            insert_anomaly(conn)

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            print("Database connection closed")

if __name__ == '__main__':
    main()
