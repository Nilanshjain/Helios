"""Real-time anomaly detection consumer"""

import json
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from app.core.logging import get_logger
from app.core.config import settings
from app.core.database import db
from app.ml.anomaly_detector import AnomalyDetector
from app.consumers.metrics import (
    events_processed,
    anomalies_detected,
    detection_latency,
    window_size_gauge,
)

logger = get_logger(__name__)


class DetectionConsumer:
    """
    Kafka consumer for real-time anomaly detection.

    Maintains sliding windows per service and runs ML inference.
    """

    def __init__(self) -> None:
        """Initialize detection consumer"""
        self.detector: Optional[AnomalyDetector] = None
        self.windows: Dict[str, deque] = {}  # service -> deque of events
        self.last_check: Dict[str, datetime] = {}  # service -> last check timestamp
        self.alert_cache: Dict[str, datetime] = {}  # Cache for deduplication

        # Kafka consumer
        self.consumer = KafkaConsumer(
            settings.kafka_events_topic,
            bootstrap_servers=settings.kafka_brokers_list,
            group_id=settings.kafka_consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
        )

        # Kafka producer for alerts
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka_brokers_list,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=3,
        )

        logger.info("detection_consumer_initialized")

    def load_model(self) -> None:
        """Load trained model"""
        try:
            self.detector = AnomalyDetector.load()
            logger.info("model_loaded_successfully")
        except Exception as e:
            logger.error("model_loading_failed", error=str(e))
            raise

    def start(self) -> None:
        """Start consuming and detecting anomalies"""
        logger.info("starting_detection_consumer")

        # Load model
        self.load_model()

        try:
            for message in self.consumer:
                self._process_event(message.value)
        except KeyboardInterrupt:
            logger.info("shutting_down_consumer")
        except Exception as e:
            logger.error("consumer_error", error=str(e))
            raise
        finally:
            self.consumer.close()
            self.producer.close()

    def _process_event(self, event: Dict[str, Any]) -> None:
        """Process a single event"""
        start_time = time.time()

        try:
            service = event.get("service", "unknown")

            # Initialize window for service if needed
            if service not in self.windows:
                self.windows[service] = deque(maxlen=1000)  # Keep last 1000 events
                self.last_check[service] = datetime.now()

            # Add event to window
            self.windows[service].append(event)
            window_size_gauge.labels(service=service).set(len(self.windows[service]))

            # Check if it's time to run detection
            time_since_last_check = (datetime.now() - self.last_check[service]).total_seconds()

            if time_since_last_check >= settings.window_size_minutes * 60:
                self._run_detection(service)
                self.last_check[service] = datetime.now()

            events_processed.labels(service=service, status="success").inc()

        except Exception as e:
            logger.error("event_processing_error", error=str(e), event_data=str(event))
            events_processed.labels(service=event.get("service", "unknown"), status="error").inc()
        finally:
            detection_latency.observe(time.time() - start_time)

    def _run_detection(self, service: str) -> None:
        """Run anomaly detection for a service"""
        events = list(self.windows[service])

        if len(events) < settings.min_events_per_window:
            logger.debug(
                "insufficient_events_for_detection",
                service=service,
                n_events=len(events),
                min_required=settings.min_events_per_window,
            )
            return

        try:
            # Run ML inference
            result = self.detector.predict(events)

            if result["is_anomaly"]:
                self._handle_anomaly(service, result, events)

            logger.debug(
                "detection_completed",
                service=service,
                is_anomaly=result["is_anomaly"],
                score=result["score"],
                severity=result["severity"],
            )

        except Exception as e:
            logger.error("detection_failed", service=service, error=str(e))

    def _handle_anomaly(
        self, service: str, result: Dict[str, Any], events: List[Dict[str, Any]]
    ) -> None:
        """Handle detected anomaly"""

        # Check if we should suppress this alert (deduplication)
        if self._should_suppress_alert(service):
            logger.debug("alert_suppressed", service=service)
            return

        # Create anomaly alert
        alert = {
            "id": f"anomaly_{service}_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "service": service,
            "severity": result["severity"],
            "score": result["score"],
            "threshold": result["threshold"],
            "features": dict(zip(result["feature_names"], result["features"])),
            "window_size": len(events),
            "window_start": events[0]["time"] if events else None,
            "window_end": events[-1]["time"] if events else None,
        }

        # Store in database
        self._store_anomaly(alert)

        # Publish to Kafka
        self._publish_alert(alert)

        # Update metrics
        anomalies_detected.labels(service=service, severity=result["severity"]).inc()

        # Update alert cache
        self.alert_cache[service] = datetime.now()

        logger.info(
            "anomaly_detected",
            service=service,
            severity=result["severity"],
            score=result["score"],
        )

    def _should_suppress_alert(self, service: str, cooldown_minutes: int = 10) -> bool:
        """
        Check if alert should be suppressed based on recent alerts.

        Args:
            service: Service name
            cooldown_minutes: Cooldown period in minutes

        Returns:
            True if alert should be suppressed
        """
        if service not in self.alert_cache:
            return False

        last_alert = self.alert_cache[service]
        time_since_last = (datetime.now() - last_alert).total_seconds() / 60

        return time_since_last < cooldown_minutes

    def _store_anomaly(self, alert: Dict[str, Any]) -> None:
        """Store anomaly in database"""
        try:
            query = """
                INSERT INTO anomalies (
                    time, service, severity, score, threshold,
                    features, window_size, window_start, window_end
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            with db.get_cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        alert["timestamp"],
                        alert["service"],
                        alert["severity"],
                        alert["score"],
                        alert["threshold"],
                        json.dumps(alert["features"]),
                        alert["window_size"],
                        alert["window_start"],
                        alert["window_end"],
                    ),
                )

            logger.debug("anomaly_stored_in_database", anomaly_id=alert["id"])

        except Exception as e:
            logger.error("failed_to_store_anomaly", error=str(e), anomaly_id=alert["id"])

    def _publish_alert(self, alert: Dict[str, Any]) -> None:
        """Publish alert to Kafka"""
        try:
            future = self.producer.send(settings.kafka_alerts_topic, value=alert)
            future.get(timeout=10)  # Wait for send confirmation

            logger.debug("alert_published_to_kafka", anomaly_id=alert["id"])

        except KafkaError as e:
            logger.error("failed_to_publish_alert", error=str(e), anomaly_id=alert["id"])


def main() -> None:
    """Main consumer entry point"""
    from app.core.logging import setup_logging

    setup_logging()

    consumer = DetectionConsumer()
    consumer.start()


if __name__ == "__main__":
    main()
