"""Hospital directory, medicine catalog, and admin doctor management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from models.schemas import (
    DepartmentResponse,
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
    MedicineResponse,
)
from routers.auth import get_current_user, pwd_context, require_roles, serialize_user
from routers.workflow_utils import department_payload

router = APIRouter()


def doctor_payload(doctor):
    return {
        **serialize_user(doctor),
        "department": department_payload(doctor.department),
    }


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
    return [doctor_payload(doctor) for doctor in doctors]


@router.get("/doctors/{doctor_id}/profile", response_model=DoctorResponse)
async def doctor_profile(
    doctor_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    doctor = crud.get_user(db, doctor_id)
    if not doctor or doctor.role != "doctor" or not doctor.is_active:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor_payload(doctor)


@router.get("/medicines", response_model=list[MedicineResponse])
async def list_medicines(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return [
        {"id": item.id, "name": item.name, "category": item.category or "General"}
        for item in crud.get_medicines(db)
    ]


@router.get("/admin/doctors", response_model=list[DoctorResponse])
async def admin_list_doctors(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    return [doctor_payload(doctor) for doctor in crud.get_all_doctors(db)]


@router.post("/admin/doctors", response_model=DoctorResponse, status_code=201)
async def admin_create_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    username = payload.username.strip().lower()
    if crud.get_user_by_username(db, username):
        raise HTTPException(status_code=409, detail="Username is already registered")
    department = crud.get_department(db, payload.department_id)
    if not department or not department.is_active:
        raise HTTPException(status_code=422, detail="Select an active department")
    doctor = crud.create_user(
        db,
        username=username,
        hashed_password=pwd_context.hash(payload.password),
        role="doctor",
        full_name=payload.full_name.strip(),
        email=payload.email.strip(),
        phone=payload.phone.strip(),
        specialization=payload.specialization.strip(),
        qualification=payload.qualification.strip(),
        department_id=department.id,
    )
    return doctor_payload(doctor)


@router.patch("/admin/doctors/{doctor_id}", response_model=DoctorResponse)
async def admin_update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    doctor = crud.get_user(db, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="Doctor not found")
    updates = payload.model_dump(exclude_unset=True)
    if "department_id" in updates:
        department = crud.get_department(db, updates["department_id"])
        if not department or not department.is_active:
            raise HTTPException(status_code=422, detail="Select an active department")
    for field in ("full_name", "qualification", "specialization", "email", "phone", "availability_note"):
        if field in updates and updates[field] is not None:
            updates[field] = updates[field].strip()
    for field, value in updates.items():
        setattr(doctor, field, value)
    if not doctor.is_active:
        doctor.is_available = False
    db.commit()
    db.refresh(doctor)
    return doctor_payload(doctor)


@router.delete("/admin/doctors/{doctor_id}", response_model=DoctorResponse)
async def admin_delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    doctor = crud.get_user(db, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor.is_active = False
    doctor.is_available = False
    doctor.availability_note = doctor.availability_note or "Not currently accepting appointments"
    db.commit()
    db.refresh(doctor)
    return doctor_payload(doctor)
