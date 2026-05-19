#!/usr/bin/env python3
"""Evaluate Helios's Isolation Forest pipeline on public anomaly benchmarks.

Runs the same 12-feature pipeline used in production (see
``services/detection/app/ml/feature_engineering.py``) on the Numenta Anomaly
Benchmark (NAB) and the Server Machine Dataset (SMD), reports metrics, and
saves artifacts under ``models/evaluation/``:

    results.json         - all metrics, all hyperparameters
    model_card.md        - Google-style model card
    {dataset}_pr.png     - precision-recall curve
    {dataset}_roc.png    - ROC curve
    {dataset}_cm.png     - confusion matrix at chosen threshold

Also logs experiments to MLflow (``mlruns/``) — three contamination values
per dataset by default.

Usage:
    python scripts/evaluate.py --dataset nab
    python scripts/evaluate.py --dataset smd
    python scripts/evaluate.py --dataset both --window-size 60 --stride 30
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.datasets.nab_loader import load_nab_streams  # noqa: E402
from scripts.datasets.smd_loader import load_smd_streams  # noqa: E402
from scripts.datasets.types import LabeledStream  # noqa: E402
from scripts.datasets.windows_to_features import (  # noqa: E402
    FEATURE_NAMES,
    fit_value_cutoff,
    normalize_streams,
    transform_to_features,
)

EVAL_DIR = REPO_ROOT / "models" / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


@dataclass
class ThresholdMetrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float
    tp: int
    fp: int
    tn: int
    fn: int


@dataclass
class DatasetResult:
    dataset: str
    n_train_windows: int
    n_val_windows: int
    n_test_windows: int
    anomaly_rate_train: float
    anomaly_rate_test: float
    chosen_threshold: float
    test_metrics: Dict[str, float]
    pr_auc: float
    roc_auc: float
    sweep: List[ThresholdMetrics] = field(default_factory=list)
    hyperparameters: Dict[str, float] = field(default_factory=dict)


def _binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> ThresholdMetrics:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return ThresholdMetrics(
        threshold=float("nan"),
        precision=precision,
        recall=recall,
        f1=f1,
        fpr=fpr,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
    )


# ---------------------------------------------------------------------------
# Split helpers
# ---------------------------------------------------------------------------


def split_streams_by_index(
    streams: List[LabeledStream],
    seed: int,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> Tuple[List[LabeledStream], List[LabeledStream], List[LabeledStream]]:
    """Split streams into train/val/test by stream identity (no temporal leakage)."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(streams))
    rng.shuffle(idx)
    n = len(streams)
    n_train = max(1, int(n * train_frac))
    n_val = max(1, int(n * val_frac))
    train = [streams[i] for i in idx[:n_train]]
    val = [streams[i] for i in idx[n_train : n_train + n_val]]
    test = [streams[i] for i in idx[n_train + n_val :]]
    if not test:
        test = val[-1:]
        val = val[:-1]
    return train, val, test


# ---------------------------------------------------------------------------
# Training + sweep
# ---------------------------------------------------------------------------


def train_isolation_forest(
    X_train: np.ndarray,
    contamination: float,
    n_estimators: int,
    seed: int,
):
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(X_train)
    X_scaled = scaler.transform(X_train)
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        max_samples="auto",
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(X_scaled)
    return model, scaler


def decision_scores(model, scaler, X: np.ndarray) -> np.ndarray:
    return model.decision_function(scaler.transform(X))


def sweep_thresholds(
    scores: np.ndarray, y_true: np.ndarray, lo: float = -1.0, hi: float = 0.5, step: float = 0.02
) -> List[ThresholdMetrics]:
    out: list[ThresholdMetrics] = []
    threshold = lo
    while threshold <= hi + 1e-9:
        y_pred = (scores < threshold).astype(np.int8)
        m = _binary_metrics(y_true, y_pred)
        m.threshold = float(threshold)
        out.append(m)
        threshold += step
    return out


