"""Database connection and utilities"""

from typing import Iterator
from contextlib import contextmanager

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
        """Get database connection with context manager"""
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
    def get_cursor(self, dict_cursor: bool = True) -> Iterator[psycopg2.extensions.cursor]:
        """Get database cursor with context manager"""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()


# Global database instance
db = Database()
