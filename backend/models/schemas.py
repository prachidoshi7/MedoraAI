"""
MedoraAI — Pydantic Request/Response Schemas
Defines all API contracts for the REST endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ============================================================
# AUTHENTICATION
# ============================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 8 hours in seconds
    user: "UserSummary"


class UserSummary(BaseModel):
    id: int
    username: str
    role: Literal["patient", "doctor", "lab_tech", "admin"]
    full_name: str = ""
    email: str = ""
    phone: str = ""
    specialization: str = ""
    department_id: Optional[int] = None
    department_name: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)


class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    icon: str = "🏥"


class DoctorResponse(UserSummary):
    department: Optional[DepartmentResponse] = None


# ============================================================
# HOSPITAL WORKFLOW
# ============================================================

AppointmentStatus = Literal["requested", "confirmed", "in_progress", "completed", "cancelled"]
DiagnosticStatus = Literal["ordered", "assigned", "in_progress", "completed", "reviewed"]


class AppointmentCreate(BaseModel):
    doctor_id: int
    department_id: Optional[int] = None
    reason: str = Field(..., min_length=3, max_length=2000)
    scheduled_at: datetime


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class AppointmentNotesUpdate(BaseModel):
    notes: str = Field(..., max_length=10000)


class AppointmentResponse(BaseModel):
    id: int
    patient: UserSummary
    doctor: UserSummary
    department: Optional[DepartmentResponse] = None
    status: AppointmentStatus
    reason: str
    notes: str
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    diagnostic_order_count: int = 0


class DiagnosticOrderCreate(BaseModel):
    appointment_id: int
    scan_type: Literal["chest_xray", "brain_mri", "lung_ct", "kidney_us"]
    priority: Literal["routine", "urgent", "stat"] = "routine"
    clinical_notes: str = Field(default="", max_length=5000)


class DiagnosticOrderResponse(BaseModel):
    id: int
    appointment_id: int
    patient: UserSummary
    ordering_doctor: UserSummary
    assigned_lab_tech: Optional[UserSummary] = None
    scan_type: str
    organ: str
    priority: str
    status: DiagnosticStatus
    clinical_notes: str
    scan_id: Optional[str] = None
    created_at: Optional[datetime] = None


class Medication(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(default="", max_length=100)
    frequency: str = Field(default="", max_length=100)
    duration: str = Field(default="", max_length=100)


class PrescriptionCreate(BaseModel):
    appointment_id: int
    scan_id: Optional[str] = None
    medications: list[Medication] = Field(default_factory=list, max_length=30)
    instructions: str = Field(default="", max_length=10000)
    diagnosis: str = Field(default="", max_length=5000)


class PrescriptionUpdate(BaseModel):
    medications: Optional[list[Medication]] = None
    instructions: Optional[str] = Field(default=None, max_length=10000)
    diagnosis: Optional[str] = Field(default=None, max_length=5000)


class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int
    doctor: UserSummary
    patient: UserSummary
    scan_id: Optional[str] = None
    medications: list[Medication]
    instructions: str
    diagnosis: str
    created_at: Optional[datetime] = None


class CaseStudyGenerate(BaseModel):
    appointment_id: int
    clinical_history: str = Field(default="", max_length=10000)
    diagnosis: str = Field(default="", max_length=10000)
    treatment_plan: str = Field(default="", max_length=10000)
    follow_up_plan: str = Field(default="", max_length=10000)


class CaseStudyUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    clinical_history: Optional[str] = None
    diagnostic_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    follow_up_plan: Optional[str] = None
    doctor_notes: Optional[str] = None
    status: Optional[Literal["draft", "preliminary"]] = None


class CaseStudyResponse(BaseModel):
    id: int
    patient: UserSummary
    appointment_id: Optional[int] = None
    chief_complaint: str
    clinical_history: str
    diagnostic_findings: str
    scan_ids: list[str]
    diagnosis: str
    treatment_plan: str
    prescriptions: list[PrescriptionResponse]
    follow_up_plan: str
    doctor_notes: str
    status: Literal["draft", "preliminary", "final"]
    preliminary_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DoctorReviewRequest(BaseModel):
    edited_findings: Optional[str] = None
    edited_impression: Optional[str] = None
    doctor_notes: str = Field(default="", max_length=10000)
    approve: bool = True


class ForwardReportRequest(BaseModel):
    doctor_id: int


# ============================================================
# SCAN UPLOAD
# ============================================================

class UploadResponse(BaseModel):
    scan_id: str
    filename: str
    scan_type: str  # "chest_xray" or "brain_mri"
    modality: str
    file_size_bytes: int
    status: str
    uploaded_at: str
    thumbnail_url: str


# ============================================================
# ANALYSIS
# ============================================================

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    label: str
    confidence: float


class ClassificationDetail(BaseModel):
    top_label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Literal["Normal", "Mild", "Moderate", "Severe"]
    all_scores: dict[str, float]


class LocalizationDetail(BaseModel):
    type: str = "heatmap"
    heatmap_url: str
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    scan_id: str
    scan_type: str
    status: str
    classification: ClassificationDetail
    localization: LocalizationDetail
    analysis_time_ms: int
    analyzed_at: str


# ============================================================
# REPORT
# ============================================================

class ReportData(BaseModel):
    patient_id: str = "DEMO-001"
    scan_date: str
    scan_type: str
    modality: str
    top_label: str = ""
    confidence: float = 0.0
    all_scores: dict[str, float] = Field(default_factory=dict)
    clinical_history: str = "Not provided."
    technique: str = ""
    comparison: str = "No prior imaging was supplied for comparison."
    image_quality: str = ""
    findings: str
    impression: str
    differential_diagnosis: str = ""
    recommendations: str = ""
    critical_communication: str = "No critical communication generated."
    severity: str
    disclaimer: str
    generated_at: str
    heatmap_target_label: str = ""
    is_low_confidence: bool = False
    methodology: str = ""
    limitations: str = ""


class ReportResponse(BaseModel):
    scan_id: str
    report: ReportData


class PDFRequest(BaseModel):
    """Optional edited report text for PDF generation."""
    edited_clinical_history: Optional[str] = None
    edited_technique: Optional[str] = None
    edited_comparison: Optional[str] = None
    edited_image_quality: Optional[str] = None
    edited_findings: Optional[str] = None
    edited_impression: Optional[str] = None
    edited_differential_diagnosis: Optional[str] = None
    edited_recommendations: Optional[str] = None
    edited_critical_communication: Optional[str] = None


class PatientSummaryRequest(BaseModel):
    language: str = Field(default="English", min_length=2, max_length=30)


class PatientSummaryResponse(BaseModel):
    scan_id: str
    language: str
    summary: str
    supported_languages: list[str]


# ============================================================
# HISTORY
# ============================================================

class HistoryScan(BaseModel):
    scan_id: str
    filename: str
    scan_type: str
    top_label: str
    confidence: float
    severity: str
    status: str
    uploaded_at: str
    thumbnail_url: str


class HistoryResponse(BaseModel):
    scans: list[HistoryScan]
    total: int


class DeleteScansRequest(BaseModel):
    scan_ids: list[str] = Field(..., min_length=1, max_length=50)


class DeleteScansResponse(BaseModel):
    deleted: int
    scan_ids: list[str] = Field(default_factory=list)


# ============================================================
# COMMON
# ============================================================

class ErrorResponse(BaseModel):
    detail: str
    error_code: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    models: dict[str, str]
