#!/usr/bin/env python3
"""Feature-drift detection using Population Stability Index (PSI).

Compares a *current* feature distribution against the *reference*
distribution the model was trained on and reports per-feature PSI. PSI is
the industry-standard drift metric for tabular ML; the conventional cutoffs
(from credit-risk modelling, adopted widely in MLOps) are:

    PSI < 0.10   -> no significant change
    0.10 - 0.25  -> minor change, monitor
    PSI > 0.25   -> significant shift, retrain candidate

Usage:
    # Compare current features in a CSV to the reference training data:
    python scripts/drift_check.py \\
        --reference models/training_data.csv \\
        --current data/recent_features.csv \\
        --output models/drift

    # Synthetic shift for demos / smoke tests (no live data needed):
    python scripts/drift_check.py --simulate moderate
    python scripts/drift_check.py --simulate severe

The script writes ``models/drift/{timestamp}/psi.json`` and a per-feature
PSI bar-chart PNG. Exit code is 0 if max PSI <= 0.25, 1 otherwise — handy
for cron / CI / a future Phase 5 ``make drift`` target.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

# Canonical feature schema. Kept in sync with
# ``services/detection/app/ml/feature_engineering.py:FEATURE_NAMES``.
# Inlined here (rather than imported) so drift_check.py runs from a
# lightweight environment without the detection service's runtime deps
# (structlog, fastapi, etc.) — useful for CI and standalone drift jobs.
KNOWN_SERVICES = (
    "api-gateway", "auth-service", "user-service", "payment-service",
    "inventory-service", "notification-service", "recommendation-engine",
    "search-service",
)
FEATURE_NAMES = [
    "event_count", "error_rate",
    "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
    "latency_std",
    "p95_p50_ratio", "p99_p95_ratio",
    "error_count", "log_event_count", "log_error_rate",
] + [
    f"{svc}_{metric}"
    for svc in KNOWN_SERVICES
    for metric in ("error_rate", "p95_latency")
]

PSI_MINOR = 0.10
PSI_MAJOR = 0.25
_EPS = 1e-6   # added to bin proportions so ln(p/q) is finite


@dataclass
class FeatureDrift:
    feature: str
    psi: float
    severity: str  # "ok" | "minor" | "major"
    bin_edges: List[float]
    reference_proportions: List[float]
    current_proportions: List[float]


# ---------------------------------------------------------------------------
# PSI core
# ---------------------------------------------------------------------------


def quantile_bin_edges(values: np.ndarray, n_bins: int) -> np.ndarray:
    """Quantile-based bin edges derived from the reference distribution.

    We use the reference (training) distribution to define bins so that PSI
    is symmetric with respect to which distribution is "newer" — the bins
    represent the reference's natural quantile structure. Edges are made
    monotonic by adding a tiny epsilon to break ties on constant features.
    """
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.array([0.0, 1.0])
    quantiles = np.linspace(0, 1, n_bins + 1)
    edges = np.quantile(finite, quantiles)
    # Make edges strictly monotonic — required for np.digitize to behave.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-9
    return edges


def bin_proportions(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Fraction of values falling in each bin defined by ``edges``."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(len(edges) - 1)
    # np.digitize returns 1..len(edges); clip into [1, n_bins]
    n_bins = len(edges) - 1
    idx = np.digitize(finite, edges[1:-1]) if n_bins > 1 else np.zeros(finite.shape, dtype=int)
    idx = np.clip(idx, 0, n_bins - 1)
    counts = np.bincount(idx, minlength=n_bins).astype(np.float64)
    total = counts.sum()
    if total == 0:
        return np.zeros(n_bins)
    return counts / total


def population_stability_index(
    reference: np.ndarray, current: np.ndarray, n_bins: int = 10
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Compute PSI between reference and current 1-D distributions.

    Returns (psi, edges, reference_props, current_props).
    """
    edges = quantile_bin_edges(reference, n_bins=n_bins)
    p_ref = bin_proportions(reference, edges) + _EPS
    p_cur = bin_proportions(current, edges) + _EPS
    psi = float(np.sum((p_cur - p_ref) * np.log(p_cur / p_ref)))
    return psi, edges, p_ref, p_cur


def classify(psi: float) -> str:
    if psi >= PSI_MAJOR:
        return "major"
    if psi >= PSI_MINOR:
        return "minor"
    return "ok"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_csv_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Filter to only columns the model knows about, keeping order stable.
    cols = [c for c in FEATURE_NAMES if c in df.columns]
    if not cols:
        raise ValueError(
            f"{path} has no recognised feature columns. Expected at least one of "
            f"{FEATURE_NAMES[:3]}..."
        )
    return df[cols]


def load_reference(path: Optional[Path]) -> pd.DataFrame:
    """Reference (training) distribution.

    Default: ``models/training_data.csv`` produced by
    ``scripts/train_production.py --save-features``. If the file is absent we
    fail loudly rather than fabricating a baseline — PSI against a synthetic
    reference would silently mislead.
    """
    if path is not None and path.exists():
        return _load_csv_features(path)

    default = REPO_ROOT / "models" / "training_data.csv"
    if default.exists():
        return _load_csv_features(default)

    raise FileNotFoundError(
        f"No reference distribution available. Expected --reference CSV or "
        f"{default}. Run "
        f"`python scripts/train_production.py --timeline ... --save-features` "
        f"to regenerate it from the same data the production model was trained on."
    )


