"""Test fixtures.

Tests run against an in-memory SQLite database so they need no external
database. Seeding is disabled; each test controls its own data.
"""

from __future__ import annotations

import os

# Configure the app for testing BEFORE importing it.
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["SCAN_EXECUTION"] = "inline"  # run real scans in-process during tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    # A single shared in-memory connection for the test (StaticPool keeps it
    # alive across sessions within the test).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # Point the app's SessionLocal at this engine too (used by lifespan/crud
    # paths that build their own sessions).
    database.engine = engine
    database.SessionLocal = TestingSession

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
