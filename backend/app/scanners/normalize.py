"""Normalization: turn adapter RawFindings into canonical finding dicts.

Responsibilities (all deterministic, no AI):
- Validate and sanitize file paths (reject traversal / absolute escapes).
- Redact secret material so it is never written to the database or reports.
- Assign a stable fingerprint and deduplicate across all scanners.
- Apply each adapter's default status / evidence basis where not set.

The output dict matches the columns of models.Finding (minus ids, which the
worker fills in).
"""

from __future__ import annotations

import hashlib
import os
import re

from .base import RawFinding, ScannerAdapter

_ALLOWED_SEVERITY = {"critical", "high", "medium", "low", "info"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def sanitize_relative_path(root: str, path: str) -> str | None:
    """Return a safe repo-relative path, or None if the path escapes root.

    Protects against path traversal (../), absolute paths and symlinked escapes
    that would otherwise point outside the scanned workspace.
    """
    if not path:
        return None
    try:
        root_abs = os.path.realpath(root)
        # Treat the given path as relative to root unless already absolute.
        candidate = path if os.path.isabs(path) else os.path.join(root, path)
        candidate_abs = os.path.realpath(candidate)
    except (OSError, ValueError):
        return None
    # Must stay inside root.
    if candidate_abs != root_abs and not candidate_abs.startswith(root_abs + os.sep):
        return None
    rel = os.path.relpath(candidate_abs, root_abs)
    # Normalize to forward slashes for stable, portable display.
    return rel.replace(os.sep, "/")


# Patterns of common secret shapes, used only to produce a redacted preview.
_SECRET_HINT = re.compile(r"[A-Za-z0-9_\-+/=]{6,}")


def redact_secret(raw: str | None) -> str:
    """Return a safe, non-reversible preview of a secret.

    Keeps a short prefix for recognizability and masks the rest. The full secret
    is never returned or stored.
    """
    if not raw:
        return "<redacted>"
    raw = raw.strip()
    if len(raw) <= 4:
        return "*" * len(raw)
    prefix = raw[:4]
    return f"{prefix}{'*' * min(len(raw) - 4, 16)}"


def _clamp(value: str, allowed: set[str], fallback: str) -> str:
    v = (value or "").lower()
    return v if v in allowed else fallback


def fingerprint(vuln_class: str, location: str | None, title: str) -> str:
    """Stable key for deduplication across scanners."""
    basis = f"{vuln_class}|{location or ''}|{title}".lower()
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def normalize_findings(
    adapter: ScannerAdapter,
    raw_findings: list[RawFinding],
    *,
    workspace_root: str | None,
) -> tuple[list[dict], int]:
    """Normalize one adapter's findings into canonical dicts.

    Path validation uses workspace_root for file-based scanners. Findings whose
    location escapes the workspace are dropped and counted. Returns
    (normalized, rejected_for_unsafe_path).
    """
    out: list[dict] = []
    rejected = 0
    for rf in raw_findings:
        location = rf.location

        # For file-based scanners, validate the path against the workspace.
        if workspace_root and location and adapter.category.value in {"sast", "secrets"}:
            safe = sanitize_relative_path(workspace_root, location.split(":")[0])
            if safe is None:
                # Unsafe path -> drop this finding rather than store a bad path.
                rejected += 1
                continue
            # Preserve any trailing :line info.
            suffix = location[len(location.split(":")[0]):]
            location = safe + suffix

        evidence = dict(rf.evidence or {})

        # Redact any secret material before it is stored.
        if rf._raw_secret is not None:
            evidence["redacted_match"] = redact_secret(rf._raw_secret)
            evidence.pop("secret", None)
            evidence.pop("raw", None)

        out.append(
            {
                "title": rf.title,
                "vuln_class": rf.vuln_class,
                "severity": _clamp(rf.severity, _ALLOWED_SEVERITY, "info"),
                "confidence": _clamp(rf.confidence, _ALLOWED_CONFIDENCE, "low"),
                "status": rf.status or adapter.default_status,
                "evidence_basis": rf.evidence_basis or adapter.default_evidence_basis,
                "location": location,
                "description": rf.description,
                "evidence": evidence,
                "is_mock": False,
                "scanner": adapter.name,
                "fingerprint": fingerprint(rf.vuln_class, location, rf.title),
            }
        )
    return out, rejected


def deduplicate(findings: list[dict]) -> tuple[list[dict], int]:
    """Remove duplicate findings by fingerprint. Returns (unique, removed_count).

    When two scanners report the same issue, we keep the first and merge the
    other scanner's name into evidence so provenance is not lost.
    """
    seen: dict[str, dict] = {}
    removed = 0
    for f in findings:
        fp = f["fingerprint"]
        if fp in seen:
            removed += 1
            existing = seen[fp]
            also = existing["evidence"].setdefault("also_reported_by", [])
            if f["scanner"] not in also and f["scanner"] != existing["scanner"]:
                also.append(f["scanner"])
        else:
            seen[fp] = f
    return list(seen.values()), removed
