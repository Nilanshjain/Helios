"""Pydantic schemas for structured LLM output.

Both ``GeminiGenerator`` and ``ClaudeGenerator`` target this schema so the
report shape is identical regardless of provider — the consumer code paths
(filesystem storage, DB insert, PDF rendering) never branch on which LLM
produced the report. Provider-specific structured-output features used:

* Gemini: ``response_mime_type="application/json"`` plus
  ``response_schema=IncidentReport`` (native JSON schema constraint).
* Claude: a JSON-only system prompt plus a single tool-style "extraction"
  message. Parsed back into the same Pydantic model after the API returns.

When the structured parse fails (rare with modern models, but defensively
handled), generators fall back to ``IncidentReport.from_free_text(...)`` so
downstream storage still gets a valid object — the markdown body is then
whatever the model produced verbatim.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ContributingFeature(BaseModel):
    """One feature called out by SHAP as driving the anomaly score."""

    name: str = Field(..., description="Feature name as it appears in feature_engineering.py")
    value: float = Field(..., description="Actual feature value for the anomalous window")
    shap: float = Field(
        ...,
        description=(
            "SHAP attribution. Negative pushes the IsolationForest score down "
            "(more anomalous); positive pushes it up (more normal)."
        ),
    )
    direction: Literal["toward_anomaly", "toward_normal"] = Field(
        ..., description="Human-friendly direction derived from the SHAP sign"
    )


class RecommendedAction(BaseModel):
    timeframe: Literal["immediate", "short_term", "long_term"] = Field(
        ..., description="Suggested execution window for this action"
    )
    action: str = Field(..., description="Concrete, actionable step")
    rationale: str = Field(..., description="Why this action follows from the evidence")


class IncidentReport(BaseModel):
    """Structured incident report. Markdown rendering is derived from this."""

    incident_id: str
    service: str
    detected_at: str
    severity: Severity
    confidence: float = Field(
        ...,
        description=(
            "LLM-assessed confidence in the root-cause hypothesis (0-1). "
            "ge/le constraints removed because Gemini's response_schema "
            "rejects JSON-schema minimum/maximum fields; the prompt enforces "
            "the range instead."
        ),
    )

    executive_summary: str = Field(
        ..., description="Two-to-three-sentence overview suitable for an oncall pager"
    )
    root_cause_hypothesis: str = Field(
        ..., description="Primary root-cause hypothesis grounded in the SHAP features"
    )
    contributing_features: List[ContributingFeature] = Field(
        default_factory=list,
        description="Top SHAP-attributed features from the detection layer",
    )
    recommended_actions: List[RecommendedAction] = Field(
        default_factory=list,
        description="Actions ordered immediate → short_term → long_term",
    )
    monitoring_checks: List[str] = Field(
        default_factory=list,
        description="Specific signals to watch after triage (metric names, dashboards)",
    )

    @classmethod
    def from_free_text(
        cls,
        incident_id: str,
        service: str,
        detected_at: str,
        severity: str,
        markdown: str,
    ) -> "IncidentReport":
        """Build a minimal IncidentReport when structured parsing fails.

        The markdown body is preserved in ``executive_summary`` (so it lands
        unchanged in the saved .md file), and the rest of the fields get
        conservative placeholders. This keeps the downstream pipeline alive
        even when the model returns malformed JSON.
        """
        normalized_severity: Severity = (
            severity.upper() if str(severity).upper() in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "MEDIUM"
        )  # type: ignore[assignment]
        return cls(
            incident_id=incident_id,
            service=service,
            detected_at=detected_at,
            severity=normalized_severity,
            confidence=0.5,
            executive_summary=markdown.strip()[:1000] or "LLM returned no content.",
            root_cause_hypothesis="Structured parse failed; see executive summary for the raw model output.",
            contributing_features=[],
            recommended_actions=[],
            monitoring_checks=[],
        )

    def to_markdown(self) -> str:
        """Render the structured report as a markdown document.

        Renders identically regardless of which LLM produced the underlying
        fields, so saved reports look uniform across Gemini, Claude, and mock.
        """
        lines: list[str] = []
        lines.append(f"# Incident Report: {self.incident_id}\n")
        lines.append(f"**Service**: `{self.service}`  ")
        lines.append(f"**Detected**: {self.detected_at}  ")
        lines.append(f"**Severity**: {self.severity}  ")
        lines.append(f"**Model confidence**: {self.confidence:.2f}\n")
        lines.append("---\n")

        lines.append("## Executive summary\n")
        lines.append(self.executive_summary + "\n")

        lines.append("## Root cause hypothesis\n")
        lines.append(self.root_cause_hypothesis + "\n")

        if self.contributing_features:
            lines.append("## Top contributing features (SHAP)\n")
            lines.append("| Feature | Value | SHAP | Direction |")
            lines.append("|---|---|---|---|")
            for f in self.contributing_features:
                lines.append(
                    f"| `{f.name}` | {f.value:.3f} | {f.shap:+.3f} | {f.direction} |"
                )
            lines.append("")

        if self.recommended_actions:
            lines.append("## Recommended actions\n")
            for tf in ("immediate", "short_term", "long_term"):
                bucket = [a for a in self.recommended_actions if a.timeframe == tf]
                if not bucket:
                    continue
                lines.append(f"### {tf.replace('_', ' ').title()}\n")
                for a in bucket:
                    lines.append(f"- **{a.action}** — {a.rationale}")
                lines.append("")

        if self.monitoring_checks:
            lines.append("## Monitoring follow-up\n")
            for m in self.monitoring_checks:
                lines.append(f"- {m}")
            lines.append("")

        lines.append("---")
        lines.append(
            f"\n*Generated by Helios at {datetime.now(timezone.utc).isoformat(timespec='seconds')}*"
        )
        return "\n".join(lines)
