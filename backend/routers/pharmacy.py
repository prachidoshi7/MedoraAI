"""Pharmacy prescription queue and itemized billing endpoints."""

import csv
import json
from datetime import date, datetime
from io import StringIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from db.models import PharmacyBill
from models.schemas import (
    PharmacyBillCreate,
    PharmacyBillResponse,
    PharmacyCsvImportResponse,
    PharmacyInventoryResponse,
    PharmacyQueueItem,
    PharmacyRestockRequest,
    PharmacyRestockResponse,
)
from routers.auth import get_current_user
from routers.workflow_utils import pharmacy_bill_payload, prescription_payload

router = APIRouter()

CSV_MAX_BYTES = 1_000_000
CSV_MAX_ROWS = 1000
CSV_HEADER_ALIASES = {
    "medicine_name": {"medicine_name", "medicine", "name", "medicine name"},
    "quantity": {"quantity", "new_quantity", "new_stock", "stock", "units"},
    "expiry_date": {"expiry_date", "expiry", "expires_on", "expiration_date"},
}


def _ensure_pharmacy_role(user) -> None:
    if user.role not in {"pharmacy", "admin"}:
        raise HTTPException(status_code=403, detail="Pharmacy access required")


def _resolve_pharmacy_id(db: Session, user) -> int:
    _ensure_pharmacy_role(user)
    if user.role == "pharmacy":
        return user.id
    pharmacies = crud.get_users_by_role(db, "pharmacy")
    if not pharmacies:
        raise HTTPException(status_code=409, detail="No active pharmacy account is configured")
    return pharmacies[0].id


def _inventory_payload(item):
    return {
        "id": item.id,
        "medicine": {
            "id": item.medicine.id,
            "name": item.medicine.name,
            "category": item.medicine.category or "General",
        },
        "current_quantity": item.quantity,
        "expiry_date": item.expiry_date,
        "updated_at": item.updated_at,
    }


