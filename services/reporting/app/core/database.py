"""Database utilities for context fetching"""

from typing import Iterator, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    """Database connection manager"""

    def __init__(self) -> None:
        self.conn_params = {
            "host": settings.db_host,
            "port": settings.db_port,
            "database": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password,
        }

    @contextmanager
    def get_connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Get database connection"""
        conn = None
        try:
            conn = psycopg2.connect(**self.conn_params)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("database_error", error=str(e))
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(
        self, dict_cursor: bool = True
    ) -> Iterator[psycopg2.extensions.cursor]:
        """Get database cursor"""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def fetch_anomaly(self, anomaly_id: str) -> Dict[str, Any]:
        """Fetch anomaly details"""
        query = """
            SELECT *
            FROM anomalies
            WHERE id = %s
        """

        with self.get_cursor() as cursor:
            cursor.execute(query, (anomaly_id,))
            result = cursor.fetchone()

        if not result:
            raise ValueError(f"Anomaly not found: {anomaly_id}")

        return dict(result)

    def fetch_context_events(
        self, service: str, anomaly_time: datetime, window_minutes: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch events around anomaly time"""
        query = """
            SELECT
                time,
                service,
                level,
                message,
                metadata,
                trace_id
            FROM events
            WHERE service = %s
              AND time BETWEEN %s AND %s
            ORDER BY time DESC
            LIMIT %s
        """

        start_time = anomaly_time - timedelta(minutes=window_minutes)
        end_time = anomaly_time + timedelta(minutes=window_minutes)

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (service, start_time, end_time, settings.max_context_events),
            )
            results = cursor.fetchall()

        return [dict(row) for row in results]

    def fetch_service_metrics(
        self, service: str, anomaly_time: datetime, window_minutes: int = 10
    ) -> Dict[str, Any]:
        """Fetch aggregated metrics for service"""
        query = """
            SELECT
                AVG(event_count) as avg_event_count,
                AVG(error_rate) as avg_error_rate,
                AVG(avg_latency) as avg_latency,
                AVG(p95_latency) as avg_p95_latency,
                AVG(p99_latency) as avg_p99_latency
            FROM event_metrics_5m
            WHERE service = %s
              AND bucket BETWEEN %s AND %s
        """

        start_time = anomaly_time - timedelta(minutes=window_minutes)
        end_time = anomaly_time + timedelta(minutes=window_minutes)

        with self.get_cursor() as cursor:
            cursor.execute(query, (service, start_time, end_time))
            result = cursor.fetchone()

        return dict(result) if result else {}

    def fetch_recent_anomalies(
        self, service: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch recent anomalies for the service"""
        query = """
            SELECT
                time,
                severity,
                score,
                features
            FROM anomalies
            WHERE service = %s
            ORDER BY time DESC
            LIMIT %s
        """

        with self.get_cursor() as cursor:
            cursor.execute(query, (service, limit))
            results = cursor.fetchall()

        return [dict(row) for row in results]


# Global database instance
db = Database()
