"""Subprocess entrypoint for running a scan OUTSIDE the web server.

Usage (spawned by the API, not run by hand):
    python -m app.workers.run_scan <job_id>

It opens its own database session so it is fully decoupled from the FastAPI
process.
"""

from __future__ import annotations

import sys

from ..database import SessionLocal
from .runner import run_scan_job


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m app.workers.run_scan <job_id>", file=sys.stderr)
        return 2
    job_id = argv[0]
    db = SessionLocal()
    try:
        job = run_scan_job(db, job_id)
        print(f"scan {job_id} finished with status={job.status} findings={job.findings_count}")
        return 0 if job.status == "completed" else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
