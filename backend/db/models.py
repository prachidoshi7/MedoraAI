"""
MedoraAI — SQLAlchemy ORM Models
Tables: users, departments, appointments, diagnostic_orders, scans, results, reports, prescriptions, case_studies
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Department(Base):
    """Hospital departments (Radiology, Neurology, etc.)."""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="🏥")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    doctors = relationship("User", back_populates="department", foreign_keys="User.department_id")
    appointments = relationship("Appointment", back_populates="department")

    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}')>"


class User(Base):
    """Authentication table with role-based access. Seeded with demo users on first run."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="patient")  # patient, doctor, lab_tech, admin
    full_name = Column(String(150), default="")
    email = Column(String(150), default="")
    phone = Column(String(20), default="")
    specialization = Column(String(100), default="")  # e.g., "Neurologist", "Pulmonologist"
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    department = relationship("Department", back_populates="doctors", foreign_keys=[department_id])
    scans = relationship("Scan", back_populates="user", cascade="all, delete-orphan",
                         foreign_keys="Scan.user_id")

    # Patient relationships
    patient_appointments = relationship("Appointment", back_populates="patient",
                                        foreign_keys="Appointment.patient_id")
    patient_prescriptions = relationship("Prescription", back_populates="patient",
                                         foreign_keys="Prescription.patient_id")
    patient_case_studies = relationship("CaseStudy", back_populates="patient",
                                        foreign_keys="CaseStudy.patient_id")

    # Doctor relationships
    doctor_appointments = relationship("Appointment", back_populates="doctor",
                                       foreign_keys="Appointment.doctor_id")
    ordered_diagnostics = relationship("DiagnosticOrder", back_populates="ordering_doctor",
                                       foreign_keys="DiagnosticOrder.ordering_doctor_id")
    doctor_prescriptions = relationship("Prescription", back_populates="doctor",
                                        foreign_keys="Prescription.doctor_id")

    # Lab tech relationships
    assigned_orders = relationship("DiagnosticOrder", back_populates="assigned_lab_tech",
                                   foreign_keys="DiagnosticOrder.assigned_lab_tech_id")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Appointment(Base):
    """Patient-Doctor appointment records."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    status = Column(String(20), default="requested")  # requested, confirmed, in_progress, completed, cancelled
    reason = Column(Text, default="")  # Patient's complaint / reason for visit
    notes = Column(Text, default="")  # Doctor's consultation notes
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("User", back_populates="patient_appointments",
                           foreign_keys=[patient_id])
    doctor = relationship("User", back_populates="doctor_appointments",
                          foreign_keys=[doctor_id])
    department = relationship("Department", back_populates="appointments")
    diagnostic_orders = relationship("DiagnosticOrder", back_populates="appointment",
                                     cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="appointment",
                                 cascade="all, delete-orphan")
    case_study = relationship("CaseStudy", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment(id={self.id}, patient={self.patient_id}, doctor={self.doctor_id}, status='{self.status}')>"


class DiagnosticOrder(Base):
    """Doctor orders a diagnostic test for a patient."""
    __tablename__ = "diagnostic_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    ordering_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_lab_tech_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scan_type = Column(String(20), nullable=False)  # chest_xray, brain_mri, lung_ct, kidney_us, blood_smear, breast_us
    organ = Column(String(20), nullable=False)  # chest, brain, lung, kidney, blood, breast
    priority = Column(String(10), default="routine")  # routine, urgent, stat
    status = Column(String(20), default="ordered")  # ordered, assigned, in_progress, completed, reviewed
    clinical_notes = Column(Text, default="")  # Why the doctor ordered this test
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=True)  # Linked after scan is uploaded
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    appointment = relationship("Appointment", back_populates="diagnostic_orders")
    ordering_doctor = relationship("User", back_populates="ordered_diagnostics",
                                   foreign_keys=[ordering_doctor_id])
    assigned_lab_tech = relationship("User", back_populates="assigned_orders",
                                     foreign_keys=[assigned_lab_tech_id])
    scan = relationship("Scan", back_populates="diagnostic_order", foreign_keys=[scan_id])

    def __repr__(self):
        return f"<DiagnosticOrder(id={self.id}, type='{self.scan_type}', status='{self.status}')>"


class Scan(Base):
    """Uploaded medical image records."""
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True)  # UUID v4 string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)  # Original filename
    scan_type = Column(String(20), nullable=False, default="chest_xray")
    modality = Column(String(50), default="X-ray")  # "X-ray", "MRI", "CT", "Ultrasound", "Microscopy"
    file_path = Column(String(500), nullable=False)  # /data/uploads/{id}.png
    heatmap_path = Column(String(500))  # /data/heatmaps/{id}.png (NULL until analyzed)
    thumbnail_path = Column(String(500))  # /data/thumbnails/{id}.png
    file_size_bytes = Column(Integer)
    status = Column(String(20), default="uploaded")  # uploaded, analyzing, analyzed, failed
    uploaded_at = Column(DateTime, server_default=func.now())

    # Hospital workflow fields
    lab_tech_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who uploaded

    # Relationships
    user = relationship("User", back_populates="scans", foreign_keys=[user_id])
    result = relationship("Result", back_populates="scan", uselist=False, cascade="all, delete-orphan")
    report = relationship("Report", back_populates="scan", uselist=False, cascade="all, delete-orphan")
    diagnostic_order = relationship("DiagnosticOrder", back_populates="scan",
                                    uselist=False, foreign_keys="DiagnosticOrder.scan_id")

    def __repr__(self):
        return f"<Scan(id='{self.id[:8]}', type='{self.scan_type}', status='{self.status}')>"


class Result(Base):
    """AI inference results. One-to-one with analyzed scans."""
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id"), unique=True, nullable=False)
    top_label = Column(String(100), nullable=False)  # e.g., "Pneumonia" or "Tumor"
    confidence = Column(Float, nullable=False)  # 0.0 – 1.0
    severity = Column(String(20), nullable=False)  # Normal, Mild, Moderate, Severe
    all_scores = Column(Text, nullable=False)  # JSON: {"Pneumonia": 0.87, ...}
    localization_type = Column(String(20), default="heatmap")  # "heatmap" or "bbox"
    bounding_boxes = Column(Text)  # JSON: [{"x1":89,"y1":120,...}, ...]
    analysis_time_ms = Column(Integer)
    analyzed_at = Column(DateTime, server_default=func.now())

    # Relationships
    scan = relationship("Scan", back_populates="result")

    def __repr__(self):
        return f"<Result(scan='{self.scan_id[:8]}', label='{self.top_label}', conf={self.confidence:.2f})>"


class Report(Base):
    """Generated clinical reports. One-to-one with analyzed scans."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id"), unique=True, nullable=False)
    patient_id = Column(String(50), default="DEMO-001")  # Placeholder for demo
    llm_provider = Column(String(20), default="template")  # groq, claude, openai, template
    report_json = Column(Text, nullable=False)  # Full structured report as JSON
    edited_findings = Column(Text)  # Clinician-edited findings (NULL until edited)
    edited_impression = Column(Text)  # Clinician-edited impression (NULL until edited)
    generated_at = Column(DateTime, server_default=func.now())

    # Doctor review fields
    reviewed_by_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    doctor_notes = Column(Text, default="")  # Doctor's additional assessment
    doctor_approved_at = Column(DateTime, nullable=True)
    forwarded_to_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    scan = relationship("Scan", back_populates="report")

    def __repr__(self):
        return f"<Report(scan='{self.scan_id[:8]}', provider='{self.llm_provider}')>"


