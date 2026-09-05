"""Application settings, loaded from the environment and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden by an environment variable of the same name
    (case-insensitively), which takes precedence over ``.env``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "rentals-api"
    environment: Literal["local", "test", "staging", "prod"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "app"
    postgres_password: SecretStr = SecretStr("app")
    postgres_db: str = "app"

    @property
    def sqlalchemy_url(self) -> URL:
        """Build the database URL.

        A plain ``@property``, deliberately not ``@computed_field``: Pydantic
        cannot generate a core schema for ``sqlalchemy.engine.URL`` and would
        raise at class-construction time. A plain property is invisible to
        Pydantic, which is exactly what we want.

        ``URL.create`` is used rather than an f-string because it handles
        special characters correctly -- note the password must NOT be
        percent-encoded here. An f-string DSN breaks the first time a password
        contains ``@``, ``/`` or ``#``, and it breaks in production, not
        locally.
        """
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that importing modules and FastAPI dependencies share one
    instance. Tests that need different values can call
    ``get_settings.cache_clear()`` after monkeypatching the environment, or
    override the ``SettingsDep`` dependency.
    """
    return Settings()
