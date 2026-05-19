"""Shared types for dataset loaders."""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class LabeledStream:
    """One labeled time series from a public benchmark.

    For univariate datasets (NAB), values has shape (n,) and represents a single
    metric over time. For multivariate datasets (SMD), values has shape (n, d)
    where d is the number of metrics for that machine.

    timestamps: pandas DatetimeIndex aligned with the first axis of values.
    labels:     1 = anomaly, 0 = normal, aligned with timestamps.
    name:       human-readable stream identifier (e.g., "ec2_cpu_utilization_24ae8d").
    source:     dataset name ("nab" or "smd").
    """

    name: str
    source: str
    timestamps: pd.DatetimeIndex
    values: np.ndarray
    labels: np.ndarray
    metadata: Optional[dict] = None

    def __post_init__(self) -> None:
        n = len(self.timestamps)
        if self.values.shape[0] != n:
            raise ValueError(f"{self.name}: values len {self.values.shape[0]} != timestamps len {n}")
        if self.labels.shape[0] != n:
            raise ValueError(f"{self.name}: labels len {self.labels.shape[0]} != timestamps len {n}")

    @property
    def is_multivariate(self) -> bool:
        return self.values.ndim == 2 and self.values.shape[1] > 1

    @property
    def n_points(self) -> int:
        return len(self.timestamps)

    @property
    def n_anomalies(self) -> int:
        return int(self.labels.sum())
