"""Load Numenta Anomaly Benchmark (NAB) as labeled streams.

NAB is a univariate streaming anomaly benchmark with 58 time series across
real cloud metrics, ad-exchange data, Twitter mentions, traffic data, and a
few synthetic streams. We use the ``combined_windows.json`` label file, which
gives anomaly *windows* per stream — any timestamp inside a window is treated
as anomalous (label = 1).

Reference: Lavin & Ahmad, "Evaluating Real-time Anomaly Detection Algorithms"
(IEEE ICMLA 2015 / Neurocomputing 2017).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from scripts.datasets.download import ensure_nab
from scripts.datasets.types import LabeledStream


def _load_label_windows(nab_root: Path) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Parse NAB's combined_windows.json into per-stream (start, end) ranges."""
    label_file = nab_root / "labels" / "combined_windows.json"
    if not label_file.exists():
        raise FileNotFoundError(f"NAB labels not found at {label_file}")
    raw = json.loads(label_file.read_text())
    parsed: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for relpath, windows in raw.items():
        parsed[relpath] = [(pd.Timestamp(s), pd.Timestamp(e)) for s, e in windows]
    return parsed


def _label_for_timestamps(
    timestamps: pd.DatetimeIndex,
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> np.ndarray:
    labels = np.zeros(len(timestamps), dtype=np.int8)
    for start, end in windows:
        mask = (timestamps >= start) & (timestamps <= end)
        labels[mask] = 1
    return labels


def load_nab_streams(
    categories: list[str] | None = None,
    max_streams: int | None = None,
) -> List[LabeledStream]:
    """Load NAB time series into LabeledStream objects.

    Args:
        categories: Subdirectories under data/ to include
            (e.g., ["realAWSCloudwatch", "realAdExchange"]).
            None = all categories with labels.
        max_streams: Cap on number of streams (useful for fast smoke runs).

    Returns:
        List of LabeledStream, one per CSV file.
    """
    nab_root = ensure_nab()
    label_windows = _load_label_windows(nab_root)

    streams: list[LabeledStream] = []
    for relpath, windows in label_windows.items():
        if categories is not None:
            category = relpath.split("/", 1)[0]
            if category not in categories:
                continue
        csv_path = nab_root / "data" / relpath
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        ts = pd.DatetimeIndex(df["timestamp"])
        values = df["value"].to_numpy(dtype=np.float64)
        labels = _label_for_timestamps(ts, windows)
        streams.append(
            LabeledStream(
                name=relpath.replace("/", "__").replace(".csv", ""),
                source="nab",
                timestamps=ts,
                values=values,
                labels=labels,
                metadata={"category": relpath.split("/", 1)[0]},
            )
        )
        if max_streams is not None and len(streams) >= max_streams:
            break

    if not streams:
        raise RuntimeError(
            f"No NAB streams loaded. Check that {nab_root}/data/ contains CSV files "
            "and that categories filter (if any) matches the NAB category names."
        )
    return streams
