"""Feature engineering for time-series anomaly detection"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """
    Extract features from event windows for ML model.

    Features extracted:
    1. total_events - Total event count
    2. error_rate - Percentage of ERROR/CRITICAL events
    3. avg_latency - Average latency in ms
    4. p95_latency - 95th percentile latency
    5. p99_latency - 99th percentile latency
    6. latency_stddev - Standard deviation of latency
    7. unique_endpoints - Number of unique endpoints
    """

    FEATURE_NAMES = [
        "event_count",
        "error_rate",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "latency_std",
        "hour_of_day",
        "p95_p50_ratio",
        "p99_p95_ratio",
        "error_count",
        "log_event_count",
        "log_error_rate",
    ]

    def __init__(self, min_events: int = 10) -> None:
        """
        Initialize feature extractor.

        Args:
            min_events: Minimum events required for feature extraction
        """
        self.min_events = min_events

    def extract_features(self, events: List[Dict[str, Any]]) -> np.ndarray:
        """
        Extract features from a list of events.

        Args:
            events: List of event dictionaries

        Returns:
            NumPy array of features [1, n_features]

        Raises:
            ValueError: If insufficient events or invalid data
        """
        if len(events) < self.min_events:
            raise ValueError(
                f"Insufficient events for feature extraction: {len(events)} < {self.min_events}"
            )

        try:
            df = pd.DataFrame(events)
            features = self._extract_from_dataframe(df)
            return np.array(features).reshape(1, -1)
        except Exception as e:
            logger.error("feature_extraction_failed", error=str(e), event_count=len(events))
            raise

    def _extract_from_dataframe(self, df: pd.DataFrame) -> List[float]:
        """Extract features from DataFrame"""
        from datetime import datetime

        # Basic counts
        event_count = len(df)
        error_events = df[df["level"].isin(["ERROR", "CRITICAL"])].shape[0]
        error_rate = error_events / event_count if event_count > 0 else 0.0

        # Extract latency values from metadata
        latencies = self._extract_latencies(df)

        # Latency features
        if len(latencies) > 0:
            p50_latency_ms = np.percentile(latencies, 50)
            p95_latency_ms = np.percentile(latencies, 95)
            p99_latency_ms = np.percentile(latencies, 99)
            latency_std = np.std(latencies)
        else:
            p50_latency_ms = 0.0
            p95_latency_ms = 0.0
            p99_latency_ms = 0.0
            latency_std = 0.0

        # Hour of day (time-based feature)
        hour_of_day = datetime.now().hour

        # Engineered features
        p95_p50_ratio = p95_latency_ms / (p50_latency_ms + 1)
        p99_p95_ratio = p99_latency_ms / (p95_latency_ms + 1)
        error_count = event_count * error_rate
        log_event_count = np.log1p(event_count)
        log_error_rate = np.log1p(error_rate * 1000)

        features = [
            float(event_count),
            float(error_rate),
            float(p50_latency_ms),
            float(p95_latency_ms),
            float(p99_latency_ms),
            float(latency_std),
            float(hour_of_day),
            float(p95_p50_ratio),
            float(p99_p95_ratio),
            float(error_count),
            float(log_event_count),
            float(log_error_rate),
        ]

        logger.debug(
            "features_extracted",
            event_count=event_count,
            error_rate=error_rate,
            p50_latency_ms=p50_latency_ms,
            p95_latency_ms=p95_latency_ms,
            hour_of_day=hour_of_day,
        )

        return features

    def _extract_latencies(self, df: pd.DataFrame) -> np.ndarray:
        """Extract latency values from metadata column"""
        latencies = []

        for metadata in df["metadata"]:
            if metadata and isinstance(metadata, dict):
                latency = metadata.get("latency_ms", 0)
                if isinstance(latency, (int, float)) and latency > 0:
                    latencies.append(float(latency))

        return np.array(latencies)

    def _count_unique_endpoints(self, df: pd.DataFrame) -> int:
        """Count unique endpoints from metadata"""
        endpoints = set()

        for metadata in df["metadata"]:
            if metadata and isinstance(metadata, dict):
                endpoint = metadata.get("endpoint")
                if endpoint:
                    endpoints.add(endpoint)

        return len(endpoints)

    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return self.FEATURE_NAMES.copy()
