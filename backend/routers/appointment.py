"""Patient booking and clinician appointment management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from models.schemas import (
    AppointmentCreate,
    AppointmentNotesUpdate,
    AppointmentResponse,
    AppointmentStatusUpdate,
)
from routers.auth import get_current_user
from routers.workflow_utils import appointment_payload, ensure_appointment_access

router = APIRouter()


@router.post("/book", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can book appointments")
    doctor = crud.get_user(db, payload.doctor_id)
    if not doctor or doctor.role != "doctor" or not doctor.is_active:
        raise HTTPException(status_code=404, detail="Doctor not found")
    department_id = payload.department_id or doctor.department_id
    if department_id != doctor.department_id:
        raise HTTPException(status_code=400, detail="Doctor does not belong to that department")
    appointment = crud.create_appointment(
        db,
        patient_id=current_user.id,
        doctor_id=doctor.id,
        department_id=department_id,
        reason=payload.reason.strip(),
        scheduled_at=payload.scheduled_at,
    )
    return appointment_payload(appointment)


@router.get("/my", response_model=list[AppointmentResponse])
async def my_appointments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "patient":
        appointments = crud.get_patient_appointments(db, current_user.id)
    elif current_user.role == "doctor":
        appointments = crud.get_doctor_appointments(db, current_user.id)
    elif current_user.role == "admin":
        from db.models import Appointment
        appointments = db.query(Appointment).order_by(Appointment.created_at.desc()).all()
    else:
        appointments = []
    return [appointment_payload(item) for item in appointments]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = crud.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    ensure_appointment_access(current_user, appointment)
    return appointment_payload(appointment)


@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
async def change_status(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = crud.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role == "patient":
        if appointment.patient_id != current_user.id or payload.status != "cancelled":
            raise HTTPException(status_code=403, detail="Patients may only cancel their own appointment")
    elif current_user.role != "admin" and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned doctor can update this appointment")
    return appointment_payload(crud.update_appointment_status(db, appointment, payload.status))


@router.post("/{appointment_id}/notes", response_model=AppointmentResponse)
async def add_notes(
    appointment_id: int,
    payload: AppointmentNotesUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = crud.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and (
        current_user.role != "doctor" or appointment.doctor_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Only the assigned doctor can add notes")
    return appointment_payload(crud.update_appointment_notes(db, appointment, payload.notes))
