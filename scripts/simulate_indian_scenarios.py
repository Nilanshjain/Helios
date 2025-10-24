#!/usr/bin/env python3
"""
Simulate realistic production scenarios for Helios observability platform
Demonstrates real-time anomaly detection across various high-scale business domains
Usage: python simulate_indian_scenarios.py --scenario payment-gateway --surge
"""

import argparse
import requests
import time
import random
from datetime import datetime
from typing import List, Dict

# Helios ingestion endpoint
HELIOS_URL = "http://localhost:8080/api/v1/events"

# Production service scenarios across different business domains
SCENARIOS = {
    'payment-gateway': {
        'name': 'Digital Payment Gateway',
        'services': ['payment-gateway-primary', 'payment-gateway-backup', 'wallet-service'],
        'normal_error_rate': 0.02,
        'surge_error_rate': 0.45,
        'errors': ['GATEWAY_TIMEOUT', 'BANK_GATEWAY_DOWN', 'TRANSACTION_LIMIT_EXCEEDED',
                   'INSUFFICIENT_BALANCE', 'AUTH_FAILED'],
        'metadata': {
            'amount_range': (100, 50000),
            'cities': ['Mumbai', 'Bangalore', 'Delhi', 'Hyderabad', 'Pune'],
        }
    },

    'food-delivery': {
        'name': 'On-Demand Food Delivery Platform',
        'services': ['order-service', 'delivery-service'],
        'normal_error_rate': 0.05,
        'surge_error_rate': 0.60,
        'errors': ['RESTAURANT_TIMEOUT', 'PARTNER_APP_CRASH', 'DB_CONN_EXHAUSTED',
                   'LOCATION_SERVICE_DOWN', 'PAYMENT_FAILED'],
        'metadata': {
            'order_value_range': (200, 2000),
            'cities': ['Bangalore', 'Mumbai', 'Delhi', 'Hyderabad', 'Pune', 'Chennai'],
            'peak_times': ['13:00-14:00', '20:00-22:00', 'LIVE_EVENT_BREAK'],
        }
    },

    'edtech-platform': {
        'name': 'EdTech Streaming Platform',
        'services': ['streaming-service', 'live-class-service', 'subscription-service'],
        'normal_error_rate': 0.03,
        'surge_error_rate': 0.75,
        'errors': ['VIDEO_CDN_OVERLOAD', 'AUTH_SERVICE_DOWN', 'PAYMENT_TIMEOUT',
                   'LIVE_CLASS_BUFFER', 'SUBSCRIPTION_VERIFY_FAILED'],
        'metadata': {
            'course_types': ['Exam_Prep', 'Professional_Course', 'School_Education', 'Competitive_Exam'],
            'video_quality': ['360p', '480p', '720p', '1080p'],
        }
    },

    'stock-trading': {
        'name': 'Stock Trading Platform',
        'services': ['trading-api', 'order-execution-service', 'market-data-service'],
        'normal_error_rate': 0.01,
        'surge_error_rate': 0.40,
        'errors': ['EXCHANGE_RATE_LIMIT', 'ORDER_BOOK_TIMEOUT', 'PRICE_FEED_DELAY',
                   'MARGIN_INSUFFICIENT', 'EXCHANGE_CLOSED'],
        'metadata': {
            'exchanges': ['NSE', 'BSE'],
            'order_types': ['MARKET', 'LIMIT', 'STOP_LOSS', 'GTT'],
            'surge_events': ['BUDGET_DAY', 'POLICY_ANNOUNCEMENT', 'MAJOR_EVENT'],
        }
    },

    'ecommerce-platform': {
        'name': 'E-commerce Platform',
        'services': ['checkout-service', 'cart-service', 'payment-service'],
        'normal_error_rate': 0.04,
        'surge_error_rate': 0.70,
        'errors': ['CART_SERVICE_TIMEOUT', 'PAYMENT_RACE_CONDITION',
                   'INVENTORY_MISMATCH', 'COD_LIMIT_EXCEEDED', 'PINCODE_UNAVAILABLE'],
        'metadata': {
            'sale_events': ['FLASH_SALE', 'SEASONAL_SALE', 'FESTIVAL_SALE'],
            'product_categories': ['Electronics', 'Fashion', 'Home', 'Mobile'],
        }
    },

    'identity-verification': {
        'name': 'Government Identity Verification Service',
        'services': ['kyc-service', 'verification-service', 'auth-service'],
        'normal_error_rate': 0.10,
        'surge_error_rate': 0.60,
        'errors': ['GOVT_API_TIMEOUT', 'OTP_DELAY', 'BIOMETRIC_MISMATCH',
                   'XML_PARSE_ERROR', 'GOVT_SERVER_DOWN'],
        'metadata': {
            'verification_types': ['OTP', 'BIOMETRIC', 'OFFLINE_XML'],
        }
    },
}

