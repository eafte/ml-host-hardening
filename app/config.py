"""Application configuration, loaded exclusively from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated, immutable application settings.

    Every value comes from a ``MLAPI_``-prefixed environment variable.
    A local ``.env`` file is read for development only; real environment
    variables always take precedence over it.
    """

    # frozen: settings cannot be mutated after startup.
    # extra="ignore": unrelated variables in the environment do not break startup.
    model_config = SettingsConfigDict(
        env_prefix="MLAPI_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "ml-inference-api"
    environment: Literal["development", "production"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Model parameters have no defaults: the service must refuse to start
    # rather than silently serve predictions from an unintended model.
    model_weights: list[float] = Field(min_length=1)
    model_bias: float


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once on first use."""
    return Settings()
