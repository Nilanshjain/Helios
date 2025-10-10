"""Database storage for report metadata"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.database import db
from app.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseStorage:
    """Store report metadata in TimescaleDB"""

    def save_metadata(
        self,
        report_id: str,
        anomaly_id: str,
        service: str,
        severity: str,
        filepath: str,
        tokens_used: int,
        cost_usd: float,
        generation_time_ms: float,
        model: str,
    ) -> None:
        """Save report metadata to database"""
        query = """
            INSERT INTO incident_reports (
                report_id, anomaly_id, service, severity,
                filepath, tokens_used, cost_usd, generation_time_ms,
                model, generated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        report_id,
                        anomaly_id,
                        service,
                        severity,
                        filepath,
                        tokens_used,
                        cost_usd,
                        generation_time_ms,
                        model,
                        datetime.now(),
                    ),
                )

            logger.info("metadata_saved", report_id=report_id)

        except Exception as e:
            logger.error("metadata_save_failed", error=str(e), report_id=report_id)
            raise

    def get_metadata(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report metadata by ID"""
        query = """
            SELECT * FROM incident_reports
            WHERE report_id = %s
        """

        try:
            with db.get_cursor() as cursor:
                cursor.execute(query, (report_id,))
                result = cursor.fetchone()

            return dict(result) if result else None

        except Exception as e:
            logger.error("metadata_fetch_failed", error=str(e))
            return None
