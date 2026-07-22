"""
MedoraAI — CRUD Operations
Database create/read/update operations for all models.
"""

import json
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .models import User, Scan, Result, Report


# ============================================================
# USER CRUD
# ============================================================

def create_user(db: Session, username: str, hashed_password: str) -> User:
    """Create a new user."""
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


# ============================================================
# SCAN CRUD
# ============================================================

def create_scan(
    db: Session,
    scan_id: str,
    user_id: int,
    filename: str,
    scan_type: str,
    modality: str,
    file_path: str,
    thumbnail_path: str | None = None,
    file_size_bytes: int | None = None,
) -> Scan:
    """Create a new scan record."""
    scan = Scan(
        id=scan_id,
        user_id=user_id,
        filename=filename,
        scan_type=scan_type,
        modality=modality,
        file_path=file_path,
        thumbnail_path=thumbnail_path,
        file_size_bytes=file_size_bytes,
        status="uploaded",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def get_scan(db: Session, scan_id: str) -> Scan | None:
    """Get scan by ID."""
    return db.query(Scan).filter(Scan.id == scan_id).first()


def update_scan_status(db: Session, scan_id: str, status: str) -> Scan | None:
    """Update scan status (uploaded → analyzing → analyzed → failed)."""
    scan = get_scan(db, scan_id)
    if scan:
        scan.status = status
        db.commit()
        db.refresh(scan)
    return scan


def update_scan_heatmap(db: Session, scan_id: str, heatmap_path: str) -> Scan | None:
    """Update scan with heatmap path after analysis."""
    scan = get_scan(db, scan_id)
    if scan:
        scan.heatmap_path = heatmap_path
        db.commit()
        db.refresh(scan)
    return scan


# ============================================================
# RESULT CRUD
# ============================================================

def create_result(
    db: Session,
    scan_id: str,
    top_label: str,
    confidence: float,
    severity: str,
    all_scores: dict,
    localization_type: str = "heatmap",
    bounding_boxes: list | None = None,
    analysis_time_ms: int | None = None,
) -> Result:
    """Create an inference result for a scan."""
    result = Result(
        scan_id=scan_id,
        top_label=top_label,
        confidence=confidence,
        severity=severity,
        all_scores=json.dumps(all_scores),
        localization_type=localization_type,
        bounding_boxes=json.dumps(bounding_boxes) if bounding_boxes else None,
        analysis_time_ms=analysis_time_ms,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def get_result_by_scan(db: Session, scan_id: str) -> Result | None:
    """Get inference result for a scan."""
    return db.query(Result).filter(Result.scan_id == scan_id).first()


# ============================================================
# REPORT CRUD
# ============================================================

def create_report(
    db: Session,
    scan_id: str,
    report_data: dict,
    llm_provider: str = "template",
    patient_id: str = "DEMO-001",
) -> Report:
    """Create a clinical report for a scan."""
    report = Report(
        scan_id=scan_id,
        patient_id=patient_id,
        llm_provider=llm_provider,
        report_json=json.dumps(report_data),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def replace_report(
    db: Session,
    scan_id: str,
    report_data: dict,
    llm_provider: str = "template",
    patient_id: str = "DEMO-001",
) -> Report:
    """Create or replace a generated report while preserving the scan record."""
    report = get_report_by_scan(db, scan_id)
    if report is None:
        return create_report(db, scan_id, report_data, llm_provider, patient_id)
    report.patient_id = patient_id or report.patient_id
    report.llm_provider = llm_provider
    report.report_json = json.dumps(report_data)
    report.edited_findings = None
    report.edited_impression = None
    report.generated_at = func.now()
    db.commit()
    db.refresh(report)
    return report


def get_report_by_scan(db: Session, scan_id: str) -> Report | None:
    """Get clinical report for a scan."""
    return db.query(Report).filter(Report.scan_id == scan_id).first()


def update_report_edits(
    db: Session,
    scan_id: str,
    edited_findings: str | None = None,
    edited_impression: str | None = None,
) -> Report | None:
    """Update report with clinician edits."""
    report = get_report_by_scan(db, scan_id)
    if report:
        if edited_findings is not None:
            report.edited_findings = edited_findings
        if edited_impression is not None:
            report.edited_impression = edited_impression
        db.commit()
        db.refresh(report)
    return report


# ============================================================
# HISTORY
# ============================================================

def get_user_scans(db: Session, user_id: int, limit: int = 50) -> list[Scan]:
    """Get all scans for a user, ordered by most recent first."""
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id)
        .order_by(Scan.uploaded_at.desc())
        .limit(limit)
        .all()
    )


def get_user_scan_count(db: Session, user_id: int) -> int:
    """Count all scans owned by a user."""
    return db.query(Scan).filter(Scan.user_id == user_id).count()


def delete_user_scans(
    db: Session,
    user_id: int,
    scan_ids: list[str] | None = None,
) -> list[str]:
    """Delete selected scans, or every scan when scan_ids is None."""
    query = db.query(Scan).filter(Scan.user_id == user_id)

    if scan_ids is not None:
        unique_ids = list(dict.fromkeys(scan_ids))
        if not unique_ids:
            return []
        query = query.filter(Scan.id.in_(unique_ids))

    scans = query.all()
    deleted_ids = [scan.id for scan in scans]

    for scan in scans:
        db.delete(scan)

    if scans:
        db.commit()

    return deleted_ids
