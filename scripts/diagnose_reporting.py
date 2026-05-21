"""Standalone diagnostic that exercises each layer of the reporting path.

Run inside the helios-reporting-consumer container:

    docker cp scripts/diagnose_reporting.py helios-reporting-consumer:/tmp/
    docker exec helios-reporting-consumer python /tmp/diagnose_reporting.py

It runs five independent checks; each fails loudly so we know exactly which
layer is broken. No Kafka involvement — the only purpose is to isolate the
Gemini + Pydantic + storage path.
"""

import json
import sys
import traceback
from datetime import datetime, timezone


def step(n: int, name: str) -> None:
    print(f"\n=== {n}. {name} ===", flush=True)


def ok(msg: str) -> None:
    print(f"  PASS: {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"  FAIL: {msg}", flush=True)


def main() -> int:
    # ------------------------------------------------------------------
    step(1, "Settings load + Gemini config")
    # ------------------------------------------------------------------
    try:
        from app.core.config import settings  # type: ignore

        ok(f"REPORT_GENERATOR_MODE={settings.report_generator_mode}")
        ok(f"GEMINI_API_KEY set={bool(settings.gemini_api_key)} (len={len(settings.gemini_api_key)})")
        ok(f"GEMINI_MODEL={settings.gemini_model}")
        ok(f"DB host={settings.db_host} port={settings.db_port}")
    except Exception as exc:
        fail(f"settings load: {exc}")
        traceback.print_exc()
        return 1

    # ------------------------------------------------------------------
    step(2, "IncidentReport Pydantic schema -> JSON schema conversion")
    # ------------------------------------------------------------------
    try:
        from app.generators.structured_output import IncidentReport

        schema = IncidentReport.model_json_schema()
        json_str = json.dumps(schema, indent=2)
        ok(f"Pydantic schema renders OK ({len(json_str)} chars)")
        # Check for fields Gemini's adapter is known to choke on
        suspects = ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"]
        found = [s for s in suspects if s in json_str]
        if found:
            fail(f"Schema contains fields Gemini's response_schema rejects: {found}")
        else:
            ok("No minimum/maximum/exclusive* fields (Gemini-safe)")
    except Exception as exc:
        fail(f"schema: {exc}")
        traceback.print_exc()
        return 1

    # ------------------------------------------------------------------
    step(3, "Gemini client initialisation")
    # ------------------------------------------------------------------
    try:
        from app.generators.gemini_generator import GeminiGenerator

        gen = GeminiGenerator()
        ok(f"GeminiGenerator initialised: model={gen.model_name}")
    except Exception as exc:
        fail(f"GeminiGenerator init: {exc}")
        traceback.print_exc()
        return 1

    # ------------------------------------------------------------------
    step(4, "End-to-end Gemini API call with a fake anomaly")
    # ------------------------------------------------------------------
    try:
        from app.generators.base import ReportContext

        fake_anomaly = {
            "id": "test_anomaly_diag",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "payment-service",
            "severity": "HIGH",
            "score": -0.31,
            "threshold": -0.04,
            "features": {
                "event_count": 100, "error_rate": 0.4, "p50_latency_ms": 100.0,
                "p95_latency_ms": 4000.0, "p99_latency_ms": 5000.0,
                "latency_std": 800.0, "hour_of_day": 12.0, "p95_p50_ratio": 40.0,
                "p99_p95_ratio": 1.25, "error_count": 40.0,
                "log_event_count": 4.6, "log_error_rate": 6.0,
            },
            "top_features": [
                {"name": "p99_latency_ms", "value": 5000.0, "shap": -1.75, "direction": "toward_anomaly"},
                {"name": "p95_latency_ms", "value": 4000.0, "shap": -1.5, "direction": "toward_anomaly"},
                {"name": "latency_std", "value": 800.0, "shap": -1.3, "direction": "toward_anomaly"},
            ],
        }
        context = ReportContext(
            anomaly=fake_anomaly,
            events=[
                {"timestamp": fake_anomaly["timestamp"], "service": "payment-service",
                 "level": "ERROR", "message": "DB timeout", "metadata": {"latency_ms": 5000}},
                {"timestamp": fake_anomaly["timestamp"], "service": "payment-service",
                 "level": "INFO", "message": "request ok", "metadata": {"latency_ms": 50}},
            ],
            metrics={"avg_event_count": 100, "avg_error_rate": 0.4, "avg_latency": 100, "avg_p99_latency": 5000},
            recent_anomalies=[],
        )
        result = gen.generate(context)
        ok(f"Gemini returned a report: id={result.report_id}")
        ok(f"  tokens_used={result.tokens_used}  cost_usd={result.cost_usd}")
        ok(f"  markdown length={len(result.content)} chars")
        ok(f"  metadata.provider={result.metadata.get('provider')}")
        ok(f"  metadata.structured={result.metadata.get('structured')}")
        # The model is asked to ground the hypothesis in a SHAP feature; verify.
        ir = result.metadata.get("incident_report", {})
        rch = ir.get("root_cause_hypothesis", "")
        if any(f["name"] in rch for f in fake_anomaly["top_features"]):
            ok("Root-cause hypothesis references at least one SHAP feature by name")
        else:
            print(f"  WARN: root_cause_hypothesis does not name a SHAP feature: {rch[:120]}")
        print(f"\n--- Generated markdown (first 600 chars) ---\n{result.content[:600]}")
    except Exception as exc:
        fail(f"Gemini end-to-end: {exc}")
        traceback.print_exc()
        return 1

    # ------------------------------------------------------------------
    step(5, "DB connection — can we actually write a report?")
    # ------------------------------------------------------------------
    try:
        from app.core.database import db
        from app.storage.database import DatabaseStorage

        storage = DatabaseStorage()
        ok("DatabaseStorage initialised")
        # Don't actually insert — just verify connectivity
        # We won't try the insert because that requires the full schema.
        from app.core.database import db as _db
        with _db.get_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        ok("DB cursor + SELECT works")
    except Exception as exc:
        fail(f"DB: {exc}")
        traceback.print_exc()
        return 1

    print("\n=== ALL DIAGNOSTIC STEPS PASSED ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
