"""FastAPI routes for report management"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime, timedelta
import os

from app.core.logging import get_logger
from app.core.database import db
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


@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(report_id: str):
    """Download report as PDF"""
    try:
        # Get metadata from database to find PDF path
        metadata = db_storage.get_metadata(report_id)

        if not metadata:
            raise HTTPException(status_code=404, detail="Report not found")

        pdf_path = metadata.get("pdf_path")

        if not pdf_path:
            raise HTTPException(
                status_code=404,
                detail="PDF not available for this report"
            )

        if not os.path.exists(pdf_path):
            logger.error("pdf_file_not_found", report_id=report_id, pdf_path=pdf_path)
            raise HTTPException(
                status_code=404,
                detail="PDF file not found on disk"
            )

        # Return PDF file with download headers
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"{report_id}.pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{report_id}.pdf"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pdf_download_failed", error=str(e), report_id=report_id)
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


@router.get("/anomalies")
async def list_anomalies(
    limit: int = Query(100, ge=1, le=1000),
    service: Optional[str] = None,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    days: int = Query(7, ge=1, le=90),
):
    """List anomalies with optional filters"""
    try:
        # Build query
        query = """
            SELECT
                time, anomaly_id, service, score, threshold, severity,
                features, confidence, is_resolved, resolved_at
            FROM anomalies
            WHERE time >= %s
        """
        params = [datetime.now() - timedelta(days=days)]

        # Add optional filters
        if service:
            query += " AND service = %s"
            params.append(service)

        if severity:
            query += " AND severity = %s"
            params.append(severity)

        if is_resolved is not None:
            query += " AND is_resolved = %s"
            params.append(is_resolved)

        query += " ORDER BY time DESC LIMIT %s"
        params.append(limit)

        # Execute query
        with db.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        # Convert to list of dicts
        anomalies = []
        for row in rows:
            anomalies.append({
                "time": row["time"].isoformat() if row["time"] else None,
                "anomaly_id": row["anomaly_id"],
                "service": row["service"],
                "score": float(row["score"]) if row["score"] else 0.0,
                "threshold": float(row["threshold"]) if row["threshold"] else 0.0,
                "severity": row["severity"],
                "features": row["features"] or {},
                "confidence": float(row["confidence"]) if row["confidence"] else 0.0,
                "is_resolved": row["is_resolved"] or False,
                "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
            })

        logger.info("anomalies_fetched", count=len(anomalies))
        return {"anomalies": anomalies, "total": len(anomalies)}

    except Exception as e:
        logger.error("list_anomalies_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies/{anomaly_id}")
async def get_anomaly(anomaly_id: str):
    """Get specific anomaly by ID"""
    try:
        query = """
            SELECT
                time, anomaly_id, service, score, threshold, severity,
                features, confidence, is_resolved, resolved_at
            FROM anomalies
            WHERE anomaly_id = %s
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, (anomaly_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Anomaly not found")

        anomaly = {
            "time": row["time"].isoformat() if row["time"] else None,
            "anomaly_id": row["anomaly_id"],
            "service": row["service"],
            "score": float(row["score"]) if row["score"] else 0.0,
            "threshold": float(row["threshold"]) if row["threshold"] else 0.0,
            "severity": row["severity"],
            "features": row["features"] or {},
            "confidence": float(row["confidence"]) if row["confidence"] else 0.0,
            "is_resolved": row["is_resolved"] or False,
            "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
        }

        return anomaly

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_anomaly_failed", error=str(e), anomaly_id=anomaly_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: str):
    """Mark anomaly as resolved"""
    try:
        query = """
            UPDATE anomalies
            SET is_resolved = true, resolved_at = %s
            WHERE anomaly_id = %s
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, (datetime.now(), anomaly_id))

        logger.info("anomaly_resolved", anomaly_id=anomaly_id)
        return {"message": "Anomaly marked as resolved", "anomaly_id": anomaly_id}

    except Exception as e:
        logger.error("resolve_anomaly_failed", error=str(e), anomaly_id=anomaly_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    service: Optional[str] = None,
    level: Optional[str] = None,
    search: Optional[str] = None,
    trace_id: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
):
    """List events with optional filters"""
    try:
        # Build query
        query = """
            SELECT
                time, service, level, message, metadata,
                trace_id, span_id, host, ingested_at
            FROM events
            WHERE time >= %s
        """
        params = [datetime.now() - timedelta(hours=hours)]

        # Add optional filters
        if service:
            query += " AND service = %s"
            params.append(service)

        if level:
            query += " AND level = %s"
            params.append(level)

        if trace_id:
            query += " AND trace_id = %s"
            params.append(trace_id)

        if search:
            query += " AND message ILIKE %s"
            params.append(f"%{search}%")

        query += " ORDER BY time DESC LIMIT %s"
        params.append(limit)

        # Execute query
        with db.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        # Convert to list of dicts
        events = []
        for row in rows:
            events.append({
                "time": row["time"].isoformat() if row["time"] else None,
                "service": row["service"],
                "level": row["level"],
                "message": row["message"],
                "metadata": row["metadata"] or {},
                "trace_id": row["trace_id"],
                "span_id": row["span_id"],
                "host": row["host"],
                "ingested_at": row["ingested_at"].isoformat() if row["ingested_at"] else None,
            })

        logger.info("events_fetched", count=len(events))
        return {"events": events, "total": len(events)}

    except Exception as e:
        logger.error("list_events_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/health")
async def get_service_health():
    """Get health metrics for all services"""
    try:
        # Query recent metrics (last 5 minutes) grouped by service
        query = """
            SELECT
                service,
                COUNT(*) as event_count,
                SUM(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END)::float /
                    NULLIF(COUNT(*), 0) as error_rate,
                AVG((metadata->>'latency_ms')::int) as avg_latency
            FROM events
            WHERE time >= %s
            GROUP BY service
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, (datetime.now() - timedelta(minutes=5),))
            metrics_rows = cursor.fetchall()

        # Query active anomalies per service
        anomaly_query = """
            SELECT service, COUNT(*) as anomaly_count
            FROM anomalies
            WHERE time >= %s AND is_resolved = false
            GROUP BY service
        """

        with db.get_cursor() as cursor:
            cursor.execute(anomaly_query, (datetime.now() - timedelta(hours=24),))
            anomaly_rows = cursor.fetchall()

        # Build anomaly map
        anomaly_map = {row["service"]: row["anomaly_count"] for row in anomaly_rows}

        # Build service health data
        services = []
        for row in metrics_rows:
            service = row["service"]
            error_rate = float(row["error_rate"]) if row["error_rate"] else 0.0
            active_anomalies = anomaly_map.get(service, 0)

            # Determine health status
            if error_rate > 0.1 or active_anomalies > 5:
                status = "critical"
            elif error_rate > 0.05 or active_anomalies > 2:
                status = "degraded"
            else:
                status = "healthy"

            services.append({
                "service": service,
                "status": status,
                "event_count": int(row["event_count"]),
                "error_rate": error_rate,
                "avg_latency": float(row["avg_latency"]) if row["avg_latency"] else 0.0,
                "active_anomalies": active_anomalies,
                "last_updated": datetime.now().isoformat(),
            })

        return {"services": services, "total": len(services)}

    except Exception as e:
        logger.error("service_health_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
