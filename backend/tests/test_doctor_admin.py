"""API coverage for doctor administration and booking availability."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud
from db.database import Base, get_db
from routers import appointment, doctors
from routers.auth import create_access_token


class DoctorAdminTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "doctor-admin.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.department = crud.get_or_create_department(
            self.db, "General Medicine", "Coordinated care", "GM"
        )
        self.admin = crud.create_user(
            self.db, "admin.test", "hash", role="admin", full_name="Admin Test"
        )
        self.patient = crud.create_user(
            self.db, "patient.test", "hash", role="patient", full_name="Patient Test"
        )

        app = FastAPI()
        app.include_router(doctors.router, prefix="/api/v1")
        app.include_router(appointment.router, prefix="/api/v1/appointments")

        def test_db():
            yield self.db

        app.dependency_overrides[get_db] = test_db
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.admin_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': self.admin.username})}"
        }
        self.patient_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': self.patient.username})}"
        }

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_admin_manages_qualification_availability_and_soft_delete(self):
        created = await self.client.post(
            "/api/v1/admin/doctors",
            headers=self.admin_headers,
            json={
                "username": "dr.new",
                "password": "doctor123",
                "full_name": "Dr. New Doctor",
                "qualification": "MBBS, MD (Medicine)",
                "specialization": "Internal Medicine",
                "department_id": self.department.id,
                "email": "doctor@example.test",
                "phone": "1234567890",
            },
        )
        self.assertEqual(created.status_code, 201)
        doctor = created.json()
        self.assertEqual(doctor["qualification"], "MBBS, MD (Medicine)")
        self.assertTrue(doctor["is_available"])

        unavailable = await self.client.patch(
            f"/api/v1/admin/doctors/{doctor['id']}",
            headers=self.admin_headers,
            json={
                "is_available": False,
                "availability_note": "Available from Monday",
            },
        )
        self.assertEqual(unavailable.status_code, 200)

        directory = await self.client.get(
            f"/api/v1/doctors?department_id={self.department.id}",
            headers=self.patient_headers,
        )
        self.assertEqual(directory.status_code, 200)
        self.assertFalse(directory.json()[0]["is_available"])
        self.assertEqual(directory.json()[0]["availability_note"], "Available from Monday")

        booking = await self.client.post(
            "/api/v1/appointments/book",
            headers=self.patient_headers,
            json={
                "doctor_id": doctor["id"],
                "department_id": self.department.id,
                "reason": "Persistent fever",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(booking.status_code, 409)
        self.assertEqual(booking.json()["detail"], "Available from Monday")

        deleted = await self.client.delete(
            f"/api/v1/admin/doctors/{doctor['id']}", headers=self.admin_headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.json()["is_active"])
        directory = await self.client.get(
            "/api/v1/doctors", headers=self.patient_headers
        )
        self.assertEqual(directory.json(), [])
        admin_directory = await self.client.get(
            "/api/v1/admin/doctors", headers=self.admin_headers
        )
        self.assertEqual(len(admin_directory.json()), 1)
        self.assertFalse(admin_directory.json()[0]["is_active"])


if __name__ == "__main__":
    unittest.main()
