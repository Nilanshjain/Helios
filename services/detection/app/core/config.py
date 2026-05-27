"""Configuration management using Pydantic Settings.

Threshold sourcing — note for readers:
The production anomaly threshold is **not** sourced from this file. It is
saved inside the trained-model pickle (``models/isolation_forest.pkl``) by
``scripts/train_production.py``, which derives it via an F1 sweep on the
validation split of the labeled telemetry the model was trained on.
``AnomalyDetector.load()`` restores that pkl-stored threshold at startup.

The ``models/evaluation/results.json`` file written by ``scripts/evaluate.py``
holds thresholds for the **NAB/SMD benchmark evaluation models** — those
models are trained on different data, so applying their thresholds to the
production model would be wrong. The eval thresholds are for reporting
benchmark F1 numbers; the production threshold belongs to the pkl.

If you need to override at runtime (e.g., A/B testing), set the
``ANOMALY_THRESHOLD`` env var and update ``AnomalyDetector.load()`` to
respect it explicitly.
"""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    contamination: float = 0.05
    # Class default — overridden by the pkl's stored threshold via
    # AnomalyDetector.load(). ANOMALY_THRESHOLD env var can override at
    # runtime if you need an explicit operating-point change.
    anomaly_threshold: float = -0.5
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


# Global settings instance. Threshold is *not* overridden from results.json
# here — see module docstring for why; the pkl is the source of truth.
settings = Settings()