def pick_best_threshold(sweep: List[ThresholdMetrics]) -> ThresholdMetrics:
    return max(sweep, key=lambda m: m.f1)


# ---------------------------------------------------------------------------
# Curves and plots
# ---------------------------------------------------------------------------


def _compute_pr_auc(scores: np.ndarray, y_true: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score

    # IsolationForest: lower score = more anomalous. average_precision_score
    # treats higher score as positive class, so we negate scores.
    return float(average_precision_score(y_true, -scores))


def _compute_roc_auc(scores: np.ndarray, y_true: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, -scores))


def _plot_pr(scores: np.ndarray, y_true: np.ndarray, out_path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve, average_precision_score

    precision, recall, _ = precision_recall_curve(y_true, -scores)
    ap = average_precision_score(y_true, -scores)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, label=f"AP = {ap:.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(title)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_roc(scores: np.ndarray, y_true: np.ndarray, out_path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve, roc_auc_score

    fpr, tpr, _ = roc_curve(y_true, -scores)
    auc = roc_auc_score(y_true, -scores)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_cm(m: ThresholdMetrics, out_path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = np.array([[m.tn, m.fp], [m.fn, m.tp]])
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["normal", "anomaly"])
    ax.set_yticklabels(["normal", "anomaly"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]}", ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Per-dataset evaluation
# ---------------------------------------------------------------------------


def evaluate_dataset(
    dataset: str,
    streams: List[LabeledStream],
    window_size: int,
    stride: int,
    contamination: float,
    n_estimators: int,
    seed: int,
    mlflow_experiment: str | None,
) -> Tuple[DatasetResult, np.ndarray, np.ndarray]:
    train_streams, val_streams, test_streams = split_streams_by_index(streams, seed)
    print(
        f"[{dataset}] split: {len(train_streams)} train / "
        f"{len(val_streams)} val / {len(test_streams)} test streams"
    )

    # Per-stream z-score normalization — each stream uses its own statistics,
    # so test streams never see training statistics (no leakage). This makes
    # the feature pipeline scale-invariant across heterogeneous NAB metrics.
    train_streams = normalize_streams(train_streams)
    val_streams = normalize_streams(val_streams)
    test_streams = normalize_streams(test_streams)

    value_cutoff = fit_value_cutoff(train_streams, quantile=0.95)
    train_feat = transform_to_features(train_streams, window_size, stride, value_cutoff)
    val_feat = transform_to_features(val_streams, window_size, stride, value_cutoff)
    test_feat = transform_to_features(test_streams, window_size, stride, value_cutoff)
    print(
        f"[{dataset}] windows: {train_feat.X.shape[0]} train / "
        f"{val_feat.X.shape[0]} val / {test_feat.X.shape[0]} test"
    )

    model, scaler = train_isolation_forest(
        train_feat.X, contamination=contamination, n_estimators=n_estimators, seed=seed
    )
    val_scores = decision_scores(model, scaler, val_feat.X)
    test_scores = decision_scores(model, scaler, test_feat.X)

    val_sweep = sweep_thresholds(val_scores, val_feat.y)
    best_val = pick_best_threshold(val_sweep)
    print(
        f"[{dataset}] best val threshold = {best_val.threshold:+.3f}  "
        f"F1 = {best_val.f1:.3f}  P = {best_val.precision:.3f}  R = {best_val.recall:.3f}"
    )

    y_test_pred = (test_scores < best_val.threshold).astype(np.int8)
    test_at_threshold = _binary_metrics(test_feat.y, y_test_pred)
    test_at_threshold.threshold = best_val.threshold

    pr_auc = _compute_pr_auc(test_scores, test_feat.y)
    roc_auc = _compute_roc_auc(test_scores, test_feat.y)

    _plot_pr(test_scores, test_feat.y, EVAL_DIR / f"{dataset}_pr.png", f"{dataset.upper()} - Precision/Recall")
    _plot_roc(test_scores, test_feat.y, EVAL_DIR / f"{dataset}_roc.png", f"{dataset.upper()} - ROC")
    _plot_cm(test_at_threshold, EVAL_DIR / f"{dataset}_cm.png", f"{dataset.upper()} - Confusion @ {best_val.threshold:+.2f}")

    if mlflow_experiment is not None:
        _log_to_mlflow(
            experiment=mlflow_experiment,
            dataset=dataset,
            contamination=contamination,
            n_estimators=n_estimators,
            window_size=window_size,
            stride=stride,
            seed=seed,
            threshold=best_val.threshold,
            test=test_at_threshold,
            pr_auc=pr_auc,
            roc_auc=roc_auc,
            model=model,
            scaler=scaler,
        )

    result = DatasetResult(
        dataset=dataset,
        n_train_windows=int(train_feat.X.shape[0]),
        n_val_windows=int(val_feat.X.shape[0]),
        n_test_windows=int(test_feat.X.shape[0]),
        anomaly_rate_train=float(train_feat.y.mean()),
        anomaly_rate_test=float(test_feat.y.mean()),
        chosen_threshold=best_val.threshold,
        test_metrics={
            "precision": test_at_threshold.precision,
            "recall": test_at_threshold.recall,
            "f1": test_at_threshold.f1,
            "fpr": test_at_threshold.fpr,
            "tp": test_at_threshold.tp,
            "fp": test_at_threshold.fp,
            "tn": test_at_threshold.tn,
            "fn": test_at_threshold.fn,
        },
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        sweep=val_sweep,
        hyperparameters={
            "contamination": contamination,
            "n_estimators": n_estimators,
            "window_size": window_size,
            "stride": stride,
            "value_cutoff_quantile": 0.95,
            "value_cutoff": value_cutoff,
            "seed": seed,
        },
    )
    return result, test_scores, test_feat.y


# ---------------------------------------------------------------------------
# MLflow logging
# ---------------------------------------------------------------------------


def _log_to_mlflow(
    experiment: str,
    dataset: str,
    contamination: float,
    n_estimators: int,
    window_size: int,
    stride: int,
    seed: int,
    threshold: float,
    test: ThresholdMetrics,
    pr_auc: float,
    roc_auc: float,
    model,
    scaler,
) -> None:
    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        print("[warn] mlflow not installed — skipping experiment logging.")
        return

    mlflow.set_tracking_uri((REPO_ROOT / "mlruns").as_uri())
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=f"{dataset}_c{contamination:.2f}_n{n_estimators}"):
        mlflow.log_params(
            {
                "dataset": dataset,
                "contamination": contamination,
                "n_estimators": n_estimators,
                "window_size": window_size,
                "stride": stride,
                "seed": seed,
                "threshold": threshold,
                "feature_pipeline": "helios_12f_v1",
            }
        )
        mlflow.log_metrics(
            {
                "precision": test.precision,
                "recall": test.recall,
                "f1": test.f1,
                "fpr": test.fpr,
                "pr_auc": pr_auc,
                "roc_auc": roc_auc,
                "tp": test.tp,
                "fp": test.fp,
                "tn": test.tn,
                "fn": test.fn,
            }
        )
        # Log the trained model as an artifact for reproducibility.
        try:
            import joblib

            tmp = REPO_ROOT / "models" / "evaluation" / f"{dataset}_c{contamination:.2f}_model.pkl"
            joblib.dump({"model": model, "scaler": scaler, "threshold": threshold}, tmp)
            mlflow.log_artifact(str(tmp))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] failed to log model artifact: {exc}")


