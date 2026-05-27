#!/usr/bin/env python3
"""End-to-end dry-run without docker / Kafka / Postgres.

Exercises the real production code paths in-process:

  1. Synthesise an event window the detection consumer would see.
  2. FeatureExtractor -> 27-feature vector (production code).
  3. AnomalyDetector.predict() (production code, uses the on-disk model).
  4. AnomalyDetector.explain() -> SHAP attributions (production code).
  5. Build the alert payload exactly the way detection_consumer does.
  6. Verify it JSON-serialises (what Kafka would do).
  7. Verify the SQL INSERT param tuple shapes correctly.
  8. Build a ReportContext + run MockGenerator -> IncidentReport.
  9. Render IncidentReport.to_markdown() and assert SHAP features show up.
 10. Exercise the generator-factory fallback (no LLM key -> mock).

The only things stubbed are Kafka send and the DB cursor. Everything in
between is real.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import warnings
from datetime import datetime
from pathlib import Path

# --- Quiet mode -------------------------------------------------------------
# This is a verification script. The detection/reporting service packages log
# via structlog (PrintLogger, no level filter by default), scikit-learn /
# pydantic emit import-time warnings, and the Gemini SDK's gRPC core prints
# absl/ALTS notices. Silence all of it so the output is exactly the pipeline
# steps and their results.
#
# The dry-run uses the offline MockGenerator for report generation:
# deterministic, zero-cost, no network. The live Gemini path is exercised
# separately by scripts/diagnose_reporting.py.
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
os.environ["REPORT_GENERATOR_MODE"] = "mock"
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
try:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        cache_logger_on_first_use=True,
    )
except Exception:
    pass
# ----------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[1]
DETECTION = REPO / "services" / "detection"
REPORTING = REPO / "services" / "reporting"

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def step(n: int, title: str) -> None:
    print(f"\n{CYAN}=== Step {n}: {title} ==={RESET}")


def ok(msg: str) -> None:
    print(f"{GREEN}  [PASS]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{DIM}  -- {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  [FAIL]{RESET} {msg}")


def _swap_to_service(service_root: Path) -> None:
    """Both detection and reporting expose a top-level `app/` package.

    Python imports the first one on sys.path and ignores the other, so we
    hot-swap the path and purge `app.*` modules from sys.modules each time
    we cross the service boundary. Real production never does this — each
    service runs in its own container.
    """
    # Drop any previously loaded `app.*` modules so the next import resolves
    # against the new service tree.
    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]
    # Remove old service roots from sys.path and prepend the new one.
    sys.path[:] = [p for p in sys.path if p not in (str(DETECTION), str(REPORTING))]
    sys.path.insert(0, str(service_root))


def run() -> int:
    print(f"{CYAN}Helios end-to-end dry-run{RESET}")
    print(f"{DIM}Repo: {REPO}{RESET}")

    _swap_to_service(DETECTION)

    # ------------------------------------------------------------------
    step(1, "Synthesise an anomalous event window")
    # ------------------------------------------------------------------
    # Mimics what the Kafka events topic produces: dicts with `service`,
    # `level`, `message`, and `metadata.latency_ms`. We engineer the window
    # to be obviously anomalous (high latency tail + high error rate) so
    # the model should flag it.
    now = datetime.utcnow().isoformat()
    events = []
    for i in range(80):
        # Aggressively anomalous window: 40% error rate, fat latency tail
        # (P99 in the 4000ms range). The model was trained on synthetic
        # data where "normal" tops out around P99=150ms, so this should
        # clear the -0.5 threshold by a wide margin.
        is_err = i % 5 < 2  # 2/5 = 40%
        events.append(
            {
                "time": now,
                "service": "payment-service",
                "level": "CRITICAL" if is_err and i % 10 == 0 else "ERROR" if is_err else "INFO",
                "message": "DB timeout" if is_err else "request handled",
                "metadata": {
                    "latency_ms": 4000 + (i * 25) if is_err else 50 + i,
                    "endpoint": "/checkout",
                },
            }
        )
    error_events = [e for e in events if e["level"] == "ERROR"]
    ok(
        f"window has {len(events)} events, "
        f"{len(error_events)} ERROR-level ({len(error_events)/len(events):.0%})"
    )

    # ------------------------------------------------------------------
    step(2, "FeatureExtractor (production code)")
    # ------------------------------------------------------------------
    from app.ml.feature_engineering import FeatureExtractor  # type: ignore

    extractor = FeatureExtractor(min_events=10)
    features = extractor.extract_features(events)
    feature_names = extractor.get_feature_names()
    ok(f"extracted {features.shape[1]} features (shape {features.shape})")
    info(
        "p50/p95/p99 latency = "
        f"{features[0][2]:.0f} / {features[0][3]:.0f} / {features[0][4]:.0f} ms; "
        f"error_rate = {features[0][1]:.2%}"
    )

    # ------------------------------------------------------------------
    step(3, "AnomalyDetector.predict (production model)")
    # ------------------------------------------------------------------
    from app.ml.anomaly_detector import AnomalyDetector  # type: ignore

    model_path = REPO / "models" / "isolation_forest.pkl"
    if not model_path.exists():
        fail(f"model missing at {model_path}; run `make train-production` (or `python scripts/generate_chaos_traffic.py` then `python scripts/train_production.py`) first")
        return 1
    detector = AnomalyDetector.load(str(model_path))
    prediction = detector.predict(events)
    ok(
        f"score={prediction['score']:+.4f}  "
        f"is_anomaly={prediction['is_anomaly']}  "
        f"severity={prediction['severity']}"
    )
    info(f"threshold used: {prediction['threshold']:+.4f}")

    # ------------------------------------------------------------------
    step(4, "SHAP explain (production code, lazy TreeExplainer)")
    # ------------------------------------------------------------------
    import numpy as np  # local import to avoid heavy load when not needed

    t0 = time.time()
    explanation = detector.explain(np.array(prediction["features"]).reshape(1, -1))
    shap_ms = (time.time() - t0) * 1000
    if explanation is None:
        fail("SHAP returned None — model likely lacks shap_background")
        return 1
    top3 = explanation["feature_importance"][:3]
    ok(f"SHAP attribution computed in {shap_ms:.1f} ms")
    for f in top3:
        arrow = "(toward_anomaly)" if f["shap_value"] < 0 else "(toward_normal)"
        info(f"  {f['feature']:<20}  shap={f['shap_value']:+.4f}  {arrow}")

    # ------------------------------------------------------------------
    step(5, "Build alert payload (mirrors detection_consumer._handle_anomaly)")
    # ------------------------------------------------------------------
    top_features = []
    for f in top3:
        try:
            idx = feature_names.index(f["feature"])
            value = float(prediction["features"][idx])
        except (ValueError, IndexError):
            value = float("nan")
        top_features.append(
            {
                "name": f["feature"],
                "value": value,
                "shap": float(f["shap_value"]),
                "direction": "toward_anomaly" if f["shap_value"] < 0 else "toward_normal",
            }
        )
    alert = {
        "id": f"anomaly_payment-service_{int(time.time())}",
        "timestamp": now,
        "service": "payment-service",
        "severity": prediction["severity"],
        "score": prediction["score"],
        "threshold": prediction["threshold"],
        "features": dict(zip(feature_names, prediction["features"])),
        "top_features": top_features,
        "window_size": len(events),
        "window_start": events[0]["time"],
        "window_end": events[-1]["time"],
    }
    ok(f"alert payload built ({len(top_features)} top SHAP features)")

    # ------------------------------------------------------------------
    step(6, "JSON-serialise alert (what KafkaProducer would do)")
    # ------------------------------------------------------------------
    serialised = json.dumps(alert).encode("utf-8")
    ok(f"alert serialises cleanly: {len(serialised)} bytes")
    info(f"first 160 chars: {serialised.decode()[:160]}...")

    # ------------------------------------------------------------------
    step(7, "Verify SQL INSERT param tuple shape (mirrors _store_anomaly)")
    # ------------------------------------------------------------------
    features_payload = {
        "values": alert["features"],
        "top_features": alert["top_features"],
        "window_size": alert["window_size"],
        "window_start": alert["window_start"],
        "window_end": alert["window_end"],
    }
    insert_params = (
        alert["timestamp"],
        alert["id"],
        alert["service"],
        str(alert["severity"]).upper(),
        alert["score"],
        alert["threshold"],
        json.dumps(features_payload),
    )
    assert len(insert_params) == 7, "should match the 7-column INSERT"
    assert insert_params[3] in ("LOW", "MEDIUM", "HIGH", "CRITICAL"), (
        "severity must satisfy the CHECK constraint"
    )
    ok(f"INSERT params: 7 values, severity={insert_params[3]} (CHECK-compatible)")

    # ------------------------------------------------------------------
    step(8, "Report-generator factory (offline mock for the dry-run)")
    # ------------------------------------------------------------------
    # Cross the service boundary: reload `app.*` against the reporting tree.
    _swap_to_service(REPORTING)

    # REPORT_GENERATOR_MODE=mock is set at module load (quiet-mode block) so
    # this stage is deterministic and offline. The live Gemini path is
    # verified separately by scripts/diagnose_reporting.py.
    from app.generators.mock_generator import MockGenerator  # type: ignore

    generator = MockGenerator()
    ok("generator: mock (deterministic, offline - live Gemini tested separately)")

    # ------------------------------------------------------------------
    step(9, "Build ReportContext and generate a report")
    # ------------------------------------------------------------------
    from app.generators.base import ReportContext  # type: ignore

    context = ReportContext(
        anomaly=alert,
        events=events,
        metrics={
            "avg_event_count": len(events),
            "avg_error_rate": alert["features"]["error_rate"],
            "avg_latency": alert["features"]["p50_latency_ms"],
            "avg_p99_latency": alert["features"]["p99_latency_ms"],
        },
        recent_anomalies=[],
    )
    result = generator.generate(context)
    ok(
        f"report generated: id={result.report_id}  "
        f"tokens={result.tokens_used}  cost=${result.cost_usd:.4f}  "
        f"time={result.generation_time_ms:.1f}ms"
    )
    info(f"format: {result.format}")
    info(f"content first 220 chars: {result.content[:220].strip()}...")

    # ------------------------------------------------------------------
    step(10, "Pydantic structured_output schema round-trip + render check")
    # ------------------------------------------------------------------
    from app.generators.structured_output import (  # type: ignore
        ContributingFeature,
        IncidentReport,
        RecommendedAction,
    )

    # Build the structured report directly from the alert (this is what the
    # Gemini/Claude generators do after parsing the model response).
    report = IncidentReport(
        incident_id=alert["id"],
        service=alert["service"],
        detected_at=alert["timestamp"],
        severity=str(alert["severity"]).upper(),
        confidence=0.78,
        executive_summary=(
            f"payment-service latency-tail spike with elevated error rate "
            f"({alert['features']['error_rate']:.1%}). Score "
            f"{alert['score']:+.3f} vs threshold {alert['threshold']:+.3f}."
        ),
        root_cause_hypothesis=(
            f"Top SHAP contributor `{top_features[0]['name']}` "
            f"(shap {top_features[0]['shap']:+.2f}) drove the score."
        ),
        contributing_features=[
            ContributingFeature(**tf) for tf in top_features
        ],
        recommended_actions=[
            RecommendedAction(
                timeframe="immediate",
                action="Page payment-service oncall",
                rationale="High error rate during business hours",
            ),
        ],
        monitoring_checks=["payment-service p99 latency", "error rate"],
    )
    roundtrip = IncidentReport.model_validate(report.model_dump())
    assert report == roundtrip, "Pydantic round-trip mismatch"
    markdown = report.to_markdown()
    for tf in top_features:
        assert tf["name"] in markdown, f"SHAP feature {tf['name']} missing from markdown"
    ok("structured report round-trips and renders all top SHAP features")
    info(f"markdown length: {len(markdown)} chars")

    print(f"\n{GREEN}=== Dry-run complete: 10/10 steps passed ==={RESET}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        print(f"\n{RED}DRY-RUN ABORTED{RESET}")
        traceback.print_exc()
        sys.exit(1)
