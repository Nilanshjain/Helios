"""Configuration management using Pydantic Settings"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

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
