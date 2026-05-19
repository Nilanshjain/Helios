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
        # Try both .md and .markdown extensions
        extensions = [format, "markdown"] if format == "md" else [format]

        for days_ago in range(settings.reports_retention_days):
            date = datetime.now() - timedelta(days=days_ago)
            date_path = self.base_path / date.strftime("%Y/%m/%d")

            for ext in extensions:
                filepath = date_path / f"{report_id}.{ext}"
                if filepath.exists():
                    with open(filepath, "r", encoding="utf-8") as f:
                        return f.read()

        logger.warning("report_not_found", report_id=report_id)
        return None

    def list_reports(
        self, limit: int = 10, service: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List recent reports"""
        reports = []

        # Search through recent dates
        for days_ago in range(min(limit, settings.reports_retention_days)):
            date = datetime.now() - timedelta(days=days_ago)
            date_path = self.base_path / date.strftime("%Y/%m/%d")

            if not date_path.exists():
                continue

            # List all markdown files in this date directory (.md and .markdown)
            md_files = list(date_path.glob("*.md")) + list(date_path.glob("*.markdown"))
            for filepath in sorted(md_files, reverse=True):
                if len(reports) >= limit:
                    break

                report_id = filepath.stem

                # Filter by service if specified
                if service and service not in report_id:
                    continue

                reports.append({
                    "report_id": report_id,
                    "path": str(filepath.relative_to(self.base_path)),
                    "date": date.strftime("%Y-%m-%d"),
                    "size_bytes": filepath.stat().st_size,
                })

        logger.debug("listed_reports", count=len(reports), limit=limit)
        return reports
