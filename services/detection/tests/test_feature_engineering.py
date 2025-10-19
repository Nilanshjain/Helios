"""Tests for feature engineering module"""

import pytest
import numpy as np
from datetime import datetime

from app.ml.feature_engineering import FeatureExtractor


class TestFeatureExtractor:
    """Test suite for FeatureExtractor class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.extractor = FeatureExtractor(min_events=10)

    def test_extract_features_success(self):
        """Test successful feature extraction with valid events"""
        events = [
            {
                "service": "test-service",
                "level": "INFO",
                "message": "test message",
                "metadata": {"latency_ms": 100, "endpoint": "/api/users"},
            }
            for _ in range(20)
        ]

        # Add some ERROR events
        for i in range(5):
            events[i]["level"] = "ERROR"
            events[i]["metadata"]["latency_ms"] = 500

        features = self.extractor.extract_features(events)

        # Verify shape
        assert features.shape == (1, 7), "Should extract 7 features"

        # Verify feature values are valid
        assert features[0, 0] == 25, "Total events should be 25"
        assert 0.15 <= features[0, 1] <= 0.25, "Error rate should be ~20%"
        assert features[0, 2] > 0, "Average latency should be positive"
        assert features[0, 6] > 0, "Should have unique endpoints"

    def test_extract_features_insufficient_events(self):
        """Test that extraction fails with insufficient events"""
        events = [
            {
                "service": "test-service",
                "level": "INFO",
                "message": "test",
                "metadata": {},
            }
            for _ in range(5)
        ]

        with pytest.raises(ValueError, match="Insufficient events"):
            self.extractor.extract_features(events)

    def test_extract_features_high_error_rate(self):
        """Test feature extraction with high error rate"""
        events = []

        # Create 80% ERROR events
        for i in range(20):
            level = "ERROR" if i < 16 else "INFO"
            events.append(
                {
                    "service": "failing-service",
                    "level": level,
                    "message": f"message {i}",
                    "metadata": {"latency_ms": 1000 if level == "ERROR" else 50},
                }
            )

        features = self.extractor.extract_features(events)

        # Error rate should be ~80%
        error_rate = features[0, 1]
        assert 0.75 <= error_rate <= 0.85, f"Error rate should be ~80%, got {error_rate}"

        # Average latency should be high
        avg_latency = features[0, 2]
        assert avg_latency > 700, f"Average latency should be high, got {avg_latency}"

    def test_extract_features_latency_percentiles(self):
        """Test that latency percentiles are calculated correctly"""
        events = []

        # Create events with known latency distribution
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 500, 1000]
        for latency in latencies:
            events.append(
                {
                    "service": "test-service",
                    "level": "INFO",
                    "message": "test",
                    "metadata": {"latency_ms": latency},
                }
            )

        features = self.extractor.extract_features(events)

        p95_latency = features[0, 3]
        p99_latency = features[0, 4]

        # P95 should be around 500-1000
        assert p95_latency >= 100, f"P95 latency too low: {p95_latency}"

        # P99 should be higher than P95
        assert p99_latency >= p95_latency, "P99 should be >= P95"

    def test_extract_features_missing_metadata(self):
        """Test feature extraction with missing metadata"""
        events = [
            {
                "service": "test-service",
                "level": "INFO",
                "message": "test",
                "metadata": None,
            }
            for _ in range(15)
        ]

        features = self.extractor.extract_features(events)

        # Should still extract features, just with zeros for latency
        assert features.shape == (1, 7)
        assert features[0, 2] == 0, "Average latency should be 0 with missing metadata"

    def test_get_feature_names(self):
        """Test that feature names are returned correctly"""
        names = self.extractor.get_feature_names()

        expected_names = [
            "total_events",
            "error_rate",
            "avg_latency",
            "p95_latency",
            "p99_latency",
            "latency_stddev",
            "unique_endpoints",
        ]

        assert names == expected_names, "Feature names mismatch"

    def test_extract_features_critical_events(self):
        """Test feature extraction with CRITICAL level events"""
        events = []

        for i in range(15):
            level = "CRITICAL" if i < 3 else "INFO"
            events.append(
                {
                    "service": "critical-service",
                    "level": level,
                    "message": f"message {i}",
                    "metadata": {"latency_ms": 100},
                }
            )

        features = self.extractor.extract_features(events)

        # Error rate should include CRITICAL events
        error_rate = features[0, 1]
        assert error_rate == 3 / 15, f"Error rate should include CRITICAL events"

    def test_extract_features_multiple_endpoints(self):
        """Test unique endpoint counting"""
        events = []
        endpoints = ["/api/users", "/api/orders", "/api/products"]

        for i in range(15):
            events.append(
                {
                    "service": "api-service",
                    "level": "INFO",
                    "message": f"message {i}",
                    "metadata": {
                        "endpoint": endpoints[i % 3],
                        "latency_ms": 100,
                    },
                }
            )

        features = self.extractor.extract_features(events)

        # Should detect 3 unique endpoints
        unique_endpoints = features[0, 6]
        assert unique_endpoints == 3, f"Should detect 3 unique endpoints, got {unique_endpoints}"

    def test_extract_features_zero_latency_handling(self):
        """Test that zero/negative latencies are handled correctly"""
        events = []

        for i in range(15):
            events.append(
                {
                    "service": "test-service",
                    "level": "INFO",
                    "message": f"message {i}",
                    "metadata": {"latency_ms": 0 if i % 2 == 0 else 100},
                }
            )

        features = self.extractor.extract_features(events)

        # Zero latencies should be excluded from calculations
        avg_latency = features[0, 2]
        assert avg_latency > 0, "Zero latencies should be excluded"


# Benchmark tests for performance
class TestFeatureExtractionPerformance:
    """Performance tests for feature extraction"""

    def test_large_event_window(self):
        """Test feature extraction with large event window"""
        events = [
            {
                "service": "high-traffic-service",
                "level": "INFO" if i % 10 != 0 else "ERROR",
                "message": f"message {i}",
                "metadata": {
                    "latency_ms": 50 + (i % 100),
                    "endpoint": f"/api/endpoint{i % 5}",
                },
            }
            for i in range(1000)
        ]

        extractor = FeatureExtractor(min_events=10)
        features = extractor.extract_features(events)

        assert features.shape == (1, 7)
        assert features[0, 0] == 1000, "Should process all 1000 events"
