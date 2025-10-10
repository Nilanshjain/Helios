"""OpenAI GPT-4 report generator"""

import time
from typing import Dict, Any
import json
from openai import OpenAI, OpenAIError, RateLimitError, APIError

from app.core.config import settings
from app.core.logging import get_logger
from app.generators.base import ReportGenerator, ReportContext, ReportResult
from app.generators.prompts import build_incident_report_prompt

logger = get_logger(__name__)


class OpenAIGenerator(ReportGenerator):
    """Generate reports using OpenAI GPT-4"""

    # Token pricing (as of 2024)
    PRICING = {
        "gpt-4": {
            "prompt": 0.03 / 1000,  # $0.03 per 1K prompt tokens
            "completion": 0.06 / 1000,  # $0.06 per 1K completion tokens
        },
        "gpt-4-turbo": {
            "prompt": 0.01 / 1000,
            "completion": 0.03 / 1000,
        },
        "gpt-3.5-turbo": {
            "prompt": 0.0015 / 1000,
            "completion": 0.002 / 1000,
        },
    }

    def __init__(self) -> None:
        """Initialize OpenAI client"""
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        self.max_retries = settings.openai_max_retries

        logger.info(
            "openai_generator_initialized",
            model=self.model,
            max_tokens=self.max_tokens,
        )

    def generate(self, context: ReportContext) -> ReportResult:
        """Generate report using GPT-4"""
        start_time = time.time()

        try:
            # Build prompt
            prompt = build_incident_report_prompt(context)

            # Call OpenAI with retry logic
            response = self._call_openai_with_retry(prompt)

            # Calculate metrics
            tokens_used = response.usage.total_tokens
            cost_usd = self._calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
            generation_time_ms = (time.time() - start_time) * 1000

            # Extract report content
            content = response.choices[0].message.content

            report_id = f"report_{context.anomaly.get('id', 'unknown')}_{int(time.time())}"

            logger.info(
                "report_generated",
                report_id=report_id,
                tokens=tokens_used,
                cost_usd=cost_usd,
                time_ms=generation_time_ms,
            )

            return ReportResult(
                report_id=report_id,
                content=content,
                format="markdown",
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                generation_time_ms=generation_time_ms,
                metadata={
                    "model": self.model,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            )

        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            raise

    def _call_openai_with_retry(self, prompt: str) -> Any:
        """Call OpenAI API with exponential backoff retry"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a senior Site Reliability Engineer analyzing production incidents. "
                                "Provide technical, actionable analysis with evidence-based conclusions. "
                                "Be concise but thorough. Focus on what matters."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=0.9,
                )

                return response

            except RateLimitError as e:
                last_error = e
                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    "openai_rate_limit",
                    attempt=attempt + 1,
                    wait_seconds=wait_time,
                )
                time.sleep(wait_time)

            except APIError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "openai_api_error",
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                        error=str(e),
                    )
                    time.sleep(wait_time)
                else:
                    raise

            except OpenAIError as e:
                logger.error("openai_error", error=str(e))
                raise

        # If all retries failed
        raise Exception(f"OpenAI API failed after {self.max_retries} retries: {last_error}")

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate estimated cost"""
        pricing = self.PRICING.get(self.model, self.PRICING["gpt-4"])

        cost = (
            prompt_tokens * pricing["prompt"]
            + completion_tokens * pricing["completion"]
        )

        return round(cost, 6)

    def health_check(self) -> bool:
        """Check OpenAI API health"""
        try:
            # Simple API call to verify connectivity
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.error("openai_health_check_failed", error=str(e))
            return False
