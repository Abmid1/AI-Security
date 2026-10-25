"""Source-code scanner adapter: Bandit (Python SAST).

Bandit finds common security issues in Python source. We wrap its JSON output
and normalize it. Bandit exits non-zero when it finds issues, so a non-zero
exit is NOT treated as an error — only unparseable output is.

Limitation: Bandit analyzes Python only. For a repository in another language
this adapter still runs but will simply report no Python issues; other-language
SAST is a separate adapter (not yet integrated — see docs).
"""

from __future__ import annotations

import json
import importlib.util

from ._proc import run_module
from .base import (
    OutcomeStatus,
    RawFinding,
    ScanLimits,
    ScannerAdapter,
    ScannerCategory,
    ScannerOutcome,
)

# Map Bandit severities (upper-case) to ours.
_SEV = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low", "UNDEFINED": "info"}
_CONF = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low", "UNDEFINED": "low"}


class BanditAdapter(ScannerAdapter):
    name = "bandit"
    category = ScannerCategory.sast
    default_evidence_basis = "STATIC_CONFIRMED"
    # Static presence of a risky pattern; reachability/exploitability unknown.
    default_status = "candidate"

    def is_available(self) -> tuple[bool, str | None]:
        if importlib.util.find_spec("bandit") is None:
            return False, "bandit is not installed"
        return True, None

    def applies_to(self, target) -> bool:
        return target.kind == "repo" and bool(target.workspace_path)

    def scan(self, target, limits: ScanLimits) -> ScannerOutcome:
        available, reason = self.is_available()
        if not available:
            return ScannerOutcome.skipped(self.name, self.category.value, reason or "unavailable")
        if not target.workspace_path:
            return ScannerOutcome.skipped(self.name, self.category.value, "no workspace path")

        res = run_module(
            ["bandit", "-r", target.workspace_path, "-f", "json", "-q"],
            timeout=limits.timeout_seconds,
        )
        if res.error:
            return ScannerOutcome.errored(self.name, self.category.value, res.error)

        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return ScannerOutcome.errored(
                self.name, self.category.value,
                "could not parse Bandit JSON output",
            )

        return self._parse(data)

    def _parse(self, data: dict) -> ScannerOutcome:
        outcome = ScannerOutcome(
            scanner=self.name,
            category=self.category.value,
            status=OutcomeStatus.completed,
        )
        for result in data.get("results", []):
            sev = _SEV.get(str(result.get("issue_severity", "")).upper(), "info")
            conf = _CONF.get(str(result.get("issue_confidence", "")).upper(), "low")
            fname = result.get("filename", "")
            line = result.get("line_number")
            location = f"{fname}:{line}" if line else fname
            test_name = result.get("test_name") or result.get("test_id") or "issue"
            outcome.findings.append(
                RawFinding(
                    title=f"{test_name}: {result.get('issue_text', '').strip()[:140]}",
                    vuln_class=_slug(test_name),
                    severity=sev,
                    confidence=conf,
                    location=location,
                    description=result.get("issue_text"),
                    evidence={
                        "tool": "bandit",
                        "test_id": result.get("test_id"),
                        "cwe": (result.get("issue_cwe") or {}).get("id"),
                        "more_info": result.get("more_info"),
                    },
                )
            )

        # Files Bandit could not analyze are recorded as skipped areas.
        for err in data.get("errors", []):
            fn = err.get("filename", "?")
            outcome.skipped_areas.append(f"bandit could not analyze {fn}: {err.get('reason')}")
        return outcome


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")[:60]
