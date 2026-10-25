"""Dependency vulnerability adapter: pip-audit.

pip-audit checks Python dependencies against known-vulnerability advisories.

Runtime note: pip-audit queries an online advisory database. When there is no
network (or the service is unreachable) the adapter records an error outcome
rather than claiming the dependencies are clean — absence of a result is never
reported as "no vulnerabilities".

Scope note: this covers Python manifests (requirements*.txt). Other ecosystems
(npm, etc.) are separate adapters, not yet integrated (see docs).
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

_MANIFEST_NAMES = ("requirements.txt", "requirements-dev.txt", "requirements.in")


class PipAuditAdapter(ScannerAdapter):
    name = "pip-audit"
    category = ScannerCategory.sca
    default_evidence_basis = "DEPENDENCY_MATCH"
    # Presence of a known-vulnerable version is confirmed; exploitability is not.
    default_status = "confirmed"

    def is_available(self) -> tuple[bool, str | None]:
        if importlib.util.find_spec("pip_audit") is None:
            return False, "pip-audit is not installed"
        return True, None

    def applies_to(self, target) -> bool:
        return target.kind == "repo" and bool(target.workspace_path)

    def _find_manifest(self, root: str) -> str | None:
        for name in _MANIFEST_NAMES:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        return None

    def scan(self, target, limits: ScanLimits) -> ScannerOutcome:
        available, reason = self.is_available()
        if not available:
            return ScannerOutcome.skipped(self.name, self.category.value, reason or "unavailable")
        if not target.workspace_path:
            return ScannerOutcome.skipped(self.name, self.category.value, "no workspace path")

        manifest = self._find_manifest(target.workspace_path)
        if not manifest:
            return ScannerOutcome.skipped(
                self.name, self.category.value,
                "no Python dependency manifest (requirements*.txt) found",
            )

        res = run_module(
            ["pip_audit", "-r", manifest, "-f", "json", "--progress-spinner", "off"],
            timeout=limits.timeout_seconds,
        )
        if res.error:
            return ScannerOutcome.errored(self.name, self.category.value, res.error)
        # pip-audit exits non-zero when vulns are found; parse stdout regardless.
        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            # Likely a network/advisory-DB failure; record honestly as an error.
            detail = (res.stderr or "").strip()[:300] or "no parseable output"
            return ScannerOutcome.errored(
                self.name, self.category.value,
                f"pip-audit produced no JSON (often a network issue): {detail}",
            )
        return self._parse(data, manifest_rel=os.path.basename(manifest))

    def _parse(self, data, *, manifest_rel: str) -> ScannerOutcome:
        outcome = ScannerOutcome(
            scanner=self.name,
            category=self.category.value,
            status=OutcomeStatus.completed,
        )
        # pip-audit JSON may be a dict with "dependencies" or (older) a list.
        deps = data.get("dependencies", data) if isinstance(data, dict) else data
        for dep in deps or []:
            name = dep.get("name")
            version = dep.get("version")
            for vuln in dep.get("vulns", []) or []:
                vid = vuln.get("id", "UNKNOWN")
                fix = vuln.get("fix_versions") or []
                outcome.findings.append(
                    RawFinding(
                        title=f"Vulnerable dependency: {name} {version} ({vid})",
                        vuln_class="vulnerable_dependency",
                        severity="medium",
                        confidence="high",
                        location=f"{manifest_rel}:{name}",
                        description=(
                            f"{name} {version} matches advisory {vid}. Confirms "
                            "PRESENCE of a known-vulnerable component, not "
                            "exploitability in this application."
                        ),
                        evidence={
                            "tool": "pip-audit",
                            "advisory_id": vid,
                            "aliases": vuln.get("aliases"),
                            "fix_versions": fix,
                            "package": name,
                            "version": version,
                        },
                    )
                )
        return outcome
