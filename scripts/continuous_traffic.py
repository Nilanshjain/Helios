"""Continuous low-volume traffic generator for the demo.

Sends 5-15 events/second forever to keep the detection consumer's window
timer triggering. Mixes normal + intentionally anomalous bursts so the
detector has real signal to fire on.
"""

import argparse
import random
import sys
import time
from datetime import datetime, timezone

import requests

SERVICES = [
    "payment-service",
    "auth-service",
    "order-service",
    "api-gateway",
    "inventory-service",
    "user-service",
]


def make_event(service: str, anomalous: bool) -> dict:
    if anomalous:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "level": "CRITICAL" if random.random() < 0.2 else "ERROR",
            "message": "DB timeout",
            "metadata": {
                "latency_ms": random.uniform(2500, 6500),
                "endpoint": "/api",
            },
        }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "level": "INFO",
        "message": "request processed",
        "metadata": {
            "latency_ms": random.uniform(30, 120),
            "endpoint": "/api",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080/api/v1/events")
    parser.add_argument("--rps", type=int, default=10, help="events/second target")
    parser.add_argument(
        "--anomaly-burst-every",
        type=int,
        default=90,
        help="trigger a high-anomaly burst every N seconds",
    )
    parser.add_argument(
        "--burst-duration", type=int, default=20, help="anomaly-burst length in seconds"
    )
    args = parser.parse_args()

    start = time.time()
    next_burst = start + args.anomaly_burst_every
    burst_until = 0.0

    sent = 0
    errors = 0
    last_report = start

    print(
        f"[traffic] rps={args.rps}  burst every {args.anomaly_burst_every}s "
        f"for {args.burst_duration}s  target={args.url}",
        flush=True,
    )

    while True:
        now = time.time()
        anomalous_window = now < burst_until
        if not anomalous_window and now >= next_burst:
            burst_until = now + args.burst_duration
            next_burst = now + args.anomaly_burst_every
            print(f"[traffic] starting anomaly burst ({args.burst_duration}s)", flush=True)

        service = random.choice(SERVICES)
        event = make_event(
            service,
            anomalous=anomalous_window or random.random() < 0.05,  # baseline 5% noise
        )
        try:
            r = requests.post(args.url, json=event, timeout=2)
            if r.status_code in (200, 202):
                sent += 1
            else:
                errors += 1
        except Exception:
            errors += 1

        # Status print every 30 seconds
        if now - last_report > 30:
            mode = "BURST" if anomalous_window else "normal"
            print(
                f"[traffic] {mode}  sent={sent}  errors={errors}  uptime={(now-start):.0f}s",
                flush=True,
            )
            last_report = now

        time.sleep(1.0 / args.rps)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[traffic] stopped")
        sys.exit(0)
