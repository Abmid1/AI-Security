"""Finding endpoints, including the placeholder 'Generate Fix' action."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db
from ..schemas import FindingOut, FixPlaceholderOut

router = APIRouter(prefix="/api/findings", tags=["findings"])


@router.get("", response_model=list[FindingOut])
def list_findings(
    scan_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[FindingOut]:
    return crud.list_findings(db, scan_id=scan_id, project_id=project_id)


@router.get("/{finding_id}", response_model=FindingOut)
def get_finding(finding_id: str, db: Session = Depends(get_db)) -> FindingOut:
    finding = crud.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


@router.post("/{finding_id}/fix", response_model=FixPlaceholderOut)
def generate_fix(finding_id: str, db: Session = Depends(get_db)) -> FixPlaceholderOut:
    """Placeholder for the 'Generate Fix' button.

    Fix generation (isolated worktree, patch review, regression testing, human
    approval) is a later milestone and is intentionally NOT implemented. This
    endpoint confirms the finding exists and returns a clear 'not implemented'
    message rather than pretending to do anything.
    """
    finding = crud.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return FixPlaceholderOut(
        status="not_implemented",
        message=(
            "Automated fix generation is not available in this milestone. "
            "Fixes will be generated in an isolated workspace, reviewed, and "
            "tested before any change is proposed for your approval."
        ),
        finding_id=finding_id,
    )
