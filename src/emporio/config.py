"""Typed application configuration loaded from environment variables or `.env`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class MissingConfigurationError(RuntimeError):
    """Raised when a command requires configuration that was not supplied."""


class Settings(BaseSettings):
    """Runtime settings with safe defaults for every non-secret value."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    model: str = Field(default="openai:gpt-4o-mini", validation_alias="MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL"
    )
    reference_date: date | None = Field(default=None, validation_alias="REFERENCE_DATE")
    database_path: Path = PROJECT_ROOT / "emporio.db"
    chroma_path: Path = PROJECT_ROOT / "chroma"

    def require_openai_api_key(self) -> str:
        """Return the configured key or raise an actionable error."""

        if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
            raise MissingConfigurationError(
                "OPENAI_API_KEY is required. Copy .env.example to .env and add your key."
            )
        return self.openai_api_key.get_secret_value()


def get_settings(**overrides: object) -> Settings:
    """Create settings, allowing tests and scripts to override individual values."""

    return Settings(**overrides)
