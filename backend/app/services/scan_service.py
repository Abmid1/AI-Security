"""Launching scans from the API.

Mock scans complete immediately (sample data). Real scans are created as queued
jobs and executed by an isolated worker process, so the web server never runs a
scan itself. Tests can force inline execution.
"""

from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy.orm import Session

from .. import crud, models
from ..config import settings
from ..workers.runner import run_scan_job


def launch_scan(db: Session, project: models.Project, *, mode: str = "mock",
                scanners: list[str] | None = None,
                run_inline: bool | None = None) -> models.ScanJob:
    """Create and launch a scan. Returns the ScanJob (mock: completed;
    real: queued, running, or completed depending on execution mode)."""
    if mode == "mock":
        return crud.create_mock_scan(db, project)

    # Real scan: create a queued job first.
    job = models.ScanJob(
        project_id=project.id,
        status="queued",
        mode="real",
        is_mock=False,
        requested_scanners=scanners,
        coverage_note="Real scan queued.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    inline = run_inline if run_inline is not None else (settings.scan_execution == "inline")
    if inline:
        run_scan_job(db, job.id)
        db.refresh(job)
    else:
        _spawn_worker(job.id)
    return job


def _spawn_worker(job_id: str) -> None:
    """Spawn an isolated OS process to run the scan, decoupled from the server."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    kwargs: dict = {"cwd": backend_dir}
    # Detach so the worker outlives the request handler.
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, "-m", "app.workers.run_scan", job_id],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs,
    )
