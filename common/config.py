"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config. Built once at the composition root, then injected."""

    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    request_id_header: str = "X-Request-ID"

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/interview_intelligence"
    )

    # --- AWS ---
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    sqs_queue_url: str = ""
    sqs_max_messages: int = 10
    sqs_wait_time_seconds: int = 20
    sqs_visibility_timeout: int = 300
    sqs_poll_error_backoff_seconds: float = 5.0

    # --- Inngest ---
    inngest_dev: bool = True
    inngest_event_key: str = "local"
    inngest_signing_key: str | None = None
    inngest_api_base_url: str | None = None
    inngest_event_api_base_url: str | None = None
    inngest_serve_origin: str | None = None

    # --- DeepSeek ---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 120.0
    deepseek_max_retries: int = 3
    deepseek_max_tokens: int = 8192
    deepseek_rpm: int = 60

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor for entrypoints that are not wired via DI."""
    return Settings()
