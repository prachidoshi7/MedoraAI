"""Diagnostic ordering and lab queue endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from models.schemas import DiagnosticOrderCreate, DiagnosticOrderResponse
from routers.auth import get_current_user
from routers.workflow_utils import diagnostic_order_payload, ensure_appointment_access

router = APIRouter()

ORGAN_BY_SCAN_TYPE = {
    "chest_xray": "chest",
    "brain_mri": "brain",
    "lung_ct": "lung",
    "kidney_us": "kidney",
}


@router.post("/order", response_model=DiagnosticOrderResponse, status_code=201)
async def create_order(
    payload: DiagnosticOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Only doctors can order diagnostics")
    appointment = crud.get_appointment(db, payload.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="This appointment is assigned to another doctor")
    if appointment.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cannot order a test for a cancelled appointment")
    order = crud.create_diagnostic_order(
        db,
        appointment_id=appointment.id,
        ordering_doctor_id=current_user.id,
        scan_type=payload.scan_type,
        organ=ORGAN_BY_SCAN_TYPE[payload.scan_type],
        priority=payload.priority,
        clinical_notes=payload.clinical_notes,
    )
    return diagnostic_order_payload(order)


@router.get("/pending", response_model=list[DiagnosticOrderResponse])
async def pending_orders(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in {"lab_tech", "admin"}:
        raise HTTPException(status_code=403, detail="Lab access required")
    return [diagnostic_order_payload(item) for item in crud.get_pending_orders(db)]


@router.get("/my", response_model=list[DiagnosticOrderResponse])
async def my_orders(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return [
        diagnostic_order_payload(item)
        for item in crud.get_orders_for_user(db, current_user)
    ]


@router.patch("/{order_id}/assign", response_model=DiagnosticOrderResponse)
async def claim_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in {"lab_tech", "admin"}:
        raise HTTPException(status_code=403, detail="Lab access required")
    order = crud.get_diagnostic_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")
    if order.status not in {"ordered", "assigned"}:
        raise HTTPException(status_code=409, detail="Order can no longer be assigned")
    if order.assigned_lab_tech_id and order.assigned_lab_tech_id != current_user.id:
        raise HTTPException(status_code=409, detail="Order is already assigned")
    return diagnostic_order_payload(crud.assign_lab_tech(db, order, current_user.id))


@router.post("/{order_id}/upload-scan")
async def upload_order_scan(
    order_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload a scan using the modality declared on a diagnostic order."""
    if current_user.role not in {"lab_tech", "doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Clinical staff access required")
    order = crud.get_diagnostic_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")
    from routers.scan import upload_scan
    return await upload_scan(
        request=request,
        file=file,
        scan_type=order.scan_type,
        diagnostic_order_id=order.id,
        db=db,
        current_user=current_user,
    )


@router.get("/{order_id}/status", response_model=DiagnosticOrderResponse)
async def order_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = crud.get_diagnostic_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")
    if current_user.role != "lab_tech":
        ensure_appointment_access(current_user, order.appointment)
    return diagnostic_order_payload(order)
