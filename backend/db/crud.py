"""
MedoraAI — CRUD Operations
Database create/read/update operations for all models.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .models import (
    Appointment,
    CaseStudy,
    Department,
    DiagnosticOrder,
    MedicineCatalog,
    PharmacyBill,
    PharmacyInventory,
    PharmacyStockMovement,
    Prescription,
    Report,
    Result,
    Scan,
    User,
)


# ============================================================
# USER CRUD
# ============================================================

def create_user(
    db: Session,
    username: str,
    hashed_password: str,
    role: str = "patient",
    full_name: str = "",
    email: str = "",
    phone: str = "",
    specialization: str = "",
    qualification: str = "",
    department_id: int | None = None,
) -> User:
    """Create a new user."""
    user = User(
        username=username,
        hashed_password=hashed_password,
        role=role,
        full_name=full_name,
        email=email,
        phone=phone,
        specialization=specialization,
        qualification=qualification,
        department_id=department_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_users_by_role(db: Session, role: str) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == role, User.is_active.is_(True))
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )


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
    lab_tech_id: int | None = None,
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
        lab_tech_id=lab_tech_id,
        status="uploaded",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


# ============================================================
# DEPARTMENTS AND DOCTORS
# ============================================================

def get_or_create_department(
    db: Session, name: str, description: str = "", icon: str = "🏥"
) -> Department:
    department = db.query(Department).filter(Department.name == name).first()
    if department is None:
        department = Department(name=name, description=description, icon=icon)
        db.add(department)
        db.commit()
        db.refresh(department)
    return department


def get_departments(db: Session) -> list[Department]:
    return (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .order_by(Department.name.asc())
        .all()
    )


def get_department(db: Session, department_id: int) -> Department | None:
    return db.query(Department).filter(Department.id == department_id).first()


def get_doctors_by_department(
    db: Session, department_id: int | None = None
) -> list[User]:
    query = db.query(User).filter(User.role == "doctor", User.is_active.is_(True))
    if department_id is not None:
        query = query.filter(User.department_id == department_id)
    return query.order_by(User.full_name.asc()).all()


def get_all_doctors(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "doctor")
        .order_by(User.is_active.desc(), User.full_name.asc(), User.username.asc())
        .all()
    )


# ============================================================
# MEDICINE CATALOG AND PHARMACY INVENTORY
# ============================================================

def seed_medicine_catalog(db: Session, medicines: list[tuple[str, str]]) -> None:
    existing = {name for (name,) in db.query(MedicineCatalog.name).all()}
    additions = [
        MedicineCatalog(name=name, category=category)
        for name, category in medicines
        if name not in existing
    ]
    if additions:
        db.add_all(additions)
        db.commit()


def link_legacy_prescriptions_to_catalog(db: Session) -> int:
    """Give older name-only prescription lines catalog IDs without losing history."""
    catalog_by_name = {
        item.name.casefold(): item for item in db.query(MedicineCatalog).all()
    }
    updated = 0
    prescriptions = db.query(Prescription).all()
    for prescription in prescriptions:
        try:
            medications = json.loads(prescription.medications or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        changed = False
        for medication in medications:
            if not isinstance(medication, dict) or medication.get("medicine_id"):
                continue
            name = str(medication.get("name") or "").strip()
            if not name:
                continue
            medicine = catalog_by_name.get(name.casefold())
            if medicine is None:
                medicine = MedicineCatalog(name=name, category="Legacy prescription")
                db.add(medicine)
                db.flush()
                catalog_by_name[name.casefold()] = medicine
            medication["medicine_id"] = medicine.id
            medication["name"] = medicine.name
            changed = True
        if changed:
            prescription.medications = json.dumps(medications)
            updated += 1
    if updated:
        db.commit()
    return updated


def get_medicines(db: Session, include_inactive: bool = False) -> list[MedicineCatalog]:
    query = db.query(MedicineCatalog)
    if not include_inactive:
        query = query.filter(MedicineCatalog.is_active.is_(True))
    return query.order_by(MedicineCatalog.category.asc(), MedicineCatalog.name.asc()).all()


def get_medicine(db: Session, medicine_id: int) -> MedicineCatalog | None:
    return db.query(MedicineCatalog).filter(MedicineCatalog.id == medicine_id).first()


def get_medicine_by_name(db: Session, name: str) -> MedicineCatalog | None:
    normalized = name.strip().casefold()
    return next(
        (medicine for medicine in get_medicines(db) if medicine.name.casefold() == normalized),
        None,
    )


def get_inventory(db: Session, pharmacy_id: int) -> list[PharmacyInventory]:
    return (
        db.query(PharmacyInventory)
        .filter(PharmacyInventory.pharmacy_id == pharmacy_id)
        .join(PharmacyInventory.medicine)
        .order_by(MedicineCatalog.name.asc())
        .all()
    )


def get_inventory_item(
    db: Session, pharmacy_id: int, medicine_id: int
) -> PharmacyInventory | None:
    return (
        db.query(PharmacyInventory)
        .filter(
            PharmacyInventory.pharmacy_id == pharmacy_id,
            PharmacyInventory.medicine_id == medicine_id,
        )
        .first()
    )


def restock_inventory(
    db: Session,
    *,
    pharmacy_id: int,
    medicine_id: int,
    quantity: int,
    created_by_user_id: int,
    expiry_date=None,
    commit: bool = True,
) -> tuple[PharmacyInventory, int]:
    item = get_inventory_item(db, pharmacy_id, medicine_id)
    if item is None:
        item = PharmacyInventory(
            pharmacy_id=pharmacy_id, medicine_id=medicine_id, quantity=0
        )
        db.add(item)
        db.flush()
    previous_quantity = item.quantity
    item.quantity += quantity
    if expiry_date is not None:
        if previous_quantity <= 0 or item.expiry_date is None:
            item.expiry_date = expiry_date
        else:
            item.expiry_date = min(item.expiry_date, expiry_date)
    db.add(PharmacyStockMovement(
        pharmacy_id=pharmacy_id,
        medicine_id=medicine_id,
        movement_type="restock",
        quantity_delta=quantity,
        balance_after=item.quantity,
        created_by_user_id=created_by_user_id,
    ))
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item, previous_quantity


# ============================================================
# APPOINTMENTS
# ============================================================

def create_appointment(
    db: Session,
    patient_id: int,
    doctor_id: int,
    department_id: int | None,
    reason: str,
    scheduled_at,
) -> Appointment:
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        reason=reason,
        scheduled_at=scheduled_at,
        status="requested",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_appointment(db: Session, appointment_id: int) -> Appointment | None:
    return db.query(Appointment).filter(Appointment.id == appointment_id).first()


def get_patient_appointments(db: Session, patient_id: int) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc(), Appointment.created_at.desc())
        .all()
    )


def get_doctor_appointments(db: Session, doctor_id: int) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(Appointment.doctor_id == doctor_id)
        .order_by(Appointment.scheduled_at.asc(), Appointment.created_at.desc())
        .all()
    )


def update_appointment_status(
    db: Session, appointment: Appointment, appointment_status: str
) -> Appointment:
    appointment.status = appointment_status
    db.commit()
    db.refresh(appointment)
    return appointment


def update_appointment_notes(
    db: Session, appointment: Appointment, notes: str
) -> Appointment:
    appointment.notes = notes
    db.commit()
    db.refresh(appointment)
    return appointment


# ============================================================
# DIAGNOSTIC ORDERS
# ============================================================

def create_diagnostic_order(
    db: Session,
    appointment_id: int,
    ordering_doctor_id: int,
    scan_type: str,
    organ: str,
    priority: str,
    clinical_notes: str,
) -> DiagnosticOrder:
    order = DiagnosticOrder(
        appointment_id=appointment_id,
        ordering_doctor_id=ordering_doctor_id,
        scan_type=scan_type,
        organ=organ,
        priority=priority,
        clinical_notes=clinical_notes,
        status="ordered",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_diagnostic_order(db: Session, order_id: int) -> DiagnosticOrder | None:
    return db.query(DiagnosticOrder).filter(DiagnosticOrder.id == order_id).first()


def get_pending_orders(db: Session) -> list[DiagnosticOrder]:
    return (
        db.query(DiagnosticOrder)
        .filter(DiagnosticOrder.status.in_(["ordered", "assigned", "in_progress"]))
        .order_by(
            DiagnosticOrder.priority.desc(),
            DiagnosticOrder.created_at.asc(),
        )
        .all()
    )


def get_orders_for_user(db: Session, user: User) -> list[DiagnosticOrder]:
    query = db.query(DiagnosticOrder)
    if user.role == "doctor":
        query = query.filter(DiagnosticOrder.ordering_doctor_id == user.id)
    elif user.role == "lab_tech":
        query = query.filter(
            (DiagnosticOrder.assigned_lab_tech_id == user.id)
            | (DiagnosticOrder.status == "ordered")
        )
    elif user.role == "patient":
        query = query.join(Appointment).filter(Appointment.patient_id == user.id)
    return query.order_by(DiagnosticOrder.created_at.desc()).all()


def assign_lab_tech(
    db: Session, order: DiagnosticOrder, lab_tech_id: int
) -> DiagnosticOrder:
    order.assigned_lab_tech_id = lab_tech_id
    order.status = "assigned"
    db.commit()
    db.refresh(order)
    return order


def link_scan_to_order(
    db: Session, order: DiagnosticOrder, scan: Scan
) -> DiagnosticOrder:
    order.scan_id = scan.id
    order.status = "in_progress"
    scan.lab_tech_id = scan.lab_tech_id or order.assigned_lab_tech_id
    db.commit()
    db.refresh(order)
    return order


def complete_order_for_scan(db: Session, scan_id: str) -> DiagnosticOrder | None:
    order = (
        db.query(DiagnosticOrder)
        .filter(DiagnosticOrder.scan_id == scan_id)
        .first()
    )
    if order:
        order.status = "completed"
        db.commit()
        db.refresh(order)
    return order


# ============================================================
# PRESCRIPTIONS
# ============================================================

def create_prescription(
    db: Session,
    appointment_id: int,
    doctor_id: int,
    patient_id: int,
    medications: list[dict],
    instructions: str = "",
    diagnosis: str = "",
    scan_id: str | None = None,
) -> Prescription:
    prescription = Prescription(
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        scan_id=scan_id,
        medications=json.dumps(medications),
        instructions=instructions,
        diagnosis=diagnosis,
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def get_prescription(db: Session, prescription_id: int) -> Prescription | None:
    return db.query(Prescription).filter(Prescription.id == prescription_id).first()


def get_patient_prescriptions(db: Session, patient_id: int) -> list[Prescription]:
    return (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )


# ============================================================
# PHARMACY BILLS
# ============================================================

def get_pharmacy_prescription_queue(db: Session) -> list[Prescription]:
    """Return every doctor-issued prescription for the pharmacy worklist."""
    return db.query(Prescription).order_by(Prescription.created_at.desc()).all()


def get_pharmacy_bill(db: Session, bill_id: int) -> PharmacyBill | None:
    return db.query(PharmacyBill).filter(PharmacyBill.id == bill_id).first()


def get_pharmacy_bill_for_prescription(
    db: Session, prescription_id: int
) -> PharmacyBill | None:
    return (
        db.query(PharmacyBill)
        .filter(PharmacyBill.prescription_id == prescription_id)
        .first()
    )


def get_patient_pharmacy_bills(db: Session, patient_id: int) -> list[PharmacyBill]:
    return (
        db.query(PharmacyBill)
        .filter(PharmacyBill.patient_id == patient_id)
        .order_by(PharmacyBill.created_at.desc())
        .all()
    )


def get_issued_pharmacy_bills(db: Session, pharmacy_id: int) -> list[PharmacyBill]:
    return (
        db.query(PharmacyBill)
        .filter(PharmacyBill.pharmacy_id == pharmacy_id)
        .order_by(PharmacyBill.created_at.desc())
        .all()
    )


def create_pharmacy_bill(
    db: Session,
    *,
    prescription: Prescription,
    pharmacy_id: int,
    items: list[dict],
    tax_percent: float = 0,
    notes: str = "",
    manage_inventory: bool = False,
    created_by_user_id: int | None = None,
) -> PharmacyBill:
    """Create an immutable bill and optionally deduct stock in one transaction."""
    money = Decimal("0.01")
    normalized_items = []
    subtotal = Decimal("0.00")
    for item in items:
        unit_price = Decimal(str(item["unit_price"])).quantize(money, ROUND_HALF_UP)
        line_total = (unit_price * int(item["quantity"])).quantize(money, ROUND_HALF_UP)
        subtotal += line_total
        normalized_items.append({
            **item,
            "unit_price": float(unit_price),
            "line_total": float(line_total),
        })

    subtotal = subtotal.quantize(money, ROUND_HALF_UP)
    normalized_tax = Decimal(str(tax_percent)).quantize(money, ROUND_HALF_UP)
    tax_amount = (subtotal * normalized_tax / Decimal("100")).quantize(
        money, ROUND_HALF_UP
    )
    total = (subtotal + tax_amount).quantize(money, ROUND_HALF_UP)
    invoice_number = (
        f"MED-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:6].upper()}"
    )

    bill = PharmacyBill(
        invoice_number=invoice_number,
        prescription_id=prescription.id,
        patient_id=prescription.patient_id,
        pharmacy_id=pharmacy_id,
        items_json=json.dumps(normalized_items),
        subtotal=float(subtotal),
        tax_percent=float(normalized_tax),
        tax_amount=float(tax_amount),
        total=float(total),
        status="billed",
        notes=notes,
    )
    db.add(bill)
    db.flush()

    if manage_inventory:
        for item in normalized_items:
            medicine_id = item.get("medicine_id")
            if not medicine_id:
                raise ValueError(f"{item.get('name', 'Medicine')} is not linked to the medicine catalog")
            inventory = get_inventory_item(db, pharmacy_id, int(medicine_id))
            requested = int(item["quantity"])
            available = inventory.quantity if inventory else 0
            if available < requested:
                raise ValueError(
                    f"Only {available} unit(s) of {item.get('name', 'this medicine')} are available"
                )
            inventory.quantity -= requested
            if inventory.quantity == 0:
                inventory.expiry_date = None
            db.add(PharmacyStockMovement(
                pharmacy_id=pharmacy_id,
                medicine_id=int(medicine_id),
                movement_type="sale",
                quantity_delta=-requested,
                balance_after=inventory.quantity,
                reference_bill_id=bill.id,
                created_by_user_id=created_by_user_id or pharmacy_id,
            ))

    db.commit()
    db.refresh(bill)
    return bill


def mark_pharmacy_bill_dispensed(db: Session, bill: PharmacyBill) -> PharmacyBill:
    bill.status = "dispensed"
    bill.dispensed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bill)
    return bill


# ============================================================
# CASE STUDIES
# ============================================================

def get_case_study(db: Session, case_study_id: int) -> CaseStudy | None:
    return db.query(CaseStudy).filter(CaseStudy.id == case_study_id).first()


def get_case_study_by_appointment(
    db: Session, appointment_id: int
) -> CaseStudy | None:
    return (
        db.query(CaseStudy)
        .filter(CaseStudy.appointment_id == appointment_id)
        .first()
    )


def get_patient_case_studies(db: Session, patient_id: int) -> list[CaseStudy]:
    return (
        db.query(CaseStudy)
        .filter(CaseStudy.patient_id == patient_id)
        .order_by(CaseStudy.created_at.desc())
        .all()
    )


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
    patient_id: str | None = None,
) -> Report:
    """Create or replace a generated report while preserving the scan record."""
    resolved_patient_id = patient_id or str(report_data.get("patient_id") or "DEMO-001")
    report = get_report_by_scan(db, scan_id)
    if report is None:
        return create_report(db, scan_id, report_data, llm_provider, resolved_patient_id)
    report.patient_id = resolved_patient_id or report.patient_id
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
