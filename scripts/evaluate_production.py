#!/usr/bin/env python3
"""Industry-standard evaluation of the production Isolation Forest.

Given the chaos timeline used for training, re-queries TimescaleDB, windows
the events, labels each window, loads the trained model, scores every
window, and produces:

  Threshold-dependent (at the model's deployed threshold):
    - Precision, Recall, F1
    - Specificity (TNR), FPR
    - Matthews Correlation Coefficient (MCC)  (robust to class imbalance)
    - Balanced Accuracy
    - Confusion matrix (TP/FP/TN/FN)

  Threshold-independent:
    - ROC-AUC
    - PR-AUC (average precision)  (preferred for imbalanced data)
    - Best F1 across all thresholds (with threshold attained)
    - F2 score at deployed threshold (recall-weighted)

  Per-scenario diagnostics:
    - Recall per chaos scenario type
    - Per-individual-scenario: caught? detection latency?
    - Mean score during chaos vs baseline

  Operational metrics:
    - False alarms per hour of clean operation
    - Distribution of scores for normal vs anomaly windows

  Plots (PNG in models/evaluation/production/):
    - ROC curve
    - PR curve
    - Score histogram (normal vs anomaly, log y-axis)
    - Per-scenario-type recall bar chart
    - Detection-latency CDF

Outputs:
    models/evaluation/production/report.json   (full machine-readable)
    models/evaluation/production/REPORT.md     (human-readable verdict)
    models/evaluation/production/*.png         (5 plots)

Usage:
    python scripts/evaluate_production.py \\
        --timeline data/chaos/timeline_<utc>.json \\
        [--model models/isolation_forest.pkl] \\
        [--eval-split all|test|val]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "detection"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.ml.anomaly_detector import AnomalyDetector  # noqa: E402
from app.ml.feature_engineering import FeatureExtractor  # noqa: E402
from train_production import (  # noqa: E402
    Timeline, query_events, load_events_jsonl, build_windows, temporal_split, score_windows,
    _binary_metrics, sweep_thresholds, pick_best_threshold,
    compute_pr_auc, compute_roc_auc,
)


OUT_DIR = REPO_ROOT / "models" / "evaluation" / "production"


# ---------------------------------------------------------------------------
# Per-scenario analysis
# ---------------------------------------------------------------------------


@dataclass
class ScenarioDetection:
    type: str
    start_utc: str
    end_utc: str
    duration_s: float
    windows_total: int
    windows_caught: int
    detection_latency_s: Optional[float]  # None if never caught


def sweep_fbeta(scores: np.ndarray, y: np.ndarray, beta: float,
                lo: float = -1.0, hi: float = 0.5, step: float = 0.02) -> Tuple[float, float, float, float]:
    """Sweep thresholds; return (best_threshold, best_fbeta, P_at_best, R_at_best).

    F_beta = (1+beta^2) * P*R / (beta^2 * P + R). beta>1 weights recall.
    """
    best = (float("nan"), -1.0, 0.0, 0.0)
    t = lo
    b2 = beta * beta
    while t <= hi + 1e-9:
        y_pred = (scores < t).astype(np.int8)
        m = _binary_metrics(y, y_pred)
        denom = b2 * m.precision + m.recall
        f_b = (1 + b2) * m.precision * m.recall / denom if denom > 0 else 0.0
        if f_b > best[1]:
            best = (float(t), float(f_b), float(m.precision), float(m.recall))
        t += step
    return best


from typing import Tuple as _Tuple  # already imported but be safe


def analyze_scenarios(
    timeline: Timeline,
    windows: List,  # LabeledWindow
    scores: np.ndarray,
    threshold: float,
) -> List[ScenarioDetection]:
    """For each individual chaos scenario, report whether and how fast the model caught it."""
    out: List[ScenarioDetection] = []
    for s_start, s_end, s_type in timeline.scenarios:
        first_detection: Optional[datetime] = None
        n_in_scenario = 0
        n_caught = 0
        for w, score in zip(windows, scores):
            if w.end <= s_start or w.start >= s_end:
                continue
            n_in_scenario += 1
            if score < threshold:
                n_caught += 1
                if first_detection is None or w.start < first_detection:
                    first_detection = w.start
        latency = (first_detection - s_start).total_seconds() if first_detection else None
        out.append(ScenarioDetection(
            type=s_type,
            start_utc=s_start.isoformat(),
            end_utc=s_end.isoformat(),
            duration_s=(s_end - s_start).total_seconds(),
            windows_total=n_in_scenario,
            windows_caught=n_caught,
            detection_latency_s=latency,
        ))
    return out


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def plot_roc(scores: np.ndarray, y: np.ndarray, out_path: Path, title: str) -> float:
    from sklearn.metrics import roc_curve, roc_auc_score
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fpr, tpr, _ = roc_curve(y, -scores)
    auc = roc_auc_score(y, -scores)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr, color="#1f77b4", linewidth=2, label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], color="gray", linestyle="--", linewidth=1, label="random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate (Recall)")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return float(auc)


def plot_pr(scores: np.ndarray, y: np.ndarray, out_path: Path, title: str) -> float:
    from sklearn.metrics import precision_recall_curve, average_precision_score
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    precision, recall, _ = precision_recall_curve(y, -scores)
    ap = average_precision_score(y, -scores)
    base_rate = float(y.mean())
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(recall, precision, color="#2ca02c", linewidth=2, label=f"AP = {ap:.3f}")
    ax.axhline(base_rate, color="gray", linestyle="--", linewidth=1, label=f"random = {base_rate:.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(title)
    ax.legend(loc="lower left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return float(ap)


def plot_score_hist(scores: np.ndarray, y: np.ndarray, threshold: float, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    bins = np.linspace(scores.min(), scores.max(), 40)
    ax.hist(scores[y == 0], bins=bins, alpha=0.6, label=f"normal (n={int((y==0).sum())})", color="#2ca02c", edgecolor="black", linewidth=0.5)
    ax.hist(scores[y == 1], bins=bins, alpha=0.6, label=f"anomaly (n={int((y==1).sum())})", color="#d62728", edgecolor="black", linewidth=0.5)
    ax.axvline(threshold, color="black", linestyle="--", linewidth=1.5, label=f"threshold = {threshold:+.3f}")
    ax.set_xlabel("Isolation Forest anomaly score  (lower = more anomalous)")
    ax.set_ylabel("# windows")
    ax.set_yscale("symlog")
    ax.set_title("Score distribution by class")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_per_scenario_recall(scenarios: List[ScenarioDetection], out_path: Path) -> Dict[str, float]:
    """Per-scenario-TYPE recall (aggregated)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_type: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))  # (caught, total) windows
    for s in scenarios:
        c, t = by_type[s.type]
        by_type[s.type] = (c + s.windows_caught, t + s.windows_total)

    types = sorted(by_type.keys())
    recalls = [(by_type[t][0] / by_type[t][1]) if by_type[t][1] else float("nan") for t in types]
    counts = [by_type[t][1] for t in types]

    colors = ["#2ca02c" if r >= 0.8 else "#ff7f0e" if r >= 0.5 else "#d62728" for r in recalls]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(types, recalls, color=colors, edgecolor="black", linewidth=0.5)
    for bar, c in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"n={c}", ha="center", fontsize=9)
    ax.axhline(0.8, color="green", linestyle=":", linewidth=1, alpha=0.5, label="good (0.8)")
    ax.axhline(0.5, color="orange", linestyle=":", linewidth=1, alpha=0.5, label="ok (0.5)")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Per-type recall")
    ax.set_title("Recall by chaos scenario type")
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return {t: float(r) for t, r in zip(types, recalls)}


