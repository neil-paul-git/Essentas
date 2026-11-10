from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (and backend/.env if present)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Essentas API"
    app_version: str = "0.1.0"
    environment: Literal["dev", "test", "prod"] = "dev"


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them. Tests override this via app.dependency_overrides."""
    return Settings()
