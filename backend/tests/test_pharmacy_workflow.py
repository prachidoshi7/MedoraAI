"""API coverage for prescription handoff and medicine-shop billing."""

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud
from db.database import Base, get_db
from db.models import PharmacyStockMovement
from routers import pharmacy
from routers.auth import create_access_token


class PharmacyWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "pharmacy.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        patient = crud.create_user(
            self.db, "patient.rx", "hash", role="patient", full_name="Rx Patient"
        )
        doctor = crud.create_user(
            self.db, "doctor.rx", "hash", role="doctor", full_name="Dr. Rx"
        )
        shop = crud.create_user(
            self.db,
            "shop.rx",
            "hash",
            role="pharmacy",
            full_name="Rx Medicine Shop",
            phone="1234567890",
        )
        self.shop = shop
        appointment = crud.create_appointment(
            self.db,
            patient_id=patient.id,
            doctor_id=doctor.id,
            department_id=None,
            reason="Fever",
            scheduled_at=datetime.now(timezone.utc),
        )
        crud.seed_medicine_catalog(
            self.db, [("Paracetamol 500 mg Tablet", "Pain & fever")]
        )
        self.medicine = crud.get_medicines(self.db)[0]
        self.prescription = crud.create_prescription(
            self.db,
            appointment_id=appointment.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            medications=[{
                "medicine_id": self.medicine.id,
                "name": self.medicine.name,
                "dosage": "500 mg",
                "frequency": "Twice daily",
                "duration": "3 days",
            }],
            diagnosis="Viral fever",
        )

        app = FastAPI()
        app.include_router(pharmacy.router, prefix="/api/v1/pharmacy")

        def test_db():
            yield self.db

        app.dependency_overrides[get_db] = test_db
        self.app = app
        self.patient_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': patient.username})}"
        }
        self.shop_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': shop.username})}"
        }

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_pharmacy_bills_only_prescribed_items_and_patient_receives_bill(self):
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )
        self.addAsyncCleanup(client.aclose)

        queue = await client.get("/api/v1/pharmacy/queue", headers=self.shop_headers)
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()[0]["prescription"]["id"], self.prescription.id)
        self.assertEqual(
            queue.json()[0]["prescription"]["medications"][0]["suggested_quantity"],
            6,
        )

        restocked = await client.post(
            "/api/v1/pharmacy/inventory/restock",
            headers=self.shop_headers,
            json={"medicine_id": self.medicine.id, "new_quantity": 5},
        )
        self.assertEqual(restocked.status_code, 200)
        self.assertEqual(restocked.json()["previous_quantity"], 0)
        self.assertEqual(restocked.json()["total_quantity"], 5)

        invalid = await client.post(
            "/api/v1/pharmacy/bills",
            headers=self.shop_headers,
            json={
                "prescription_id": self.prescription.id,
                "items": [{"medication_index": 1, "quantity": 1, "unit_price": 10}],
                "tax_percent": 0,
                "notes": "",
            },
        )
        self.assertEqual(invalid.status_code, 422)

        created = await client.post(
            "/api/v1/pharmacy/bills",
            headers=self.shop_headers,
            json={
                "prescription_id": self.prescription.id,
                "items": [{"medication_index": 0, "quantity": 3, "unit_price": 12.50}],
                "tax_percent": 5,
                "notes": "Pickup at front counter",
            },
        )
        self.assertEqual(created.status_code, 201)
        bill = created.json()
        self.assertEqual(bill["items"][0]["name"], "Paracetamol 500 mg Tablet")
        self.assertEqual(bill["subtotal"], 37.5)
        self.assertEqual(bill["tax_amount"], 1.88)
        self.assertEqual(bill["total"], 39.38)
        self.assertEqual(bill["pharmacy"]["full_name"], "Rx Medicine Shop")

        patient_bills = await client.get(
            "/api/v1/pharmacy/bills/mine", headers=self.patient_headers
        )
        self.assertEqual(patient_bills.status_code, 200)
        self.assertEqual(patient_bills.json()[0]["id"], bill["id"])
        self.assertEqual(
            (await client.get("/api/v1/pharmacy/queue", headers=self.patient_headers)).status_code,
            403,
        )

        inventory = await client.get(
            "/api/v1/pharmacy/inventory", headers=self.shop_headers
        )
        self.assertEqual(inventory.json()[0]["current_quantity"], 2)
        movements = self.db.query(PharmacyStockMovement).order_by(PharmacyStockMovement.id).all()
        self.assertEqual([item.quantity_delta for item in movements], [5, -3])

        repeated = await client.post(
            "/api/v1/pharmacy/bills",
            headers=self.shop_headers,
            json={
                "prescription_id": self.prescription.id,
                "items": [{"medication_index": 0, "quantity": 1, "unit_price": 12.50}],
                "tax_percent": 0,
                "notes": "",
            },
        )
        self.assertEqual(repeated.status_code, 409)
        inventory = await client.get(
            "/api/v1/pharmacy/inventory", headers=self.shop_headers
        )
        self.assertEqual(inventory.json()[0]["current_quantity"], 2)

    async def test_insufficient_stock_does_not_create_a_bill_or_change_inventory(self):
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )
        self.addAsyncCleanup(client.aclose)
        await client.post(
            "/api/v1/pharmacy/inventory/restock",
            headers=self.shop_headers,
            json={"medicine_id": self.medicine.id, "new_quantity": 2},
        )
        response = await client.post(
            "/api/v1/pharmacy/bills",
            headers=self.shop_headers,
            json={
                "prescription_id": self.prescription.id,
                "items": [{"medication_index": 0, "quantity": 3, "unit_price": 12.50}],
                "tax_percent": 0,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Only 2 unit(s)", response.json()["detail"])
        self.assertIsNone(crud.get_pharmacy_bill_for_prescription(self.db, self.prescription.id))
        self.assertEqual(
            crud.get_inventory_item(self.db, self.shop.id, self.medicine.id).quantity, 2
        )

    async def test_csv_import_updates_stock_and_expiry_atomically(self):
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )
        self.addAsyncCleanup(client.aclose)
        expiry = date.today() + timedelta(days=365)
        content = (
            "medicine_name,quantity,expiry_date\n"
            f"{self.medicine.name},12,{expiry.isoformat()}\n"
        )

        imported = await client.post(
            "/api/v1/pharmacy/inventory/import-csv",
            headers=self.shop_headers,
            files={"file": ("inventory.csv", content, "text/csv")},
        )

        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["rows_processed"], 1)
        self.assertEqual(imported.json()["total_units_added"], 12)
        stock = crud.get_inventory_item(self.db, self.shop.id, self.medicine.id)
        self.db.refresh(stock)
        self.assertEqual(stock.quantity, 12)
        self.assertEqual(stock.expiry_date, expiry)

        invalid_content = (
            "medicine_name,quantity,expiry_date\n"
            f"{self.medicine.name},5,{expiry.isoformat()}\n"
            f"Unknown Medicine,9,{expiry.isoformat()}\n"
        )
        invalid = await client.post(
            "/api/v1/pharmacy/inventory/import-csv",
            headers=self.shop_headers,
            files={"file": ("inventory.csv", invalid_content, "text/csv")},
        )

        self.assertEqual(invalid.status_code, 422)
        self.db.refresh(stock)
        self.assertEqual(stock.quantity, 12)

    async def test_bill_defaults_to_editable_eighteen_percent_gst(self):
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )
        self.addAsyncCleanup(client.aclose)
        await client.post(
            "/api/v1/pharmacy/inventory/restock",
            headers=self.shop_headers,
            json={"medicine_id": self.medicine.id, "new_quantity": 10},
        )

        created = await client.post(
            "/api/v1/pharmacy/bills",
            headers=self.shop_headers,
            json={
                "prescription_id": self.prescription.id,
                "items": [{"medication_index": 0, "quantity": 2, "unit_price": 100}],
                "notes": "",
            },
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["tax_percent"], 18.0)
        self.assertEqual(created.json()["tax_amount"], 36.0)
        self.assertEqual(created.json()["total"], 236.0)


if __name__ == "__main__":
    unittest.main()