def generate_event(scenario_config: Dict, is_error: bool = False) -> Dict:
    """Generate a realistic event based on scenario"""

    service = random.choice(scenario_config['services'])

    if is_error:
        level = 'ERROR' if random.random() > 0.3 else 'CRITICAL'
        error_type = random.choice(scenario_config['errors'])
        message = f"{error_type}: {get_error_message(error_type)}"
        latency = random.randint(3000, 8000)  # High latency on errors
    else:
        level = 'INFO'
        message = f"Request processed successfully"
        latency = random.randint(50, 300)  # Normal latency

    metadata = {
        'latency_ms': latency,
        'timestamp': datetime.now().isoformat(),
    }

    # Add scenario-specific metadata
    if 'amount_range' in scenario_config['metadata']:
        min_amt, max_amt = scenario_config['metadata']['amount_range']
        metadata['amount'] = f"₹{random.randint(min_amt, max_amt)}"

    if 'cities' in scenario_config['metadata']:
        metadata['city'] = random.choice(scenario_config['metadata']['cities'])

    if 'order_value_range' in scenario_config['metadata']:
        min_val, max_val = scenario_config['metadata']['order_value_range']
        metadata['order_value'] = f"₹{random.randint(min_val, max_val)}"

    if 'exchanges' in scenario_config['metadata']:
        metadata['exchange'] = random.choice(scenario_config['metadata']['exchanges'])

    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'service': service,
        'level': level,
        'message': message,
        'metadata': metadata
    }

def get_error_message(error_type: str) -> str:
    """Get descriptive error message"""
    messages = {
        'GATEWAY_TIMEOUT': 'Payment gateway timeout after 30 seconds',
        'BANK_GATEWAY_DOWN': 'Bank gateway not responding',
        'TRANSACTION_LIMIT_EXCEEDED': 'Daily transaction limit exceeded',
        'AUTH_FAILED': 'Authentication failed',
        'RESTAURANT_TIMEOUT': 'Restaurant confirmation timeout',
        'PARTNER_APP_CRASH': 'Delivery partner app not responding',
        'VIDEO_CDN_OVERLOAD': 'CDN bandwidth limit reached',
        'AUTH_SERVICE_DOWN': 'Authentication service unavailable',
        'EXCHANGE_RATE_LIMIT': 'Exchange API rate limit exceeded',
        'ORDER_BOOK_TIMEOUT': 'Order book write timeout',
        'CART_SERVICE_TIMEOUT': 'Cart service response timeout',
        'GOVT_API_TIMEOUT': 'Government API server timeout',
        'OTP_DELAY': 'OTP delivery delayed by 5+ minutes',
        'DB_CONN_EXHAUSTED': 'Database connection pool exhausted',
        'PAYMENT_TIMEOUT': 'Payment service timeout',
    }
    return messages.get(error_type, f'{error_type} occurred')

def send_event(event: Dict) -> bool:
    """Send event to Helios"""
    try:
        response = requests.post(HELIOS_URL, json=event, timeout=5)
        return response.status_code == 202
    except Exception as e:
        print(f"[ERROR] Failed to send event: {e}")
        return False

def simulate_scenario(scenario_name: str, num_events: int,
                     is_surge: bool = False, rate: int = 100):
    """Simulate a complete scenario"""

    if scenario_name not in SCENARIOS:
        print(f"[ERROR] Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(SCENARIOS.keys())}")
        return

    config = SCENARIOS[scenario_name]
    error_rate = config['surge_error_rate'] if is_surge else config['normal_error_rate']

    print(f"\n{'='*60}")
    print(f"[START] Simulating: {config['name']}")
    print(f"{'='*60}")
    print(f"Scenario: {'SURGE' if is_surge else 'NORMAL'}")
    print(f"Events: {num_events}")
    print(f"Error rate: {error_rate*100:.1f}%")
    print(f"Rate: {rate} events/sec")
    print(f"Services: {', '.join(config['services'])}")
    print(f"{'='*60}\n")

    success_count = 0
    error_count = 0
    start_time = time.time()

    for i in range(num_events):
        is_error = random.random() < error_rate
        event = generate_event(config, is_error)

        if send_event(event):
            if is_error:
                error_count += 1
            else:
                success_count += 1

        # Progress bar
        if (i + 1) % 100 == 0:
            progress = (i + 1) / num_events * 100
            print(f"Progress: [{('=' * int(progress/5)):<20}] {progress:.0f}% "
                  f"(Errors: {error_count})", end='\r')

        # Rate limiting
        if rate > 0:
            time.sleep(1.0 / rate)

    duration = time.time() - start_time

    print(f"\n\n{'='*60}")
    print(f"[SUCCESS] Simulation Complete")
    print(f"{'='*60}")
    print(f"Total events: {num_events}")
    print(f"Success: {success_count} ({success_count/num_events*100:.1f}%)")
    print(f"Errors: {error_count} ({error_count/num_events*100:.1f}%)")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Rate: {num_events/duration:.0f} events/sec")
    print(f"{'='*60}\n")

    if is_surge:
        print("[INFO] Wait 5 minutes for Helios to detect the anomaly...")
        print("   Then check: http://localhost:8002/reports")

def main():
    parser = argparse.ArgumentParser(
        description='Simulate production scenarios for Helios observability platform'
    )

    parser.add_argument(
        '--scenario',
        choices=list(SCENARIOS.keys()),
        required=True,
        help='Scenario to simulate'
    )

    parser.add_argument(
        '--events',
        type=int,
        default=1000,
        help='Number of events to generate (default: 1000)'
    )

    parser.add_argument(
        '--surge',
        action='store_true',
        help='Simulate surge/peak traffic with high error rate'
    )

    parser.add_argument(
        '--rate',
        type=int,
        default=100,
        help='Events per second (default: 100)'
    )

    args = parser.parse_args()

    # Test connection first
    print("[*] Testing Helios connection...")
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Helios is running\n")
        else:
            print("[WARN] Helios returned unexpected status")
    except Exception as e:
        print(f"[ERROR] Cannot connect to Helios at {HELIOS_URL}")
        print(f"   Make sure Helios is running: docker-compose up -d")
        return

    simulate_scenario(
        args.scenario,
        args.events,
        args.surge,
        args.rate
    )

if __name__ == '__main__':
    main()
