"""Tests for feature engineering module (v2 schema: 27 features)."""

import pytest
import numpy as np

from app.ml.feature_engineering import FeatureExtractor, KNOWN_SERVICES


FEATURE_INDEX = {name: i for i, name in enumerate(FeatureExtractor.FEATURE_NAMES)}
N_FEATURES = len(FeatureExtractor.FEATURE_NAMES)


def _event(level: str = "INFO", latency_ms: int = 100, endpoint: str = "/api/users",
           timestamp: str = "2024-01-01T12:00:00Z", message: str = "test",
           service: str = "test-service") -> dict:
    return {
        "timestamp": timestamp,
        "service": service,
        "level": level,
        "message": message,
        "metadata": {"latency_ms": latency_ms, "endpoint": endpoint},
    }


class TestFeatureExtractor:
    def setup_method(self):
        self.extractor = FeatureExtractor(min_events=10)

    def test_extract_features_success(self):
        events = [_event() for _ in range(20)]
        for i in range(5):
            events[i]["level"] = "ERROR"
            events[i]["metadata"]["latency_ms"] = 500

        features = self.extractor.extract_features(events)

        assert features.shape == (1, N_FEATURES)
        assert features[0, FEATURE_INDEX["event_count"]] == 20
        assert 0.20 <= features[0, FEATURE_INDEX["error_rate"]] <= 0.30  # 5/20 == 0.25
        assert features[0, FEATURE_INDEX["p50_latency_ms"]] > 0

    def test_extract_features_insufficient_events(self):
        events = [_event() for _ in range(5)]
        with pytest.raises(ValueError, match="Insufficient events"):
            self.extractor.extract_features(events)

    def test_extract_features_high_error_rate(self):
        events = []
        for i in range(20):
            level = "ERROR" if i < 16 else "INFO"
            events.append(_event(level=level, latency_ms=1000 if level == "ERROR" else 50))

        features = self.extractor.extract_features(events)
        error_rate = features[0, FEATURE_INDEX["error_rate"]]
        assert 0.75 <= error_rate <= 0.85
        p95 = features[0, FEATURE_INDEX["p95_latency_ms"]]
        assert p95 >= 100

    def test_extract_features_latency_percentiles(self):
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 500, 1000]
        events = [_event(latency_ms=lat) for lat in latencies]

        features = self.extractor.extract_features(events)
        p50 = features[0, FEATURE_INDEX["p50_latency_ms"]]
        p95 = features[0, FEATURE_INDEX["p95_latency_ms"]]
        p99 = features[0, FEATURE_INDEX["p99_latency_ms"]]

        assert p50 > 0
        assert p95 >= p50
        assert p99 >= p95

    def test_extract_features_missing_metadata(self):
        events = []
        for _ in range(15):
            ev = _event()
            ev["metadata"] = None
            events.append(ev)

        features = self.extractor.extract_features(events)
        assert features.shape == (1, N_FEATURES)
        # No latency data → all latency features default to 0
        assert features[0, FEATURE_INDEX["p50_latency_ms"]] == 0.0

    def test_get_feature_names(self):
        names = self.extractor.get_feature_names()
        assert len(names) == 27
        # Global features (11 of them, no hour_of_day in v2)
        assert names[:11] == [
            "event_count", "error_rate",
            "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
            "latency_std",
            "p95_p50_ratio", "p99_p95_ratio",
            "error_count", "log_event_count", "log_error_rate",
        ]
        assert "hour_of_day" not in names
        # Per-service features (2 per service x 8 services = 16)
        for svc in KNOWN_SERVICES:
            assert f"{svc}_error_rate" in names
            assert f"{svc}_p95_latency" in names

    def test_per_service_error_rate_isolates_chaos(self):
        """A 20% error spike on payment-service alone should move
        payment-service_error_rate by 20pp while leaving global error_rate
        diluted (~2pp). This is the key motivation for v2's per-service columns."""
        events = []
        # 10 payment events, 2 of them errors
        for i in range(10):
            events.append(_event(service="payment-service",
                                 level="ERROR" if i < 2 else "INFO",
                                 latency_ms=500))
        # 90 api-gateway events, all normal
        for i in range(90):
            events.append(_event(service="api-gateway", level="INFO", latency_ms=80))

        features = self.extractor.extract_features(events)
        # Global error rate is diluted: 2/100 = 2%
        assert features[0, FEATURE_INDEX["error_rate"]] == pytest.approx(0.02)
        # Per-service rate captures the spike clearly: 2/10 = 20%
        assert features[0, FEATURE_INDEX["payment-service_error_rate"]] == pytest.approx(0.20)
        # api-gateway service column is clean
        assert features[0, FEATURE_INDEX["api-gateway_error_rate"]] == 0.0

    def test_per_service_features_default_to_zero_when_absent(self):
        """A service with no events in the window gets 0.0 for both per-service
        columns — IF treats 0 as 'quiet service this minute'."""
        events = [_event(service="api-gateway") for _ in range(15)]
        features = self.extractor.extract_features(events)
        for svc in KNOWN_SERVICES:
            if svc == "api-gateway":
                continue
            assert features[0, FEATURE_INDEX[f"{svc}_error_rate"]] == 0.0
            assert features[0, FEATURE_INDEX[f"{svc}_p95_latency"]] == 0.0

    def test_extract_features_critical_events(self):
        events = []
        for i in range(15):
            level = "CRITICAL" if i < 3 else "INFO"
            events.append(_event(level=level))

        features = self.extractor.extract_features(events)
        error_rate = features[0, FEATURE_INDEX["error_rate"]]
        assert error_rate == pytest.approx(3 / 15)



class TestFeatureExtractionPerformance:
    def test_large_event_window(self):
        events = [
            _event(
                level="INFO" if i % 10 != 0 else "ERROR",
                latency_ms=50 + (i % 100),
                endpoint=f"/api/endpoint{i % 5}",
            )
            for i in range(1000)
        ]
        extractor = FeatureExtractor(min_events=10)
        features = extractor.extract_features(events)
        assert features.shape == (1, N_FEATURES)
        # `event_count` is the first feature
        assert features[0, 0] == 1000
