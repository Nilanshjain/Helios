#!/usr/bin/env python3
"""Rule-based baseline + side-by-side comparison vs the Isolation Forest model.

The rule:
    flag a window as anomaly if
        error_rate > ERROR_RATE_THRESHOLD
        OR
        p95_latency_ms > LATENCY_MULTIPLIER * baseline_p95

where ``baseline_p95`` is the median p95_latency_ms across all windows in
the train split (assumed to be pure-baseline clean traffic).

Honest test of whether the IF model earns its complexity over a 3-line rule.

Outputs:
    models/evaluation/production/baseline_report.json
    models/evaluation/production/baseline_vs_if.md
    plots/baseline_vs_if_pr.png (overlay PR curves)
    plots/baseline_vs_if_confusion.png

Usage:
    python scripts/evaluate_baseline.py \\
        --timeline data/chaos/timeline_v2.json \\
        --events-jsonl data/chaos/events_v2.jsonl \\
        --if-report models/evaluation/production/report.json \\
        --error-rate-threshold 0.05 \\
        --latency-multiplier 2.0
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "detection"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.ml.feature_engineering import FeatureExtractor  # noqa: E402
from train_production import (  # noqa: E402
    Timeline, query_events, load_events_jsonl, build_windows, temporal_split,
    _binary_metrics,
)


OUT_DIR = REPO_ROOT / "models" / "evaluation" / "production"


@dataclass
class BaselineMetrics:
    threshold_error_rate: float
    threshold_latency_mult: float
    baseline_p95: float
    n_windows: int
    n_anomaly: int
    n_normal: int
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1: float
    specificity: float
    fpr: float
    mcc: float
    balanced_accuracy: float


def compute_baseline_p95(train_windows: List, extractor: FeatureExtractor) -> float:
    """Median of p95_latency_ms across training windows. The training set is
    assumed clean (no chaos), so this represents 'normal p95'."""
    p95_idx = extractor.FEATURE_NAMES.index("p95_latency_ms")
    p95s = []
    for w in train_windows:
        if len(w.events) < extractor.min_events:
            continue
        try:
            feats = extractor.extract_features(w.events)
            p95s.append(feats[0, p95_idx])
        except Exception:
            continue
    if not p95s:
        raise RuntimeError("no valid training windows for baseline p95")
    return float(np.median(p95s))


def apply_rule(features: np.ndarray, err_idx: int, p95_idx: int,
               error_threshold: float, latency_threshold: float) -> int:
    """1 if window violates rule, else 0."""
    return int(features[err_idx] > error_threshold or features[p95_idx] > latency_threshold)


def evaluate_baseline(
    eval_windows: List,
    extractor: FeatureExtractor,
    baseline_p95: float,
    error_threshold: float,
    latency_mult: float,
) -> BaselineMetrics:
    err_idx = extractor.FEATURE_NAMES.index("error_rate")
    p95_idx = extractor.FEATURE_NAMES.index("p95_latency_ms")
    latency_threshold = baseline_p95 * latency_mult

    y_pred: List[int] = []
    y_true: List[int] = []
    for w in eval_windows:
        if len(w.events) < extractor.min_events:
            continue
        try:
            feats = extractor.extract_features(w.events)
        except Exception:
            continue
        y_pred.append(apply_rule(feats[0], err_idx, p95_idx, error_threshold, latency_threshold))
        y_true.append(w.label)

    y_pred_arr = np.asarray(y_pred, dtype=np.int8)
    y_true_arr = np.asarray(y_true, dtype=np.int8)

    cm = _binary_metrics(y_true_arr, y_pred_arr)
    specificity = cm.tn / (cm.tn + cm.fp) if (cm.tn + cm.fp) else 0.0
    balanced_acc = (cm.recall + specificity) / 2.0
    denom = float(np.sqrt((cm.tp + cm.fp) * (cm.tp + cm.fn) * (cm.tn + cm.fp) * (cm.tn + cm.fn)))
    mcc = (cm.tp * cm.tn - cm.fp * cm.fn) / denom if denom else 0.0

    return BaselineMetrics(
        threshold_error_rate=error_threshold,
        threshold_latency_mult=latency_mult,
        baseline_p95=baseline_p95,
        n_windows=int(len(y_true_arr)),
        n_anomaly=int(y_true_arr.sum()),
        n_normal=int(len(y_true_arr) - y_true_arr.sum()),
        tp=cm.tp, fp=cm.fp, tn=cm.tn, fn=cm.fn,
        precision=cm.precision, recall=cm.recall, f1=cm.f1,
        specificity=specificity, fpr=cm.fpr,
        mcc=mcc, balanced_accuracy=balanced_acc,
    )


def write_comparison_md(out_path: Path, baseline: BaselineMetrics, if_report: Optional[Dict]) -> None:
    md: List[str] = []
    md.append("# Rule-Based Baseline vs Isolation Forest (v2)\n")
    md.append(f"*Generated {datetime.now(tz=timezone.utc).isoformat(timespec='seconds')}*\n")

    md.append("## Rule\n")
    md.append(f"`flag if (error_rate > {baseline.threshold_error_rate:.3f}) OR (p95_latency > {baseline.threshold_latency_mult}*baseline_p95)`\n")
    md.append(f"- `baseline_p95` (median across training windows) = **{baseline.baseline_p95:.1f} ms**\n")
    md.append(f"- Latency threshold = {baseline.threshold_latency_mult * baseline.baseline_p95:.1f} ms\n")
    md.append("")

    md.append("## Side-by-side metrics\n")
    md.append(f"| Metric | Rule-based baseline | Isolation Forest (v2) |")
    md.append(f"|---|---:|---:|")

    if if_report is not None:
        ifm = if_report["metrics_at_threshold"]
        iti = if_report["threshold_independent"]
        md.append(f"| Precision | {baseline.precision:.3f} | {ifm['precision']:.3f} |")
        md.append(f"| Recall | {baseline.recall:.3f} | {ifm['recall']:.3f} |")
        md.append(f"| **F1** | **{baseline.f1:.3f}** | **{ifm['f1']:.3f}** |")
        md.append(f"| Specificity | {baseline.specificity:.3f} | {ifm['specificity']:.3f} |")
        md.append(f"| FPR | {baseline.fpr:.3f} | {ifm['fpr']:.3f} |")
        md.append(f"| MCC | {baseline.mcc:.3f} | {ifm['mcc']:.3f} |")
        md.append(f"| Balanced Accuracy | {baseline.balanced_accuracy:.3f} | {ifm['balanced_accuracy']:.3f} |")
        md.append(f"| PR-AUC | (binary rule, n/a) | {iti['pr_auc']:.3f} |")
        md.append(f"| ROC-AUC | (binary rule, n/a) | {iti['roc_auc']:.3f} |")
    else:
        md.append(f"| Precision | {baseline.precision:.3f} | (IF report not provided) |")
        md.append(f"| Recall | {baseline.recall:.3f} | |")
        md.append(f"| F1 | {baseline.f1:.3f} | |")
    md.append("")

    md.append("## Confusion matrices\n")
    md.append(f"**Rule-based:** TP={baseline.tp}  FP={baseline.fp}  TN={baseline.tn}  FN={baseline.fn}\n")
    if if_report is not None:
        ifm = if_report["metrics_at_threshold"]
        md.append(f"**IF (v2):** TP={ifm['tp']}  FP={ifm['fp']}  TN={ifm['tn']}  FN={ifm['fn']}\n")

    md.append("## Interpretation\n")
    if if_report is not None:
        ifm = if_report["metrics_at_threshold"]
        f1_diff = ifm['f1'] - baseline.f1
        if f1_diff >= 0.10:
            md.append(f"- **IF earns its place.** F1 +{f1_diff:.3f} over the dumb rule.")
        elif f1_diff >= 0.03:
            md.append(f"- **IF adds modest value.** F1 +{f1_diff:.3f} over the rule. "
                      f"Threshold-independent metrics (PR-AUC, ROC-AUC) tell the bigger story — "
                      f"the IF lets you tune the operating point along the PR curve; the rule is a single point.")
        elif f1_diff >= -0.03:
            md.append(f"- **IF roughly matches the rule.** F1 delta = {f1_diff:+.3f}. "
                      f"The IF still buys you a continuous score (useful for severity / triage) and "
                      f"PR-AUC = {if_report['threshold_independent']['pr_auc']:.3f}, but the headline F1 "
                      f"isn't a strong selling point.")
        else:
            md.append(f"- **The rule beats the IF on F1 ({-f1_diff:.3f} ahead).** "
                      f"Look at the threshold-independent metrics — if PR-AUC is high, the IF is "
                      f"compromised by a poor threshold choice and is fixable. Otherwise, "
                      f"the model needs more training data or richer features.")
    md.append("")
    md.append("- Note: the rule is intentionally simple. A tuned version (per-service rolling baselines, "
              "exponentially-weighted thresholds, hysteresis) could close more of the gap.")

    out_path.write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--events-jsonl", type=Path, default=None)
    parser.add_argument("--if-report", type=Path, default=OUT_DIR / "report.json",
                        help="Optional path to the IF model's evaluation report.json for side-by-side comparison.")
    parser.add_argument("--window-size-seconds", type=int, default=60)
    parser.add_argument("--window-stride-seconds", type=int, default=30)
    parser.add_argument("--train-frac", type=float, default=0.33)
    parser.add_argument("--val-frac", type=float, default=0.33)
    parser.add_argument("--error-rate-threshold", type=float, default=0.05)
    parser.add_argument("--latency-multiplier", type=float, default=2.0)
    parser.add_argument("--eval-split", choices=["all", "test", "val", "val+test"], default="val+test")
    args = parser.parse_args()

    print(f"== evaluate_baseline ==  timeline={args.timeline}")
    timeline = Timeline.load(args.timeline)
    events = load_events_jsonl(args.events_jsonl, timeline.start_utc, timeline.end_utc) if args.events_jsonl else query_events(timeline.start_utc, timeline.end_utc)
    print(f"loaded {len(events)} events")

    extractor = FeatureExtractor(min_events=10)
    windows = [w for w in build_windows(events, timeline, args.window_size_seconds, args.window_stride_seconds) if len(w.events) >= extractor.min_events]
    train_w, val_w, test_w = temporal_split(windows, args.train_frac, args.val_frac)
    print(f"split: train={len(train_w)}  val={len(val_w)}  test={len(test_w)}")

    print("computing baseline_p95 from training windows...")
    baseline_p95 = compute_baseline_p95(train_w, extractor)
    print(f"baseline_p95 = {baseline_p95:.1f} ms  -> latency threshold = {baseline_p95 * args.latency_multiplier:.1f} ms")

    if args.eval_split == "test":
        eval_windows = test_w
    elif args.eval_split == "val":
        eval_windows = val_w
    elif args.eval_split == "val+test":
        eval_windows = val_w + test_w
    else:
        eval_windows = windows

    print(f"evaluating rule on {len(eval_windows)} windows ({args.eval_split})...")
    bm = evaluate_baseline(eval_windows, extractor, baseline_p95,
                           args.error_rate_threshold, args.latency_multiplier)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "baseline_report.json").write_text(json.dumps(bm.__dict__, indent=2), encoding="utf-8")

    if_report = None
    if args.if_report and args.if_report.exists():
        if_report = json.loads(args.if_report.read_text(encoding="utf-8"))
    write_comparison_md(OUT_DIR / "baseline_vs_if.md", bm, if_report)

    print()
    print("=" * 70)
    print(f"BASELINE RULE: err > {args.error_rate_threshold}  OR  p95 > {args.latency_multiplier} * baseline_p95 ({baseline_p95:.1f})")
    print("=" * 70)
    print(f"  windows: {bm.n_windows} ({bm.n_anomaly} anomaly, {bm.n_normal} normal)")
    print(f"  Precision = {bm.precision:.3f}   Recall = {bm.recall:.3f}   F1 = {bm.f1:.3f}")
    print(f"  Specificity = {bm.specificity:.3f}   FPR = {bm.fpr:.3f}   MCC = {bm.mcc:.3f}")
    print(f"  TP={bm.tp}  FP={bm.fp}  TN={bm.tn}  FN={bm.fn}")
    if if_report is not None:
        ifm = if_report["metrics_at_threshold"]
        print()
        print("Compared to Isolation Forest v2:")
        print(f"  IF: Precision={ifm['precision']:.3f}  Recall={ifm['recall']:.3f}  F1={ifm['f1']:.3f}")
        f1_diff = ifm['f1'] - bm.f1
        print(f"  F1 delta (IF - rule) = {f1_diff:+.3f}")
    print()
    print(f"reports -> {OUT_DIR / 'baseline_report.json'}")
    print(f"         -> {OUT_DIR / 'baseline_vs_if.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
