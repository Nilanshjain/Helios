"""Pydantic models for API requests and responses"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Event model matching ingestion service schema"""

    time: str = Field(..., description="Event timestamp (ISO format)")
    service: str = Field(..., description="Service name")
    level: str = Field(..., description="Log level (INFO, WARN, ERROR, CRITICAL)")
    message: str = Field(..., description="Event message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    trace_id: Optional[str] = Field(None, description="Distributed tracing ID")
    span_id: Optional[str] = Field(None, description="Span ID")


class PredictionRequest(BaseModel):
    """Request model for anomaly prediction"""

    events: List[Event] = Field(..., description="List of events to analyze")


class PredictionResponse(BaseModel):
    """Response model for anomaly prediction"""

    is_anomaly: bool = Field(..., description="Whether the window is anomalous")
    score: float = Field(..., description="Anomaly score (lower = more anomalous)")
    severity: str = Field(..., description="Severity level (low/medium/high/critical)")
    threshold: float = Field(..., description="Anomaly threshold used")
    features: List[float] = Field(..., description="Extracted features")
    feature_names: List[str] = Field(..., description="Feature names")
    n_events: int = Field(..., description="Number of events analyzed")


class TrainingRequest(BaseModel):
    """Request model for model training"""

    days: int = Field(7, description="Days of historical data to use", ge=1, le=30)
    use_database: bool = Field(True, description="Use database or synthetic data")


class TrainingResponse(BaseModel):
    """Response model for training completion"""

    status: str = Field(..., description="Training status")
    n_windows: int = Field(..., description="Number of training windows")
    n_valid_windows: int = Field(..., description="Valid windows after filtering")
    n_features: int = Field(..., description="Number of features")
    anomalies_in_training: int = Field(..., description="Anomalies found in training data")
    score_mean: float = Field(..., description="Mean anomaly score")
    score_std: float = Field(..., description="Standard deviation of scores")
    model_path: str = Field(..., description="Path where model was saved")


class ModelInfo(BaseModel):
    """Model information response"""

    is_trained: bool = Field(..., description="Whether model is trained")
    model_path: str = Field(..., description="Model file path")
    threshold: float = Field(..., description="Anomaly threshold")
    contamination: float = Field(..., description="Expected contamination rate")
    window_size_minutes: int = Field(..., description="Window size in minutes")
    min_events_per_window: int = Field(..., description="Minimum events per window")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    timestamp: datetime = Field(..., description="Current timestamp")
    version: str = Field(..., description="Service version")


class MetricsResponse(BaseModel):
    """Metrics summary response"""

    total_predictions: int = Field(..., description="Total predictions made")
    total_anomalies: int = Field(..., description="Total anomalies detected")
    anomaly_rate: float = Field(..., description="Anomaly detection rate")
    avg_detection_time_ms: float = Field(..., description="Average detection time in ms")
