"""
Realistic Data Generator for ML Training

Generates 30 days of synthetic event data with:
- 5 realistic failure scenarios
- 25 correlated features (infrastructure, DB, cache, dependencies)
- Time-based patterns (peak hours, deployment windows)
- Realistic correlations between features
"""

import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ScenarioConfig:
    """Configuration for a failure scenario"""
    name: str
    probability: float
    error_rate_range: Tuple[float, float]
    latency_multiplier: Tuple[float, float]
    cpu_range: Tuple[float, float]
    memory_range: Tuple[float, float]
    db_conn_range: Tuple[float, float]
    cache_hit_rate_range: Tuple[float, float]


class RealisticDataGenerator:
    """
    Generate realistic synthetic data for training ML models.

    Features 5 scenarios:
    1. normal - Healthy system operation
    2. deployment_spike - Post-deployment errors and resource spikes
    3. database_slowdown - DB saturation causing high latency
    4. cache_miss_storm - Cache invalidation causing performance degradation
    5. cascading_failure - Multiple systems failing together
    """

    # 5 Realistic Scenarios
    SCENARIOS = {
        "normal": ScenarioConfig(
            name="normal",
            probability=0.85,  # 85% of time is normal
            error_rate_range=(0.01, 0.03),  # 1-3% errors
            latency_multiplier=(1.0, 1.2),
            cpu_range=(0.20, 0.60),
            memory_range=(0.30, 0.65),
            db_conn_range=(0.10, 0.40),
            cache_hit_rate_range=(0.85, 0.98)
        ),
        "deployment_spike": ScenarioConfig(
            name="deployment_spike",
            probability=0.05,  # 5% of time
            error_rate_range=(0.10, 0.20),  # 10-20% errors
            latency_multiplier=(1.5, 2.5),
            cpu_range=(0.60, 0.90),
            memory_range=(0.55, 0.85),
            db_conn_range=(0.50, 0.80),
            cache_hit_rate_range=(0.70, 0.85)
        ),
        "database_slowdown": ScenarioConfig(
            name="database_slowdown",
            probability=0.04,
            error_rate_range=(0.02, 0.08),  # Some errors
            latency_multiplier=(2.0, 4.0),  # Very high latency
            cpu_range=(0.30, 0.50),
            memory_range=(0.35, 0.60),
            db_conn_range=(0.80, 0.99),  # DB connection saturation
            cache_hit_rate_range=(0.80, 0.95)
        ),
        "cache_miss_storm": ScenarioConfig(
            name="cache_miss_storm",
            probability=0.03,
            error_rate_range=(0.03, 0.10),
            latency_multiplier=(1.8, 3.0),
            cpu_range=(0.40, 0.70),
            memory_range=(0.65, 0.90),  # High memory usage
            db_conn_range=(0.40, 0.70),
            cache_hit_rate_range=(0.20, 0.50)  # Very low cache hits
        ),
        "cascading_failure": ScenarioConfig(
            name="cascading_failure",
            probability=0.03,  # 3% of time
            error_rate_range=(0.20, 0.40),  # 20-40% errors
            latency_multiplier=(3.0, 6.0),
            cpu_range=(0.80, 0.99),
            memory_range=(0.80, 0.99),
            db_conn_range=(0.75, 0.99),
            cache_hit_rate_range=(0.10, 0.40)
        )
    }

    # Services to generate data for
    SERVICES = [
        "api-gateway", "payment-service", "auth-service",
        "inventory-service", "notification-service"
    ]

    # API endpoints per service
    ENDPOINTS = {
        "api-gateway": ["/api/v1/users", "/api/v1/products", "/api/v1/orders", "/health"],
        "payment-service": ["/checkout", "/refund", "/validate", "/health"],
        "auth-service": ["/login", "/logout", "/refresh", "/verify", "/health"],
        "inventory-service": ["/stock", "/reserve", "/release", "/health"],
        "notification-service": ["/email", "/sms", "/push", "/health"]
    }

    def __init__(
        self,
        days: int = 30,
        events_per_window: int = 100,
        window_minutes: int = 5
    ):
        """
        Initialize data generator.

        Args:
            days: Number of days to generate
            events_per_window: Average events per 5-minute window
            window_minutes: Window size in minutes
        """
        self.days = days
        self.events_per_window = events_per_window
        self.window_minutes = window_minutes
        self.windows_per_day = (24 * 60) // window_minutes  # 288 windows per day

        # Generate deployment schedule (deployments every 3 days at 2am)
        self.deployment_schedule = self._generate_deployment_schedule()

        random.seed(42)
        np.random.seed(42)

    def generate(self) -> Tuple[List[List[Dict[str, Any]]], List[str]]:
        """
        Generate all training data.

        Returns:
            Tuple of (windows, labels) where:
            - windows: List of event windows (each window is list of events)
            - labels: List of scenario names for each window
        """
        windows = []
        labels = []

        total_windows = self.days * self.windows_per_day

        print(f"Generating {total_windows} windows ({self.days} days)...")

        for day in range(self.days):
            for window_idx in range(self.windows_per_day):
                # Calculate hour of day
                hour = (window_idx * self.window_minutes) // 60

                # Pick scenario for this window
                scenario_name = self._pick_scenario(hour, day)
                scenario = self.SCENARIOS[scenario_name]

                # Generate events for this window
                events = self._generate_window(scenario, hour)

                windows.append(events)
                labels.append(scenario_name)

                if len(windows) % 1000 == 0:
                    print(f"  Generated {len(windows)}/{total_windows} windows...")

        print(f"[OK] Generated {len(windows)} windows with {sum(len(w) for w in windows):,} total events")

        # Print scenario distribution
        from collections import Counter
        scenario_counts = Counter(labels)
        print("\nScenario Distribution:")
        for scenario, count in scenario_counts.most_common():
            percentage = (count / len(labels)) * 100
            print(f"  {scenario:20s}: {count:5d} ({percentage:5.2f}%)")

        return windows, labels

    def _pick_scenario(self, hour: int, day: int) -> str:
        """
        Pick scenario based on time and deployment schedule.

        Args:
            hour: Hour of day (0-23)
            day: Day number

        Returns:
            Scenario name
        """
        # Check if this is deployment window (2am, day after deployment)
        is_deployment_window = (
            day in self.deployment_schedule and
            hour >= 2 and hour <= 4
        )

        if is_deployment_window:
            # High chance of deployment_spike during deployment
            if random.random() < 0.5:
                return "deployment_spike"

        # Pick scenario based on probabilities
        rand = random.random()
        cumulative = 0.0

        for scenario_name, scenario in self.SCENARIOS.items():
            cumulative += scenario.probability
            if rand < cumulative:
                return scenario_name

        return "normal"  # Fallback

    def _generate_window(
        self,
        scenario: ScenarioConfig,
        hour_of_day: int
    ) -> List[Dict[str, Any]]:
        """
        Generate events for a single window.

        Args:
            scenario: Scenario configuration
            hour_of_day: Hour (0-23)

        Returns:
            List of event dictionaries
        """
        # Adjust event count based on peak hours
        base_events = self.events_per_window
        if self._is_peak_hour(hour_of_day):
            num_events = int(base_events * random.uniform(2.5, 3.5))  # 2.5-3.5x traffic
        else:
            num_events = int(base_events * random.uniform(0.8, 1.2))

        # Pick a random service for this window
        service = random.choice(self.SERVICES)

        # Generate events
        events = []
        for _ in range(num_events):
            event = self._generate_event(scenario, service, hour_of_day)
            events.append(event)

        return events

    def _generate_event(
        self,
        scenario: ScenarioConfig,
        service: str,
        hour: int
    ) -> Dict[str, Any]:
        """
        Generate a single event with correlated features.

        Args:
            scenario: Scenario configuration
            service: Service name
            hour: Hour of day

        Returns:
            Event dictionary
        """
        # Base latency depends on service and time
        base_latency = {
            "api-gateway": 50,
            "payment-service": 120,
            "auth-service": 80,
            "inventory-service": 90,
            "notification-service": 200
        }.get(service, 100)

        # Sample from scenario ranges
        error_rate = random.uniform(*scenario.error_rate_range)
        latency_mult = random.uniform(*scenario.latency_multiplier)
        cpu_usage = random.uniform(*scenario.cpu_range)
        memory_usage = random.uniform(*scenario.memory_range)
        db_conn_usage = random.uniform(*scenario.db_conn_range)
        cache_hit_rate = random.uniform(*scenario.cache_hit_rate_range)

        # Apply correlations
        # 1. High CPU → Higher latency (+30% correlation)
        latency_cpu_boost = 1.0 + (cpu_usage * 0.3)

        # 2. Low cache hits → Higher latency (+50% correlation)
        cache_miss_rate = 1.0 - cache_hit_rate
        latency_cache_boost = 1.0 + (cache_miss_rate * 0.5)

        # 3. High DB connections → Higher latency (+40% correlation)
        latency_db_boost = 1.0 + (db_conn_usage * 0.4)

        # 4. CPU and Memory correlate (+70%)
        memory_usage = memory_usage * 0.3 + cpu_usage * 0.7
        memory_usage = min(0.99, max(0.05, memory_usage))  # Clamp

        # Calculate final latency
        latency_ms = (
            base_latency *
            latency_mult *
            latency_cpu_boost *
            latency_cache_boost *
            latency_db_boost *
            random.uniform(0.8, 1.2)  # Add noise
        )

        # Determine if this event is an error
        is_error = random.random() < error_rate

        # Pick endpoint
        endpoint = random.choice(self.ENDPOINTS.get(service, ["/api"]))

        # Database query latency (correlated with overall latency)
        db_query_p99 = latency_ms * random.uniform(0.6, 1.4)

        # Slow query ratio (higher when DB saturated)
        db_slow_query_ratio = db_conn_usage * 0.3 + random.uniform(0, 0.1)

        # Downstream error rate (increases during cascading failures)
        downstream_error_rate = error_rate * random.uniform(0.5, 1.5)

        # Resource pressure score (composite metric)
        resource_pressure = (cpu_usage + memory_usage + db_conn_usage) / 3

        # Build event
        event = {
            "time": datetime.utcnow().isoformat() + "Z",
            "service": service,
            "level": "ERROR" if is_error else ("WARN" if random.random() < 0.1 else "INFO"),
            "message": self._generate_message(is_error, service, endpoint),
            "metadata": {
                # Original 12 features (latency-based)
                "latency_ms": round(latency_ms, 2),
                "endpoint": endpoint,
                "status_code": self._pick_status_code(is_error),

                # NEW: Infrastructure Metrics (6 features)
                "cpu_usage": round(cpu_usage, 4),
                "max_cpu_usage": round(min(0.99, cpu_usage * random.uniform(1.1, 1.3)), 4),
                "memory_usage": round(memory_usage, 4),
                "max_memory_usage": round(min(0.99, memory_usage * random.uniform(1.05, 1.2)), 4),

                # NEW: Database Metrics (4 features)
                "db_connection_usage": round(db_conn_usage, 4),
                "db_query_p99_ms": round(db_query_p99, 2),
                "db_slow_query_ratio": round(db_slow_query_ratio, 4),

                # NEW: Cache Metrics (2 features)
                "cache_hit_rate": round(cache_hit_rate, 4),

                # NEW: Dependency Metrics (1 feature)
                "downstream_error_rate": round(downstream_error_rate, 4),
            }
        }

        # Add error details if error
        if is_error:
            event["metadata"]["error_code"] = random.choice([
                "TIMEOUT", "DB_ERROR", "SERVICE_UNAVAILABLE",
                "INTERNAL_ERROR", "DEPENDENCY_FAILURE"
            ])

        return event

    def _generate_message(self, is_error: bool, service: str, endpoint: str) -> str:
        """Generate realistic log message"""
        if is_error:
            messages = [
                f"Request to {endpoint} failed",
                f"Database query timeout on {service}",
                f"Downstream service unavailable",
                f"Internal server error processing request",
                f"Cache miss storm detected"
            ]
        else:
            messages = [
                f"Request processed successfully",
                f"API call to {endpoint} completed",
                f"Transaction completed",
                f"Request handled",
                f"Operation successful"
            ]

        return random.choice(messages)

    def _pick_status_code(self, is_error: bool) -> int:
        """Pick HTTP status code"""
        if is_error:
            return random.choice([500, 503, 504, 502, 429])
        else:
            return random.choice([200, 201, 204])

    def _is_peak_hour(self, hour: int) -> bool:
        """Check if hour is peak traffic (9am-5pm)"""
        return 9 <= hour <= 17

    def _generate_deployment_schedule(self) -> List[int]:
        """Generate deployment schedule (every 3 days at 2am)"""
        deployments = []
        for day in range(0, self.days, 3):
            deployments.append(day)
        return deployments


