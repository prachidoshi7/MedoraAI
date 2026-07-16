"""
MedoraAI — History Router
Returns and manages scan history for the authenticated user.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db import crud
from models.schemas import (
    DeleteScansRequest,
    DeleteScansResponse,
    HistoryResponse,
    HistoryScan,
)
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _delete_scan_files(scan_ids: list[str]) -> None:
    """Delete only UUID-named scan files inside the configured data folders."""
    roots = [
        os.path.realpath(settings.uploads_dir),
        os.path.realpath(settings.heatmaps_dir),
        os.path.realpath(settings.thumbnails_dir),
    ]

    for scan_id in scan_ids:
        for root in roots:
            file_path = os.path.realpath(os.path.join(root, f"{scan_id}.png"))
            try:
                if os.path.commonpath([root, file_path]) != root:
                    logger.error("Refusing to delete history file outside data root: %s", file_path)
                    continue
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except (OSError, ValueError) as error:
                logger.warning("Could not delete history file %s: %s", file_path, error)


def _delete_for_user(
    db: Session,
    user_id: int,
    scan_ids: list[str] | None,
) -> DeleteScansResponse:
    deleted_ids = crud.delete_user_scans(db, user_id, scan_ids)
    _delete_scan_files(deleted_ids)
    logger.info("Deleted %s scan(s) from history for user %s", len(deleted_ids), user_id)
    return DeleteScansResponse(deleted=len(deleted_ids), scan_ids=deleted_ids)


@router.get("", response_model=HistoryResponse)
async def get_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get all scans for the current user, ordered by most recent first.
    Includes result data (top_label, confidence, severity) for analyzed scans.
    """
    scans = crud.get_user_scans(db, current_user.id, limit=50)
    total = crud.get_user_scan_count(db, current_user.id)

    history_scans = []
    for scan in scans:
        # Get result if analyzed
        top_label = "Pending"
        confidence = 0.0
        severity = "Unknown"

        if scan.result:
            top_label = scan.result.top_label
            confidence = scan.result.confidence
            severity = scan.result.severity

        history_scans.append(
            HistoryScan(
                scan_id=scan.id,
                filename=scan.filename,
                scan_type=scan.scan_type,
                top_label=top_label,
                confidence=confidence,
                severity=severity,
                status=scan.status,
                uploaded_at=scan.uploaded_at.isoformat() if scan.uploaded_at else "",
                thumbnail_url=f"/static/thumbnails/{scan.id}.png",
            )
        )

    return HistoryResponse(
        scans=history_scans,
        total=total,
    )


@router.post("/delete", response_model=DeleteScansResponse)
async def delete_selected_history(
    payload: DeleteScansRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete up to 50 selected scans owned by the current user."""
    return _delete_for_user(db, current_user.id, payload.scan_ids)


@router.delete("", response_model=DeleteScansResponse)
async def clear_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete every scan owned by the current user."""
    return _delete_for_user(db, current_user.id, None)


@router.delete("/{scan_id}", response_model=DeleteScansResponse)
async def delete_history_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete one scan owned by the current user."""
    response = _delete_for_user(db, current_user.id, [scan_id])
    if response.deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )
    return response
