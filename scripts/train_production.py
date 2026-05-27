#!/usr/bin/env python3
"""Train the production Isolation Forest on Helios's own labeled telemetry.

Reads a chaos timeline JSON produced by ``scripts/generate_chaos_traffic.py``,
queries TimescaleDB for the events that flowed through the live ingestion
pipeline during that window, splits them into non-overlapping 60s windows
labeled from the timeline, and trains via the production
``AnomalyDetector.train()`` — so training and inference share a single
feature pipeline (``FeatureExtractor.extract_features``). Threshold is swept
on a temporal validation split.

Usage:
    python scripts/train_production.py \\
        --timeline data/chaos/timeline_<utc>.json \\
        --window-size-seconds 60 \\
        --window-stride-seconds 60 \\
        --train-frac 0.6 --val-frac 0.2 \\
        --output models/isolation_forest.pkl \\
        --seed 42

End-to-end pipeline:
    1. Load timeline (start_utc, end_utc, scenarios)
    2. Query events from TimescaleDB in [start_utc, end_utc]
    3. Window into 60s buckets aligned to start_utc
    4. Label each window from the timeline (1 if any scenario overlaps)
    5. Filter windows with < min_events_per_window events
    6. Temporal split: first 60% time -> train; next 20% -> val; last 20% -> test
    7. Train AnomalyDetector on train windows (uses production FeatureExtractor)
    8. Score val + test via detector.predict()
    9. Sweep threshold on val, pick F1-best
    10. Test eval at chosen threshold + PR-AUC + ROC-AUC
    11. Save model + model_config.json + training_metrics.json
    12. MLflow logging (skip with --no-mlflow)
    13. Round-trip sanity check
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "detection"))

from app.ml.anomaly_detector import AnomalyDetector  # noqa: E402
from app.ml.feature_engineering import FeatureExtractor  # noqa: E402


# ---------------------------------------------------------------------------
# Metric helpers (inlined from scripts/evaluate.py to avoid cross-script imports)
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
        precision=precision, recall=recall, f1=f1, fpr=fpr,
        tp=tp, fp=fp, tn=tn, fn=fn,
    )


def sweep_thresholds(scores: np.ndarray, y_true: np.ndarray,
                     lo: float = -1.0, hi: float = 0.5, step: float = 0.02) -> List[ThresholdMetrics]:
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


def compute_pr_auc(scores: np.ndarray, y_true: np.ndarray) -> float:
    """Higher anomaly = more negative score → use -scores as the positive score."""
    if y_true.sum() == 0 or y_true.sum() == len(y_true):
        return float("nan")
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y_true, -scores))


def compute_roc_auc(scores: np.ndarray, y_true: np.ndarray) -> float:
    if y_true.sum() == 0 or y_true.sum() == len(y_true):
        return float("nan")
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y_true, -scores))


# ---------------------------------------------------------------------------
# Timeline + DB
# ---------------------------------------------------------------------------


@dataclass
class Timeline:
    start_utc: datetime
    end_utc: datetime
    scenarios: List[Tuple[datetime, datetime, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Timeline":
        data = json.loads(path.read_text(encoding="utf-8"))
        start = _parse_iso(data["start_utc"])
        end = _parse_iso(data["end_utc"])
        scenarios = []
        for s in data.get("scenarios", []):
            scenarios.append((
                _parse_iso(s["start_utc"]),
                _parse_iso(s["end_utc"]),
                s["type"],
            ))
        return cls(start_utc=start, end_utc=end, scenarios=scenarios)

    def label_window(self, w_start: datetime, w_end: datetime) -> Tuple[int, Optional[str]]:
        """Return (label, active_scenario_type or None)."""
        for s_start, s_end, s_type in self.scenarios:
            if s_start < w_end and s_end > w_start:
                return 1, s_type
        return 0, None


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def query_events(start: datetime, end: datetime) -> List[Dict]:
    """Query TimescaleDB for all events in [start, end). Returns event dicts
    compatible with FeatureExtractor.extract_features() — i.e. carrying
    ``time``, ``service``, ``level``, ``message``, ``metadata``.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5433")),
        dbname=os.getenv("DB_NAME", "helios"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT time, service, level, message, metadata, trace_id, span_id
                FROM events
                WHERE time >= %s AND time < %s
                ORDER BY time ASC
                """,
                (start, end),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    events: List[Dict] = []
    for r in rows:
        events.append({
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "service": r["service"],
            "level": r["level"],
            "message": r["message"],
            "metadata": r["metadata"] if isinstance(r["metadata"], dict) else (json.loads(r["metadata"]) if r["metadata"] else {}),
            "trace_id": r["trace_id"],
            "span_id": r["span_id"],
        })
    return events


def load_events_jsonl(path: Path, start: datetime, end: datetime) -> List[Dict]:
    """Load events from a JSON-Lines file (one event per line). Filters to [start, end).

    Used when host:5433 is blocked by a non-Docker Postgres on the developer
    machine — `scripts/dump_events.sh` exports the table via `docker exec` so
    the trainer doesn't depend on host networking.
    """
    events: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            t = ev["time"] if isinstance(ev["time"], str) else ev["time"]
            t_parsed = datetime.fromisoformat(t.replace("Z", "+00:00")) if isinstance(t, str) else t
            if t_parsed.tzinfo is None:
                t_parsed = t_parsed.replace(tzinfo=timezone.utc)
            if t_parsed < start or t_parsed >= end:
                continue
            events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Windowing + labeling
# ---------------------------------------------------------------------------


@dataclass
class LabeledWindow:
    start: datetime
    end: datetime
    events: List[Dict]
    label: int
    scenario_type: Optional[str]


def build_windows(
    events: List[Dict],
    timeline: Timeline,
    window_size_s: int,
    stride_s: int,
) -> List[LabeledWindow]:
    """Non-overlapping (stride==window) or sliding (stride<window) windows aligned to timeline.start_utc."""
    if not events:
        return []
    # Pre-bucket events by minute index for efficiency
    events_by_time: List[Tuple[datetime, Dict]] = []
    for ev in events:
        t = _parse_iso(ev["time"]) if isinstance(ev["time"], str) else ev["time"]
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        events_by_time.append((t, ev))
    events_by_time.sort(key=lambda x: x[0])

    windows: List[LabeledWindow] = []
    cursor = timeline.start_utc
    end_cap = timeline.end_utc

    # Two-pointer scan over events
    i = 0
    n = len(events_by_time)
    while cursor + timedelta(seconds=window_size_s) <= end_cap:
        w_start = cursor
        w_end = cursor + timedelta(seconds=window_size_s)
        # Advance i to first event >= w_start
        while i < n and events_by_time[i][0] < w_start:
            i += 1
        # Collect events in [w_start, w_end)
        j = i
        bucket: List[Dict] = []
        while j < n and events_by_time[j][0] < w_end:
            bucket.append(events_by_time[j][1])
            j += 1
        label, scen = timeline.label_window(w_start, w_end)
        windows.append(LabeledWindow(w_start, w_end, bucket, label, scen))
        cursor += timedelta(seconds=stride_s)
    return windows


def temporal_split(
    windows: List[LabeledWindow], train_frac: float, val_frac: float,
) -> Tuple[List[LabeledWindow], List[LabeledWindow], List[LabeledWindow]]:
    n = len(windows)
    n_train = max(1, int(n * train_frac))
    n_val = max(1, int(n * val_frac))
    train = windows[:n_train]
    val = windows[n_train : n_train + n_val]
    test = windows[n_train + n_val:]
    if not test:
        test = val[-1:]
        val = val[:-1]
    return train, val, test


# ---------------------------------------------------------------------------
# Score helper (uses production predict() path for fidelity)
# ---------------------------------------------------------------------------


def score_windows(detector: AnomalyDetector, windows: List[LabeledWindow]) -> Tuple[np.ndarray, np.ndarray, List[LabeledWindow]]:
    """Returns (scores, y, kept_windows). Drops any window where predict() raises."""
    scores: List[float] = []
    y: List[int] = []
    kept: List[LabeledWindow] = []
    for w in windows:
        try:
            res = detector.predict(w.events)
        except Exception as exc:
            print(f"[warn] predict failed for window {w.start.isoformat()}: {exc}", file=sys.stderr)
            continue
        scores.append(res["score"])
        y.append(w.label)
        kept.append(w)
    return np.asarray(scores), np.asarray(y, dtype=np.int8), kept


# ---------------------------------------------------------------------------
# Model card + metadata writers
# ---------------------------------------------------------------------------


def write_model_config(
    path: Path, detector: AnomalyDetector, n_train: int, chosen_threshold: float,
    feature_names: List[str], per_split_metrics: Dict[str, Dict[str, float]],
) -> None:
    config = {
        "model_type": "IsolationForest",
        "training_date": datetime.now(tz=timezone.utc).isoformat(),
        "training_source": "chaos_traffic_v1",
        "training_samples": int(n_train),
        "features": feature_names,
        "hyperparameters": {
            "n_estimators": int(detector.model.n_estimators),
            "contamination": float(detector.model.contamination),
            "max_samples": "auto",
            "random_state": int(detector.model.random_state) if detector.model.random_state is not None else None,
        },
        "chosen_threshold": float(chosen_threshold),
        "metrics": per_split_metrics,
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def write_training_metrics(path: Path, per_split: Dict[str, Dict[str, float]], chosen_threshold: float, val_best_f1: float) -> None:
    payload = {
        "training_source": "chaos_traffic_v1",
        "chosen_threshold": float(chosen_threshold),
        "val_sweep_best_f1": float(val_best_f1),
        "splits": per_split,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def maybe_save_features_csv(path: Path, windows: List[LabeledWindow], feature_names: List[str], extractor: FeatureExtractor) -> None:
    """Write the training feature matrix as CSV for downstream drift_check.py."""
    import csv
    rows: List[List[float]] = []
    for w in windows:
        try:
            feats = extractor.extract_features(w.events)
            rows.append(feats[0].tolist())
        except Exception:
            continue
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(feature_names)
        writer.writerows(rows)
    print(f"wrote {len(rows)} feature rows -> {path}")


# ---------------------------------------------------------------------------
# MLflow (optional)
# ---------------------------------------------------------------------------


def log_mlflow(
    experiment: str, hyperparams: Dict, per_split: Dict[str, Dict[str, float]],
    chosen_threshold: float, model_path: Path,
) -> None:
    try:
        import mlflow
    except ImportError:
        print("[warn] mlflow not installed — skipping experiment logging")
        return
    mlflow.set_tracking_uri((REPO_ROOT / "mlruns").as_uri())
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=f"prod_train_{datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"):
        mlflow.log_params({**hyperparams, "chosen_threshold": chosen_threshold, "training_source": "chaos_traffic_v1"})
        for split, m in per_split.items():
            for key, val in m.items():
                if isinstance(val, (int, float)) and not (isinstance(val, float) and (val != val)):
                    mlflow.log_metric(f"{split}_{key}", float(val))
        mlflow.log_artifact(str(model_path))


# ---------------------------------------------------------------------------
# Round-trip check
# ---------------------------------------------------------------------------


def roundtrip_check(path: Path, sample_window: LabeledWindow, expected_threshold: float) -> None:
    loaded = AnomalyDetector.load(str(path))
    assert loaded.is_trained, "round-trip: loaded detector is not is_trained"
    assert abs(loaded.threshold - expected_threshold) < 1e-9, (
        f"round-trip: threshold mismatch {loaded.threshold} vs {expected_threshold}"
    )
    expected_n_features = len(loaded.feature_extractor.get_feature_names())
    assert loaded._shap_background is not None and loaded._shap_background.shape[1] == expected_n_features, (
        f"round-trip: shap_background shape unexpected: "
        f"{None if loaded._shap_background is None else loaded._shap_background.shape}"
    )
    res = loaded.predict(sample_window.events)
    assert "score" in res and "is_anomaly" in res, "round-trip: predict result missing keys"
    print(f"round-trip OK: loaded model scored sample window -> score={res['score']:.4f}  is_anomaly={res['is_anomaly']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--timeline", type=Path, required=True, help="Path to chaos timeline JSON")
    parser.add_argument("--window-size-seconds", type=int, default=60)
    parser.add_argument("--window-stride-seconds", type=int, default=60)
    parser.add_argument("--train-frac", type=float, default=0.6)
    parser.add_argument("--val-frac", type=float, default=0.2)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "models" / "isolation_forest.pkl")
    parser.add_argument("--no-mlflow", action="store_true")
    parser.add_argument("--no-roundtrip-check", action="store_true")
    parser.add_argument("--save-features", action="store_true",
                        help="Also write models/training_data.csv (for drift_check.py)")
    parser.add_argument("--events-jsonl", type=Path, default=None,
                        help="Load events from JSONL file instead of querying TimescaleDB. "
                             "Useful when host port 5433 is occupied by a non-Docker Postgres.")
    parser.add_argument("--exclude-anomalies-from-train", action="store_true",
                        help="Drop labeled-anomaly windows from the training split. "
                             "Standard practice for unsupervised AD when labels happen to be "
                             "available — keeps the model's notion of 'normal' uncontaminated.")
    args = parser.parse_args()

    print(f"== train_production ==  timeline={args.timeline}")
    timeline = Timeline.load(args.timeline)
    print(f"timeline: {timeline.start_utc.isoformat()} .. {timeline.end_utc.isoformat()}  scenarios={len(timeline.scenarios)}")

    if args.events_jsonl:
        print(f"loading events from {args.events_jsonl}...")
        events = load_events_jsonl(args.events_jsonl, timeline.start_utc, timeline.end_utc)
    else:
        print("querying events from TimescaleDB...")
        events = query_events(timeline.start_utc, timeline.end_utc)
    print(f"loaded {len(events)} events")
    if not events:
        print("error: no events in the timeline window — generator may not have run, or DB target is wrong", file=sys.stderr)
        return 1

    windows = build_windows(events, timeline, args.window_size_seconds, args.window_stride_seconds)
    extractor = FeatureExtractor(min_events=10)
    kept_windows = [w for w in windows if len(w.events) >= extractor.min_events]
    dropped = len(windows) - len(kept_windows)
    pos = sum(1 for w in kept_windows if w.label == 1)
    print(f"windows: built={len(windows)}  kept={len(kept_windows)}  dropped<min_events={dropped}  positive={pos}")
    if pos == 0:
        print("error: no positive (anomaly) windows after filtering — extend duration or lower stride", file=sys.stderr)
        return 1

    train_w, val_w, test_w = temporal_split(kept_windows, args.train_frac, args.val_frac)
    print(f"split: train={len(train_w)} (pos={sum(w.label for w in train_w)})  "
          f"val={len(val_w)} (pos={sum(w.label for w in val_w)})  "
          f"test={len(test_w)} (pos={sum(w.label for w in test_w)})")
    if sum(w.label for w in val_w) == 0:
        print("error: validation split has zero positive windows — cannot sweep threshold", file=sys.stderr)
        return 1
    if sum(w.label for w in test_w) == 0:
        print("[warn] test split has zero positive windows — F1 on test will be 0; PR/ROC AUC undefined")

    train_for_fit = train_w
    if args.exclude_anomalies_from_train:
        train_for_fit = [w for w in train_w if w.label == 0]
        print(f"excluding {len(train_w) - len(train_for_fit)} labeled-anomaly windows from training "
              f"-> {len(train_for_fit)} clean windows for fit")
        if len(train_for_fit) < 10:
            print(f"error: only {len(train_for_fit)} clean train windows — need >= 10", file=sys.stderr)
            return 1

    print("training AnomalyDetector...")
    detector = AnomalyDetector(
        contamination=args.contamination,
        threshold=0.0,  # placeholder; overridden by sweep below
        n_estimators=args.n_estimators,
        random_state=args.seed,
    )
    stats = detector.train([w.events for w in train_for_fit])
    print(f"trained: {stats}")

    # hour_of_day sanity: variance must be > 0 (otherwise the bug fix did not take)
    train_feats = []
    for w in train_w:
        try:
            train_feats.append(extractor.extract_features(w.events)[0])
        except Exception:
            continue
    if train_feats:
        train_feats_arr = np.stack(train_feats)
        hour_var = float(train_feats_arr[:, 6].var())
        print(f"hour_of_day variance across train windows: {hour_var:.4f}")
        if hour_var == 0.0:
            print("[warn] hour_of_day has zero variance — generator may have run shorter than 1h")

    print("scoring val/test via detector.predict()...")
    val_scores, val_y, val_kept = score_windows(detector, val_w)
    test_scores, test_y, test_kept = score_windows(detector, test_w)
    print(f"val scored: {len(val_scores)}/{len(val_w)}   test scored: {len(test_scores)}/{len(test_w)}")

    print("sweeping threshold on val...")
    sweep = sweep_thresholds(val_scores, val_y)
    best = pick_best_threshold(sweep)
    detector.threshold = best.threshold
    print(f"best val threshold = {best.threshold:+.3f}  F1={best.f1:.3f}  P={best.precision:.3f}  R={best.recall:.3f}")

    y_test_pred = (test_scores < best.threshold).astype(np.int8) if test_scores.size else np.array([], dtype=np.int8)
    test_at_threshold = _binary_metrics(test_y, y_test_pred) if test_y.size else None
    test_pr = compute_pr_auc(test_scores, test_y) if test_y.size else float("nan")
    test_roc = compute_roc_auc(test_scores, test_y) if test_y.size else float("nan")

    per_split: Dict[str, Dict[str, float]] = {
        "train": {
            "n_windows": len(train_w),
            "n_positive": int(sum(w.label for w in train_w)),
            "anomaly_rate": float(sum(w.label for w in train_w) / max(1, len(train_w))),
        },
        "val": {
            "n_windows": len(val_w),
            "n_positive": int(sum(w.label for w in val_w)),
            "anomaly_rate": float(sum(w.label for w in val_w) / max(1, len(val_w))),
            "best_threshold": float(best.threshold),
            "f1": float(best.f1),
            "precision": float(best.precision),
            "recall": float(best.recall),
        },
        "test": {
            "n_windows": len(test_w),
            "n_positive": int(sum(w.label for w in test_w)),
            "anomaly_rate": float(sum(w.label for w in test_w) / max(1, len(test_w))),
            "f1": float(test_at_threshold.f1) if test_at_threshold else float("nan"),
            "precision": float(test_at_threshold.precision) if test_at_threshold else float("nan"),
            "recall": float(test_at_threshold.recall) if test_at_threshold else float("nan"),
            "fpr": float(test_at_threshold.fpr) if test_at_threshold else float("nan"),
            "tp": int(test_at_threshold.tp) if test_at_threshold else 0,
            "fp": int(test_at_threshold.fp) if test_at_threshold else 0,
            "tn": int(test_at_threshold.tn) if test_at_threshold else 0,
            "fn": int(test_at_threshold.fn) if test_at_threshold else 0,
            "pr_auc": float(test_pr),
            "roc_auc": float(test_roc),
        },
    }

    print(f"saving model -> {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    detector.save(str(args.output))

    feature_names = extractor.get_feature_names()
    write_model_config(REPO_ROOT / "models" / "model_config.json",
                       detector, len(train_w), best.threshold, feature_names, per_split)
    write_training_metrics(REPO_ROOT / "models" / "training_metrics.json",
                           per_split, best.threshold, best.f1)

    if args.save_features:
        maybe_save_features_csv(REPO_ROOT / "models" / "training_data.csv", train_w, feature_names, extractor)

    if not args.no_mlflow:
        log_mlflow(
            experiment="helios-production-train",
            hyperparams={
                "contamination": args.contamination,
                "n_estimators": args.n_estimators,
                "window_size_seconds": args.window_size_seconds,
                "window_stride_seconds": args.window_stride_seconds,
                "seed": args.seed,
            },
            per_split=per_split,
            chosen_threshold=best.threshold,
            model_path=args.output,
        )

    if not args.no_roundtrip_check and test_kept:
        roundtrip_check(args.output, test_kept[len(test_kept) // 2], best.threshold)

    # Summary
    print()
    print("=" * 70)
    print(f"  threshold       = {best.threshold:+.3f}")
    print(f"  val   F1        = {best.f1:.3f}   P={best.precision:.3f}   R={best.recall:.3f}")
    if test_at_threshold is not None:
        print(f"  test  F1        = {test_at_threshold.f1:.3f}   P={test_at_threshold.precision:.3f}   R={test_at_threshold.recall:.3f}   FPR={test_at_threshold.fpr:.3f}")
        print(f"  test  PR-AUC    = {test_pr:.3f}   ROC-AUC = {test_roc:.3f}")
    print("=" * 70)
    print(f"model -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
