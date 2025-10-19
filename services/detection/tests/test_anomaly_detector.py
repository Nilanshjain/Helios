"""Tests for anomaly detection module"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from app.ml.anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    """Test suite for AnomalyDetector class"""

    def create_sample_events(self, n_events: int, error_rate: float = 0.1, avg_latency: int = 100):
        """Helper to create sample events for testing"""
        events = []

        for i in range(n_events):
            level = "ERROR" if i < int(n_events * error_rate) else "INFO"
            latency = avg_latency * 10 if level == "ERROR" else avg_latency

            events.append(
                {
                    "service": "test-service",
                    "level": level,
                    "message": f"message {i}",
                    "metadata": {
                        "latency_ms": latency,
                        "endpoint": f"/api/endpoint{i % 3}",
                    },
                }
            )

        return events

    def create_training_data(self, n_windows: int = 50):
        """Create training data with multiple event windows"""
        return [self.create_sample_events(20, error_rate=0.05) for _ in range(n_windows)]

    def test_initialization(self):
        """Test detector initialization with default parameters"""
        detector = AnomalyDetector()

        assert detector.threshold == -0.7
        assert not detector.is_trained
        assert detector.model is not None
        assert detector.scaler is not None

    def test_initialization_custom_params(self):
        """Test detector initialization with custom parameters"""
        detector = AnomalyDetector(
            contamination=0.1, threshold=-0.8, n_estimators=50, random_state=123
        )

        assert detector.threshold == -0.8
        assert not detector.is_trained

    def test_train_success(self):
        """Test successful model training"""
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        training_data = self.create_training_data(n_windows=30)

        stats = detector.train(training_data)

        assert detector.is_trained
        assert stats["n_windows"] == 30
        assert stats["n_valid_windows"] >= 20
        assert stats["n_features"] == 7
        assert "score_mean" in stats
        assert "score_std" in stats

    def test_train_insufficient_windows(self):
        """Test training fails with insufficient windows"""
        detector = AnomalyDetector()
        training_data = self.create_training_data(n_windows=5)

        with pytest.raises(ValueError, match="Insufficient training windows"):
            detector.train(training_data)

    def test_predict_without_training(self):
        """Test that prediction fails if model not trained"""
        detector = AnomalyDetector()
        events = self.create_sample_events(20)

        with pytest.raises(ValueError, match="Model not trained"):
            detector.predict(events)

    def test_predict_normal_behavior(self):
        """Test prediction on normal behavior"""
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)
        training_data = self.create_training_data(n_windows=30)
        detector.train(training_data)

        # Normal events with low error rate
        normal_events = self.create_sample_events(20, error_rate=0.05, avg_latency=100)
        result = detector.predict(normal_events)

        assert "is_anomaly" in result
        assert "score" in result
        assert "features" in result
        assert "severity" in result
        assert len(result["features"]) == 7

    def test_predict_anomalous_behavior(self):
        """Test prediction on anomalous behavior"""
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)

        # Train on normal data
        normal_data = [
            self.create_sample_events(20, error_rate=0.05, avg_latency=100)
            for _ in range(30)
        ]
        detector.train(normal_data)

        # Test on anomalous data (high error rate and latency)
        anomalous_events = self.create_sample_events(20, error_rate=0.8, avg_latency=1000)
        result = detector.predict(anomalous_events)

        # Anomalous data should have lower score (more negative)
        assert result["score"] < 0, "Anomalous data should have negative score"

    def test_severity_calculation(self):
        """Test severity level calculation"""
        detector = AnomalyDetector()

        # Test different severity levels
        test_cases = [
            # (score, error_rate, expected_severity)
            (-1.5, 0.6, "critical"),
            (-0.9, 0.4, "high"),
            (-0.75, 0.2, "medium"),
            (-0.5, 0.05, "low"),
        ]

        for score, error_rate, expected_severity in test_cases:
            features = np.array([100, error_rate, 100, 200, 300, 50, 3])
            severity = detector._calculate_severity(score, features)
            assert (
                severity == expected_severity
            ), f"Score {score}, error_rate {error_rate} should be {expected_severity}, got {severity}"

    def test_feature_names_in_result(self):
        """Test that feature names are included in prediction result"""
        detector = AnomalyDetector()
        training_data = self.create_training_data(n_windows=30)
        detector.train(training_data)

        events = self.create_sample_events(20)
        result = detector.predict(events)

        expected_features = [
            "total_events",
            "error_rate",
            "avg_latency",
            "p95_latency",
            "p99_latency",
            "latency_stddev",
            "unique_endpoints",
        ]

        assert result["feature_names"] == expected_features

    def test_save_without_training(self):
        """Test that save fails if model not trained"""
        detector = AnomalyDetector()

        with pytest.raises(ValueError, match="Cannot save untrained model"):
            detector.save("/tmp/test_model.pkl")

    @patch("joblib.dump")
    @patch("pathlib.Path.mkdir")
    def test_save_success(self, mock_mkdir, mock_dump):
        """Test successful model save"""
        detector = AnomalyDetector()
        training_data = self.create_training_data(n_windows=30)
        detector.train(training_data)

        detector.save("/tmp/test_model.pkl")

        mock_dump.assert_called_once()
        # Verify the data being saved includes model, scaler, threshold
        saved_data = mock_dump.call_args[0][0]
        assert "model" in saved_data
        assert "scaler" in saved_data
        assert "threshold" in saved_data

    @patch("joblib.load")
    @patch("pathlib.Path.exists")
    def test_load_success(self, mock_exists, mock_load):
        """Test successful model load"""
        mock_exists.return_value = True
        mock_load.return_value = {
            "model": Mock(),
            "scaler": Mock(),
            "threshold": -0.7,
            "feature_names": ["feature1", "feature2"],
        }

        detector = AnomalyDetector.load("/tmp/test_model.pkl")

        assert detector.is_trained
        assert detector.threshold == -0.7
        mock_load.assert_called_once_with("/tmp/test_model.pkl")

    @patch("pathlib.Path.exists")
    def test_load_file_not_found(self, mock_exists):
        """Test load fails when file doesn't exist"""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError):
            AnomalyDetector.load("/tmp/nonexistent_model.pkl")


class TestAnomalyDetectorIntegration:
    """Integration tests for complete anomaly detection workflow"""

    def create_sample_events(self, n_events: int, error_rate: float = 0.1, avg_latency: int = 100):
        """Helper to create sample events"""
        events = []
        for i in range(n_events):
            level = "ERROR" if i < int(n_events * error_rate) else "INFO"
            latency = avg_latency * 10 if level == "ERROR" else avg_latency
            events.append(
                {
                    "service": "test-service",
                    "level": level,
                    "message": f"message {i}",
                    "metadata": {"latency_ms": latency, "endpoint": "/api/test"},
                }
            )
        return events

    def test_end_to_end_workflow(self):
        """Test complete workflow: train -> predict -> save -> load -> predict"""
        # Initialize detector
        detector = AnomalyDetector(contamination=0.05, threshold=-0.7)

        # Train on normal data
        training_data = [
            self.create_sample_events(20, error_rate=0.05, avg_latency=100) for _ in range(30)
        ]
        stats = detector.train(training_data)

        assert stats["n_windows"] == 30

        # Predict on normal data
        normal_result = detector.predict(
            self.create_sample_events(20, error_rate=0.05, avg_latency=100)
        )

        # Predict on anomalous data
        anomalous_result = detector.predict(
            self.create_sample_events(20, error_rate=0.7, avg_latency=2000)
        )

        # Anomalous data should have lower score
        assert anomalous_result["score"] < normal_result["score"]