class Prescription(Base):
    """Doctor's prescription for a patient."""
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=True)  # Linked diagnostic scan
    medications = Column(Text, default="[]")  # JSON: [{name, dosage, frequency, duration}]
    instructions = Column(Text, default="")  # Doctor's notes
    diagnosis = Column(Text, default="")  # Doctor's diagnosis summary
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    appointment = relationship("Appointment", back_populates="prescriptions")
    doctor = relationship("User", back_populates="doctor_prescriptions",
                          foreign_keys=[doctor_id])
    patient = relationship("User", back_populates="patient_prescriptions",
                           foreign_keys=[patient_id])

    def __repr__(self):
        return f"<Prescription(id={self.id}, doctor={self.doctor_id}, patient={self.patient_id})>"


class CaseStudy(Base):
    """Final comprehensive case study combining all findings."""
    __tablename__ = "case_studies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    chief_complaint = Column(Text, default="")
    clinical_history = Column(Text, default="")
    diagnostic_findings = Column(Text, default="")  # Combined AI + doctor findings
    scan_ids = Column(Text, default="[]")  # JSON array of scan IDs
    diagnosis = Column(Text, default="")
    treatment_plan = Column(Text, default="")
    prescriptions_json = Column(Text, default="[]")  # JSON: linked prescriptions
    follow_up_plan = Column(Text, default="")
    doctor_notes = Column(Text, default="")
    status = Column(String(20), default="draft")  # draft, preliminary, final
    preliminary_at = Column(DateTime, nullable=True)
    finalized_at = Column(DateTime, nullable=True)
    finalized_by_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("User", back_populates="patient_case_studies",
                           foreign_keys=[patient_id])
    appointment = relationship("Appointment", back_populates="case_study")

    def __repr__(self):
        return f"<CaseStudy(id={self.id}, patient={self.patient_id}, status='{self.status}')>"
