"""
Anomaly Detection Model using Isolation Forest

This module provides the core ML functionality for detecting anomalies in
time-series event data.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector for time-series events.

    Features:
    - Unsupervised learning (no labeled data required)
    - Real-time inference (<100ms)
    - Adaptive threshold tuning
    - Model persistence and loading
    """

    def __init__(
        self,
        contamination: float = 0.05,
        threshold: float = -0.7,
        n_estimators: int = 100,
        max_samples: str = "auto",
        random_state: int = 42,
    ):
        """
        Initialize anomaly detector.

        Args:
            contamination: Expected proportion of anomalies in dataset (0.01-0.10)
            threshold: Anomaly score threshold (lower = more sensitive)
            n_estimators: Number of trees in Isolation Forest
            max_samples: Number of samples to train each tree
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.threshold = threshold
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state

        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self.training_date: Optional[datetime] = None

    def extract_features(self, events_df: pd.DataFrame) -> np.ndarray:
        """
        Extract time-series features from event window.

        Features extracted:
        1. event_count: Total events in window
        2. error_rate: Percentage of ERROR/CRITICAL events
        3. avg_latency: Mean latency across events
        4. p95_latency: 95th percentile latency
        5. p99_latency: 99th percentile latency
        6. latency_stddev: Standard deviation of latency
        7. unique_endpoints: Number of distinct endpoints

        Args:
            events_df: DataFrame with columns ['level', 'metadata']

        Returns:
            Feature vector as numpy array (shape: 1 x 7)
        """
        if events_df.empty:
            return np.zeros((1, 7))

        # Basic counts
        total_events = len(events_df)
        error_events = events_df[events_df["level"].isin(["ERROR", "CRITICAL"])].shape[0]
        error_rate = error_events / total_events if total_events > 0 else 0.0

        # Extract latency from metadata
        latencies = events_df["metadata"].apply(lambda x: x.get("latency_ms", 0))

        # Latency statistics
        avg_latency = latencies.mean()
        p95_latency = latencies.quantile(0.95) if len(latencies) > 0 else 0.0
        p99_latency = latencies.quantile(0.99) if len(latencies) > 0 else 0.0
        latency_stddev = latencies.std()

        # Endpoint diversity
        unique_endpoints = (
            events_df["metadata"].apply(lambda x: x.get("endpoint", "")).nunique()
        )

        # Construct feature vector
        features = np.array(
            [
                total_events,
                error_rate,
                avg_latency,
                p95_latency,
                p99_latency,
                latency_stddev,
                unique_endpoints,
            ]
        ).reshape(1, -1)

        return features

    def train(self, historical_events: pd.DataFrame, window_size: str = "5T") -> Dict[str, float]:
        """
        Train Isolation Forest on historical data.

        Args:
            historical_events: DataFrame with event data
            window_size: Time window for feature aggregation (e.g., '5T' = 5 minutes)

        Returns:
            Training metrics (samples, duration, etc.)
        """
        logger.info("Starting model training...")
        start_time = datetime.now()

        # Create time windows
        historical_events["time"] = pd.to_datetime(historical_events["time"])
        historical_events = historical_events.sort_values("time")

        feature_list = []
        window_start = historical_events["time"].min()
        window_end = historical_events["time"].max()

        # Generate features for each window
        for current_time in pd.date_range(start=window_start, end=window_end, freq=window_size):
            window_end_time = current_time + pd.Timedelta(window_size)
            window_data = historical_events[
                (historical_events["time"] >= current_time)
                & (historical_events["time"] < window_end_time)
            ]

            if len(window_data) > 0:
                features = self.extract_features(window_data)
                feature_list.append(features)

        # Stack features
        X = np.vstack(feature_list)
        logger.info(f"Extracted {len(X)} feature vectors")

        # Normalize features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train Isolation Forest
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1,  # Use all CPU cores
        )
        self.model.fit(X_scaled)

        self.is_trained = True
        self.training_date = datetime.now()

        training_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Model training completed in {training_duration:.2f} seconds")

        return {
            "training_samples": len(X),
            "training_duration_seconds": training_duration,
            "features_extracted": X.shape[1],
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
        }

    def predict(self, events_df: pd.DataFrame) -> Dict[str, any]:
        """
        Predict if current event window is anomalous.

        Args:
            events_df: DataFrame with current event window

        Returns:
            Dictionary with prediction results:
                - is_anomaly: bool
                - score: float (anomaly score)
                - features: list (extracted features)
                - confidence: float (0-1)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Extract features
        features = self.extract_features(events_df)

        # Normalize features
        features_scaled = self.scaler.transform(features)

        # Get anomaly score
        score = self.model.decision_function(features_scaled)[0]

        # Determine if anomalous
        is_anomaly = score < self.threshold

        # Calculate confidence (distance from threshold)
        confidence = abs(score - self.threshold) / abs(self.threshold)
        confidence = min(confidence, 1.0)  # Cap at 1.0

        # Determine severity based on score
        severity = self._calculate_severity(score)

        return {
            "is_anomaly": bool(is_anomaly),
            "score": float(score),
            "threshold": self.threshold,
            "features": features.tolist()[0],
            "confidence": float(confidence),
            "severity": severity,
        }

    def _calculate_severity(self, score: float) -> str:
        """Calculate anomaly severity based on score"""
        if score >= self.threshold:
            return "NORMAL"
        elif score < -0.9:
            return "CRITICAL"
        elif score < -0.7:
            return "HIGH"
        elif score < -0.5:
            return "MEDIUM"
        else:
            return "LOW"

    def save(self, filepath: str) -> None:
        """
        Save trained model to disk.

        Args:
            filepath: Path to save model file (e.g., 'model.pkl')
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "threshold": self.threshold,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "training_date": self.training_date,
        }

        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "AnomalyDetector":
        """
        Load trained model from disk.

        Args:
            filepath: Path to model file

        Returns:
            Loaded AnomalyDetector instance
        """
        model_data = joblib.load(filepath)

        detector = cls(
            contamination=model_data["contamination"],
            threshold=model_data["threshold"],
            n_estimators=model_data["n_estimators"],
        )

        detector.model = model_data["model"]
        detector.scaler = model_data["scaler"]
        detector.training_date = model_data["training_date"]
        detector.is_trained = True

        logger.info(f"Model loaded from {filepath}")
        logger.info(f"Model trained at: {detector.training_date}")

        return detector

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.

        Note: Isolation Forest doesn't provide direct feature importance,
        but we can use feature contribution to anomaly scores.
        """
        feature_names = [
            "event_count",
            "error_rate",
            "avg_latency",
            "p95_latency",
            "p99_latency",
            "latency_stddev",
            "unique_endpoints",
        ]

        # TODO: Implement feature importance calculation
        # For now, return placeholder
        return {name: 0.0 for name in feature_names}
