"""Scan endpoints. In Milestone 1 scans are MOCK only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db
from ..schemas import ScanCreate, ScanOut

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("", response_model=list[ScanOut])
def list_scans(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ScanOut]:
    return crud.list_scans(db, project_id=project_id)


@router.post("", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
def start_scan(payload: ScanCreate, db: Session = Depends(get_db)) -> ScanOut:
    """Start a scan for a project.

    NOTE: this creates a MOCK scan with sample findings. No real scanning
    happens. The response is clearly flagged is_mock=True.
    """
    project = crud.get_project(db, payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.authorization_confirmed:
        # Defence in depth: never scan an unauthorized target.
        raise HTTPException(
            status_code=403,
            detail="Project is not authorized for scanning.",
        )
    scan = crud.create_mock_scan(db, project)
    return scan


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, db: Session = Depends(get_db)) -> ScanOut:
    scan = crud.get_scan(db, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
