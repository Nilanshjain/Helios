"""Prometheus metrics for detection consumer with safe registration"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY


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
