"""Google Gemini structured-output report generator.

Default LLM for Helios. Uses Gemini 1.5 Flash via the official
``google-generativeai`` SDK with native JSON-schema constrained output —
the response is parsed straight back into the ``IncidentReport`` Pydantic
model, no regex / markdown fence stripping required.

Free-tier limits (1500 req/day, 1M TPM) are enforced server-side; on
quota-exhaustion the generator raises and the consumer falls back to the
mock generator gracefully (see ``ReportConsumer._build_generator``).
"""

from __future__ import annotations

import json
import time
from typing import Any

import google.generativeai as genai

from app.core.config import settings
from app.core.logging import get_logger
from app.generators.base import ReportContext, ReportGenerator, ReportResult
from app.generators.prompts import build_structured_prompt
from app.generators.structured_output import IncidentReport

logger = get_logger(__name__)


# Gemini 1.5 Flash pricing (publicly listed; free tier covers Helios demo use).
# Kept explicit so the cost-tracking code path is symmetric with the Claude
# generator and so the interview talking point ("I track cost per report
# regardless of provider") is defensible.
_GEMINI_PRICING = {
    "gemini-1.5-flash": {
        "input": 0.075 / 1_000_000,   # $0.075 per 1M input tokens
        "output": 0.30 / 1_000_000,   # $0.30 per 1M output tokens
    },
    "gemini-1.5-flash-8b": {
        "input": 0.0375 / 1_000_000,
        "output": 0.15 / 1_000_000,
    },
    "gemini-1.5-pro": {
        "input": 1.25 / 1_000_000,
        "output": 5.00 / 1_000_000,
    },
}


class GeminiGenerator(ReportGenerator):
    """Generate incident reports via Google Gemini with structured output."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        genai.configure(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_model
        self.max_tokens = settings.gemini_max_tokens
        self.temperature = settings.gemini_temperature
        self.max_retries = settings.gemini_max_retries

        # Configure structured output: the SDK accepts a Pydantic class as
        # the schema and will produce JSON that round-trips through it.
        self.generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=IncidentReport,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=(
                "You are a senior Site Reliability Engineer. Produce strict "
                "JSON conforming to the IncidentReport schema. Ground every "
                "claim in the provided evidence; never invent metrics."
            ),
        )

        logger.info(
            "gemini_generator_initialized",
            model=self.model_name,
            max_tokens=self.max_tokens,
        )

    def generate(self, context: ReportContext) -> ReportResult:
        start_time = time.time()

        prompt = build_structured_prompt(context)
        response = self._call_with_retry(prompt)

        report = self._parse_response(context, response)
        markdown = report.to_markdown()

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        tokens_used = input_tokens + output_tokens
        cost_usd = self._calculate_cost(input_tokens, output_tokens)

        report_id = f"report_{context.anomaly.get('id', 'unknown')}_{int(time.time())}"
        generation_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "report_generated",
            report_id=report_id,
            provider="gemini",
            model=self.model_name,
            tokens=tokens_used,
            cost_usd=cost_usd,
            time_ms=generation_time_ms,
        )

        return ReportResult(
            report_id=report_id,
            content=markdown,
            format="markdown",
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            generation_time_ms=generation_time_ms,
            metadata={
                "model": self.model_name,
                "provider": "gemini",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "structured": True,
                "incident_report": report.model_dump(),
            },
        )

    def _call_with_retry(self, prompt: str) -> Any:
        """Single-shot call with exponential-backoff retry on transient errors.

        Gemini surfaces transient failures (quota, server) as exceptions in
        ``google.api_core.exceptions``. We don't import that module
        explicitly to keep the dependency surface small — instead we sleep
        and retry on any exception, raising after the last attempt.
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._model.generate_content(
                    prompt,
                    generation_config=self.generation_config,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                wait_seconds = 2**attempt
                logger.warning(
                    "gemini_call_failed",
                    attempt=attempt + 1,
                    wait_seconds=wait_seconds,
                    error=str(exc),
                )
                time.sleep(wait_seconds)
        raise RuntimeError(
            f"Gemini API failed after {self.max_retries} retries: {last_error}"
        )

    def _parse_response(self, context: ReportContext, response: Any) -> IncidentReport:
        """Parse Gemini's JSON response into an IncidentReport.

        With ``response_schema`` set, ``response.text`` is JSON conforming to
        the schema. If parsing still fails (model returned something off-spec
        despite the schema), we fall back to a free-text wrapper so the
        downstream pipeline (filesystem, DB, PDF) still receives a valid
        object instead of crashing.
        """
        anomaly = context.anomaly
        try:
            text = response.text
            data = json.loads(text)
            return IncidentReport.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("gemini_structured_parse_failed", error=str(exc))
            raw = getattr(response, "text", "") or ""
            return IncidentReport.from_free_text(
                incident_id=anomaly.get("id", "unknown"),
                service=anomaly.get("service", "unknown"),
                detected_at=anomaly.get("timestamp", "unknown"),
                severity=str(anomaly.get("severity", "MEDIUM")),
                markdown=raw,
            )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = _GEMINI_PRICING.get(self.model_name, _GEMINI_PRICING["gemini-1.5-flash"])
        return round(input_tokens * pricing["input"] + output_tokens * pricing["output"], 6)

    def health_check(self) -> bool:
        try:
            self._model.generate_content(
                "ping",
                generation_config=genai.types.GenerationConfig(max_output_tokens=4),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("gemini_health_check_failed", error=str(exc))
            return False
