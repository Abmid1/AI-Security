"""Pydantic schemas: request validation and response shaping.

Enums here are the single source of truth for allowed values. The DB stores
plain strings; these enums reject anything outside the allowed set at the API
boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectKind(str, Enum):
    web = "web"
    repo = "repo"


class ScanStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class FindingStatus(str, Enum):
    candidate = "candidate"
    confirmed = "confirmed"
    disproven = "disproven"
    inconclusive = "inconclusive"
    untested = "untested"
    verification_failed = "verification_failed"


class EvidenceBasis(str, Enum):
    ai_reviewed = "AI_REVIEWED"
    dynamic_reproduced = "DYNAMIC_REPRODUCED"
    static_confirmed = "STATIC_CONFIRMED"
    dependency_match = "DEPENDENCY_MATCH"
    config_observed = "CONFIG_OBSERVED"
    secret_match = "SECRET_MATCH"


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: ProjectKind
    target_url: str | None = Field(default=None, max_length=2048)
    repo_url: str | None = Field(default=None, max_length=2048)
    authorization_confirmed: bool = False
    authorization_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_shape(self) -> "ProjectCreate":
        if self.kind == ProjectKind.web and not self.target_url:
            raise ValueError("A web project requires target_url.")
        if self.kind == ProjectKind.repo and not self.repo_url:
            raise ValueError("A repository project requires repo_url.")
        # Authorization is mandatory before a project can be created. Scanning an
        # unauthorized target is never allowed (see the engine spec principles).
        if not self.authorization_confirmed:
            raise ValueError(
                "authorization_confirmed must be true: you may only add targets "
                "you are explicitly authorized to test."
            )
        return self


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    target_url: str | None
    repo_url: str | None
    authorization_confirmed: bool
    authorization_note: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Scan jobs
# --------------------------------------------------------------------------- #
class ScanMode(str, Enum):
    mock = "mock"
    real = "real"


class ScanCreate(BaseModel):
    project_id: str
    mode: ScanMode = ScanMode.mock
    # Optional subset of scanner names to run; None = all applicable.
    scanners: list[str] | None = None


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    mode: str
    is_mock: bool
    coverage_note: str | None
    coverage: dict | None
    error: str | None
    requested_scanners: list | None
    findings_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_job_id: str
    project_id: str
    title: str
    vuln_class: str
    severity: str
    confidence: str
    status: str
    evidence_basis: str
    location: str | None
    description: str | None
    evidence: dict | None
    scanner: str | None = None
    is_mock: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
class HealthOut(BaseModel):
    status: str
    version: str
    mock_mode: bool


class DbHealthOut(BaseModel):
    status: str
    database: str


class FixPlaceholderOut(BaseModel):
    status: str
    message: str
    finding_id: str
