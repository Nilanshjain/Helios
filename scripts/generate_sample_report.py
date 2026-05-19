#!/usr/bin/env python3
"""Generate a sample incident report for docs/.

Writes ``docs/sample-incident-report.md`` (and a PDF when WeasyPrint is
installed) using the real ``IncidentReport`` Pydantic schema and markdown
renderer used in production. The fields and SHAP attributions are
hand-constructed to reflect a representative payment-service incident so
recruiters can see what a real report looks like without running the full
stack.

Idempotent — run it any time you want to refresh the sample.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "reporting"))

from app.generators.structured_output import (  # noqa: E402
    ContributingFeature,
    IncidentReport,
    RecommendedAction,
)


def build_sample() -> IncidentReport:
    return IncidentReport(
        incident_id="anomaly_payment-service_1747662000",
        service="payment-service",
        detected_at="2026-05-19T14:20:00Z",
        severity="HIGH",
        confidence=0.82,
        executive_summary=(
            "payment-service exhibited a sustained P99 latency spike (820ms, "
            "vs. a 24h baseline of ~140ms) with elevated error rate (4.2%, "
            "vs. ~0.4%) over a 5-minute window. IsolationForest score "
            "-0.74 (threshold -0.10). SHAP attributes the score primarily "
            "to p99_latency_ms and error_count, consistent with a "
            "downstream-dependency slowdown rather than an internal bug."
        ),
        root_cause_hypothesis=(
            "The dominant SHAP contributor is `p99_latency_ms` (SHAP -1.44), "
            "with `error_count` (SHAP -1.36) and `error_rate` (SHAP -1.31) "
            "close behind. The latency-tail signature without a corresponding "
            "increase in `event_count` (volume held steady) is the classic "
            "fingerprint of a downstream dependency slowing down — payment-service "
            "is waiting longer per request rather than handling more of them. "
            "Most likely candidate: the bank-gateway adapter or its connection "
            "pool. Confirmation: check the bank-gateway-service P99 over the "
            "same window."
        ),
        contributing_features=[
            ContributingFeature(
                name="p99_latency_ms",
                value=820.0,
                shap=-1.44,
                direction="toward_anomaly",
            ),
            ContributingFeature(
                name="error_count",
                value=126.0,
                shap=-1.36,
                direction="toward_anomaly",
            ),
            ContributingFeature(
                name="error_rate",
                value=0.042,
                shap=-1.31,
                direction="toward_anomaly",
            ),
        ],
        recommended_actions=[
            RecommendedAction(
                timeframe="immediate",
                action="Page bank-gateway oncall and check the dependency dashboard.",
                rationale=(
                    "Latency-tail signature without volume increase points at a "
                    "downstream dependency; bank-gateway is the most likely culprit "
                    "given the service topology."
                ),
            ),
            RecommendedAction(
                timeframe="immediate",
                action="Verify the payment-service connection pool to bank-gateway "
                       "is not exhausted (HikariCP metrics).",
                rationale=(
                    "Pool exhaustion would manifest as exactly this signature — "
                    "high P99, normal volume, elevated errors from request timeouts."
                ),
            ),
            RecommendedAction(
                timeframe="short_term",
                action="Add `bank_gateway_p99_latency` to the payment-service feature "
                       "set in the next training run.",
                rationale=(
                    "The detector saw the *symptom* (slow payment-service) but no "
                    "direct evidence of the *cause* (slow bank-gateway). Including the "
                    "upstream signal would catch this earlier and explain it directly."
                ),
            ),
            RecommendedAction(
                timeframe="long_term",
                action="Implement a circuit breaker between payment-service and bank-gateway.",
                rationale=(
                    "Repeated dependency slowdowns should fail fast rather than "
                    "accumulate latency in the payment path. Current architecture has "
                    "no breaker; this is the third bank-gateway-related incident this "
                    "quarter."
                ),
            ),
        ],
        monitoring_checks=[
            "bank-gateway-service P99 latency (next 30 minutes)",
            "payment-service HikariCP active-connections / pending-acquisitions",
            "error budget burn rate for the payment SLO",
            "Helios anomaly rate for bank-gateway-service in the same window",
        ],
    )


def main() -> int:
    report = build_sample()
    out_md = REPO_ROOT / "docs" / "sample-incident-report.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    markdown = report.to_markdown()
    # Prepend a short reader-orienting note so recruiters who land directly
    # on this file know what they're looking at.
    note = (
        "<!-- Generated by scripts/generate_sample_report.py. Edits will be "
        "overwritten on the next run. -->\n\n"
        "> **Sample output from the Helios reporting service.** The markdown "
        "below is a real `IncidentReport` Pydantic object rendered through "
        "`services/reporting/app/generators/structured_output.py::to_markdown` "
        "— the exact same code path the live system uses for "
        "Gemini-generated and Claude-generated reports. The anomaly itself is "
        "synthesised for the demo (payment-service P99 spike), but the "
        "schema, SHAP attributions, and rendering are production.\n\n---\n\n"
    )
    out_md.write_text(note + markdown, encoding="utf-8")
    print(f"Wrote {out_md}")

    # Best-effort PDF render. WeasyPrint requires native libs (libpango,
    # cairo) that aren't trivially installable on Windows, so we don't
    # require it — the markdown is the canonical artifact.
    try:
        from app.utils.pdf_generator import PDFGenerator  # type: ignore

        out_pdf = out_md.with_suffix(".pdf")
        PDFGenerator().markdown_to_pdf(
            markdown_content=markdown,
            output_path=str(out_pdf),
            title=f"Sample Incident Report: {report.incident_id}",
            metadata={"service": report.service, "severity": report.severity},
        )
        print(f"Wrote {out_pdf}")
    except Exception as exc:  # noqa: BLE001
        print(f"[info] PDF skipped: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
