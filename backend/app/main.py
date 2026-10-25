"""FastAPI application entrypoint (Milestone 1).

Serves MOCK data only. No real security scanning is performed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import SessionLocal, init_db
from .routers import findings, health, projects, scans
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables, then optionally seed sample data for development.
    init_db()
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="AI Pentest Platform (Milestone 2)",
    version=__version__,
    description=(
        "Real scanning via modular adapters (Bandit, detect-secrets, pip-audit, "
        "and a safe passive dynamic scanner), run in isolated workers. Mock "
        "sample scans remain available for demonstration."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(scans.router)
app.include_router(findings.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "name": "AI Pentest Platform",
        "milestone": "M2",
        "mock_mode": settings.mock_mode,
        "message": "Real scanning (isolated workers) + mock samples. See /docs.",
    }
