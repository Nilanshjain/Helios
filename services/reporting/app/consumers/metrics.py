"""Prometheus metrics for reporting consumer with safe registration"""

from prometheus_client import Counter, Histogram, REGISTRY


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


# Safe metric creation
reports_generated = get_or_create_counter(
    "helios_reports_generated_total",
    "Total reports generated",
    ["service", "severity", "generator"],
)

report_generation_latency = get_or_create_histogram(
    "helios_report_generation_latency_seconds",
    "Report generation time",
)

claude_tokens_used = get_or_create_counter(
    "helios_claude_tokens_used_total",
    "Total Claude tokens consumed",
)

claude_cost_usd = get_or_create_counter(
    "helios_claude_cost_usd_total",
    "Total Claude API cost in USD",
)
