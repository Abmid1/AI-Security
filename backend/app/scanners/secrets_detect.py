"""Secret-detection adapter: detect-secrets (Yelp).

detect-secrets reports the *type*, *file* and *line* of a potential secret and
a one-way hash of the value — it does not emit the raw secret. We store only the
type, location and a masked hash reference, so no secret material is ever written
to the database or reports.
"""

from __future__ import annotations

import importlib.util
import json
import os

from ._proc import run_module
from .base import (
    OutcomeStatus,
    RawFinding,
    ScanLimits,
    ScannerAdapter,
    ScannerCategory,
    ScannerOutcome,
)


class DetectSecretsAdapter(ScannerAdapter):
    name = "detect-secrets"
    category = ScannerCategory.secrets
    default_evidence_basis = "SECRET_MATCH"
    default_status = "candidate"

    def is_available(self) -> tuple[bool, str | None]:
        if importlib.util.find_spec("detect_secrets") is None:
            return False, "detect-secrets is not installed"
        return True, None

    def applies_to(self, target) -> bool:
        return target.kind == "repo" and bool(target.workspace_path)

    def scan(self, target, limits: ScanLimits) -> ScannerOutcome:
        available, reason = self.is_available()
        if not available:
            return ScannerOutcome.skipped(self.name, self.category.value, reason or "unavailable")
        if not target.workspace_path:
            return ScannerOutcome.skipped(self.name, self.category.value, "no workspace path")

        # detect-secrets only scans git-tracked files when given a directory, so
        # we enumerate candidate files ourselves and pass them explicitly. This
        # works regardless of whether the workspace is a git repository.
        files, skipped_dirs = _collect_files(target.workspace_path, limits.max_findings)
        if not files:
            outcome = ScannerOutcome(scanner=self.name, category=self.category.value,
                                     status=OutcomeStatus.completed)
            outcome.skipped_areas.extend(skipped_dirs)
            return outcome

        merged: dict = {"results": {}}
        for batch in _batches(files, 150):
            res = run_module(["detect_secrets", "scan", *batch],
                             cwd=target.workspace_path, timeout=limits.timeout_seconds)
            if res.error:
                return ScannerOutcome.errored(self.name, self.category.value, res.error)
            try:
                data = json.loads(res.stdout or "{}")
            except json.JSONDecodeError:
                return ScannerOutcome.errored(
                    self.name, self.category.value,
                    "could not parse detect-secrets JSON output",
                )
            merged["results"].update(data.get("results", {}))

        outcome = self._parse(merged)
        outcome.skipped_areas.extend(skipped_dirs)
        return outcome

    def _parse(self, data: dict) -> ScannerOutcome:
        outcome = ScannerOutcome(
            scanner=self.name,
            category=self.category.value,
            status=OutcomeStatus.completed,
        )
        results = data.get("results", {})
        for filename, items in results.items():
            filename = filename.replace("\\", "/")
            for item in items:
                line = item.get("line_number")
                secret_type = item.get("type", "secret")
                hashed = item.get("hashed_secret", "")
                location = f"{filename}:{line}" if line else filename
                outcome.findings.append(
                    RawFinding(
                        title=f"Potential exposed secret: {secret_type}",
                        vuln_class="exposed_secret",
                        severity="high",
                        confidence="medium",  # may be placeholder/example
                        location=location,
                        description=(
                            f"A potential {secret_type} was detected. Validity "
                            "not verified; may be a placeholder or test fixture."
                        ),
                        evidence={
                            "tool": "detect-secrets",
                            "secret_type": secret_type,
                            # Masked reference to the one-way hash. Never the secret.
                            "hashed_ref": (hashed[:8] + "…") if hashed else None,
                            "is_verified": item.get("is_verified", False),
                        },
                    )
                )
        return outcome


# Directories and file types we never scan for secrets.
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
              "dist", "build", ".next", ".idea", ".mypy_cache"}
_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
             ".tar", ".exe", ".dll", ".so", ".woff", ".woff2", ".ttf", ".mp4"}
_MAX_BYTES = 1_000_000  # skip files larger than ~1MB


def _collect_files(root: str, cap: int) -> tuple[list[str], list[str]]:
    """Return (relative file paths to scan, skipped-area notes)."""
    files: list[str] = []
    skipped: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        pruned = [d for d in dirnames if d in _SKIP_DIRS]
        for d in pruned:
            skipped.append(f"secret scan skipped directory: {d}")
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            full = os.path.join(dirpath, name)
            if ext in _SKIP_EXT:
                continue
            try:
                if os.path.getsize(full) > _MAX_BYTES:
                    skipped.append(f"secret scan skipped large file: {name}")
                    continue
            except OSError:
                continue
            files.append(os.path.relpath(full, root).replace(os.sep, "/"))
            if len(files) >= cap:
                skipped.append("secret scan file cap reached; some files not scanned")
                return files, skipped
    return files, skipped


def _batches(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]