def load_current(
    path: Optional[Path], simulate: Optional[str], reference: pd.DataFrame
) -> pd.DataFrame:
    """Current production-window distribution.

    Either loaded from a CSV (real production snapshot) or synthesised by
    perturbing the reference (``--simulate`` flag) so the demo always has a
    runnable case. The simulator is deliberately crude — it shifts certain
    features and rescales others; that exercises both directions of PSI
    sensitivity.
    """
    if path is not None and path.exists():
        return _load_csv_features(path)
    if not simulate:
        raise FileNotFoundError(
            "No --current CSV provided and no --simulate flag. Use --simulate moderate "
            "for a synthetic drifted distribution."
        )

    rng = np.random.default_rng(42)
    current = reference.copy()

    if simulate == "none":
        return current

    if simulate == "minor":
        latency_mult = 1.10
        error_shift = 1.5
        traffic_mult = 1.05
    elif simulate == "moderate":
        latency_mult = 1.40
        error_shift = 3.0
        traffic_mult = 1.20
    elif simulate == "severe":
        latency_mult = 2.0
        error_shift = 6.0
        traffic_mult = 1.5
    else:
        raise ValueError(f"unknown --simulate value: {simulate}")

    current["p50_latency_ms"] *= latency_mult * rng.uniform(0.95, 1.05, size=len(current))
    current["p95_latency_ms"] *= latency_mult * rng.uniform(0.95, 1.05, size=len(current))
    current["p99_latency_ms"] *= latency_mult * rng.uniform(0.95, 1.05, size=len(current))
    current["latency_std"] *= latency_mult
    current["error_rate"] = np.clip(current["error_rate"] * error_shift, 0, 1.0)
    current["event_count"] = (current["event_count"] * traffic_mult).astype(int)

    # Recompute the derived features so the simulator stays self-consistent.
    current["p95_p50_ratio"] = current["p95_latency_ms"] / (current["p50_latency_ms"] + 1)
    current["p99_p95_ratio"] = current["p99_latency_ms"] / (current["p95_latency_ms"] + 1)
    current["error_count"] = current["event_count"] * current["error_rate"]
    current["log_event_count"] = np.log1p(current["event_count"])
    current["log_error_rate"] = np.log1p(current["error_rate"] * 1000)
    return current


# ---------------------------------------------------------------------------
# Plot + report
# ---------------------------------------------------------------------------


def plot_psi_bars(drifts: List[FeatureDrift], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [d.feature for d in drifts]
    psis = [d.psi for d in drifts]
    colors = []
    for d in drifts:
        if d.severity == "major":
            colors.append("#d62728")  # red
        elif d.severity == "minor":
            colors.append("#ff7f0e")  # orange
        else:
            colors.append("#2ca02c")  # green

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(names, psis, color=colors)
    ax.axhline(PSI_MINOR, color="orange", linestyle="--", linewidth=1, label=f"minor (PSI={PSI_MINOR})")
    ax.axhline(PSI_MAJOR, color="red", linestyle="--", linewidth=1, label=f"major (PSI={PSI_MAJOR})")
    ax.set_ylabel("PSI")
    ax.set_title("Population Stability Index per feature")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_report(
    drifts: List[FeatureDrift], reference_rows: int, current_rows: int, out_dir: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    max_psi = max((d.psi for d in drifts), default=0.0)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference_rows": reference_rows,
        "current_rows": current_rows,
        "thresholds": {"minor": PSI_MINOR, "major": PSI_MAJOR},
        "max_psi": max_psi,
        "max_psi_severity": classify(max_psi),
        "drift": [asdict(d) for d in drifts],
    }
    json_path = out_dir / "psi.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="CSV with reference (training) feature distribution. "
        "Defaults to models/training_data.csv; falls back to synthetic.",
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=None,
        help="CSV with current feature distribution to compare against reference.",
    )
    parser.add_argument(
        "--simulate",
        choices=["none", "minor", "moderate", "severe"],
        default=None,
        help="If no --current CSV, perturb the reference to simulate drift "
        "(useful for demos and smoke tests).",
    )
    parser.add_argument(
        "--n-bins", type=int, default=10, help="Quantile bin count for PSI"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "models" / "drift",
        help="Directory to write psi.json + psi_bars.png",
    )
    args = parser.parse_args()

    reference = load_reference(args.reference)
    current = load_current(args.current, args.simulate, reference)

    print(f"reference rows: {len(reference)}  current rows: {len(current)}")
    drifts: List[FeatureDrift] = []
    for feature in FEATURE_NAMES:
        if feature not in reference.columns or feature not in current.columns:
            continue
        psi, edges, p_ref, p_cur = population_stability_index(
            reference[feature].to_numpy(dtype=float),
            current[feature].to_numpy(dtype=float),
            n_bins=args.n_bins,
        )
        drifts.append(
            FeatureDrift(
                feature=feature,
                psi=psi,
                severity=classify(psi),
                bin_edges=edges.tolist(),
                reference_proportions=p_ref.tolist(),
                current_proportions=p_cur.tolist(),
            )
        )

    drifts.sort(key=lambda d: d.psi, reverse=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output / timestamp
    json_path = write_report(drifts, len(reference), len(current), out_dir)
    plot_psi_bars(drifts, out_dir / "psi_bars.png")
    # Also update a "latest" pointer next to the timestamped runs so the
    # model-health dashboard / drift alert can read a stable path.
    latest_dir = args.output / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "psi.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    plot_psi_bars(drifts, latest_dir / "psi_bars.png")

    print(f"\nWrote {json_path}")
    print(f"Wrote {out_dir / 'psi_bars.png'}")
    print(f"\nTop 5 by PSI:")
    for d in drifts[:5]:
        marker = {"major": "!!", "minor": "! ", "ok": "  "}[d.severity]
        print(f"  {marker} {d.feature:<20} psi={d.psi:.3f}  ({d.severity})")

    max_psi = max((d.psi for d in drifts), default=0.0)
    return 1 if max_psi > PSI_MAJOR else 0


if __name__ == "__main__":
    sys.exit(main())
