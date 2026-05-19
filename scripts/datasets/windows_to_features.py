"""Convert labeled time-series windows into Helios's 12-feature rows.

The production Helios FeatureExtractor (services/detection/app/ml/feature_engineering.py)
expects a list of event dicts with `level`, `metadata.latency_ms`, etc. Public
benchmarks like NAB and SMD don't have that schema — they're raw numeric time
series. To evaluate the *Helios feature-engineering + Isolation Forest*
pipeline on those benchmarks we use this adapter, which produces the exact
same 12 features (and same names) by treating each numeric value as if it
were one event's latency.

**Per-stream normalization.** NAB streams span very different scales (CPU
percent 0-100, Twitter mentions 0-50000, AWS request counts in millions). To
make the feature pipeline scale-invariant — without leaking across the
train/test stream split — each stream is z-score normalized using its OWN
mean and std before feature extraction. This is applied via
``normalize_streams``.

Mapping (documented in the model card):
    event_count       = window_size (constant per window; emitted for parity)
    error_rate        = fraction of |z| > train-derived 95th-percentile cutoff
                        of |z| (two-sided: catches both up-spikes and drops)
    p50/p95/p99       = percentiles of (normalized) values inside the window
    latency_std       = std of (normalized) values inside the window
    hour_of_day       = midpoint timestamp's hour
    p95_p50_ratio     = p95 / (p50 + 1)
    p99_p95_ratio     = p99 / (p95 + 1)
    error_count       = event_count * error_rate
    log_event_count   = log1p(event_count)
    log_error_rate    = log1p(error_rate * 1000)

A window is labeled anomalous (1) if any underlying timestep is labeled
anomalous in the source dataset.

For multivariate streams (SMD), values are first z-score normalized per
metric per machine, then pooled across (timestep, metric) before percentile
computation. This loses metric identity but preserves the feature schema for
cross-dataset comparability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

from scripts.datasets.types import LabeledStream

# Match services/detection/app/ml/feature_engineering.py exactly.
FEATURE_NAMES = [
    "event_count",
    "error_rate",
    "p50_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "latency_std",
    "hour_of_day",
    "p95_p50_ratio",
    "p99_p95_ratio",
    "error_count",
    "log_event_count",
    "log_error_rate",
]


@dataclass
class WindowedFeatures:
    """Output of windowing one or more LabeledStreams.

    X: (n_windows, 12) feature matrix in FEATURE_NAMES order.
    y: (n_windows,) binary labels (1 = anomaly).
    stream_names: per-window stream identifier (for diagnostics).
    """

    X: np.ndarray
    y: np.ndarray
    stream_names: List[str]


def _flatten_window_values(stream: LabeledStream, start: int, end: int) -> np.ndarray:
    """Return all numeric values within window [start, end) as a 1-D array."""
    chunk = stream.values[start:end]
    if stream.is_multivariate:
        return chunk.reshape(-1)
    return chunk


def _window_label(stream: LabeledStream, start: int, end: int) -> int:
    return int(stream.labels[start:end].any())


def extract_windows(
    streams: List[LabeledStream],
    window_size: int,
    stride: int,
) -> List[Tuple[LabeledStream, int, int]]:
    """Enumerate all (stream, start, end) windows across all streams."""
    out: list[tuple[LabeledStream, int, int]] = []
    for stream in streams:
        n = stream.n_points
        if n < window_size:
            continue
        for start in range(0, n - window_size + 1, stride):
            out.append((stream, start, start + window_size))
    return out


def normalize_streams(streams: List[LabeledStream]) -> List[LabeledStream]:
    """Z-score normalize each stream by its own mean and std.

    Univariate streams use scalar (mean, std). Multivariate streams use
    per-metric (mean, std) computed over the time axis. Zero-std metrics
    (constant) are left at zero (std=1 substitute) to avoid divide-by-zero.
    The labels, timestamps, name, source, and metadata are preserved.
    """
    out: list[LabeledStream] = []
    for s in streams:
        if s.is_multivariate:
            mean = s.values.mean(axis=0, keepdims=True)
            std = s.values.std(axis=0, keepdims=True)
            std = np.where(std == 0, 1.0, std)
            normed = (s.values - mean) / std
        else:
            mean = float(s.values.mean())
            std = float(s.values.std())
            if std == 0:
                std = 1.0
            normed = (s.values - mean) / std
        out.append(
            LabeledStream(
                name=s.name,
                source=s.source,
                timestamps=s.timestamps,
                values=normed,
                labels=s.labels,
                metadata=s.metadata,
            )
        )
    return out


def fit_value_cutoff(streams: List[LabeledStream], quantile: float = 0.95) -> float:
    """Compute the 'abnormal value' cutoff from training-stream absolute z-scores.

    With per-stream z-score normalization applied via ``normalize_streams``,
    the training values are roughly N(0, 1). Their absolute values follow a
    half-normal-like distribution; the 95th percentile of |z| from training
    becomes a principled cutoff for "abnormal" values in either direction.
    Multivariate streams contribute every (timestep, metric) value.
    """
    all_abs: list[np.ndarray] = []
    for s in streams:
        all_abs.append(np.abs(s.values).reshape(-1))
    pooled = np.concatenate(all_abs) if all_abs else np.array([])
    if pooled.size == 0:
        return float("inf")
    return float(np.quantile(pooled, quantile))


def transform_to_features(
    streams: List[LabeledStream],
    window_size: int,
    stride: int,
    value_cutoff: float,
) -> WindowedFeatures:
    """Convert streams into Helios-format feature rows.

    Args:
        streams: Streams to window.
        window_size: Number of timesteps per window.
        stride: Stride between window starts.
        value_cutoff: 'Abnormal value' threshold from ``fit_value_cutoff`` on
            training data. Used to compute error_rate inside each window.
    """
    rows: list[np.ndarray] = []
    labels: list[int] = []
    names: list[str] = []

    for stream, start, end in extract_windows(streams, window_size, stride):
        values = _flatten_window_values(stream, start, end)
        if values.size == 0:
            continue

        event_count = end - start
        if values.size == 0 or not np.isfinite(values).any():
            continue
        finite_vals = values[np.isfinite(values)]
        if finite_vals.size == 0:
            continue

        # Two-sided: |z| > cutoff catches both spikes and drops.
        error_rate = float(np.mean(np.abs(finite_vals) > value_cutoff))
        p50 = float(np.percentile(finite_vals, 50))
        p95 = float(np.percentile(finite_vals, 95))
        p99 = float(np.percentile(finite_vals, 99))
        latency_std = float(np.std(finite_vals))

        mid_ts: pd.Timestamp = stream.timestamps[(start + end) // 2]
        hour_of_day = float(mid_ts.hour)

        p95_p50_ratio = p95 / (p50 + 1.0)
        p99_p95_ratio = p99 / (p95 + 1.0)
        error_count = float(event_count) * error_rate
        log_event_count = float(np.log1p(event_count))
        log_error_rate = float(np.log1p(error_rate * 1000.0))

        rows.append(
            np.array(
                [
                    float(event_count),
                    error_rate,
                    p50,
                    p95,
                    p99,
                    latency_std,
                    hour_of_day,
                    p95_p50_ratio,
                    p99_p95_ratio,
                    error_count,
                    log_event_count,
                    log_error_rate,
                ],
                dtype=np.float64,
            )
        )
        labels.append(_window_label(stream, start, end))
        names.append(stream.name)

    if not rows:
        raise RuntimeError(
            f"No windows produced. Streams: {len(streams)}, window_size={window_size}, "
            f"stride={stride}. Check that streams are longer than window_size."
        )

    X = np.vstack(rows)
    y = np.array(labels, dtype=np.int8)
    return WindowedFeatures(X=X, y=y, stream_names=names)
