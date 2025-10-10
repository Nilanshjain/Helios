"""Anomaly detection using Isolation Forest"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

from app.core.logging import get_logger
from app.core.config import settings
from app.ml.feature_engineering import FeatureExtractor

logger = get_logger(__name__)


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector for time-series events.

    Uses unsupervised learning to identify anomalous patterns in event streams.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        threshold: float = -0.7,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        """
        Initialize anomaly detector.

        Args:
            contamination: Expected proportion of anomalies (0.0 to 0.5)
            threshold: Decision threshold for anomaly classification
            n_estimators: Number of trees in the forest
            random_state: Random seed for reproducibility
        """
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            max_samples="auto",
            random_state=random_state,
            n_jobs=-1,  # Use all CPU cores
        )
        self.scaler = StandardScaler()
        self.feature_extractor = FeatureExtractor(min_events=settings.min_events_per_window)
        self.threshold = threshold
        self.is_trained = False

    def train(self, training_events: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Train the anomaly detection model on historical data.

        Args:
            training_events: List of event windows (each window is a list of events)

        Returns:
            Training statistics dictionary

        Raises:
            ValueError: If insufficient training data
        """
        if len(training_events) < 10:
            raise ValueError(f"Insufficient training windows: {len(training_events)} < 10")

        logger.info("training_started", n_windows=len(training_events))

        # Extract features from each window
        features_list = []
        for i, window in enumerate(training_events):
            try:
                features = self.feature_extractor.extract_features(window)
                features_list.append(features)
            except Exception as e:
                logger.warning(
                    "feature_extraction_failed_for_window",
                    window_index=i,
                    error=str(e),
                )
                continue

        if len(features_list) < 10:
            raise ValueError(
                f"Too few valid training windows after feature extraction: {len(features_list)}"
            )

        # Stack features and normalize
        X = np.vstack(features_list)
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled)
        self.is_trained = True

        # Calculate training statistics
        scores = self.model.decision_function(X_scaled)
        anomalies_detected = np.sum(scores < self.threshold)

        stats = {
            "n_windows": len(training_events),
            "n_valid_windows": len(features_list),
            "n_features": X.shape[1],
            "anomalies_in_training": int(anomalies_detected),
            "score_mean": float(np.mean(scores)),
            "score_std": float(np.std(scores)),
            "score_min": float(np.min(scores)),
            "score_max": float(np.max(scores)),
        }

        logger.info("training_completed", **stats)
        return stats

    def predict(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Predict if a window of events is anomalous.

        Args:
            events: List of event dictionaries

        Returns:
            Prediction dictionary with:
                - is_anomaly: Boolean indicating anomaly
                - score: Anomaly score (lower = more anomalous)
                - features: Extracted features
                - severity: Anomaly severity (critical/high/medium/low)

        Raises:
            ValueError: If model not trained
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Extract and normalize features
        features = self.feature_extractor.extract_features(events)
        features_scaled = self.scaler.transform(features)

        # Get anomaly score
        score = self.model.decision_function(features_scaled)[0]
        is_anomaly = score < self.threshold

        # Determine severity
        severity = self._calculate_severity(score, features[0])

        result = {
            "is_anomaly": bool(is_anomaly),
            "score": float(score),
            "features": features[0].tolist(),
            "feature_names": self.feature_extractor.get_feature_names(),
            "severity": severity,
            "threshold": self.threshold,
        }

        logger.debug(
            "prediction_made",
            is_anomaly=is_anomaly,
            score=score,
            severity=severity,
            n_events=len(events),
        )

        return result

    def _calculate_severity(self, score: float, features: np.ndarray) -> str:
        """
        Calculate anomaly severity based on score and features.

        Severity levels:
        - critical: score < -1.0 or error_rate > 0.5
        - high: score < -0.85 or error_rate > 0.3
        - medium: score < -0.7 or error_rate > 0.15
        - low: score < threshold
        """
        error_rate = features[1]  # Second feature is error_rate

        if score < -1.0 or error_rate > 0.5:
            return "critical"
        elif score < -0.85 or error_rate > 0.3:
            return "high"
        elif score < -0.7 or error_rate > 0.15:
            return "medium"
        else:
            return "low"

    def save(self, path: Optional[str] = None) -> None:
        """
        Save model to disk.

        Args:
            path: Path to save model. Defaults to settings.model_path
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        save_path = path or settings.model_path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "threshold": self.threshold,
            "feature_names": self.feature_extractor.get_feature_names(),
        }

        joblib.dump(model_data, save_path)
        logger.info("model_saved", path=save_path)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AnomalyDetector":
        """
        Load model from disk.

        Args:
            path: Path to load model from. Defaults to settings.model_path

        Returns:
            Loaded AnomalyDetector instance
        """
        load_path = path or settings.model_path

        if not Path(load_path).exists():
            raise FileNotFoundError(f"Model not found at {load_path}")

        model_data = joblib.load(load_path)

        detector = cls(threshold=model_data["threshold"])
        detector.model = model_data["model"]
        detector.scaler = model_data["scaler"]
        detector.is_trained = True

        logger.info("model_loaded", path=load_path)
        return detector
