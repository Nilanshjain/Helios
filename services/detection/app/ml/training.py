"""Model training script with synthetic data generation"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

from app.core.logging import get_logger, setup_logging
from app.core.database import db
from app.ml.anomaly_detector import AnomalyDetector
from app.core.config import settings

logger = get_logger(__name__)


class TrainingDataGenerator:
    """Generate realistic training data for model training"""

    SERVICES = {
        "api-gateway": {"error_rate": 0.02, "latency_mean": 50, "latency_std": 20},
        "auth-service": {"error_rate": 0.01, "latency_mean": 30, "latency_std": 10},
        "payment-service": {"error_rate": 0.03, "latency_mean": 120, "latency_std": 50},
        "notification-service": {"error_rate": 0.05, "latency_mean": 200, "latency_std": 80},
        "user-service": {"error_rate": 0.015, "latency_mean": 40, "latency_std": 15},
    }

    ENDPOINTS = {
        "api-gateway": ["/api/v1/users", "/api/v1/posts", "/api/v1/comments", "/health"],
        "auth-service": ["/login", "/logout", "/refresh", "/register"],
        "payment-service": ["/checkout", "/refund", "/validate", "/balance"],
        "notification-service": ["/email", "/sms", "/push", "/webhook"],
        "user-service": ["/profile", "/settings", "/preferences", "/avatar"],
    }

    LEVELS = ["INFO", "WARN", "ERROR", "CRITICAL"]

    def __init__(self, days: int = 7, events_per_window: int = 100) -> None:
        """
        Initialize training data generator.

        Args:
            days: Number of days of data to generate
            events_per_window: Average number of events per 5-minute window
        """
        self.days = days
        self.events_per_window = events_per_window

    def generate(self) -> List[List[Dict[str, Any]]]:
        """
        Generate training data windows.

        Returns:
            List of windows, where each window is a list of event dictionaries
        """
        logger.info("generating_training_data", days=self.days)

        windows = []
        start_time = datetime.now() - timedelta(days=self.days)
        window_duration = timedelta(minutes=settings.window_size_minutes)

        # Generate windows for the entire period
        current_time = start_time
        end_time = datetime.now()

        while current_time < end_time:
            window_end = current_time + window_duration
            events = self._generate_window_events(current_time, window_end)
            windows.append(events)
            current_time = window_end

        logger.info("training_data_generated", n_windows=len(windows))
        return windows

    def _generate_window_events(
        self, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Generate events for a single window"""
        # Add some randomness to event count
        n_events = max(
            settings.min_events_per_window,
            int(random.gauss(self.events_per_window, self.events_per_window * 0.2)),
        )

        events = []
        for _ in range(n_events):
            event = self._generate_event(start_time, end_time)
            events.append(event)

        return events

    def _generate_event(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate a single realistic event"""
        # Select random service
        service = random.choice(list(self.SERVICES.keys()))
        service_config = self.SERVICES[service]

        # Determine level based on error rate
        is_error = random.random() < service_config["error_rate"]
        level = random.choice(["ERROR", "CRITICAL"]) if is_error else "INFO"

        # Generate latency with normal distribution
        latency = max(
            1,
            int(
                random.gauss(service_config["latency_mean"], service_config["latency_std"])
            ),
        )

        # Random timestamp within window
        time_delta = (end_time - start_time).total_seconds()
        event_time = start_time + timedelta(seconds=random.uniform(0, time_delta))

        # Select random endpoint
        endpoint = random.choice(self.ENDPOINTS[service])

        return {
            "time": event_time.isoformat(),
            "service": service,
            "level": level,
            "message": f"Request processed" if not is_error else f"Request failed",
            "metadata": {
                "endpoint": endpoint,
                "latency_ms": latency,
                "request_id": f"req_{random.randint(100000, 999999)}",
            },
            "trace_id": f"trace_{random.randint(100000, 999999)}",
            "span_id": f"span_{random.randint(1000, 9999)}",
        }


def train_model_from_database() -> Dict[str, Any]:
    """
    Train model from events stored in TimescaleDB.

    Returns:
        Training statistics
    """
    logger.info("training_from_database")

    # Fetch training data from database
    query = f"""
        SELECT
            time_bucket('{settings.window_size_minutes} minutes', time) AS bucket,
            array_agg(
                json_build_object(
                    'time', time,
                    'service', service,
                    'level', level,
                    'message', message,
                    'metadata', metadata,
                    'trace_id', trace_id,
                    'span_id', span_id
                )
            ) AS events
        FROM events
        WHERE time > NOW() - INTERVAL '{7} days'
        GROUP BY bucket
        HAVING COUNT(*) >= {settings.min_events_per_window}
        ORDER BY bucket;
    """

    try:
        with db.get_cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        if len(rows) < 10:
            raise ValueError(f"Insufficient training windows in database: {len(rows)} < 10")

        # Extract windows
        windows = [row["events"] for row in rows]

        logger.info("fetched_training_data_from_db", n_windows=len(windows))

        # Train model
        detector = AnomalyDetector(
            contamination=settings.contamination,
            threshold=settings.anomaly_threshold,
        )

        stats = detector.train(windows)
        detector.save()

        return stats

    except Exception as e:
        logger.error("training_from_database_failed", error=str(e))
        raise


def train_model_synthetic(days: int = 7, events_per_window: int = 100) -> Dict[str, Any]:
    """
    Train model from synthetically generated data.

    Args:
        days: Number of days of data to generate
        events_per_window: Average events per window

    Returns:
        Training statistics
    """
    logger.info("training_from_synthetic_data", days=days)

    # Generate training data
    generator = TrainingDataGenerator(days=days, events_per_window=events_per_window)
    windows = generator.generate()

    # Train model
    detector = AnomalyDetector(
        contamination=settings.contamination,
        threshold=settings.anomaly_threshold,
    )

    stats = detector.train(windows)
    detector.save()

    logger.info("training_completed", **stats)
    return stats


def main() -> None:
    """Main training script"""
    setup_logging()

    logger.info("starting_model_training")

    try:
        # Try training from database first
        try:
            stats = train_model_from_database()
            logger.info("trained_from_database", **stats)
        except Exception as e:
            logger.warning("database_training_failed", error=str(e))
            logger.info("falling_back_to_synthetic_data")

            # Fall back to synthetic data
            stats = train_model_synthetic(days=7, events_per_window=150)
            logger.info("trained_from_synthetic_data", **stats)

        print("\n" + "="*60)
        print("Model Training Complete!")
        print("="*60)
        print(f"Training Windows: {stats['n_valid_windows']}")
        print(f"Features: {stats['n_features']}")
        print(f"Anomalies in Training: {stats['anomalies_in_training']}")
        print(f"Score Mean: {stats['score_mean']:.4f}")
        print(f"Score Std: {stats['score_std']:.4f}")
        print(f"Score Range: [{stats['score_min']:.4f}, {stats['score_max']:.4f}]")
        print(f"Model saved to: {settings.model_path}")
        print("="*60)

    except Exception as e:
        logger.error("training_failed", error=str(e))
        raise


if __name__ == "__main__":
    main()
