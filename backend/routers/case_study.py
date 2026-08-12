"""Comprehensive, doctor-finalized patient case studies."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from db.models import Appointment, CaseStudy
from models.schemas import CaseStudyGenerate, CaseStudyResponse, CaseStudyUpdate
from routers.auth import get_current_user, serialize_user
from routers.workflow_utils import prescription_payload

router = APIRouter()


def _case_payload(case_study: CaseStudy):
    try:
        scan_ids = json.loads(case_study.scan_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        scan_ids = []
    prescriptions = list(case_study.appointment.prescriptions) if case_study.appointment else []
    return {
        "id": case_study.id,
        "patient": serialize_user(case_study.patient),
        "appointment_id": case_study.appointment_id,
        "chief_complaint": case_study.chief_complaint or "",
        "clinical_history": case_study.clinical_history or "",
        "diagnostic_findings": case_study.diagnostic_findings or "",
        "scan_ids": scan_ids,
        "diagnosis": case_study.diagnosis or "",
        "treatment_plan": case_study.treatment_plan or "",
        "prescriptions": [prescription_payload(item) for item in prescriptions],
        "follow_up_plan": case_study.follow_up_plan or "",
        "doctor_notes": case_study.doctor_notes or "",
        "status": case_study.status,
        "preliminary_at": case_study.preliminary_at,
        "finalized_at": case_study.finalized_at,
        "created_at": case_study.created_at,
    }


def _ensure_case_access(user, case_study: CaseStudy, doctor_write: bool = False):
    appointment = case_study.appointment
    permitted = (
        user.role == "admin"
        or case_study.patient_id == user.id
        or (appointment is not None and appointment.doctor_id == user.id)
    )
    if not permitted or (doctor_write and user.role not in {"doctor", "admin"}):
        raise HTTPException(status_code=403, detail="Access denied")
    if user.role == "patient" and case_study.status == "draft":
        raise HTTPException(status_code=409, detail="Case study is awaiting doctor release")


def _collect_findings(appointment) -> tuple[list[str], str]:
    scan_ids: list[str] = []
    sections: list[str] = []
    for order in appointment.diagnostic_orders:
        if not order.scan_id:
            continue
        scan_ids.append(order.scan_id)
        scan = order.scan
        if scan and scan.report:
            try:
                report = json.loads(scan.report.report_json or "{}")
            except (json.JSONDecodeError, TypeError):
                report = {}
            finding = scan.report.edited_impression or report.get("impression", "")
        elif scan and scan.result:
            finding = f"{scan.result.top_label} ({scan.result.confidence * 100:.1f}% model confidence)"
        else:
            finding = "Awaiting analysis"
        sections.append(f"{order.scan_type.replace('_', ' ').title()}: {finding}")
    return scan_ids, "\n\n".join(sections) or "No completed diagnostic findings yet."


@router.post("/generate", response_model=CaseStudyResponse, status_code=201)
async def generate_case_study(
    payload: CaseStudyGenerate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Only doctors can generate case studies")
    appointment = crud.get_appointment(db, payload.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="This appointment is assigned to another doctor")

    scan_ids, findings = _collect_findings(appointment)
    case_study = crud.get_case_study_by_appointment(db, appointment.id)
    if case_study is None:
        case_study = CaseStudy(
            patient_id=appointment.patient_id,
            appointment_id=appointment.id,
        )
        db.add(case_study)
    case_study.chief_complaint = appointment.reason or ""
    case_study.clinical_history = payload.clinical_history or appointment.notes or ""
    case_study.diagnostic_findings = findings
    case_study.scan_ids = json.dumps(scan_ids)
    case_study.diagnosis = payload.diagnosis
    case_study.treatment_plan = payload.treatment_plan
    case_study.follow_up_plan = payload.follow_up_plan
    case_study.prescriptions_json = json.dumps(
        [item.id for item in appointment.prescriptions]
    )
    case_study.status = "draft"
    db.commit()
    db.refresh(case_study)
    return _case_payload(case_study)


@router.get("/mine", response_model=list[CaseStudyResponse])
async def my_case_studies(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "patient":
        items = [
            item for item in crud.get_patient_case_studies(db, current_user.id)
            if item.status in {"preliminary", "final"}
        ]
    elif current_user.role == "doctor":
        items = (
            db.query(CaseStudy)
            .join(CaseStudy.appointment)
            .filter(Appointment.doctor_id == current_user.id)
            .order_by(CaseStudy.created_at.desc())
            .all()
        )
    else:
        items = db.query(CaseStudy).order_by(CaseStudy.created_at.desc()).all()
    return [_case_payload(item) for item in items]


@router.get("/{case_study_id}", response_model=CaseStudyResponse)
async def get_case_study(
    case_study_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    case_study = crud.get_case_study(db, case_study_id)
    if not case_study:
        raise HTTPException(status_code=404, detail="Case study not found")
    _ensure_case_access(current_user, case_study)
    return _case_payload(case_study)


@router.patch("/{case_study_id}", response_model=CaseStudyResponse)
async def update_case_study(
    case_study_id: int,
    payload: CaseStudyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    case_study = crud.get_case_study(db, case_study_id)
    if not case_study:
        raise HTTPException(status_code=404, detail="Case study not found")
    _ensure_case_access(current_user, case_study, doctor_write=True)
    if case_study.status == "final":
        raise HTTPException(status_code=409, detail="A finalized case study is immutable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case_study, field, value)
    if payload.status == "preliminary":
        case_study.preliminary_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case_study)
    return _case_payload(case_study)


@router.post("/{case_study_id}/finalize", response_model=CaseStudyResponse)
async def finalize_case_study(
    case_study_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    case_study = crud.get_case_study(db, case_study_id)
    if not case_study:
        raise HTTPException(status_code=404, detail="Case study not found")
    _ensure_case_access(current_user, case_study, doctor_write=True)
    case_study.status = "final"
    case_study.finalized_at = datetime.now(timezone.utc)
    case_study.finalized_by_doctor_id = current_user.id
    db.commit()
    db.refresh(case_study)
    return _case_payload(case_study)


@router.get("/{case_study_id}/pdf")
async def case_study_pdf(
    case_study_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    case_study = crud.get_case_study(db, case_study_id)
    if not case_study:
        raise HTTPException(status_code=404, detail="Case study not found")
    _ensure_case_access(current_user, case_study)
    pdf = request.app.state.pdf_generator.generate_case_study_pdf(_case_payload(case_study))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="MedoraAI_Case_{case_study.id}.pdf"'},
    )
