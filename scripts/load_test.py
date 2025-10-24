#!/usr/bin/env python3
"""
Load Testing Script for Helios Ingestion Service

This script performs comprehensive load testing to verify the system can handle
50,000+ events/sec as specified in the project requirements.
"""

import argparse
import asyncio
import time
import random
import json
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import aiohttp
import statistics


@dataclass
class LoadTestConfig:
    """Configuration for load test"""
    url: str = "http://localhost:8080/api/v1/events"
    target_rps: int = 1000  # requests per second
    duration: int = 60  # seconds
    concurrent_clients: int = 50
    batch_size: int = 10
    warmup_duration: int = 5  # seconds
    use_batch_endpoint: bool = True


@dataclass
class LoadTestResults:
    """Results from load test"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_events: int = 0
    latencies: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: float = 0
    end_time: float = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def actual_rps(self) -> float:
        return self.total_requests / self.duration if self.duration > 0 else 0

    @property
    def actual_eps(self) -> float:
        """Events per second"""
        return self.total_events / self.duration if self.duration > 0 else 0

    @property
    def success_rate(self) -> float:
        total = self.successful_requests + self.failed_requests
        return (self.successful_requests / total * 100) if total > 0 else 0

    @property
    def p50_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx]

    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx]

    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0


# Service configurations for realistic event generation
SERVICES = [
    {
        "name": "api-gateway",
        "endpoints": ["/api/v1/users", "/api/v1/posts", "/api/v1/comments"],
        "error_rate": 0.02,
        "latency_mean": 50,
    },
    {
        "name": "auth-service",
        "endpoints": ["/login", "/logout", "/refresh"],
        "error_rate": 0.01,
        "latency_mean": 30,
    },
    {
        "name": "payment-service",
        "endpoints": ["/checkout", "/refund", "/validate"],
        "error_rate": 0.03,
        "latency_mean": 120,
    },
    {
        "name": "user-service",
        "endpoints": ["/profile", "/settings", "/preferences"],
        "error_rate": 0.015,
        "latency_mean": 40,
    },
]

ERROR_MESSAGES = {
    "api-gateway": ["Request timeout", "Rate limit exceeded"],
    "auth-service": ["Invalid credentials", "Token expired"],
    "payment-service": ["Database timeout", "Payment gateway error"],
    "user-service": ["User not found", "Database query timeout"],
}

INFO_MESSAGES = [
    "Request processed successfully",
    "Operation completed",
]


def generate_event() -> Dict[str, Any]:
    """Generate a single realistic event"""
    service = random.choice(SERVICES)
    endpoint = random.choice(service["endpoints"])

    # Determine if error
    is_error = random.random() < service["error_rate"]

    if is_error:
        level = "ERROR"
        message = random.choice(ERROR_MESSAGES[service["name"]])
    else:
        level = "INFO"
        message = random.choice(INFO_MESSAGES)

    latency = service["latency_mean"] + random.gauss(0, 20)
    latency = max(latency, 1)  # Ensure positive

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": service["name"],
        "level": level,
        "message": message,
        "metadata": {
            "endpoint": endpoint,
            "latency_ms": latency,
            "request_id": f"req_{random.randint(1000000, 9999999)}",
        },
        "trace_id": f"trace_{random.randint(1000000, 9999999):016x}",
        "span_id": f"span_{random.randint(1000, 9999):08x}",
    }


async def send_request(
    session: aiohttp.ClientSession,
    config: LoadTestConfig,
    results: LoadTestResults,
) -> None:
    """Send a single request (batch of events)"""
    events = [generate_event() for _ in range(config.batch_size)]

    # Choose endpoint based on config
    if config.use_batch_endpoint:
        url = config.url.replace("/events", "/events/batch")
        payload = {"events": events}
    else:
        url = config.url
        payload = events[0]  # Send single event

    start = time.time()
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            latency = time.time() - start

            if resp.status in [200, 202]:
                results.successful_requests += 1
                results.latencies.append(latency)
                results.total_events += len(events) if config.use_batch_endpoint else 1
            else:
                results.failed_requests += 1
                error_text = await resp.text()
                results.errors[f"HTTP_{resp.status}"] += 1

    except asyncio.TimeoutError:
        results.failed_requests += 1
        results.errors["timeout"] += 1
    except aiohttp.ClientError as e:
        results.failed_requests += 1
        results.errors[type(e).__name__] += 1
    except Exception as e:
        results.failed_requests += 1
        results.errors[f"unknown_{type(e).__name__}"] += 1

    results.total_requests += 1


async def worker(
    worker_id: int,
    session: aiohttp.ClientSession,
    config: LoadTestConfig,
    results: LoadTestResults,
    stop_event: asyncio.Event,
) -> None:
    """Worker that continuously sends requests"""
    request_count = 0

    while not stop_event.is_set():
        await send_request(session, config, results)
        request_count += 1

        # Add small delay to control rate
        # Each worker should send (target_rps / concurrent_clients) requests per second
        target_worker_rps = config.target_rps / config.concurrent_clients
        await asyncio.sleep(1 / target_worker_rps)


async def print_progress(
    results: LoadTestResults,
    config: LoadTestConfig,
    stop_event: asyncio.Event,
) -> None:
    """Print progress periodically"""
    last_requests = 0
    last_time = time.time()

    while not stop_event.is_set():
        await asyncio.sleep(5)

        current_requests = results.total_requests
        current_time = time.time()

        requests_delta = current_requests - last_requests
        time_delta = current_time - last_time
        current_rps = requests_delta / time_delta if time_delta > 0 else 0
        current_eps = (requests_delta * config.batch_size) / time_delta if time_delta > 0 else 0

        elapsed = current_time - results.start_time

        print(f"\n[PROGRESS] (t={elapsed:.1f}s):")
        print(f"   Requests: {current_requests:,} ({current_rps:.0f} req/s)")
        print(f"   Events: {results.total_events:,} ({current_eps:.0f} events/s)")
        print(f"   Success Rate: {results.success_rate:.2f}%")
        if results.latencies:
            print(f"   P50 Latency: {results.p50_latency*1000:.2f}ms")
            print(f"   P99 Latency: {results.p99_latency*1000:.2f}ms")

        last_requests = current_requests
        last_time = current_time


async def run_load_test(config: LoadTestConfig) -> LoadTestResults:
    """Run the load test"""
    results = LoadTestResults()

    print("\n" + "="*70)
    print("HELIOS LOAD TEST")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  URL: {config.url}")
    print(f"  Target Rate: {config.target_rps:,} req/s")
    print(f"  Batch Size: {config.batch_size}")
    print(f"  Target Events/Sec: {config.target_rps * config.batch_size:,}")
    print(f"  Duration: {config.duration}s")
    print(f"  Concurrent Clients: {config.concurrent_clients}")
    print(f"  Warmup: {config.warmup_duration}s")
    print()

    # Create aiohttp session
    connector = aiohttp.TCPConnector(limit=config.concurrent_clients * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Warmup phase
        if config.warmup_duration > 0:
            print(f"[WARMUP] Warming up for {config.warmup_duration} seconds...")
            warmup_stop = asyncio.Event()
            warmup_results = LoadTestResults()
            warmup_results.start_time = time.time()

            warmup_tasks = [
                asyncio.create_task(worker(i, session, config, warmup_results, warmup_stop))
                for i in range(min(10, config.concurrent_clients))
            ]

            await asyncio.sleep(config.warmup_duration)
            warmup_stop.set()
            await asyncio.gather(*warmup_tasks)
            print(f"[OK] Warmup complete ({warmup_results.total_requests} requests)")
            print()

        # Main load test
        print(f"[START] Starting load test for {config.duration} seconds...")
        print()

        stop_event = asyncio.Event()
        results.start_time = time.time()

        # Create worker tasks
        workers = [
            asyncio.create_task(worker(i, session, config, results, stop_event))
            for i in range(config.concurrent_clients)
        ]

        # Create progress reporter
        progress_task = asyncio.create_task(print_progress(results, config, stop_event))

        # Wait for test duration
        await asyncio.sleep(config.duration)

        # Stop all workers
        stop_event.set()
        results.end_time = time.time()

        # Wait for workers to finish
        await asyncio.gather(*workers, progress_task)

    return results


def print_results(results: LoadTestResults, config: LoadTestConfig) -> None:
    """Print final test results"""
    print("\n" + "="*70)
    print("[RESULTS] LOAD TEST RESULTS")
    print("="*70)

    print(f"\n[TIME] Duration: {results.duration:.2f}s")

    print(f"\n[STATS] Request Statistics:")
    print(f"  Total Requests: {results.total_requests:,}")
    print(f"  Successful: {results.successful_requests:,}")
    print(f"  Failed: {results.failed_requests:,}")
    print(f"  Success Rate: {results.success_rate:.2f}%")
    print(f"  Actual RPS: {results.actual_rps:,.0f}")

    print(f"\n[EVENTS] Event Statistics:")
    print(f"  Total Events: {results.total_events:,}")
    print(f"  Events/Sec: {results.actual_eps:,.0f}")

    print(f"\n[LATENCY] Latency Statistics:")
    print(f"  Average: {results.avg_latency*1000:.2f}ms")
    print(f"  P50: {results.p50_latency*1000:.2f}ms")
    print(f"  P95: {results.p95_latency*1000:.2f}ms")
    print(f"  P99: {results.p99_latency*1000:.2f}ms")

    if results.errors:
        print(f"\n[ERRORS] Errors:")
        for error_type, count in sorted(results.errors.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count:,}")

    print(f"\n[ASSESSMENT] Performance Assessment:")
    target_eps = config.target_rps * config.batch_size

    if results.actual_eps >= target_eps * 0.95:
        print(f"  [PASS] Achieved {results.actual_eps:.0f} events/sec (target: {target_eps:,})")
    else:
        print(f"  [FAIL] Only achieved {results.actual_eps:.0f} events/sec (target: {target_eps:,})")

    if results.p99_latency <= 0.050:  # 50ms
        print(f"  [PASS] P99 latency is {results.p99_latency*1000:.2f}ms (target: <50ms)")
    else:
        print(f"  [WARN] P99 latency is {results.p99_latency*1000:.2f}ms (target: <50ms)")

    if results.success_rate >= 99:
        print(f"  [PASS] Success rate is {results.success_rate:.2f}% (target: >99%)")
    else:
        print(f"  [FAIL] Success rate is {results.success_rate:.2f}% (target: >99%)")

    print("\n" + "="*70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Load test Helios ingestion service")
    parser.add_argument("--url", default="http://localhost:8080/api/v1/events", help="API URL")
    parser.add_argument("--rps", type=int, default=1000, help="Target requests per second")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--clients", type=int, default=50, help="Number of concurrent clients")
    parser.add_argument("--batch-size", type=int, default=10, help="Events per request")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup duration in seconds")
    parser.add_argument("--no-batch", action="store_true", help="Don't use batch endpoint")

    args = parser.parse_args()

    config = LoadTestConfig(
        url=args.url,
        target_rps=args.rps,
        duration=args.duration,
        concurrent_clients=args.clients,
        batch_size=args.batch_size,
        warmup_duration=args.warmup,
        use_batch_endpoint=not args.no_batch,
    )

    # Run test
    results = asyncio.run(run_load_test(config))

    # Print results
    print_results(results, config)

    # Exit with appropriate code
    if results.success_rate >= 99 and results.actual_eps >= config.target_rps * config.batch_size * 0.95:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
