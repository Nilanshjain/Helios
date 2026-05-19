"""Load the Server Machine Dataset (SMD) as labeled streams.

SMD is a multivariate operational-telemetry benchmark from a large internet
company, released with the OmniAnomaly paper (KDD 2019). It contains 28
machines, each with 38 metrics sampled at 1-minute intervals, with per-timestep
anomaly labels.

Reference: Su et al., "Robust Anomaly Detection for Multivariate Time Series
through Stochastic Recurrent Neural Network" (KDD 2019).

Layout under ServerMachineDataset/:
    train/machine-X-Y.txt        : pure-normal training values (no labels)
    test/machine-X-Y.txt         : test values
    test_label/machine-X-Y.txt   : 0/1 per timestep, 1 = anomaly

For evaluation we use the test split only — both for training and held-out
metrics — splitting per-machine by time. This matches how SMD is typically
benchmarked when ground-truth labels are needed end-to-end.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from scripts.datasets.download import ensure_smd
from scripts.datasets.types import LabeledStream

# SMD has no real timestamps; synthesize 1-minute intervals starting 2020-01-01
# so the hour_of_day feature gets a sensible (albeit synthetic) value.
_SYNTH_START = pd.Timestamp("2020-01-01 00:00:00")
_SYNTH_FREQ = pd.Timedelta(minutes=1)


def _read_csv_matrix(path: Path) -> np.ndarray:
    """Read SMD's comma-separated value-per-line files into an ndarray."""
    return pd.read_csv(path, header=None).to_numpy(dtype=np.float64)


def _read_label_vector(path: Path) -> np.ndarray:
    return pd.read_csv(path, header=None).to_numpy(dtype=np.int8).reshape(-1)


def load_smd_streams(max_streams: int | None = None) -> List[LabeledStream]:
    """Load each SMD machine as a multivariate LabeledStream.

    Args:
        max_streams: Cap on number of machines (useful for fast smoke runs).

    Returns:
        List of LabeledStream, one per machine. ``values`` has shape (n, 38).
    """
    smd_root = ensure_smd()
    test_dir = smd_root / "test"
    label_dir = smd_root / "test_label"
    if not test_dir.exists() or not label_dir.exists():
        raise RuntimeError(
            f"SMD layout unexpected at {smd_root}. Expected test/ and test_label/."
        )

    machine_files = sorted(p for p in test_dir.glob("*.txt"))
    if not machine_files:
        raise RuntimeError(f"No SMD test files found under {test_dir}")

    streams: list[LabeledStream] = []
    for csv_path in machine_files:
        machine_id = csv_path.stem  # e.g. "machine-1-1"
        label_path = label_dir / csv_path.name
        if not label_path.exists():
            continue
        values = _read_csv_matrix(csv_path)
        labels = _read_label_vector(label_path)
        if values.shape[0] != labels.shape[0]:
            # Some SMD distributions have a 1-row mismatch; truncate to min.
            n = min(values.shape[0], labels.shape[0])
            values = values[:n]
            labels = labels[:n]
        n = values.shape[0]
        ts = pd.DatetimeIndex(
            [_SYNTH_START + i * _SYNTH_FREQ for i in range(n)]
        )
        streams.append(
            LabeledStream(
                name=machine_id,
                source="smd",
                timestamps=ts,
                values=values,
                labels=labels,
                metadata={"n_metrics": int(values.shape[1])},
            )
        )
        if max_streams is not None and len(streams) >= max_streams:
            break
    return streams
