"""Health-check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import settings
from ..database import get_db
from ..schemas import DbHealthOut, HealthOut

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
def health() -> HealthOut:
    """Liveness: is the API process up?"""
    return HealthOut(status="ok", version=__version__, mock_mode=settings.mock_mode)


@router.get("/db", response_model=DbHealthOut)
def health_db(db: Session = Depends(get_db)) -> DbHealthOut:
    """Readiness: can the API reach the database?"""
    try:
        db.execute(text("SELECT 1"))
        return DbHealthOut(status="ok", database="reachable")
    except Exception:  # pragma: no cover - defensive
        return DbHealthOut(status="error", database="unreachable")
