"""Public hospital directory endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from models.schemas import DepartmentResponse, DoctorResponse
from routers.auth import get_current_user, serialize_user
from routers.workflow_utils import department_payload

router = APIRouter()


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return [department_payload(item) for item in crud.get_departments(db)]


@router.get("/doctors", response_model=list[DoctorResponse])
async def list_doctors(
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    doctors = crud.get_doctors_by_department(db, department_id)
    return [
        {
            **serialize_user(doctor),
            "department": department_payload(doctor.department),
        }
        for doctor in doctors
    ]


@router.get("/doctors/{doctor_id}/profile", response_model=DoctorResponse)
async def doctor_profile(
    doctor_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    doctor = crud.get_user(db, doctor_id)
    if not doctor or doctor.role != "doctor" or not doctor.is_active:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {
        **serialize_user(doctor),
        "department": department_payload(doctor.department),
    }
