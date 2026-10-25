"""Core types and the ScannerAdapter interface.

Everything a scanner needs to receive (ScanTarget, ScanLimits) and produce
(RawFinding, ScannerOutcome) is defined here, independent of the database and
the web layer, so adapters are easy to test in isolation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class ScannerCategory(str, Enum):
    sast = "sast"          # source-code analysis
    sca = "sca"            # dependency / known-CVE analysis
    secrets = "secrets"    # exposed-secret detection
    dynamic = "dynamic"    # network testing against a running app


class OutcomeStatus(str, Enum):
    completed = "completed"  # ran and produced results (possibly zero findings)
    skipped = "skipped"      # deliberately not run (tool missing, not authorized, N/A)
    error = "error"          # attempted but failed


@dataclass
class ScanLimits:
    """Resource guards passed to every adapter."""
    timeout_seconds: int = 180
    max_findings: int = 2000


@dataclass
class ScanTarget:
    """What a scan runs against. Repo scans use workspace_path; dynamic scans
    use base_url. Authorization fields gate dynamic testing."""
    project_id: str
    kind: str                       # "web" | "repo"
    workspace_path: str | None = None   # local dir of code to scan (repo)
    base_url: str | None = None         # origin to test (web)
    authorized: bool = False
    authorization_note: str | None = None
    # Dynamic scope: the one origin the scanner is permitted to contact, and
    # whether private/loopback hosts (e.g. local staging) are allowed.
    allowed_origin: str | None = None
    allow_private_hosts: bool = False


@dataclass
class RawFinding:
    """A finding as produced by one adapter, before normalization.

    The adapter sets the security meaning (class/severity/evidence). Normalization
    later validates paths, redacts secrets, assigns status/basis defaults where
    missing, dedups, and maps to the canonical DB shape.
    """
    title: str
    vuln_class: str
    severity: str                   # critical|high|medium|low|info
    confidence: str                 # high|medium|low
    location: str | None = None     # file path, or URL/header for dynamic
    description: str | None = None
    evidence: dict = field(default_factory=dict)
    # Optional overrides; if None, the adapter's defaults are applied.
    status: str | None = None
    evidence_basis: str | None = None
    # Raw secret material, if any, so normalization can redact it. NEVER stored.
    _raw_secret: str | None = None


@dataclass
class ScannerOutcome:
    """The full result of running one adapter."""
    scanner: str
    category: str
    status: OutcomeStatus
    findings: list[RawFinding] = field(default_factory=list)
    reason: str | None = None            # why skipped/errored
    errors: list[str] = field(default_factory=list)
    skipped_areas: list[str] = field(default_factory=list)
    tool_version: str | None = None

    @classmethod
    def skipped(cls, scanner: str, category: str, reason: str) -> "ScannerOutcome":
        return cls(scanner=scanner, category=category,
                   status=OutcomeStatus.skipped, reason=reason,
                   skipped_areas=[reason])

    @classmethod
    def errored(cls, scanner: str, category: str, reason: str) -> "ScannerOutcome":
        return cls(scanner=scanner, category=category,
                   status=OutcomeStatus.error, reason=reason, errors=[reason])


class ScannerAdapter(abc.ABC):
    """Interface every scanner must implement.

    Add a new scanner by subclassing this and registering it in registry.py.
    """

    name: str = "unnamed"
    category: ScannerCategory = ScannerCategory.sast
    # Defaults applied to findings that don't set their own.
    default_evidence_basis: str = "STATIC_CONFIRMED"
    default_status: str = "candidate"
    # Dynamic (network) scanners must be gated on authorization + scope.
    requires_dynamic_authorization: bool = False

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str | None]:
        """Return (available, reason_if_not). Checks the underlying tool exists."""

    @abc.abstractmethod
    def applies_to(self, target: ScanTarget) -> bool:
        """Whether this scanner is relevant to the given target kind."""

    @abc.abstractmethod
    def scan(self, target: ScanTarget, limits: ScanLimits) -> ScannerOutcome:
        """Run the scan. Must never raise for expected conditions — return an
        error/skipped outcome instead. May raise only on truly unexpected bugs,
        which the worker converts into an error outcome."""
