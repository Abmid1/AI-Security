"""The scan runner: orchestrates adapters and persists normalized findings.

run_scan_job is the single entry point. It is driven either in-process (tests)
or from the subprocess entrypoint in run_scan.py (production). It never trusts
scanner output: paths are validated, secrets redacted, duplicates removed, and
every skipped/errored area is recorded so coverage is honest.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..scanners.base import OutcomeStatus, ScanLimits, ScanTarget
from ..scanners.normalize import deduplicate, normalize_findings
from ..scanners.registry import ScannerRegistry, default_registry
from ..scanners.scope import _is_private_or_loopback, origin_of  # noqa: F401
from .workspace import prepare_repo_workspace


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_target(project: models.Project, workspace_path: str | None) -> ScanTarget:
    allowed_origin = origin_of(project.target_url) if project.target_url else None
    allow_private = False
    if project.target_url:
        from urllib.parse import urlsplit
        host = urlsplit(project.target_url).hostname or ""
        allow_private = _is_private_or_loopback(host)
    return ScanTarget(
        project_id=project.id,
        kind=project.kind,
        workspace_path=workspace_path,
        base_url=project.target_url,
        authorized=bool(project.authorization_confirmed),
        authorization_note=project.authorization_note,
        allowed_origin=allowed_origin,
        allow_private_hosts=allow_private,
    )


def run_scan_job(db: Session, job_id: str,
                 registry: ScannerRegistry | None = None,
                 limits: ScanLimits | None = None) -> models.ScanJob:
    """Execute a real scan job. Updates and returns the ScanJob."""
    registry = registry or default_registry()
    limits = limits or ScanLimits()

    job = db.get(models.ScanJob, job_id)
    if job is None:
        raise ValueError(f"scan job {job_id} not found")
    project = db.get(models.Project, job.project_id)
    if project is None:
        _fail(db, job, "project no longer exists")
        return job

    job.status = "running"
    job.started_at = _now()
    db.commit()

    workspace = None
    scanner_reports: list[dict] = []
    all_normalized: list[dict] = []
    agg_errors: list[str] = []
    agg_skipped: list[str] = []
    rejected_paths = 0

    try:
        workspace_path = None
        if project.kind == "repo":
            workspace = prepare_repo_workspace(project.repo_url, timeout=limits.timeout_seconds)
            workspace_path = workspace.path
            if workspace.error:
                agg_errors.append(f"workspace: {workspace.error}")
                agg_skipped.append(f"source/dependency/secret scans: {workspace.error}")

        target = _build_target(project, workspace_path)
        adapters = registry.applicable(target, requested=job.requested_scanners or None)

        if not adapters:
            agg_skipped.append("no applicable scanners for this target")

        for adapter in adapters:
            # Worker-level authorization gate for dynamic scanners (defense in depth).
            if adapter.requires_dynamic_authorization and not target.authorized:
                scanner_reports.append(_report(adapter, OutcomeStatus.skipped.value,
                                                reason="target not authorized for dynamic testing"))
                agg_skipped.append(f"{adapter.name}: target not authorized")
                continue

            # A repo scanner with no workspace path cannot run.
            if adapter.category.value in {"sast", "sca", "secrets"} and not workspace_path:
                scanner_reports.append(_report(adapter, OutcomeStatus.skipped.value,
                                                reason="no workspace available"))
                agg_skipped.append(f"{adapter.name}: no workspace available")
                continue

            try:
                outcome = adapter.scan(target, limits)
            except Exception as exc:  # unexpected adapter bug -> error outcome
                scanner_reports.append(_report(adapter, OutcomeStatus.error.value,
                                                reason=f"{type(exc).__name__}: {exc}"))
                agg_errors.append(f"{adapter.name}: {type(exc).__name__}: {exc}")
                continue

            normalized, rejected = normalize_findings(
                adapter, outcome.findings, workspace_root=workspace_path,
            )
            rejected_paths += rejected
            all_normalized.extend(normalized)
            agg_errors.extend(f"{adapter.name}: {e}" for e in outcome.errors)
            agg_skipped.extend(outcome.skipped_areas)

            report = _report(adapter, outcome.status.value, reason=outcome.reason)
            report["findings"] = len(normalized)
            report["errors"] = outcome.errors
            report["skipped_areas"] = outcome.skipped_areas
            if rejected:
                report["findings_rejected_unsafe_path"] = rejected
            scanner_reports.append(report)

        # Deduplicate across all scanners.
        unique, removed = deduplicate(all_normalized)

        # Persist findings.
        for f in unique:
            db.add(models.Finding(
                scan_job_id=job.id,
                project_id=project.id,
                title=f["title"],
                vuln_class=f["vuln_class"],
                severity=f["severity"],
                confidence=f["confidence"],
                status=f["status"],
                evidence_basis=f["evidence_basis"],
                location=f["location"],
                description=f["description"],
                evidence=f["evidence"],
                scanner=f["scanner"],
                fingerprint=f["fingerprint"],
                is_mock=False,
            ))

        job.status = "completed"
        job.mode = "real"
        job.is_mock = False
        job.findings_count = len(unique)
        job.coverage = {
            "scanners": scanner_reports,
            "errors": agg_errors,
            "skipped_areas": agg_skipped,
            "duplicates_removed": removed,
            "findings_rejected_unsafe_path": rejected_paths,
            "total_findings": len(unique),
            "workspace_note": workspace.note if workspace else None,
        }
        job.coverage_note = _summary_note(scanner_reports, agg_skipped, agg_errors)
        job.finished_at = _now()
        db.commit()
    except Exception as exc:  # pragma: no cover - top-level safety net
        _fail(db, job, f"unexpected worker error: {type(exc).__name__}: {exc}")
    finally:
        if workspace is not None:
            workspace.cleanup()

    db.refresh(job)
    return job


def _report(adapter, status: str, reason: str | None = None) -> dict:
    return {
        "name": adapter.name,
        "category": adapter.category.value,
        "status": status,
        "reason": reason,
    }


def _summary_note(reports: list[dict], skipped: list[str], errors: list[str]) -> str:
    ran = sum(1 for r in reports if r["status"] == "completed")
    sk = sum(1 for r in reports if r["status"] == "skipped")
    er = sum(1 for r in reports if r["status"] == "error")
    note = f"Real scan. {ran} scanner(s) ran, {sk} skipped, {er} errored."
    if skipped:
        note += f" Skipped areas: {len(skipped)}."
    if errors:
        note += f" Errors: {len(errors)}."
    return note


def _fail(db: Session, job: models.ScanJob, reason: str) -> None:
    job.status = "failed"
    job.error = reason
    job.finished_at = _now()
    db.commit()
