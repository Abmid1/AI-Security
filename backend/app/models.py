"""PostgreSQL / SQLAlchemy models for Milestone 1.

Three tables: projects, scan jobs, findings. Column types are deliberately
portable (String / DateTime / JSON) so the same models run on SQLite locally
and PostgreSQL in production.

Status/severity/etc. are stored as plain strings; their allowed values are
validated at the API boundary by the Pydantic enums in schemas.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """An authorized scan target: either a web application or a code repository."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # "web" or "repo". Validated by ProjectKind enum at the API layer.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # No scan may run without explicit authorization. In M1 this is a simple
    # confirmation flag; later milestones strengthen it (ownership proof, etc.).
    authorization_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    authorization_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    scan_jobs: Mapped[list["ScanJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ScanJob(Base):
    """A single scan run against a project.

    In Milestone 1 every scan is a MOCK scan: is_mock is always True and the
    findings are generated sample data, not real scan results.
    """

    __tablename__ = "scan_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")

    # "mock" (sample data) or "real" (actual scanner tools). Added in M2.
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="mock")

    # True for mock scans. For real scans this is False.
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Short human-readable note about what was and was not covered.
    coverage_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Scanners requested (names) and the structured coverage report:
    # per-scanner status, errors, skipped areas, dedup count. (M2)
    requested_scanners: Mapped[list | None] = mapped_column(SA_JSON, nullable=True)
    coverage: Mapped[dict | None] = mapped_column(SA_JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Denormalised counts for quick dashboard display.
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped["Project"] = relationship(back_populates="scan_jobs")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan_job", cascade="all, delete-orphan"
    )


class Finding(Base):
    """A single vulnerability finding produced by a scan.

    Fields mirror the verification design: a verdict-style status, a confidence,
    and an evidence basis that distinguishes AI-reviewed from reproduced results.
    """

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    scan_job_id: Mapped[str] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    vuln_class: Mapped[str] = mapped_column(String(80), nullable=False)

    # critical | high | medium | low | info
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    # high | medium | low
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    # candidate | confirmed | disproven | inconclusive | untested
    #   | verification_failed
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    # How we "know": AI_REVIEWED | DYNAMIC_REPRODUCED | STATIC_CONFIRMED
    #   | DEPENDENCY_MATCH | CONFIG_OBSERVED | SECRET_MATCH
    evidence_basis: Mapped[str] = mapped_column(String(32), nullable=False)

    location: Mapped[str | None] = mapped_column(String(600), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Structured, redacted evidence bundle.
    evidence: Mapped[dict | None] = mapped_column(SA_JSON, nullable=True)

    # Which scanner produced this, and a dedup fingerprint. (M2)
    scanner: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    scan_job: Mapped["ScanJob"] = relationship(back_populates="findings")
    project: Mapped["Project"] = relationship(back_populates="findings")
