"""Feature engineering for time-series anomaly detection.

Schema v2 (27 features): 11 global + 16 per-service. The per-service columns
prevent aggregation dilution — a 20% error spike on a 5%-traffic service moves
the global ``error_rate`` by ~1pp but moves its own ``<service>_error_rate``
by 20pp, giving the Isolation Forest a much cleaner signal to learn from.

``hour_of_day`` was removed in v2: across a typical sub-hour training run it
collapses to a constant (zero variance), contributing only noise to the model.
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)


# Services the per-service feature columns cover. Matches the 8 services in
# ``scripts/generate_chaos_traffic.py:SERVICES``. New services in production
# would still contribute to the global features but not to per-service columns;
# adding them here requires retraining the model.
KNOWN_SERVICES = (
    "api-gateway",
    "auth-service",
    "user-service",
    "payment-service",
    "inventory-service",
    "notification-service",
    "recommendation-engine",
    "search-service",
)

PER_SERVICE_METRICS = ("error_rate", "p95_latency")


def _build_feature_names() -> List[str]:
    global_names = [
        "event_count",
        "error_rate",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "latency_std",
        "p95_p50_ratio",
        "p99_p95_ratio",
        "error_count",
        "log_event_count",
        "log_error_rate",
    ]
    per_service = [f"{svc}_{metric}" for svc in KNOWN_SERVICES for metric in PER_SERVICE_METRICS]
    return global_names + per_service


class FeatureExtractor:
    """Extract a 27-feature row from a window of events."""

    FEATURE_NAMES = _build_feature_names()

    def __init__(self, min_events: int = 10) -> None:
        self.min_events = min_events

    def extract_features(self, events: List[Dict[str, Any]]) -> np.ndarray:
        """Return a (1, 27) feature array. Raises ValueError if too few events."""
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
        # --- Global features ---
        event_count = len(df)
        error_events = df[df["level"].isin(["ERROR", "CRITICAL"])].shape[0]
        error_rate = error_events / event_count if event_count > 0 else 0.0

        latencies = self._extract_latencies(df)
        if len(latencies) > 0:
            p50_latency_ms = float(np.percentile(latencies, 50))
            p95_latency_ms = float(np.percentile(latencies, 95))
            p99_latency_ms = float(np.percentile(latencies, 99))
            latency_std = float(np.std(latencies))
        else:
            p50_latency_ms = p95_latency_ms = p99_latency_ms = latency_std = 0.0

        p95_p50_ratio = p95_latency_ms / (p50_latency_ms + 1)
        p99_p95_ratio = p99_latency_ms / (p95_latency_ms + 1)
        error_count = float(event_count) * error_rate
        log_event_count = float(np.log1p(event_count))
        log_error_rate = float(np.log1p(error_rate * 1000))

        global_features = [
            float(event_count),
            float(error_rate),
            p50_latency_ms,
            p95_latency_ms,
            p99_latency_ms,
            latency_std,
            float(p95_p50_ratio),
            float(p99_p95_ratio),
            error_count,
            log_event_count,
            log_error_rate,
        ]

        # --- Per-service features ---
        per_service_features = self._extract_per_service(df)

        features = global_features + per_service_features

        logger.debug(
            "features_extracted",
            event_count=event_count,
            error_rate=error_rate,
            p95_latency_ms=p95_latency_ms,
        )

        return features

    def _extract_per_service(self, df: pd.DataFrame) -> List[float]:
        """For each KNOWN_SERVICES: append [error_rate, p95_latency]."""
        out: List[float] = []
        # Group once for efficiency; missing services default to 0.0.
        grouped = {svc: g for svc, g in df.groupby("service")}
        for svc in KNOWN_SERVICES:
            g = grouped.get(svc)
            if g is None or len(g) == 0:
                out.extend([0.0, 0.0])
                continue
            err_n = g[g["level"].isin(["ERROR", "CRITICAL"])].shape[0]
            svc_error_rate = err_n / len(g)
            svc_lats = self._extract_latencies(g)
            svc_p95 = float(np.percentile(svc_lats, 95)) if len(svc_lats) > 0 else 0.0
            out.extend([float(svc_error_rate), svc_p95])
        return out

    def _extract_latencies(self, df: pd.DataFrame) -> np.ndarray:
        latencies = []
        for metadata in df["metadata"]:
            if metadata and isinstance(metadata, dict):
                latency = metadata.get("latency_ms", 0)
                if isinstance(latency, (int, float)) and latency > 0:
                    latencies.append(float(latency))
        return np.array(latencies)

    def get_feature_names(self) -> List[str]:
        return self.FEATURE_NAMES.copy()