# ---------------------------------------------------------------------------
# Model card
# ---------------------------------------------------------------------------


def write_model_card(results: List[DatasetResult], out_path: Path) -> None:
    md: list[str] = []
    md.append("# Helios Anomaly Detector — Model Card\n")
    md.append(f"*Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}*\n")
    md.append("## Model details\n")
    md.append(
        "- **Architecture:** scikit-learn `IsolationForest` with `StandardScaler`.\n"
        f"- **Feature pipeline:** 12 features, identical to "
        f"`services/detection/app/ml/feature_engineering.py`: {', '.join(FEATURE_NAMES)}.\n"
        "- **Threshold:** chosen per dataset by sweeping decision-function thresholds "
        "on the validation split and picking the value that maximises F1.\n"
    )

    md.append("## Intended use\n")
    md.append(
        "Detect anomalous windows in operational telemetry (event counts, error rates, "
        "latency percentiles) for the Helios observability platform. Out of scope: "
        "fraud detection, security intrusion detection, root-cause inference (SHAP "
        "feature attribution is provided separately by `app/ml/explainability.py`).\n"
    )

    md.append("## Evaluation data\n")
    md.append(
        "Two public, labeled benchmarks:\n"
        "- **NAB** (Numenta Anomaly Benchmark, Neurocomputing 2017): 58 univariate "
        "real-world streams (AWS CloudWatch, ad exchange, Twitter mentions, traffic).\n"
        "- **SMD** (Server Machine Dataset, OmniAnomaly KDD 2019): 28 server machines "
        "× 38 metrics × per-timestep labels.\n\n"
        "**Adapter:** raw values were mapped into Helios's 12-feature window schema "
        "by treating each value as one event's `latency_ms`. `error_rate` was proxied "
        "by the fraction of values exceeding the 95th-percentile cutoff of the "
        "training streams (computed once, applied to val and test — no label "
        "leakage). For SMD's multivariate streams, all (timestep, metric) values "
        "in a window were pooled before percentile computation.\n"
        "**Splits:** streams (NAB) / machines (SMD) shuffled with seed and split "
        "60% train / 20% validation / 20% test. Held-out test streams are never "
        "seen during training or threshold selection.\n"
    )

    md.append("## Performance\n")
    md.append("| Dataset | F1 | Precision | Recall | FPR | PR-AUC | ROC-AUC | Threshold | Test windows |")
    md.append("|---------|------|-----------|--------|------|--------|---------|-----------|--------------|")
    for r in results:
        t = r.test_metrics
        md.append(
            f"| {r.dataset.upper()} | {t['f1']:.3f} | {t['precision']:.3f} | {t['recall']:.3f} | "
            f"{t['fpr']:.3f} | {r.pr_auc:.3f} | {r.roc_auc:.3f} | "
            f"{r.chosen_threshold:+.2f} | {r.n_test_windows} |"
        )
    md.append("")

    md.append("## Limitations\n")
    md.append(
        "- Public benchmark performance is a proxy for production behaviour. NAB streams "
        "are mostly single-metric system telemetry; SMD is multivariate but its anomaly "
        "labels are inherently noisy (human-labeled by SREs). Production Helios sees "
        "12-feature windows over real Kafka event streams — performance there may "
        "differ.\n"
        "- The `error_rate` adapter is a self-supervised proxy (values above 95th "
        "percentile of training). On true Helios traffic this feature is computed from "
        "`level=ERROR|CRITICAL` event ratios, which is a different signal.\n"
        "- Isolation Forest is unsupervised: the chosen threshold reflects a "
        "validation-set operating point. Production should re-derive the threshold "
        "from its own labeled incidents (see `docs/MLOPS.md` for the retraining "
        "process).\n"
    )

    md.append("## Reproducibility\n")
    md.append(
        "```bash\n"
        "python scripts/evaluate.py --dataset both\n"
        "```\n\n"
        "Artifacts: `models/evaluation/results.json`, per-dataset PR/ROC/confusion "
        "PNGs, MLflow experiments under `mlruns/`. The chosen production threshold is "
        "loaded from `results.json` at service startup (see "
        "`services/detection/app/core/config.py`).\n"
    )

    out_path.write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tertiary eval: realistic_data_generator scenarios
