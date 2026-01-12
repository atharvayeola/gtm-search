"""
GTM Engine Configuration

Centralized configuration using Pydantic Settings with environment variable support.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Infrastructure
    # =========================================================================
    postgres_url: str = Field(
        default="postgresql://gtm:gtm_password@localhost:5432/gtm_engine",
        description="PostgreSQL connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery broker",
    )

    # MinIO / S3
    s3_endpoint: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="gtm-raw")

    # =========================================================================
    # LLM Configuration
    # =========================================================================
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama HTTP API base URL",
    )
    tier1_provider: Literal["ollama", "openai"] = Field(
        default="ollama",
        description="Provider for Tier 1 extraction (ollama or openai)",
    )
    tier1_model_name: str = Field(
        default="llama3",
        description="Model name for Tier 1 local extraction",
    )
    tier2_provider: Literal["openai", "anthropic", "disabled"] = Field(
        default="disabled",
        description="Tier 2 LLM provider (disabled for MVP by default)",
    )
    openai_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)

    # =========================================================================
    # Pipeline Configuration
    # =========================================================================
    target_job_count: int = Field(
        default=50000,
        description="Target number of unique job postings to ingest",
    )
    tier1_batch_size: int = Field(
        default=20,
        description="Number of jobs per Tier 1 LLM batch",
    )

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    greenhouse_max_concurrent: int = Field(
        default=5,
        description="Max concurrent requests to boards-api.greenhouse.io",
    )
    lever_max_concurrent: int = Field(
        default=5,
        description="Max concurrent requests to api.lever.co",
    )
    max_retries: int = Field(default=5)
    retry_backoff_base: int = Field(default=2, description="Base seconds for exponential backoff")

    # =========================================================================
    # Application
    # =========================================================================
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    @property
    def tier2_enabled(self) -> bool:
        """Check if Tier 2 extraction is enabled and has valid credentials."""
        if self.tier2_provider == "disabled":
            return False
        if self.tier2_provider == "openai" and self.openai_api_key:
            return True
        if self.tier2_provider == "anthropic" and self.anthropic_api_key:
            return True
        return False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
