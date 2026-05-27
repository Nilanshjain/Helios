"""Tests for anomaly detection module (v2 schema: 27 features)."""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from app.ml.anomaly_detector import AnomalyDetector
from app.ml.feature_engineering import FeatureExtractor


FEATURE_NAMES_V2 = list(FeatureExtractor.FEATURE_NAMES)
N_FEATURES = len(FEATURE_NAMES_V2)


def _events(n: int, error_rate: float = 0.1, avg_latency: int = 100,
            timestamp: str = "2024-01-01T12:00:00Z") -> list:
    events = []
    n_errors = int(n * error_rate)
    for i in range(n):
        is_error = i < n_errors
        events.append({
            "timestamp": timestamp,
            "service": "test-service",
            "level": "ERROR" if is_error else "INFO",
            "message": f"message {i}",
            "metadata": {
                "latency_ms": avg_latency * 10 if is_error else avg_latency,
                "endpoint": f"/api/endpoint{i % 3}",
            },
        })
    return events


def _training_data(n_windows: int = 30, seed: int = 0) -> list:
    """Realistic-ish training data with feature variance — the IF can't learn
    discrimination from a constant matrix."""
    import random as _random
    rng = _random.Random(seed)
    out = []
    for i in range(n_windows):
        hour = i % 24
        size = rng.randint(15, 40)
        avg_lat = rng.randint(40, 150)
        err = rng.uniform(0.02, 0.08)
        # Build events with per-event latency jitter so percentile/std features have spread.
        events = []
        n_errors = int(size * err)
        for j in range(size):
            is_error = j < n_errors
            events.append({
                "timestamp": f"2024-01-01T{hour:02d}:30:00Z",
                "service": "test-service",
                "level": "ERROR" if is_error else "INFO",
                "message": f"m{j}",
                "metadata": {
                    "latency_ms": int(rng.gauss(avg_lat * (10 if is_error else 1), avg_lat * 0.3)),
                    "endpoint": f"/api/endpoint{j % 3}",
                },
            })
        out.append(events)
    return out


class TestAnomalyDetector:
    def test_initialization(self):
        detector = AnomalyDetector()
        assert detector.threshold == -0.7
        assert not detector.is_trained
        assert detector.model is not None
        assert detector.scaler is not None

    def test_initialization_custom_params(self):
        detector = AnomalyDetector(contamination=0.1, threshold=-0.8, n_estimators=50, random_state=123)
        assert detector.threshold == -0.8
        assert not detector.is_trained

    def test_train_success(self):
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        stats = detector.train(_training_data(n_windows=30))
        assert detector.is_trained
        assert stats["n_windows"] == 30
        assert stats["n_valid_windows"] >= 20
        assert stats["n_features"] == N_FEATURES

    def test_train_insufficient_windows(self):
        detector = AnomalyDetector()
        with pytest.raises(ValueError, match="Insufficient training windows"):
            detector.train(_training_data(n_windows=5))

    def test_predict_without_training(self):
        detector = AnomalyDetector()
        with pytest.raises(ValueError, match="Model not trained"):
            detector.predict(_events(20))

    def test_predict_returns_expected_keys(self):
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        detector.train(_training_data(n_windows=30))
        result = detector.predict(_events(20))
        for key in ("is_anomaly", "score", "features", "severity", "threshold", "feature_names"):
            assert key in result
        assert len(result["features"]) == N_FEATURES
        assert result["feature_names"] == FEATURE_NAMES_V2

    def test_predict_anomalous_lower_score(self):
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        detector.train(_training_data(n_windows=30))
        normal_score = detector.predict(_events(20, error_rate=0.05, avg_latency=100))["score"]
        anomalous_score = detector.predict(_events(20, error_rate=0.8, avg_latency=1000))["score"]
        assert anomalous_score < normal_score

    def test_severity_calculation(self):
        detector = AnomalyDetector()
        # 27-feature vector; feature index 1 is error_rate (production uses it
        # in the severity hybrid)
        def feat(error_rate: float) -> np.ndarray:
            arr = np.zeros(N_FEATURES, dtype=float)
            arr[0] = 100  # event_count
            arr[1] = error_rate
            arr[2] = 100  # p50
            arr[3] = 200  # p95
            arr[4] = 300  # p99
            return arr

        cases = [
            (-1.5, 0.6, "critical"),
            (-0.9, 0.4, "high"),
            (-0.75, 0.2, "medium"),
            (-0.5, 0.05, "low"),
        ]
        for score, err, expected in cases:
            assert detector._calculate_severity(score, feat(err)) == expected, (
                f"score={score} err={err} expected {expected}"
            )

    def test_save_without_training(self):
        detector = AnomalyDetector()
        with pytest.raises(ValueError, match="Cannot save untrained model"):
            detector.save("/tmp/test_model.pkl")

    @patch("joblib.dump")
    @patch("pathlib.Path.mkdir")
    def test_save_includes_full_payload(self, mock_mkdir, mock_dump):
        detector = AnomalyDetector()
        detector.train(_training_data(n_windows=30))
        detector.save("/tmp/test_model.pkl")
        mock_dump.assert_called_once()
        saved = mock_dump.call_args[0][0]
        for key in ("model", "scaler", "threshold", "feature_names", "shap_background"):
            assert key in saved

    @patch("joblib.load")
    @patch("pathlib.Path.exists")
    def test_load_restores_state(self, mock_exists, mock_load):
        mock_exists.return_value = True
        mock_load.return_value = {
            "model": Mock(),
            "scaler": Mock(),
            "threshold": -0.7,
            "feature_names": FEATURE_NAMES_V2,
            "shap_background": np.zeros((10, N_FEATURES)),
        }
        detector = AnomalyDetector.load("/tmp/test_model.pkl")
        assert detector.is_trained
        assert detector.threshold == -0.7
        assert detector._shap_background is not None

    @patch("pathlib.Path.exists")
    def test_load_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        with pytest.raises(FileNotFoundError):
            AnomalyDetector.load("/tmp/nonexistent_model.pkl")


class TestAnomalyDetectorIntegration:
    def test_end_to_end_workflow(self):
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        stats = detector.train(_training_data(n_windows=30))
        assert stats["n_windows"] == 30

        normal_result = detector.predict(_events(20, error_rate=0.05, avg_latency=100))
        anomalous_result = detector.predict(_events(20, error_rate=0.7, avg_latency=2000))
        assert anomalous_result["score"] < normal_result["score"]