# ---------------------------------------------------------------------------


def evaluate_scenarios(seed: int) -> Dict[str, float] | None:
    """Per-scenario recall on the controlled failure-mode generator."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "services" / "detection"))
        from app.ml.realistic_data_generator import RealisticDataGenerator  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] could not import RealisticDataGenerator: {exc}")
        return None

    try:
        # RealisticDataGenerator hardcodes random.seed(42); we just instantiate.
        _ = RealisticDataGenerator()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] scenario generator unavailable: {exc}")
        return None

    # The tertiary eval is intentionally lightweight here; deeper integration
    # belongs in Phase 4 once SHAP+drift are wired. Documenting scenario names
    # keeps a slot in results.json for per-scenario recall numbers once they
    # can be computed against the live consumer.
    scenarios = [
        "deployment_spike",
        "database_slowdown",
        "cache_miss_storm",
        "cascading_failure",
        "traffic_drop",
    ]
    return {s: float("nan") for s in scenarios}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _serialize_result(r: DatasetResult) -> dict:
    d = asdict(r)
    d["sweep"] = [asdict(m) for m in r.sweep]
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=["nab", "smd", "both"],
        default="both",
    )
    parser.add_argument("--window-size", type=int, default=60)
    parser.add_argument("--stride", type=int, default=30)
    parser.add_argument(
        "--contaminations",
        type=float,
        nargs="+",
        default=[0.05],
        help="Contamination values to log (each becomes a separate MLflow run). "
        "The first value is used for the canonical results.json metrics.",
    )
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-streams", type=int, default=None)
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Disable MLflow logging (still writes results.json and plots).",
    )
    args = parser.parse_args()

    datasets_to_run: list[tuple[str, list[LabeledStream]]] = []
    if args.dataset in ("nab", "both"):
        print("Loading NAB streams ...")
        nab = load_nab_streams(max_streams=args.max_streams)
        print(f"  loaded {len(nab)} NAB streams")
        datasets_to_run.append(("nab", nab))
    if args.dataset in ("smd", "both"):
        print("Loading SMD streams ...")
        smd = load_smd_streams(max_streams=args.max_streams)
        print(f"  loaded {len(smd)} SMD machines")
        datasets_to_run.append(("smd", smd))

    mlflow_experiment = None if args.no_mlflow else "helios-evaluation"

    canonical_results: list[DatasetResult] = []
    for name, streams in datasets_to_run:
        for i, contamination in enumerate(args.contaminations):
            print(
                f"\n=== {name.upper()}  contamination={contamination}  "
                f"n_estimators={args.n_estimators} ==="
            )
            result, _scores, _y = evaluate_dataset(
                dataset=name,
                streams=streams,
                window_size=args.window_size,
                stride=args.stride,
                contamination=contamination,
                n_estimators=args.n_estimators,
                seed=args.seed,
                mlflow_experiment=mlflow_experiment,
            )
            if i == 0:
                canonical_results.append(result)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feature_pipeline_version": "helios_12f_v1",
        "feature_names": FEATURE_NAMES,
        "args": {
            "window_size": args.window_size,
            "stride": args.stride,
            "contaminations": args.contaminations,
            "n_estimators": args.n_estimators,
            "seed": args.seed,
        },
        "datasets": [_serialize_result(r) for r in canonical_results],
        "scenarios": evaluate_scenarios(args.seed),
    }

    results_path = EVAL_DIR / "results.json"
    results_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {results_path}")

    card_path = EVAL_DIR / "model_card.md"
    write_model_card(canonical_results, card_path)
    print(f"Wrote {card_path}")

    print("\n=== Summary ===")
    for r in canonical_results:
        t = r.test_metrics
        print(
            f"  {r.dataset.upper():>4}  F1={t['f1']:.3f}  "
            f"P={t['precision']:.3f}  R={t['recall']:.3f}  "
            f"FPR={t['fpr']:.3f}  PR-AUC={r.pr_auc:.3f}  "
            f"ROC-AUC={r.roc_auc:.3f}  thr={r.chosen_threshold:+.2f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
