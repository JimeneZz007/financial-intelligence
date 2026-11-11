"""Application settings loaded from the environment (.env in development)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_db: str = "financial_intelligence"
    postgres_test_db: str = "financial_intelligence_test"
    postgres_user: str = "fi_app"
    postgres_password: SecretStr = SecretStr("")

    api_cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    def database_url(self, database: str | None = None) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=database or self.postgres_db,
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
