"""Application configuration.

Everything sensitive comes from server-side environment variables (see the
platform-hardening spec, section 4). This file reads env vars and provides
safe defaults for local development only.
"""

from __future__ import annotations

import os


class Settings:
    """Runtime settings, read from environment variables.

    For local development with zero setup we default to a local SQLite file.
    For a PostgreSQL-backed run (recommended, and what production uses), set
    DATABASE_URL, e.g.:
        postgresql+psycopg://user:password@localhost:5432/aipentest
    """

    def __init__(self) -> None:
        # Default to SQLite so a beginner can start with no database to install.
        # The models are written to work on PostgreSQL too (just set DATABASE_URL).
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

        # Comma-separated list of allowed frontend origins (CORS).
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ]

        # Whether to insert sample/mock data on startup when the DB is empty.
        self.seed_on_startup: bool = _env_bool("SEED_ON_STARTUP", True)

        # A flag the whole app honours: in M1 real scanning does not exist.
        self.mock_mode: bool = True


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()
