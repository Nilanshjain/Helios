"""Tests for report generation"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.generators.base import ReportContext, ReportResult
from app.generators.claude_generator import ClaudeGenerator


class TestClaudeGenerator:
    """Test suite for Claude report generator"""

    def create_sample_context(self):
        """Create sample report context for testing"""
        return ReportContext(
            anomaly={
                "id": "anomaly_123",
                "service": "payment-service",
                "score": -0.95,
                "severity": "high",
                "detected_at": datetime.now().isoformat(),
                "features": {
                    "total_events": 150,
                    "error_rate": 0.45,
                    "avg_latency": 850,
                    "p95_latency": 1200,
                    "p99_latency": 1500,
                },
            },
            recent_events=[
                {
                    "timestamp": datetime.now().isoformat(),
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": "Database connection timeout",
                    "metadata": {"latency_ms": 5000, "error_code": "DB_TIMEOUT"},
                }
                for _ in range(10)
            ],
            historical_patterns={
                "avg_daily_errors": 5,
                "avg_daily_events": 10000,
                "previous_incidents": 2,
            },
            service_metadata={
                "name": "payment-service",
                "version": "1.2.3",
                "team": "payments",
                "dependencies": ["database", "cache"],
            },
        )

    @patch("app.generators.claude_generator.Anthropic")
    def test_initialization_success(self, mock_anthropic):
        """Test successful initialization with API key"""
        with patch("app.generators.claude_generator.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-api-key"
            mock_settings.claude_model = "claude-3-5-sonnet-20241022"
            mock_settings.claude_max_tokens = 1500
            mock_settings.claude_temperature = 0.3
            mock_settings.claude_max_retries = 3

            generator = ClaudeGenerator()

            assert generator.model == "claude-3-5-sonnet-20241022"
            assert generator.max_tokens == 1500
            assert generator.temperature == 0.3

    def test_initialization_missing_api_key(self):
        """Test initialization fails without API key"""
        with patch("app.generators.claude_generator.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not configured"):
                ClaudeGenerator()

    @patch("app.generators.claude_generator.Anthropic")
    def test_generate_report_success(self, mock_anthropic):
        """Test successful report generation"""
        # Setup mocks
        with patch("app.generators.claude_generator.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-api-key"
            mock_settings.claude_model = "claude-3-5-sonnet-20241022"
            mock_settings.claude_max_tokens = 1500
            mock_settings.claude_temperature = 0.3
            mock_settings.claude_max_retries = 3

            # Mock Claude API response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="# Incident Report\n\nTest report content")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=300)
            mock_response.stop_reason = "end_turn"

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            generator = ClaudeGenerator()
            context = self.create_sample_context()

            result = generator.generate(context)

            assert isinstance(result, ReportResult)
            assert result.content == "# Incident Report\n\nTest report content"
            assert result.format == "markdown"
            assert result.tokens_used == 800
            assert result.cost_usd > 0
            assert result.generation_time_ms > 0

    @patch("app.generators.claude_generator.Anthropic")
    def test_cost_calculation(self, mock_anthropic):
        """Test cost calculation for Claude API usage"""
        with patch("app.generators.claude_generator.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-api-key"
            mock_settings.claude_model = "claude-3-5-sonnet-20241022"
            mock_settings.claude_max_tokens = 1500
            mock_settings.claude_temperature = 0.3
            mock_settings.claude_max_retries = 3

            generator = ClaudeGenerator()

            # Test cost calculation
            # $3 per 1M input tokens, $15 per 1M output tokens
            input_tokens = 1000
            output_tokens = 500

            expected_cost = (1000 * 3.00 / 1_000_000) + (500 * 15.00 / 1_000_000)

            cost = generator._calculate_cost(input_tokens, output_tokens)

            assert abs(cost - expected_cost) < 0.00001, f"Expected {expected_cost}, got {cost}"


class TestMockGenerator:
    """Test suite for mock report generator"""

    def create_sample_context(self):
        """Create sample report context"""
        return ReportContext(
            anomaly={
                "id": "anomaly_456",
                "service": "api-gateway",
                "score": -0.85,
                "severity": "medium",
                "features": {"error_rate": 0.25},
            },
            recent_events=[],
            historical_patterns={},
            service_metadata={"name": "api-gateway"},
        )

    def test_mock_generator_no_cost(self):
        """Test that mock generator has zero cost"""
        from app.generators.base import MockGenerator

        generator = MockGenerator()
        context = self.create_sample_context()

        result = generator.generate(context)

        assert result.cost_usd == 0.0, "Mock generator should have zero cost"
        assert result.tokens_used == 0, "Mock generator should have zero tokens"
        assert result.format == "markdown"
        assert len(result.content) > 0

    def test_mock_generator_structure(self):
        """Test that mock generator produces structured output"""
        from app.generators.base import MockGenerator

        generator = MockGenerator()
        context = self.create_sample_context()

        result = generator.generate(context)

        # Check for key sections in report
        content = result.content.lower()
        assert "executive summary" in content or "summary" in content
        assert "service" in content
        assert "severity" in content

    def test_mock_generator_fast_generation(self):
        """Test that mock generator is fast"""
        from app.generators.base import MockGenerator

        generator = MockGenerator()
        context = self.create_sample_context()

        result = generator.generate(context)

        # Should be very fast (< 100ms)
        assert result.generation_time_ms < 100, f"Mock generation too slow: {result.generation_time_ms}ms"


class TestReportContext:
    """Test suite for ReportContext"""

    def test_report_context_creation(self):
        """Test creating report context"""
        context = ReportContext(
            anomaly={"id": "test", "service": "test-service"},
            recent_events=[{"message": "test"}],
            historical_patterns={"avg_errors": 10},
            service_metadata={"name": "test-service"},
        )

        assert context.anomaly["id"] == "test"
        assert len(context.recent_events) == 1
        assert context.historical_patterns["avg_errors"] == 10


class TestReportResult:
    """Test suite for ReportResult"""

    def test_report_result_creation(self):
        """Test creating report result"""
        result = ReportResult(
            report_id="report_123",
            content="# Test Report",
            format="markdown",
            tokens_used=100,
            cost_usd=0.005,
            generation_time_ms=1500.0,
            metadata={"model": "claude-3-5-sonnet"},
        )

        assert result.report_id == "report_123"
        assert result.format == "markdown"
        assert result.tokens_used == 100
        assert result.cost_usd == 0.005
        assert result.metadata["model"] == "claude-3-5-sonnet"
