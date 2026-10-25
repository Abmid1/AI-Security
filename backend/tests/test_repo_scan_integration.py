"""Integration test: run the real scanner pipeline against a temp workspace.

This actually invokes Bandit and detect-secrets (both offline). pip-audit needs
network, so we only assert it is accounted for in coverage (completed OR error),
never that it silently passed.
"""

import os
import tempfile

import pytest

from app import models
from app.scanners.base import ScanLimits
from app.workers.runner import run_scan_job


VULN_PY = '''\
import subprocess

def run(cmd):
    # Insecure: shell=True with external input (Bandit B602).
    subprocess.Popen(cmd, shell=True)

password = "hardcoded_secret_123"          # Bandit B105 hardcoded password
aws_key = "AKIAIOSFODNN7EXAMPLE"            # detect-secrets AWS key pattern
'''


@pytest.fixture()
def workspace():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "vuln.py"), "w", encoding="utf-8") as f:
            f.write(VULN_PY)
        with open(os.path.join(d, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("requests==2.19.0\n")
        yield d


def _make_repo_job(db, workspace_path):
    project = models.Project(
        name="Integration Repo", kind="repo", repo_url=workspace_path,
        authorization_confirmed=True,
    )
    db.add(project)
    db.flush()
    job = models.ScanJob(project_id=project.id, status="queued", mode="real", is_mock=False)
    db.add(job)
    db.commit()
    return job


def test_real_repo_scan_produces_normalized_findings(db_session, workspace):
    job = _make_repo_job(db_session, workspace)
    run_scan_job(db_session, job.id, limits=ScanLimits(timeout_seconds=120))

    db_session.refresh(job)
    assert job.status == "completed"
    assert job.is_mock is False
    assert job.mode == "real"

    findings = db_session.query(models.Finding).filter_by(scan_job_id=job.id).all()
    classes = {f.vuln_class for f in findings}
    scanners = {f.scanner for f in findings}

    # Bandit should flag the insecure code; detect-secrets the exposed secret.
    assert "bandit" in scanners
    assert "detect-secrets" in scanners
    assert "exposed_secret" in classes

    # Every real finding is non-mock, carries a fingerprint, and (for secrets)
    # stores no raw secret value.
    for f in findings:
        assert f.is_mock is False
        assert f.fingerprint
        assert "AKIAIOSFODNN7EXAMPLE" not in str(f.evidence)

    # Coverage is recorded honestly, including pip-audit's outcome.
    cov = job.coverage
    assert cov is not None
    names = {s["name"]: s["status"] for s in cov["scanners"]}
    assert names.get("bandit") == "completed"
    assert names.get("detect-secrets") == "completed"
    # pip-audit either completed (network) or errored (offline) — but is present.
    assert "pip-audit" in names
    assert names["pip-audit"] in {"completed", "error", "skipped"}


def test_dynamic_skipped_for_unauthorized_web_project(db_session):
    project = models.Project(
        name="Unauth Web", kind="web", target_url="https://staging.example.com",
        authorization_confirmed=False,
    )
    # Bypass the API's create-time authorization check to test the worker gate
    # directly: an unauthorized project must never be dynamically scanned.
    db_session.add(project)
    db_session.flush()
    job = models.ScanJob(project_id=project.id, status="queued", mode="real", is_mock=False)
    db_session.add(job)
    db_session.commit()

    run_scan_job(db_session, job.id)
    db_session.refresh(job)

    assert job.status == "completed"
    assert job.findings_count == 0
    names = {s["name"]: s["status"] for s in job.coverage["scanners"]}
    assert names.get("dynamic-safe") == "skipped"
