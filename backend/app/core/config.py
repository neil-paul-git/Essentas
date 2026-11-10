from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (and backend/.env if present)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Essentas API"
    app_version: str = "0.1.0"
    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: str

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Supabase hands out postgresql:// URLs, which SQLAlchemy maps to psycopg2.
        We install psycopg 3, so name that driver explicitly."""
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them. Tests override this via app.dependency_overrides."""
    return Settings()