def plot_detection_latency_cdf(scenarios: List[ScenarioDetection], out_path: Path) -> Dict[str, float]:
    """CDF of detection latency (in seconds), one curve per scenario type.
    Returns summary stats (median, p90 over all detected scenarios)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    caught = [s.detection_latency_s for s in scenarios if s.detection_latency_s is not None]
    if not caught:
        # Empty plot
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "no scenarios were detected", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        fig.savefig(out_path, dpi=150); plt.close(fig)
        return {"median_latency_s": float("nan"), "p90_latency_s": float("nan")}

    sorted_lat = np.sort(caught)
    p = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(sorted_lat, p, marker="o", linewidth=2, color="#1f77b4")
    ax.set_xlabel("Detection latency (seconds from chaos onset)")
    ax.set_ylabel("CDF")
    ax.set_title("Detection latency CDF")
    ax.axvline(60, color="green", linestyle=":", alpha=0.5, label="1 window (60s)")
    ax.axvline(120, color="orange", linestyle=":", alpha=0.5, label="2 windows (120s)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return {
        "median_latency_s": float(np.median(sorted_lat)),
        "p90_latency_s": float(np.quantile(sorted_lat, 0.9)),
    }


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def grade(value: float, good: float, decent: float, higher_is_better: bool = True) -> str:
    if not isinstance(value, (int, float)) or value != value:  # nan
        return "n/a"
    if higher_is_better:
        if value >= good: return "GOOD"
        if value >= decent: return "DECENT"
        return "POOR"
    else:
        if value <= good: return "GOOD"
        if value <= decent: return "DECENT"
        return "POOR"


def write_verdict_markdown(path: Path, report: Dict) -> None:
    m = report["metrics_at_threshold"]
    ti = report["threshold_independent"]
    op = report["operational"]
    md: List[str] = []
    md.append("# Helios Production Model — Evaluation Report\n")
    md.append(f"*Generated {datetime.now(tz=timezone.utc).isoformat(timespec='seconds')}*  ")
    md.append(f"*Timeline: {report['timeline_path']}*  ")
    md.append(f"*Eval split: {report['eval_split']}*\n")

    md.append("## Dataset\n")
    md.append(f"- Total windows: **{report['n_windows']}**  "
              f"({report['n_anomaly']} anomaly, {report['n_normal']} normal, "
              f"anomaly rate = {report['anomaly_rate']:.1%})")
    md.append(f"- Chaos scenarios: **{report['n_scenarios']}**\n")

    md.append("## Threshold-dependent metrics\n")
    md.append(f"At deployed threshold = **{report['threshold']:+.3f}**:")
    md.append(f"")
    md.append(f"| Metric | Value | Grade |")
    md.append(f"|---|---:|:---:|")
    md.append(f"| Precision | {m['precision']:.3f} | {grade(m['precision'], 0.70, 0.40)} |")
    md.append(f"| Recall | {m['recall']:.3f} | {grade(m['recall'], 0.80, 0.50)} |")
    md.append(f"| F1 | {m['f1']:.3f} | {grade(m['f1'], 0.60, 0.40)} |")
    md.append(f"| F2 (recall-weighted) | {m['f2']:.3f} | {grade(m['f2'], 0.60, 0.40)} |")
    md.append(f"| Specificity (TNR) | {m['specificity']:.3f} | {grade(m['specificity'], 0.95, 0.85)} |")
    md.append(f"| False Positive Rate | {m['fpr']:.3f} | {grade(m['fpr'], 0.05, 0.10, higher_is_better=False)} |")
    md.append(f"| MCC | {m['mcc']:.3f} | {grade(m['mcc'], 0.50, 0.20)} |")
    md.append(f"| Balanced Accuracy | {m['balanced_accuracy']:.3f} | {grade(m['balanced_accuracy'], 0.80, 0.65)} |")
    md.append("")
    md.append(f"Confusion matrix: TP={m['tp']}  FP={m['fp']}  TN={m['tn']}  FN={m['fn']}\n")

    md.append("## Threshold-independent metrics\n")
    md.append(f"| Metric | Value | Grade | Note |")
    md.append(f"|---|---:|:---:|---|")
    md.append(f"| **PR-AUC** | {ti['pr_auc']:.3f} | {grade(ti['pr_auc'], 0.70, 0.50)} | preferred for imbalanced data |")
    md.append(f"| **ROC-AUC** | {ti['roc_auc']:.3f} | {grade(ti['roc_auc'], 0.85, 0.70)} | overall ranking quality |")
    md.append(f"| Best F1 (any threshold) | {ti['best_f1']:.3f} @ {ti['best_f1_threshold']:+.3f} | {grade(ti['best_f1'], 0.70, 0.50)} | upper bound of F1 |")
    md.append(f"| Baseline (random) PR-AUC | {report['anomaly_rate']:.3f} |  | model must exceed |")
    md.append("")

    md.append("## Per-scenario-type recall\n")
    md.append(f"| Type | Recall | Grade |")
    md.append(f"|---|---:|:---:|")
    for stype, recall in sorted(report["per_type_recall"].items()):
        md.append(f"| {stype} | {recall:.3f} | {grade(recall, 0.80, 0.50)} |")
    md.append("")

    md.append("## Detection latency\n")
    md.append(f"- Median latency: **{op['median_latency_s']:.1f}s** ({op['median_latency_s']/60:.1f} min) — {grade(op['median_latency_s'], 60, 180, higher_is_better=False)}")
    md.append(f"- P90 latency: **{op['p90_latency_s']:.1f}s** ({op['p90_latency_s']/60:.1f} min)")
    md.append(f"- Scenarios caught: {op['scenarios_caught']}/{op['scenarios_total']}\n")

    md.append("## Operational metrics\n")
    md.append(f"- Clean-period false alarms: **{op['false_alarms']}** in {op['clean_windows']} normal windows = {op['false_alarm_rate_per_hour']:.2f}/hour")
    md.append(f"- Mean score during anomaly windows: {op['mean_score_anomaly']:+.3f}")
    md.append(f"- Mean score during normal windows: {op['mean_score_normal']:+.3f}")
    md.append(f"- Score separability (mean diff / pooled std): {op['score_separability']:.2f}σ\n")

    md.append("## Verdict\n")
    verdict_lines = report["verdict"]
    for line in verdict_lines:
        md.append(f"- {line}")
    md.append("")

    md.append("## Plots\n")
    md.append("- `roc.png` — ROC curve")
    md.append("- `pr.png` — Precision-Recall curve")
    md.append("- `score_histogram.png` — Score distribution by class")
    md.append("- `per_scenario_recall.png` — Recall per chaos scenario type")
    md.append("- `detection_latency_cdf.png` — Detection latency CDF\n")

    path.write_text("\n".join(md), encoding="utf-8")


def build_verdict(m: Dict, ti: Dict, op: Dict, anomaly_rate: float, per_type: Dict[str, float]) -> List[str]:
    out: List[str] = []
    # Headline
    pr_grade = grade(ti["pr_auc"], 0.70, 0.50)
    roc_grade = grade(ti["roc_auc"], 0.85, 0.70)
    f1_grade = grade(m["f1"], 0.60, 0.40)
    if pr_grade == "GOOD" and f1_grade in ("GOOD", "DECENT"):
        out.append(f"**WORKS WELL.** PR-AUC {ti['pr_auc']:.3f} significantly above random ({anomaly_rate:.3f}), F1 {m['f1']:.3f}, ROC-AUC {ti['roc_auc']:.3f}.")
    elif pr_grade in ("GOOD", "DECENT") and f1_grade in ("GOOD", "DECENT"):
        out.append(f"**MOSTLY WORKS.** PR-AUC {ti['pr_auc']:.3f} above random ({anomaly_rate:.3f}), F1 {m['f1']:.3f} usable. Threshold-tunable for better operating point.")
    elif ti["pr_auc"] > anomaly_rate * 1.5:
        out.append(f"**WEAK SIGNAL.** PR-AUC {ti['pr_auc']:.3f} > baseline {anomaly_rate:.3f} but threshold-dependent metrics are poor (F1 {m['f1']:.3f}). The model has some signal; consider per-service models or richer features.")
    else:
        out.append(f"**MODEL DOES NOT WORK** on this data. PR-AUC {ti['pr_auc']:.3f} barely above random baseline {anomaly_rate:.3f}. F1 {m['f1']:.3f}. Investigate: data quality, feature pipeline, training duration, or class imbalance.")

    # Operational
    if op["false_alarm_rate_per_hour"] > 5:
        out.append(f"High false-alarm rate ({op['false_alarm_rate_per_hour']:.1f}/hour) would create alert fatigue. Raise threshold or improve features.")
    elif op["false_alarm_rate_per_hour"] > 1:
        out.append(f"Moderate false-alarm rate ({op['false_alarm_rate_per_hour']:.1f}/hour). Acceptable for development; tune for production.")
    else:
        out.append(f"Low false-alarm rate ({op['false_alarm_rate_per_hour']:.1f}/hour) — operationally clean.")

    # Latency
    if op["scenarios_caught"] == 0:
        out.append("**Zero scenarios detected.** Model fails to alert on real incidents.")
    elif op["median_latency_s"] < 120:
        out.append(f"Fast detection: median latency {op['median_latency_s']:.0f}s — alerts fire within 1-2 windows of incident onset.")
    elif op["median_latency_s"] < 300:
        out.append(f"Acceptable detection latency ({op['median_latency_s']:.0f}s median). Faster requires sub-minute windows.")
    else:
        out.append(f"Slow detection (median {op['median_latency_s']:.0f}s = {op['median_latency_s']/60:.1f} min). Real incidents could escalate before alerts fire.")

    # Per-type
    missed_types = [t for t, r in per_type.items() if r < 0.5]
    great_types = [t for t, r in per_type.items() if r >= 0.8]
    if great_types:
        out.append(f"Reliably catches: {', '.join(great_types)}.")
    if missed_types:
        out.append(f"Struggles with: {', '.join(missed_types)} (recall < 0.5). These chaos types don't perturb the feature distribution enough.")

    # Separability
    if op["score_separability"] >= 2.0:
        out.append(f"Strong class separation: anomaly scores are {op['score_separability']:.1f}σ from normal — clear decision boundary.")
    elif op["score_separability"] >= 1.0:
        out.append(f"Moderate class separation ({op['score_separability']:.1f}σ). Threshold choice matters.")
    else:
        out.append(f"Weak class separation ({op['score_separability']:.1f}σ) — model can barely tell classes apart.")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=REPO_ROOT / "models" / "isolation_forest.pkl")
    parser.add_argument("--window-size-seconds", type=int, default=60)
    parser.add_argument("--window-stride-seconds", type=int, default=60)
    parser.add_argument("--train-frac", type=float, default=0.6)
    parser.add_argument("--val-frac", type=float, default=0.2)
    parser.add_argument("--eval-split", choices=["all", "test", "val", "train+val+test"], default="test",
                        help="Which split to evaluate on (default: test). 'all' uses every labeled window.")
    parser.add_argument("--events-jsonl", type=Path, default=None,
                        help="Load events from JSONL instead of TimescaleDB.")
    args = parser.parse_args()

    print(f"== evaluate_production ==  model={args.model}  timeline={args.timeline}")
    timeline = Timeline.load(args.timeline)
    if args.events_jsonl:
        events = load_events_jsonl(args.events_jsonl, timeline.start_utc, timeline.end_utc)
    else:
        events = query_events(timeline.start_utc, timeline.end_utc)
    if not events:
        print("error: no events in timeline window", file=sys.stderr)
        return 1
    print(f"loaded {len(events)} events from DB")

    extractor = FeatureExtractor(min_events=10)
    windows_all = build_windows(events, timeline, args.window_size_seconds, args.window_stride_seconds)
    kept = [w for w in windows_all if len(w.events) >= extractor.min_events]
    print(f"windows: built={len(windows_all)}  kept(>={extractor.min_events} events)={len(kept)}")

    # Apply same temporal split as the trainer so 'test' here matches training-time test
    train_w, val_w, test_w = temporal_split(kept, args.train_frac, args.val_frac)
    if args.eval_split == "test":
        eval_windows = test_w
    elif args.eval_split == "val":
        eval_windows = val_w
    elif args.eval_split in ("all", "train+val+test"):
        eval_windows = kept
    else:
        raise ValueError(args.eval_split)
    print(f"evaluating on split={args.eval_split} ({len(eval_windows)} windows)")

    detector = AnomalyDetector.load(str(args.model))
    threshold = detector.threshold
    print(f"loaded model: threshold={threshold:+.4f}")

    print("scoring windows via detector.predict() ...")
    scores, y, kept_eval = score_windows(detector, eval_windows)
    print(f"scored {len(scores)}/{len(eval_windows)} windows")
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    print(f"label distribution: positive(anomaly)={n_pos}  negative(normal)={n_neg}")

    if n_pos == 0:
        print("error: zero positive labels in eval split — cannot compute classification metrics", file=sys.stderr)
        return 1
    if n_neg == 0:
        print("error: zero negative labels in eval split — cannot compute FPR/specificity", file=sys.stderr)
        return 1

    # --- Threshold-dependent metrics ---
    y_pred = (scores < threshold).astype(np.int8)
    cm = _binary_metrics(y, y_pred)
    cm.threshold = float(threshold)

    specificity = cm.tn / (cm.tn + cm.fp) if (cm.tn + cm.fp) else 0.0
    balanced_acc = (cm.recall + specificity) / 2.0
    # F2
    if cm.precision + cm.recall > 0:
        f2 = 5 * cm.precision * cm.recall / (4 * cm.precision + cm.recall) if (4 * cm.precision + cm.recall) else 0.0
    else:
        f2 = 0.0
    # MCC
    denom = float(np.sqrt((cm.tp + cm.fp) * (cm.tp + cm.fn) * (cm.tn + cm.fp) * (cm.tn + cm.fn)))
    mcc = (cm.tp * cm.tn - cm.fp * cm.fn) / denom if denom else 0.0

    metrics_at_threshold = {
        "threshold": float(threshold),
        "precision": float(cm.precision),
        "recall": float(cm.recall),
        "f1": float(cm.f1),
        "f2": float(f2),
        "specificity": float(specificity),
        "fpr": float(cm.fpr),
        "mcc": float(mcc),
        "balanced_accuracy": float(balanced_acc),
        "tp": int(cm.tp), "fp": int(cm.fp), "tn": int(cm.tn), "fn": int(cm.fn),
    }

    # --- Threshold-independent metrics ---
    pr_auc = compute_pr_auc(scores, y)
    roc_auc = compute_roc_auc(scores, y)
    sweep = sweep_thresholds(scores, y)
    best = pick_best_threshold(sweep)

    # --- F-beta operating points (give ops a real curve to pick from) ---
    op_f0_5 = sweep_fbeta(scores, y, beta=0.5)  # precision-weighted
    op_f1 = (best.threshold, best.f1, best.precision, best.recall)
    op_f2 = sweep_fbeta(scores, y, beta=2.0)  # recall-weighted

    threshold_independent = {
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc_auc),
        "best_f1": float(best.f1),
        "best_f1_threshold": float(best.threshold),
        "best_f1_precision": float(best.precision),
        "best_f1_recall": float(best.recall),
    }

    operating_points = {
        "F0.5_precision_weighted": {
            "threshold": op_f0_5[0], "f_score": op_f0_5[1],
            "precision": op_f0_5[2], "recall": op_f0_5[3],
        },
        "F1_balanced": {
            "threshold": op_f1[0], "f_score": op_f1[1],
            "precision": op_f1[2], "recall": op_f1[3],
        },
        "F2_recall_weighted": {
            "threshold": op_f2[0], "f_score": op_f2[1],
            "precision": op_f2[2], "recall": op_f2[3],
        },
    }

    # --- Per-scenario diagnostics ---
    scenarios = analyze_scenarios(timeline, kept_eval, scores, threshold)

    # --- Operational metrics ---
    scenarios_caught = sum(1 for s in scenarios if s.windows_caught > 0)
    clean_windows = n_neg
    duration_hours = (timeline.end_utc - timeline.start_utc).total_seconds() / 3600.0
    clean_hours = clean_windows * (args.window_size_seconds / 3600.0)
    false_alarms_in_clean = int(cm.fp)
    fa_rate_per_hour = false_alarms_in_clean / clean_hours if clean_hours > 0 else 0.0

    pos_scores = scores[y == 1]
    neg_scores = scores[y == 0]
    pooled_std = float(np.sqrt(0.5 * (pos_scores.var() + neg_scores.var()))) if len(pos_scores) > 1 and len(neg_scores) > 1 else 0.0
    separability = abs(pos_scores.mean() - neg_scores.mean()) / pooled_std if pooled_std > 0 else 0.0

    operational = {
        "scenarios_total": len(scenarios),
        "scenarios_caught": scenarios_caught,
        "false_alarms": false_alarms_in_clean,
        "clean_windows": clean_windows,
        "false_alarm_rate_per_hour": float(fa_rate_per_hour),
        "mean_score_anomaly": float(pos_scores.mean()),
        "mean_score_normal": float(neg_scores.mean()),
        "score_separability": float(separability),
        # filled in by plot_detection_latency_cdf below
        "median_latency_s": float("nan"),
        "p90_latency_s": float("nan"),
    }

    # --- Plots ---
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"writing plots -> {OUT_DIR}/")
    _ = plot_roc(scores, y, OUT_DIR / "roc.png", "ROC — production model on chaos telemetry")
    _ = plot_pr(scores, y, OUT_DIR / "pr.png", "Precision-Recall — production model")
    plot_score_hist(scores, y, threshold, OUT_DIR / "score_histogram.png")
    per_type_recall = plot_per_scenario_recall(scenarios, OUT_DIR / "per_scenario_recall.png")
    lat_stats = plot_detection_latency_cdf(scenarios, OUT_DIR / "detection_latency_cdf.png")
    operational.update(lat_stats)

    # --- Assemble report ---
    report = {
        "timeline_path": str(args.timeline),
        "model_path": str(args.model),
        "eval_split": args.eval_split,
        "evaluated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "n_windows": int(len(y)),
        "n_anomaly": n_pos,
        "n_normal": n_neg,
        "anomaly_rate": float(n_pos / len(y)),
        "n_scenarios": len(scenarios),
        "threshold": float(threshold),
        "metrics_at_threshold": metrics_at_threshold,
        "threshold_independent": threshold_independent,
        "operating_points": operating_points,
        "per_type_recall": per_type_recall,
        "scenarios": [
            {
                "type": s.type, "start_utc": s.start_utc, "end_utc": s.end_utc,
                "duration_s": s.duration_s, "windows_total": s.windows_total,
                "windows_caught": s.windows_caught,
                "detection_latency_s": s.detection_latency_s,
            }
            for s in scenarios
        ],
        "operational": operational,
        "verdict": build_verdict(metrics_at_threshold, threshold_independent, operational, float(n_pos / len(y)), per_type_recall),
    }

    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_verdict_markdown(OUT_DIR / "REPORT.md", report)

    # --- Print summary to stdout ---
    print()
    print("=" * 70)
    print(f"EVAL SPLIT: {args.eval_split}   windows: {len(y)} ({n_pos} anomaly, {n_neg} normal)")
    print("=" * 70)
    print(f"At deployed threshold {threshold:+.3f}:")
    print(f"  Precision = {cm.precision:.3f}   Recall = {cm.recall:.3f}   F1 = {cm.f1:.3f}   F2 = {f2:.3f}")
    print(f"  FPR = {cm.fpr:.3f}   Specificity = {specificity:.3f}   MCC = {mcc:.3f}   Bal-Acc = {balanced_acc:.3f}")
    print(f"  TP={cm.tp}  FP={cm.fp}  TN={cm.tn}  FN={cm.fn}")
    print()
    print(f"Threshold-independent:")
    print(f"  PR-AUC = {pr_auc:.3f}   (baseline = {n_pos/len(y):.3f})")
    print(f"  ROC-AUC = {roc_auc:.3f}")
    print(f"  Best F1 (any threshold) = {best.f1:.3f} @ {best.threshold:+.3f}")
    print()
    print(f"Operating points (pick by ops priority):")
    print(f"  F0.5 (precision-weighted): thr={op_f0_5[0]:+.3f}  F0.5={op_f0_5[1]:.3f}  P={op_f0_5[2]:.3f}  R={op_f0_5[3]:.3f}")
    print(f"  F1   (balanced)         : thr={op_f1[0]:+.3f}  F1  ={op_f1[1]:.3f}  P={op_f1[2]:.3f}  R={op_f1[3]:.3f}")
    print(f"  F2   (recall-weighted)  : thr={op_f2[0]:+.3f}  F2  ={op_f2[1]:.3f}  P={op_f2[2]:.3f}  R={op_f2[3]:.3f}")
    print()
    print(f"Per-type recall:")
    for stype, recall in sorted(per_type_recall.items()):
        print(f"  {stype:<22} {recall:.3f}")
    print()
    print(f"Operational:")
    print(f"  Scenarios caught: {scenarios_caught}/{len(scenarios)}")
    print(f"  Median detection latency: {operational['median_latency_s']:.1f}s  (P90: {operational['p90_latency_s']:.1f}s)")
    print(f"  False alarms in clean windows: {false_alarms_in_clean}/{clean_windows} = {fa_rate_per_hour:.2f}/hour")
    print(f"  Score separability: {separability:.2f} sigma  (mean anomaly={pos_scores.mean():+.3f}, mean normal={neg_scores.mean():+.3f})")
    print()
    print("VERDICT:")
    for line in report["verdict"]:
        print(f"  *{line}")
    print()
    print(f"Full JSON report  -> {OUT_DIR / 'report.json'}")
    print(f"Markdown report  -> {OUT_DIR / 'REPORT.md'}")
    print(f"Plots            -> {OUT_DIR}/*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
