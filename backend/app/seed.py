"""Seed sample/mock data for local development.

Only runs when the database has no projects yet. All data is clearly mock.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crud, models


def seed_if_empty(db: Session) -> bool:
    """Insert sample data if there are no projects. Returns True if it seeded."""
    existing = db.scalar(select(models.Project.id).limit(1))
    if existing is not None:
        return False

    # Sample web target (authorized — a well-known intentionally-vulnerable app
    # people run locally for practice).
    web = crud.create_project(
        db,
        name="Demo Web Target (Juice Shop - local)",
        kind="web",
        target_url="http://localhost:3000",
        repo_url=None,
        authorization_confirmed=True,
        authorization_note="Local, self-hosted practice target. Owned by me.",
    )

    # Sample repository project.
    repo = crud.create_project(
        db,
        name="Demo Repository",
        kind="repo",
        target_url=None,
        repo_url="https://example.com/my-org/my-app.git",
        authorization_confirmed=True,
        authorization_note="My own repository.",
    )

    # Give each project one completed mock scan with sample findings.
    crud.create_mock_scan(db, web)
    crud.create_mock_scan(db, repo)
    return True
