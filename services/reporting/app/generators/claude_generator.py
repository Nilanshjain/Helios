"""Anthropic Claude 3.5 Sonnet report generator"""

import time
from typing import Any
from anthropic import Anthropic, APIError, RateLimitError, APIStatusError

from app.core.config import settings
from app.core.logging import get_logger
from app.generators.base import ReportGenerator, ReportContext, ReportResult
from app.generators.prompts import build_incident_report_prompt

logger = get_logger(__name__)


class ClaudeGenerator(ReportGenerator):
    """
    Generate reports using Anthropic Claude 3.5 Sonnet.

    Why Claude for resume/portfolio:
    - Latest AI technology (cutting-edge)
    - Superior at technical writing
    - Shows ability to integrate multiple AI providers
    - Better quality demos
    """

    # Token pricing (Claude 3.5 Sonnet as of 2024)
    PRICING = {
        "claude-3-5-sonnet-20241022": {
            "input": 3.00 / 1_000_000,   # $3 per 1M tokens
            "output": 15.00 / 1_000_000,  # $15 per 1M tokens
        },
        "claude-3-5-haiku-20241022": {
            "input": 1.00 / 1_000_000,
            "output": 5.00 / 1_000_000,
        },
    }

    def __init__(self) -> None:
        """Initialize Anthropic client"""
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens
        self.temperature = settings.claude_temperature
        self.max_retries = settings.claude_max_retries

        logger.info(
            "claude_generator_initialized",
            model=self.model,
            max_tokens=self.max_tokens,
        )

    def generate(self, context: ReportContext) -> ReportResult:
        """Generate report using Claude 3.5 Sonnet"""
        start_time = time.time()

        try:
            # Build prompt
            prompt = build_incident_report_prompt(context)

            # Call Claude with retry logic
            response = self._call_claude_with_retry(prompt)

            # Calculate metrics
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            cost_usd = self._calculate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            generation_time_ms = (time.time() - start_time) * 1000

            # Extract report content
            content = response.content[0].text

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
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "stop_reason": response.stop_reason,
                },
            )

        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            raise

    def _call_claude_with_retry(self, prompt: str) -> Any:
        """Call Claude API with exponential backoff retry"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=(
                        "You are a senior Site Reliability Engineer with 10+ years of experience "
                        "analyzing production incidents. Provide technical, evidence-based analysis "
                        "with actionable recommendations. Be thorough yet concise. Focus on root causes "
                        "and preventive measures."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )

                return response

            except RateLimitError as e:
                last_error = e
                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    "claude_rate_limit",
                    attempt=attempt + 1,
                    wait_seconds=wait_time,
                )
                time.sleep(wait_time)

            except APIStatusError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "claude_api_error",
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                        error=str(e),
                    )
                    time.sleep(wait_time)
                else:
                    raise

            except APIError as e:
                logger.error("claude_error", error=str(e))
                raise

        # If all retries failed
        raise Exception(
            f"Claude API failed after {self.max_retries} retries: {last_error}"
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost"""
        pricing = self.PRICING.get(
            self.model, self.PRICING["claude-3-5-sonnet-20241022"]
        )

        cost = (
            input_tokens * pricing["input"] + output_tokens * pricing["output"]
        )

        return round(cost, 6)

    def health_check(self) -> bool:
        """Check Claude API health"""
        try:
            # Simple API call to verify connectivity
            response = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception as e:
            logger.error("claude_health_check_failed", error=str(e))
            return False
