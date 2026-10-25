"""Database engine, session and base class.

Uses SQLAlchemy 2.0. Works on both SQLite (local dev / tests) and PostgreSQL
(set DATABASE_URL). The models in models.py avoid DB-specific column types so
the same code runs on both.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _make_engine(url: str):
    # SQLite needs a special flag when used across threads (FastAPI uses them).
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables if they do not exist.

    M1 uses create_all for simplicity. A real deployment uses versioned
    migrations (e.g. Alembic) run as a separate, least-privilege DB role
    (see platform-hardening spec section 3).
    """
    # Import models so they are registered on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
