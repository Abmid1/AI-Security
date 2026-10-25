"""Database operations (thin data-access layer).

Kept separate from the HTTP routers so the logic is easy to unit-test.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .mock_scanner import MOCK_COVERAGE_NOTE, generate_mock_findings


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
def list_projects(db: Session) -> list[models.Project]:
    return list(db.scalars(select(models.Project).order_by(models.Project.created_at.desc())))


def get_project(db: Session, project_id: str) -> models.Project | None:
    return db.get(models.Project, project_id)


def create_project(db: Session, *, name: str, kind: str, target_url: str | None,
                   repo_url: str | None, authorization_confirmed: bool,
                   authorization_note: str | None) -> models.Project:
    project = models.Project(
        name=name,
        kind=kind,
        target_url=target_url,
        repo_url=repo_url,
        authorization_confirmed=authorization_confirmed,
        authorization_note=authorization_note,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


# --------------------------------------------------------------------------- #
# Scan jobs
# --------------------------------------------------------------------------- #
def list_scans(db: Session, project_id: str | None = None) -> list[models.ScanJob]:
    stmt = select(models.ScanJob).order_by(models.ScanJob.created_at.desc())
    if project_id:
        stmt = stmt.where(models.ScanJob.project_id == project_id)
    return list(db.scalars(stmt))


def get_scan(db: Session, scan_id: str) -> models.ScanJob | None:
    return db.get(models.ScanJob, scan_id)


def create_mock_scan(db: Session, project: models.Project) -> models.ScanJob:
    """Create a completed MOCK scan with sample findings.

    This does not perform any scanning. It records a scan job and attaches the
    fixed sample findings from mock_scanner, so the rest of the app has data.
    """
    now = _now()
    scan = models.ScanJob(
        project_id=project.id,
        status="completed",
        is_mock=True,
        coverage_note=MOCK_COVERAGE_NOTE,
        started_at=now,
        finished_at=now,
    )
    db.add(scan)
    db.flush()  # assign scan.id before creating findings

    sample = generate_mock_findings(project_id=project.id, scan_job_id=scan.id)
    for f in sample:
        db.add(models.Finding(**f))
    scan.findings_count = len(sample)

    db.commit()
    db.refresh(scan)
    return scan


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
def list_findings(db: Session, *, scan_id: str | None = None,
                  project_id: str | None = None) -> list[models.Finding]:
    stmt = select(models.Finding).order_by(models.Finding.created_at.desc())
    if scan_id:
        stmt = stmt.where(models.Finding.scan_job_id == scan_id)
    if project_id:
        stmt = stmt.where(models.Finding.project_id == project_id)
    return list(db.scalars(stmt))


def get_finding(db: Session, finding_id: str) -> models.Finding | None:
    return db.get(models.Finding, finding_id)


def count_findings(db: Session) -> int:
    return len(list(db.scalars(select(models.Finding.id))))
