"""Clinician prescription endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from models.schemas import PrescriptionCreate, PrescriptionResponse, PrescriptionUpdate
from routers.auth import get_current_user
from routers.workflow_utils import prescription_payload

router = APIRouter()


def _catalog_medications(db: Session, medications) -> list[dict]:
    normalized = []
    for item in medications:
        if item.medicine_id is None:
            raise HTTPException(
                status_code=422,
                detail="Select every medicine from the medicine catalog",
            )
        catalog_item = crud.get_medicine(db, item.medicine_id)
        if not catalog_item or not catalog_item.is_active:
            raise HTTPException(status_code=422, detail="Selected medicine is unavailable")
        normalized.append({
            "medicine_id": catalog_item.id,
            "name": catalog_item.name,
            "dosage": item.dosage,
            "frequency": item.frequency,
            "duration": item.duration,
        })
    return normalized


@router.post("", response_model=PrescriptionResponse, status_code=201)
async def create_prescription(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Only doctors can prescribe")
    appointment = crud.get_appointment(db, payload.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="This appointment is assigned to another doctor")
    if payload.scan_id:
        scan = crud.get_scan(db, payload.scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Linked scan not found")
    prescription = crud.create_prescription(
        db,
        appointment_id=appointment.id,
        doctor_id=appointment.doctor_id if current_user.role == "admin" else current_user.id,
        patient_id=appointment.patient_id,
        scan_id=payload.scan_id,
        medications=_catalog_medications(db, payload.medications),
        instructions=payload.instructions,
        diagnosis=payload.diagnosis,
    )
    return prescription_payload(prescription)


@router.get("/mine", response_model=list[PrescriptionResponse])
async def my_prescriptions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "patient":
        items = crud.get_patient_prescriptions(db, current_user.id)
    elif current_user.role == "doctor":
        from db.models import Prescription
        items = (
            db.query(Prescription)
            .filter(Prescription.doctor_id == current_user.id)
            .order_by(Prescription.created_at.desc())
            .all()
        )
    else:
        items = []
    return [prescription_payload(item) for item in items]


@router.get("/patient/{patient_id}", response_model=list[PrescriptionResponse])
async def patient_prescriptions(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "patient" and current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role not in {"patient", "doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    return [
        prescription_payload(item)
        for item in crud.get_patient_prescriptions(db, patient_id)
    ]


@router.patch("/{prescription_id}", response_model=PrescriptionResponse)
async def update_prescription(
    prescription_id: int,
    payload: PrescriptionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    prescription = crud.get_prescription(db, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if current_user.role != "admin" and (
        current_user.role != "doctor" or prescription.doctor_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Only the prescribing doctor can edit this")
    if payload.medications is not None:
        prescription.medications = json.dumps(_catalog_medications(db, payload.medications))
    if payload.instructions is not None:
        prescription.instructions = payload.instructions
    if payload.diagnosis is not None:
        prescription.diagnosis = payload.diagnosis
    db.commit()
    db.refresh(prescription)
    return prescription_payload(prescription)