def _normalized_header(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", "_").split())


def _csv_columns(fieldnames: list[str] | None) -> dict[str, str]:
    available = {
        _normalized_header(header): header
        for header in (fieldnames or [])
        if header and header.strip()
    }
    resolved = {}
    for canonical, aliases in CSV_HEADER_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalized_header(alias)
            if normalized_alias in available:
                resolved[canonical] = available[normalized_alias]
                break
    missing = [name for name in CSV_HEADER_ALIASES if name not in resolved]
    if missing:
        raise ValueError(
            "Missing required CSV column(s): " + ", ".join(missing)
        )
    return resolved


def _parse_expiry_date(value: str) -> date:
    cleaned = value.strip()
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    raise ValueError("expiry_date must use YYYY-MM-DD, DD-MM-YYYY, or DD/MM/YYYY")


def _ensure_bill_access(user, bill: PharmacyBill) -> None:
    allowed = (
        user.role == "admin"
        or (user.role == "patient" and bill.patient_id == user.id)
        or (user.role == "pharmacy" and bill.pharmacy_id == user.id)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/inventory", response_model=list[PharmacyInventoryResponse])
async def inventory(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    pharmacy_id = _resolve_pharmacy_id(db, current_user)
    return [_inventory_payload(item) for item in crud.get_inventory(db, pharmacy_id)]


@router.post("/inventory/restock", response_model=PharmacyRestockResponse)
async def restock(
    payload: PharmacyRestockRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    pharmacy_id = _resolve_pharmacy_id(db, current_user)
    medicine = crud.get_medicine(db, payload.medicine_id)
    if not medicine or not medicine.is_active:
        raise HTTPException(status_code=404, detail="Medicine not found")
    if payload.expiry_date and payload.expiry_date < date.today():
        raise HTTPException(status_code=422, detail="Cannot add already expired medicine")
    item, previous = crud.restock_inventory(
        db,
        pharmacy_id=pharmacy_id,
        medicine_id=medicine.id,
        quantity=payload.new_quantity,
        created_by_user_id=current_user.id,
        expiry_date=payload.expiry_date,
    )
    return {
        "inventory": _inventory_payload(item),
        "previous_quantity": previous,
        "added_quantity": payload.new_quantity,
        "total_quantity": item.quantity,
    }


@router.post("/inventory/import-csv", response_model=PharmacyCsvImportResponse)
async def import_inventory_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Atomically add CSV stock rows matched against the medicine catalog."""
    pharmacy_id = _resolve_pharmacy_id(db, current_user)
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a .csv inventory file")
    content = await file.read(CSV_MAX_BYTES + 1)
    if len(content) > CSV_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file must be 1 MB or smaller")
    if not content.strip():
        raise HTTPException(status_code=422, detail="CSV file is empty")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV file must be UTF-8 encoded")

    reader = csv.DictReader(StringIO(decoded))
    try:
        columns = _csv_columns(reader.fieldnames)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    catalog = {
        medicine.name.casefold(): medicine
        for medicine in crud.get_medicines(db)
    }
    validated = []
    errors = []
    data_row_count = 0
    for row in reader:
        data_row_count += 1
        if data_row_count > CSV_MAX_ROWS:
            errors.append(f"CSV can contain at most {CSV_MAX_ROWS} data rows")
            break
        row_number = reader.line_num
        name = str(row.get(columns["medicine_name"]) or "").strip()
        quantity_text = str(row.get(columns["quantity"]) or "").strip()
        expiry_text = str(row.get(columns["expiry_date"]) or "").strip()
        if not name and not quantity_text and not expiry_text:
            continue
        medicine = catalog.get(name.casefold())
        if medicine is None:
            errors.append(f'Row {row_number}: medicine "{name or "(blank)"}" is not in the catalog')
            continue
        try:
            quantity = int(quantity_text)
            if quantity < 1 or quantity > 1_000_000:
                raise ValueError
        except ValueError:
            errors.append(f"Row {row_number}: quantity must be a whole number from 1 to 1000000")
            continue
        try:
            expiry_date = _parse_expiry_date(expiry_text)
            if expiry_date < date.today():
                raise ValueError("medicine is already expired")
        except ValueError as exc:
            errors.append(f"Row {row_number}: {exc}")
            continue
        validated.append((row_number, medicine, quantity, expiry_date))

    if not validated and not errors:
        errors.append("CSV contains no inventory rows")
    if errors:
        detail = "; ".join(errors[:10])
        if len(errors) > 10:
            detail += f"; and {len(errors) - 10} more error(s)"
        raise HTTPException(status_code=422, detail=detail)

    imported_rows = []
    try:
        for row_number, medicine, quantity, expiry_date in validated:
            item, previous = crud.restock_inventory(
                db,
                pharmacy_id=pharmacy_id,
                medicine_id=medicine.id,
                quantity=quantity,
                created_by_user_id=current_user.id,
                expiry_date=expiry_date,
                commit=False,
            )
            imported_rows.append({
                "row_number": row_number,
                "medicine": {
                    "id": medicine.id,
                    "name": medicine.name,
                    "category": medicine.category or "General",
                },
                "previous_quantity": previous,
                "added_quantity": quantity,
                "total_quantity": item.quantity,
                "expiry_date": expiry_date,
            })
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "rows_processed": len(imported_rows),
        "medicines_updated": len({row[1].id for row in validated}),
        "total_units_added": sum(row[2] for row in validated),
        "rows": imported_rows,
    }


@router.get("/queue", response_model=list[PharmacyQueueItem])
async def prescription_queue(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Show doctor prescriptions in the medicine-shop dashboard."""
    _ensure_pharmacy_role(current_user)
    return [
        {
            "prescription": prescription_payload(prescription),
            "bill": (
                pharmacy_bill_payload(prescription.pharmacy_bill)
                if prescription.pharmacy_bill else None
            ),
        }
        for prescription in crud.get_pharmacy_prescription_queue(db)
    ]


@router.get("/bills/mine", response_model=list[PharmacyBillResponse])
async def my_pharmacy_bills(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "patient":
        bills = crud.get_patient_pharmacy_bills(db, current_user.id)
    elif current_user.role == "pharmacy":
        bills = crud.get_issued_pharmacy_bills(db, current_user.id)
    elif current_user.role == "admin":
        bills = db.query(PharmacyBill).order_by(PharmacyBill.created_at.desc()).all()
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    return [pharmacy_bill_payload(bill) for bill in bills]


@router.post("/bills", response_model=PharmacyBillResponse, status_code=201)
async def create_bill(
    payload: PharmacyBillCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ensure_pharmacy_role(current_user)
    pharmacy_id = _resolve_pharmacy_id(db, current_user)
    prescription = crud.get_prescription(db, payload.prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if crud.get_pharmacy_bill_for_prescription(db, prescription.id):
        raise HTTPException(
            status_code=409, detail="A bill already exists for this prescription"
        )

    try:
        prescribed_medications = json.loads(prescription.medications or "[]")
    except (json.JSONDecodeError, TypeError):
        prescribed_medications = []

    selected_indices = [item.medication_index for item in payload.items]
    if len(selected_indices) != len(set(selected_indices)):
        raise HTTPException(status_code=422, detail="Each medicine can only be billed once")

    bill_items = []
    for item in payload.items:
        if item.medication_index >= len(prescribed_medications):
            raise HTTPException(
                status_code=422,
                detail="Bill items must come from the doctor's prescription",
            )
        medication = prescribed_medications[item.medication_index]
        if not isinstance(medication, dict) or not medication.get("name"):
            raise HTTPException(status_code=422, detail="Prescription medicine is invalid")
        bill_items.append({
            "medication_index": item.medication_index,
            "medicine_id": medication.get("medicine_id"),
            "name": str(medication.get("name", "")),
            "dosage": str(medication.get("dosage", "")),
            "frequency": str(medication.get("frequency", "")),
            "duration": str(medication.get("duration", "")),
            "quantity": item.quantity,
            "unit_price": item.unit_price,
        })

    try:
        bill = crud.create_pharmacy_bill(
            db,
            prescription=prescription,
            pharmacy_id=pharmacy_id,
            items=bill_items,
            tax_percent=payload.tax_percent,
            notes=payload.notes.strip(),
            manage_inventory=True,
            created_by_user_id=current_user.id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A bill already exists for this prescription"
        )
    return pharmacy_bill_payload(bill)


@router.get("/bills/{bill_id}", response_model=PharmacyBillResponse)
async def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    bill = crud.get_pharmacy_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    _ensure_bill_access(current_user, bill)
    return pharmacy_bill_payload(bill)


@router.patch("/bills/{bill_id}/dispense", response_model=PharmacyBillResponse)
async def dispense_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ensure_pharmacy_role(current_user)
    bill = crud.get_pharmacy_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if current_user.role != "admin" and bill.pharmacy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if bill.status == "dispensed":
        return pharmacy_bill_payload(bill)
    return pharmacy_bill_payload(crud.mark_pharmacy_bill_dispensed(db, bill))
