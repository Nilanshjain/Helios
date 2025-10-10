"""FastAPI routes for report management"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.core.logging import get_logger
from app.storage.filesystem import FileSystemStorage
from app.storage.database import DatabaseStorage
from app import __version__

logger = get_logger(__name__)
router = APIRouter()

# Global storage instances
file_storage = FileSystemStorage()
db_storage = DatabaseStorage()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "helios-reporting",
        "version": __version__,
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get report by ID"""
    try:
        # Get content from filesystem
        content = file_storage.get_report(report_id)

        if not content:
            raise HTTPException(status_code=404, detail="Report not found")

        # Get metadata from database
        metadata = db_storage.get_metadata(report_id)

        return {
            "report_id": report_id,
            "content": content,
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_report_failed", error=str(e), report_id=report_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def list_reports(
    limit: int = 10,
    service: Optional[str] = None,
):
    """List recent reports"""
    try:
        reports = file_storage.list_reports(limit=limit, service=service)
        return {"reports": reports, "count": len(reports)}

    except Exception as e:
        logger.error("list_reports_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
