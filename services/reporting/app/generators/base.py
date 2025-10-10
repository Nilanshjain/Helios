"""Base report generator interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ReportContext:
    """Context data for report generation"""

    anomaly: Dict[str, Any]
    events: list
    metrics: Dict[str, Any]
    recent_anomalies: list


@dataclass
class ReportResult:
    """Generated report result"""

    report_id: str
    content: str
    format: str = "markdown"
    tokens_used: int = 0
    cost_usd: float = 0.0
    generation_time_ms: float = 0.0
    metadata: Dict[str, Any] = None


class ReportGenerator(ABC):
    """Base class for report generators"""

    @abstractmethod
    def generate(self, context: ReportContext) -> ReportResult:
        """Generate incident report from context"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if generator is healthy"""
        pass
