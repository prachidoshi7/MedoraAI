"""Integration coverage for the v2 hospital journey foundation."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud
from db.database import Base


class HospitalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "workflow.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_patient_to_doctor_to_lab_to_case_record(self):
        medicine = crud.get_or_create_department(
            self.db, "General Medicine", "Coordinated care", "✦"
        )
        radiology = crud.get_or_create_department(
            self.db, "Radiology", "Diagnostic imaging", "⌁"
        )
        patient = crud.create_user(
            self.db, "patient.test", "hash", role="patient", full_name="Test Patient"
        )
        doctor = crud.create_user(
            self.db,
            "doctor.test",
            "hash",
            role="doctor",
            full_name="Dr. Test",
            department_id=medicine.id,
        )
        lab_tech = crud.create_user(
            self.db,
            "lab.test",
            "hash",
            role="lab_tech",
            full_name="Lab Test",
            department_id=radiology.id,
        )
        pharmacy = crud.create_user(
            self.db,
            "pharmacy.test",
            "hash",
            role="pharmacy",
            full_name="Test Pharmacy",
        )

        appointment = crud.create_appointment(
            self.db,
            patient_id=patient.id,
            doctor_id=doctor.id,
            department_id=medicine.id,
            reason="Persistent cough",
            scheduled_at=datetime.now(timezone.utc),
        )
        crud.update_appointment_status(self.db, appointment, "confirmed")
        order = crud.create_diagnostic_order(
            self.db,
            appointment_id=appointment.id,
            ordering_doctor_id=doctor.id,
            scan_type="lung_ct",
            organ="lung",
            priority="urgent",
            clinical_notes="Evaluate persistent pulmonary symptoms",
        )
        crud.assign_lab_tech(self.db, order, lab_tech.id)
        scan = crud.create_scan(
            self.db,
            scan_id="test-scan-id",
            user_id=patient.id,
            filename="lung.png",
            scan_type="lung_ct",
            modality="CT",
            file_path="/tmp/lung.png",
            lab_tech_id=lab_tech.id,
        )
        crud.link_scan_to_order(self.db, order, scan)
        crud.complete_order_for_scan(self.db, scan.id)
        prescription = crud.create_prescription(
            self.db,
            appointment_id=appointment.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            scan_id=scan.id,
            medications=[{
                "name": "Example medication",
                "dosage": "1 tablet",
                "frequency": "Daily",
                "duration": "5 days",
            }],
            diagnosis="Clinical review pending",
        )
        self.assertEqual(crud.link_legacy_prescriptions_to_catalog(self.db), 1)
        self.db.refresh(prescription)
        linked_medication = json.loads(prescription.medications)[0]
        self.assertIsInstance(linked_medication["medicine_id"], int)
        self.assertEqual(linked_medication["name"], "Example medication")
        bill = crud.create_pharmacy_bill(
            self.db,
            prescription=prescription,
            pharmacy_id=pharmacy.id,
            items=[{
                "medication_index": 0,
                "name": "Example medication",
                "dosage": "1 tablet",
                "frequency": "Daily",
                "duration": "5 days",
                "quantity": 2,
                "unit_price": 125.25,
            }],
            tax_percent=5,
            notes="Collect from the hospital pharmacy",
        )

        self.assertEqual(crud.get_patient_appointments(self.db, patient.id)[0].status, "confirmed")
        self.assertEqual(crud.get_pending_orders(self.db), [])
        self.assertEqual(crud.get_diagnostic_order(self.db, order.id).status, "completed")
        self.assertEqual(crud.get_patient_prescriptions(self.db, patient.id)[0].id, prescription.id)
        self.assertEqual(crud.get_patient_pharmacy_bills(self.db, patient.id)[0].id, bill.id)
        self.assertEqual(bill.subtotal, 250.50)
        self.assertEqual(bill.tax_amount, 12.53)
        self.assertEqual(bill.total, 263.03)
        self.assertEqual(prescription.pharmacy_bill.id, bill.id)
        self.assertEqual(scan.diagnostic_order.id, order.id)


if __name__ == "__main__":
    unittest.main()
