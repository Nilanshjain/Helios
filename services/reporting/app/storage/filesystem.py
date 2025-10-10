"""Filesystem-based report storage"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileSystemStorage:
    """Store reports on local filesystem"""

    def __init__(self, base_path: Optional[str] = None) -> None:
        """Initialize filesystem storage"""
        self.base_path = Path(base_path or settings.reports_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("filesystem_storage_initialized", path=str(self.base_path))

    def save_report(self, report_id: str, content: str, format: str = "md") -> str:
        """Save report to filesystem"""
        timestamp = datetime.now()
        date_path = self.base_path / timestamp.strftime("%Y/%m/%d")
        date_path.mkdir(parents=True, exist_ok=True)

        filename = f"{report_id}.{format}"
        filepath = date_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("report_saved", report_id=report_id, path=str(filepath))
        return str(filepath)

    def get_report(self, report_id: str, format: str = "md") -> Optional[str]:
        """Retrieve report by ID"""
        for days_ago in range(settings.reports_retention_days):
            date = datetime.now() - timedelta(days=days_ago)
            filepath = (
                self.base_path
                / date.strftime("%Y/%m/%d")
                / f"{report_id}.{format}"
            )

            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()

        logger.warning("report_not_found", report_id=report_id)
        return None
