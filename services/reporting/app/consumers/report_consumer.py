"""Kafka consumer for anomaly alerts → report generation"""

import json
from kafka import KafkaConsumer

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import db
from app.generators.claude_generator import ClaudeGenerator
from app.generators.mock_generator import MockGenerator
from app.generators.base import ReportContext
from app.storage.filesystem import FileSystemStorage
from app.storage.database import DatabaseStorage
from app.consumers.metrics import (
    reports_generated,
    report_generation_latency,
    claude_tokens_used,
    claude_cost_usd,
)

logger = get_logger(__name__)


class ReportConsumer:
    """
    Consume anomaly alerts from Kafka and generate incident reports.

    Flow:
    1. Listen to anomaly-alerts topic
    2. Fetch context from database
    3. Generate report using Claude/Mock
    4. Store report to filesystem + database
    """

    def __init__(self) -> None:
        """Initialize report consumer"""
        self.consumer = KafkaConsumer(
            settings.kafka_alerts_topic,
            bootstrap_servers=settings.kafka_brokers_list,
            group_id=settings.kafka_consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )

        # Initialize generator based on mode
        if settings.use_claude:
            logger.info("using_claude_generator")
            self.generator = ClaudeGenerator()
        else:
            logger.info("using_mock_generator")
            self.generator = MockGenerator()

        # Initialize storage
        self.file_storage = FileSystemStorage()
        self.db_storage = DatabaseStorage()

        logger.info("report_consumer_initialized")

    def start(self) -> None:
        """Start consuming anomaly alerts"""
        logger.info("starting_report_consumer")

        try:
            for message in self.consumer:
                self._process_anomaly(message.value)
        except KeyboardInterrupt:
            logger.info("shutting_down_consumer")
        except Exception as e:
            logger.error("consumer_error", error=str(e))
            raise
        finally:
            self.consumer.close()

    def _process_anomaly(self, anomaly: dict) -> None:
        """Process single anomaly alert"""
        try:
            anomaly_id = anomaly.get("id", "unknown")
            service = anomaly.get("service", "unknown")
            severity = anomaly.get("severity", "unknown")

            logger.info(
                "processing_anomaly",
                anomaly_id=anomaly_id,
                service=service,
                severity=severity,
            )

            # Fetch context from database
            context = self._fetch_context(anomaly)

            # Generate report
            with report_generation_latency.time():
                report = self.generator.generate(context)

            # Save to filesystem
            filepath = self.file_storage.save_report(
                report.report_id, report.content, report.format
            )

            # Save metadata to database
            self.db_storage.save_metadata(
                report_id=report.report_id,
                anomaly_id=anomaly_id,
                service=service,
                severity=severity,
                filepath=filepath,
                tokens_used=report.tokens_used,
                cost_usd=report.cost_usd,
                generation_time_ms=report.generation_time_ms,
                model=report.metadata.get("model", "unknown"),
            )

            # Update metrics
            generator_type = "claude" if settings.use_claude else "mock"
            reports_generated.labels(
                service=service, severity=severity, generator=generator_type
            ).inc()

            if report.tokens_used > 0:
                claude_tokens_used.inc(report.tokens_used)
                claude_cost_usd.inc(report.cost_usd)

            logger.info(
                "report_generated_successfully",
                report_id=report.report_id,
                service=service,
                tokens=report.tokens_used,
                cost_usd=report.cost_usd,
            )

        except Exception as e:
            logger.error("anomaly_processing_failed", error=str(e), anomaly=anomaly)

    def _fetch_context(self, anomaly: dict) -> ReportContext:
        """Fetch context data for report generation"""
        from datetime import datetime

        service = anomaly.get("service", "unknown")
        timestamp_str = anomaly.get("timestamp")

        # Parse timestamp
        try:
            anomaly_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except:
            anomaly_time = datetime.now()

        # Fetch context from database
        events = db.fetch_context_events(
            service=service,
            anomaly_time=anomaly_time,
            window_minutes=settings.context_window_minutes,
        )

        metrics = db.fetch_service_metrics(
            service=service,
            anomaly_time=anomaly_time,
            window_minutes=settings.context_window_minutes,
        )

        recent_anomalies = db.fetch_recent_anomalies(service=service, limit=5)

        return ReportContext(
            anomaly=anomaly, events=events, metrics=metrics, recent_anomalies=recent_anomalies
        )


def main() -> None:
    """Main entry point"""
    from app.core.logging import setup_logging

    setup_logging()

    consumer = ReportConsumer()
    consumer.start()


if __name__ == "__main__":
    main()
