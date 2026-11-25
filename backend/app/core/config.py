"""Typed application settings, loaded from environment variables (and the repo-root ``.env``).

A missing or invalid required setting raises ``pydantic.ValidationError`` when ``Settings()`` is
built, which happens when ``app.main`` is imported, so the API refuses to start.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.security import normalize_origin

# backend/app/core/config.py -> parents[3] is the repository root. Ignored if the file is absent
# (containers, CI), where the environment is the only source.
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

Environment = Literal["local", "ci", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _parse_origin(value: str) -> str:
    origin = normalize_origin(value)
    if origin is None:
        raise ValueError(
            f"{value!r} is not a bare origin; use scheme://host[:port] with http or https "
            "and no path, query or credentials"
        )
    return origin


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        # The shared .env also holds worker and GitHub App variables this model doesn't use yet.
        extra="ignore",
        frozen=True,
    )

    env: Environment = "local"
    # Public origin of the app (Caddy serves / and /api on it). Required: it drives the CSRF
    # Origin check (ADR-0007).
    site_origin: str
    # Extra origins accepted by the Origin check and CORS, only when env == "local" (frontend and
    # API on different ports). Comma-separated in the environment.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_level: LogLevel = "INFO"

    @field_validator("site_origin")
    @classmethod
    def _validate_site_origin(cls, value: str) -> str:
        return _parse_origin(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, value: list[str]) -> list[str]:
        return [_parse_origin(item) for item in value]

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _require_https_in_production(self) -> Self:
        if self.env == "production" and not self.site_origin.startswith("https://"):
            raise ValueError("SITE_ORIGIN must use https when ENV=production")
        return self

    @property
    def allowed_origins(self) -> frozenset[str]:
        """Origins accepted on unsafe requests: the site origin, plus CORS_ORIGINS in local dev."""
        if self.env == "local":
            return frozenset({self.site_origin, *self.cors_origins})
        return frozenset({self.site_origin})

    @property
    def cors_enabled(self) -> bool:
        return self.env == "local" and bool(self.cors_origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
