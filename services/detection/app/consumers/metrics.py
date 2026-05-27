"""Prometheus metrics for detection consumer with safe registration"""

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, REGISTRY


def get_or_create_counter(name: str, documentation: str, labelnames=None):
    """Get existing counter or create new one"""
    try:
        # Try to get existing metric
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
    except AttributeError:
        pass

    # Create new counter
    return Counter(name, documentation, labelnames or [])


def get_or_create_histogram(name: str, documentation: str, labelnames=None):
    """Get existing histogram or create new one"""
    try:
        # Try to get existing metric
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
    except AttributeError:
        pass

    # Create new histogram
    return Histogram(name, documentation, labelnames or [])


def get_or_create_gauge(name: str, documentation: str, labelnames=None):
    """Get existing gauge or create new one"""
    try:
        # Try to get existing metric
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
    except AttributeError:
        pass

    # Create new gauge
    return Gauge(name, documentation, labelnames or [])


def get_or_create_summary(name: str, documentation: str, labelnames=None):
    """Get existing summary or create new one"""
    try:
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
    except AttributeError:
        pass
    return Summary(name, documentation, labelnames or [])


# Safe metric creation
events_processed = get_or_create_counter(
    "helios_detection_events_processed_total",
    "Total events processed",
    ["service", "status"],
)

anomalies_detected = get_or_create_counter(
    "helios_anomalies_detected_total",
    "Total anomalies detected",
    ["service", "severity"],
)

detection_latency = get_or_create_histogram(
    "helios_detection_latency_seconds",
    "Detection latency in seconds",
)

window_size_gauge = get_or_create_gauge(
    "helios_detection_window_size",
    "Current window size",
    ["service"],
)

# SHAP inference latency. Emitted once per anomaly that gets explained, so
# the histogram doubles as a "did we successfully explain?" rate proxy:
# `rate(helios_shap_inference_seconds_count[5m])` vs.
# `rate(helios_anomalies_detected_total[5m])` should track 1:1 when SHAP is
# healthy.
shap_inference_latency = get_or_create_histogram(
    "helios_shap_inference_seconds",
    "SHAP attribution computation time per anomaly (seconds)",
)

# Phase-4 ML-observability metrics.
#
# Distribution of IsolationForest decision-function scores across every
# window the consumer evaluates (not just anomalies). Shift in this
# histogram is the earliest signal that the model is seeing data unlike
# what it was trained on — a leading indicator for feature drift before
# PSI even runs.
prediction_score = get_or_create_histogram(
    "helios_model_prediction_score",
    "IsolationForest decision_function score per window",
)

# Quantile snapshot of every feature value the model sees in production.
# Compared against the model's training distribution by scripts/drift_check.py
# (PSI) to detect data drift. One series per feature.
#
# KNOWN ISSUE: prometheus_client.Summary does NOT emit {quantile="..."} labels
# unless quantile objectives are configured at creation, which the Python client
# doesn't support directly. The Grafana "Live feature quantiles" panel queries
# helios_model_feature_value{quantile="0.5"} and shows "No data" as a result.
# Fix: switch to a Histogram with explicit buckets, then update the dashboard
# query to histogram_quantile(0.5, ...). Until that change lands, only _sum and
# _count are usable from this metric.
feature_value = get_or_create_summary(
    "helios_model_feature_value",
    "Per-feature value distribution seen in production",
    ["feature"],
)

# Days since the loaded model was trained. Updated once at startup and
# again on each model reload. Lets us alert on stale models even when
# everything else looks healthy.
prediction_age_days = get_or_create_gauge(
    "helios_model_prediction_age_days",
    "Days since the currently-loaded model was trained",
)
