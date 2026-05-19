"""Kafka consumer for anomaly alerts → report generation"""

import json
from kafka import KafkaConsumer

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import db
from app.generators.base import ReportContext, ReportGenerator
from app.generators.claude_generator import ClaudeGenerator
from app.generators.mock_generator import MockGenerator
from app.storage.filesystem import FileSystemStorage
from app.storage.database import DatabaseStorage
from app.utils.pdf_generator import PDFGenerator
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

        # Pick the configured generator, falling back to mock if the chosen
        # provider isn't usable (missing key, missing SDK). Mock is always
        # usable so the demo never silently fails.
        self.generator: ReportGenerator
        self.generator_name: str
        self.generator, self.generator_name = self._build_generator()
        logger.info("generator_selected", generator=self.generator_name)

        # Initialize storage
        self.file_storage = FileSystemStorage()
        self.db_storage = DatabaseStorage()

        # Initialize PDF generator
        self.pdf_generator = PDFGenerator()

        logger.info("report_consumer_initialized")

    def _build_generator(self) -> tuple[ReportGenerator, str]:
        """Construct the configured generator with graceful fallback to mock.

        Selection rule: ``REPORT_GENERATOR_MODE`` env var picks the provider
        (``gemini`` / ``claude`` / ``mock``). If the chosen provider's
        required key/SDK is missing, we log a warning and use mock — better
        a templated report than a crashed consumer. The mock generator is
        considered a first-class option for local development.
        """
        mode = (settings.report_generator_mode or "").lower().strip()

        if mode == "gemini":
            try:
                from app.generators.gemini_generator import GeminiGenerator

                return GeminiGenerator(), "gemini"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "gemini_unavailable_falling_back_to_mock",
                    error=str(exc),
                )

        if mode == "claude":
            try:
                return ClaudeGenerator(), "claude"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "claude_unavailable_falling_back_to_mock",
                    error=str(exc),
                )

        if mode not in ("gemini", "claude", "mock", ""):
            logger.warning("unknown_generator_mode_falling_back_to_mock", mode=mode)

        return MockGenerator(), "mock"

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

            # Generate PDF version
            pdf_path = None
            try:
                pdf_filepath = filepath.replace('.markdown', '.pdf')
                self.pdf_generator.markdown_to_pdf(
                    markdown_content=report.content,
                    output_path=pdf_filepath,
                    title=f"Incident Report: {anomaly_id}",
                    metadata={
                        "service": service,
                        "severity": severity,
                        "anomaly_score": anomaly.get("score"),
                        "generated_at": report.metadata.get("generated_at"),
                    }
                )
                pdf_path = pdf_filepath
                logger.info("pdf_generated", report_id=report.report_id, pdf_path=pdf_path)
            except Exception as e:
                logger.error("pdf_generation_failed", report_id=report.report_id, error=str(e))
                # Continue without PDF - markdown is still available

            # Save metadata to database
            self.db_storage.save_metadata(
                report_id=report.report_id,
                anomaly_id=anomaly_id,
                service=service,
                severity=severity,
                content=report.content,
                filepath=filepath,
                tokens_used=report.tokens_used,
                cost_usd=report.cost_usd,
                generation_time_ms=report.generation_time_ms,
                model=report.metadata.get("model", "unknown"),
                pdf_path=pdf_path,
            )

            # Update metrics
            reports_generated.labels(
                service=service, severity=severity, generator=self.generator_name
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
