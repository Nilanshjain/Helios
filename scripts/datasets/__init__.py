"""Dataset adapters for evaluating Helios on public anomaly benchmarks.

Each loader returns a list of LabeledStream objects: one per logical "service"
in the benchmark (an AWS metric stream in NAB, a server machine in SMD).
The evaluation harness then converts each stream into Helios-format feature
rows via windows_to_features.py and trains a fresh Isolation Forest per
dataset.
"""

from scripts.datasets.types import LabeledStream

__all__ = ["LabeledStream"]
