"""FastAPI routes for model management and prediction"""

from typing import Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.models import (
    PredictionRequest,
    PredictionResponse,
    ModelInfo,
    HealthResponse,
)
from app.core.logging import get_logger
from app.core.config import settings
from app.ml.anomaly_detector import AnomalyDetector
from app import __version__

logger = get_logger(__name__)
router = APIRouter()

# Global model instance
_detector: Optional[AnomalyDetector] = None


def get_detector() -> AnomalyDetector:
    """Get or load the detector instance"""
    global _detector

    if _detector is None:
        try:
            _detector = AnomalyDetector.load()
            logger.info("model_loaded_on_demand")
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Model not trained yet. Run "
                    "`python scripts/generate_chaos_traffic.py` then "
                    "`python scripts/train_production.py` to produce one."
                ),
            )
        except Exception as e:
            logger.error("model_loading_failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")

    return _detector


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    model_exists = Path(settings.model_path).exists()

    return HealthResponse(
        status="healthy",
        model_loaded=_detector is not None,
        timestamp=datetime.now(),
        version=__version__,
    )


@router.get("/model/info", response_model=ModelInfo)
async def get_model_info() -> ModelInfo:
    """Get model configuration information"""
    model_exists = Path(settings.model_path).exists()

    return ModelInfo(
        is_trained=model_exists,
        model_path=settings.model_path,
        threshold=settings.anomaly_threshold,
        contamination=settings.contamination,
        window_size_minutes=settings.window_size_minutes,
        min_events_per_window=settings.min_events_per_window,
    )


@router.post("/predict", response_model=PredictionResponse)
async def predict_anomaly(request: PredictionRequest) -> PredictionResponse:
    """
    Predict if a window of events is anomalous.

    Requires a trained model. Returns anomaly score and classification.
    """
    detector = get_detector()

    # Convert Pydantic models to dicts
    events = [event.model_dump() for event in request.events]

    if len(events) < settings.min_events_per_window:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient events: {len(events)} < {settings.min_events_per_window}",
        )

    try:
        result = detector.predict(events)

        return PredictionResponse(
            is_anomaly=result["is_anomaly"],
            score=result["score"],
            severity=result["severity"],
            threshold=result["threshold"],
            features=result["features"],
            feature_names=result["feature_names"],
            n_events=len(events),
        )

    except Exception as e:
        logger.error("prediction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.delete("/model")
async def delete_model() -> JSONResponse:
    """Delete the trained model"""
    global _detector

    model_path = Path(settings.model_path)

    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        model_path.unlink()
        _detector = None

        logger.info("model_deleted", path=settings.model_path)

        return JSONResponse(
            content={"status": "success", "message": "Model deleted successfully"}
        )

    except Exception as e:
        logger.error("model_deletion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")


@router.post("/model/reload")
async def reload_model() -> JSONResponse:
    """Reload the model from disk"""
    global _detector

    try:
        _detector = AnomalyDetector.load()
        logger.info("model_reloaded")

        return JSONResponse(
            content={"status": "success", "message": "Model reloaded successfully"}
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model file not found")
    except Exception as e:
        logger.error("model_reload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reload model: {str(e)}")
