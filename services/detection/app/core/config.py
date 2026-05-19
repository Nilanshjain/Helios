"""Configuration management using Pydantic Settings"""

import json
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


def _threshold_from_evaluation(results_path: str | os.PathLike) -> Optional[float]:
    """Read the per-dataset chosen threshold from models/evaluation/results.json.

    The evaluation harness (scripts/evaluate.py) writes one chosen_threshold per
    evaluated dataset (NAB, SMD). For production we use the NAB threshold when
    available — NAB streams more closely resemble Helios's single-service
    operational telemetry — and fall back to whichever dataset is present.

    Returns None if the file is missing or malformed, in which case the default
    ANOMALY_THRESHOLD env value (or class default) is used.
    """
    try:
        path = Path(results_path)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        per_dataset = {d["dataset"]: d for d in data.get("datasets", [])}
        for preferred in ("nab", "smd"):
            if preferred in per_dataset:
                return float(per_dataset[preferred]["chosen_threshold"])
        return None
    except Exception:
        return None


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields like anthropic_api_key
        protected_namespaces=('settings_',)  # Fix model_ namespace warning
    )

    # Kafka Configuration
    kafka_brokers: str = "localhost:9092"
    kafka_events_topic: str = "events"
    kafka_alerts_topic: str = "anomaly-alerts"
    kafka_consumer_group: str = "anomaly-detectors"

    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "helios"
    db_user: str = "postgres"
    db_password: str = "postgres"

    # Model Configuration
    model_path: str = "./models/isolation_forest.pkl"
    eval_results_path: str = "./models/evaluation/results.json"
    contamination: float = 0.05
    # Default threshold: overridden at startup by the value chosen during
    # evaluation (see scripts/evaluate.py + _threshold_from_evaluation above).
    # If no eval results exist, ANOMALY_THRESHOLD env var (or this default)
    # is used.
    anomaly_threshold: float = -0.7
    window_size_minutes: int = 5
    min_events_per_window: int = 10

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Metrics
    metrics_port: int = 8001

    @property
    def kafka_brokers_list(self) -> List[str]:
        """Parse Kafka brokers from comma-separated string"""
        return [broker.strip() for broker in self.kafka_brokers.split(",")]

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL"""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


# Global settings instance
settings = Settings()

# If a Phase-2 evaluation has been run, derive the production threshold from
# the held-out validation sweep instead of using the hard-coded default. This
# lets `python scripts/evaluate.py` drive the operating point in production
# without manual env-var management.
_eval_threshold = _threshold_from_evaluation(settings.eval_results_path)
if _eval_threshold is not None and "ANOMALY_THRESHOLD" not in os.environ:
    settings.anomaly_threshold = _eval_threshold
