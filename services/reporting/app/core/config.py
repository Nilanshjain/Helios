"""Configuration management for reporting service"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Report Generator
    report_generator_mode: str = "mock"  # 'claude' or 'mock'
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_max_tokens: int = 1500
    claude_temperature: float = 0.3
    claude_max_retries: int = 3

    # Kafka
    kafka_brokers: str = "localhost:9092"
    kafka_alerts_topic: str = "anomaly-alerts"
    kafka_consumer_group: str = "report-generators"

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "helios"
    db_user: str = "postgres"
    db_password: str = "postgres"

    # Storage
    reports_storage_path: str = "./reports"
    reports_retention_days: int = 30

    # Slack
    slack_webhook_url: str = ""
    slack_enabled: bool = False
    slack_channel: str = "#incidents"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8002
    log_level: str = "INFO"
    metrics_port: int = 8003

    # Context
    context_window_minutes: int = 10
    max_context_events: int = 100
    include_metrics: bool = True
    include_recent_deployments: bool = False

    @property
    def kafka_brokers_list(self) -> List[str]:
        """Parse Kafka brokers"""
        return [b.strip() for b in self.kafka_brokers.split(",")]

    @property
    def database_url(self) -> str:
        """Construct database URL"""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def use_claude(self) -> bool:
        """Check if Claude should be used"""
        return self.report_generator_mode == "claude" and bool(self.anthropic_api_key)


# Global settings instance
settings = Settings()
