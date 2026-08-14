"""Shared serialization and authorization helpers for hospital workflows."""

import json

from fastapi import HTTPException

from routers.auth import serialize_user
from services.prescription_quantity import suggest_dispense_quantity


def department_payload(department):
    if department is None:
        return None
    return {
        "id": department.id,
        "name": department.name,
        "description": department.description or "",
        "icon": department.icon or "🏥",
    }


def appointment_payload(appointment):
    return {
        "id": appointment.id,
        "patient": serialize_user(appointment.patient),
        "doctor": serialize_user(appointment.doctor),
        "department": department_payload(appointment.department),
        "status": appointment.status,
        "reason": appointment.reason or "",
        "notes": appointment.notes or "",
        "scheduled_at": appointment.scheduled_at,
        "created_at": appointment.created_at,
        "diagnostic_order_count": len(appointment.diagnostic_orders),
    }


def diagnostic_order_payload(order):
    return {
        "id": order.id,
        "appointment_id": order.appointment_id,
        "patient": serialize_user(order.appointment.patient),
        "ordering_doctor": serialize_user(order.ordering_doctor),
        "assigned_lab_tech": (
            serialize_user(order.assigned_lab_tech)
            if order.assigned_lab_tech else None
        ),
        "scan_type": order.scan_type,
        "organ": order.organ,
        "priority": order.priority,
        "status": order.status,
        "clinical_notes": order.clinical_notes or "",
        "scan_id": order.scan_id,
        "created_at": order.created_at,
    }


def prescription_payload(prescription):
    try:
        medications = json.loads(prescription.medications or "[]")
    except (json.JSONDecodeError, TypeError):
        medications = []
    enriched_medications = []
    for medication in medications:
        if not isinstance(medication, dict):
            continue
        suggested_quantity, quantity_basis = suggest_dispense_quantity(medication)
        enriched_medications.append({
            **medication,
            "suggested_quantity": suggested_quantity,
            "quantity_basis": quantity_basis,
        })
    return {
        "id": prescription.id,
        "appointment_id": prescription.appointment_id,
        "doctor": serialize_user(prescription.doctor),
        "patient": serialize_user(prescription.patient),
        "scan_id": prescription.scan_id,
        "medications": enriched_medications,
        "instructions": prescription.instructions or "",
        "diagnosis": prescription.diagnosis or "",
        "created_at": prescription.created_at,
    }


def pharmacy_bill_payload(bill):
    try:
        items = json.loads(bill.items_json or "[]")
    except (json.JSONDecodeError, TypeError):
        items = []
    return {
        "id": bill.id,
        "invoice_number": bill.invoice_number,
        "prescription": prescription_payload(bill.prescription),
        "patient": serialize_user(bill.patient),
        "pharmacy": serialize_user(bill.pharmacy),
        "items": items,
        "subtotal": bill.subtotal,
        "tax_percent": bill.tax_percent,
        "tax_amount": bill.tax_amount,
        "total": bill.total,
        "status": bill.status,
        "notes": bill.notes or "",
        "created_at": bill.created_at,
        "dispensed_at": bill.dispensed_at,
    }


def can_access_appointment(user, appointment) -> bool:
    return (
        user.role == "admin"
        or appointment.patient_id == user.id
        or appointment.doctor_id == user.id
    )


def ensure_appointment_access(user, appointment) -> None:
    if not can_access_appointment(user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")


def can_access_scan(user, scan) -> bool:
    if scan.user_id == user.id or scan.lab_tech_id == user.id or getattr(user, "role", None) == "admin":
        return True
    order = scan.diagnostic_order
    if not order:
        return False
    return (
        order.appointment.patient_id == user.id
        or order.appointment.doctor_id == user.id
        or order.ordering_doctor_id == user.id
        or order.assigned_lab_tech_id == user.id
        or (
            scan.report is not None
            and scan.report.forwarded_to_doctor_id == user.id
        )
    )


def ensure_scan_access(user, scan) -> None:
    if not can_access_scan(user, scan):
        raise HTTPException(status_code=403, detail="Access denied")