if __name__ == "__main__":
    """Test the generator"""

    print("Testing RealisticDataGenerator...")
    print("=" * 60)

    # Generate small test dataset
    generator = RealisticDataGenerator(days=7, events_per_window=50)
    windows, labels = generator.generate()

    print(f"\n{'=' * 60}")
    print("Sample Event (Normal):")
    print("=" * 60)

    # Find a normal window
    normal_idx = labels.index("normal")
    sample_event = windows[normal_idx][0]

    import json
    print(json.dumps(sample_event, indent=2))

    print(f"\n{'=' * 60}")
    print("Sample Event (Cascading Failure):")
    print("=" * 60)

    # Find a cascading failure window
    if "cascading_failure" in labels:
        failure_idx = labels.index("cascading_failure")
        sample_failure = windows[failure_idx][0]
        print(json.dumps(sample_failure, indent=2))

    print(f"\n{'=' * 60}")
    print("Feature Correlation Check:")
    print("=" * 60)

    # Check correlations
    import pandas as pd

    # Extract features from all events
    all_events = [event for window in windows for event in window]
    df = pd.DataFrame([e["metadata"] for e in all_events])

    # Calculate correlations
    correlations = {
        "CPU ↔ Memory": df["cpu_usage"].corr(df["memory_usage"]),
        "CPU ↔ Latency": df["cpu_usage"].corr(df["latency_ms"]),
        "DB Conn ↔ Latency": df["db_connection_usage"].corr(df["latency_ms"]),
        "Cache Miss ↔ Latency": (1 - df["cache_hit_rate"]).corr(df["latency_ms"]),
    }

    for pair, corr in correlations.items():
        print(f"  {pair:25s}: {corr:+.3f}")

    print(f"\n✓ Data generator test complete!")
