"""
MedoraAI — Pydantic Request/Response Schemas
Defines all API contracts for the REST endpoints.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import date, datetime


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
    role: Literal["patient", "doctor", "lab_tech", "pharmacy", "admin"]
    full_name: str = ""
    email: str = ""
    phone: str = ""
    avatar_url: str = ""
    specialization: str = ""
    qualification: str = ""
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    is_active: bool = True
    is_available: bool = True
    availability_note: str = ""


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)


class ProfileUpdate(BaseModel):
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


class DoctorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=150)
    qualification: str = Field(..., min_length=2, max_length=150)
    specialization: str = Field(..., min_length=2, max_length=100)
    department_id: int
    email: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)


class DoctorUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    qualification: Optional[str] = Field(default=None, min_length=2, max_length=150)
    specialization: Optional[str] = Field(default=None, min_length=2, max_length=100)
    department_id: Optional[int] = None
    email: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    is_available: Optional[bool] = None
    availability_note: Optional[str] = Field(default=None, max_length=250)
    is_active: Optional[bool] = None


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
    medicine_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(default="", max_length=100)
    frequency: str = Field(default="", max_length=100)
    duration: str = Field(default="", max_length=100)
    suggested_quantity: Optional[int] = Field(default=None, ge=1, le=1000)
    quantity_basis: str = Field(default="", max_length=200)


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


class PharmacyCartItemCreate(BaseModel):
    medication_index: int = Field(..., ge=0, le=29)
    quantity: int = Field(..., ge=1, le=1000)
    unit_price: float = Field(..., ge=0, le=1000000, allow_inf_nan=False)


class PharmacyBillCreate(BaseModel):
    prescription_id: int
    items: list[PharmacyCartItemCreate] = Field(..., min_length=1, max_length=30)
    tax_percent: float = Field(default=18, ge=0, le=100, allow_inf_nan=False)
    notes: str = Field(default="", max_length=2000)


class PharmacyBillItem(BaseModel):
    medication_index: int
    medicine_id: Optional[int] = None
    name: str
    dosage: str = ""
    frequency: str = ""
    duration: str = ""
    quantity: int
    unit_price: float
    line_total: float


class PharmacyBillResponse(BaseModel):
    id: int
    invoice_number: str
    prescription: PrescriptionResponse
    patient: UserSummary
    pharmacy: UserSummary
    items: list[PharmacyBillItem]
    subtotal: float
    tax_percent: float
    tax_amount: float
    total: float
    status: Literal["billed", "dispensed"]
    notes: str
    created_at: Optional[datetime] = None
    dispensed_at: Optional[datetime] = None


class PharmacyQueueItem(BaseModel):
    prescription: PrescriptionResponse
    bill: Optional[PharmacyBillResponse] = None


class MedicineResponse(BaseModel):
    id: int
    name: str
    category: str


class PharmacyInventoryResponse(BaseModel):
    id: int
    medicine: MedicineResponse
    current_quantity: int
    expiry_date: Optional[date] = None
    updated_at: Optional[datetime] = None


class PharmacyRestockRequest(BaseModel):
    medicine_id: int
    new_quantity: int = Field(..., ge=1, le=1000000)
    expiry_date: Optional[date] = None


class PharmacyRestockResponse(BaseModel):
    inventory: PharmacyInventoryResponse
    previous_quantity: int
    added_quantity: int
    total_quantity: int


class PharmacyCsvImportRow(BaseModel):
    row_number: int
    medicine: MedicineResponse
    previous_quantity: int
    added_quantity: int
    total_quantity: int
    expiry_date: date


class PharmacyCsvImportResponse(BaseModel):
    rows_processed: int
    medicines_updated: int
    total_units_added: int
    rows: list[PharmacyCsvImportRow]


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
    model_config = ConfigDict(extra="forbid")

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
    doctor_assessment: str = ""


class ReportResponse(BaseModel):
    scan_id: str
    report: ReportData


class PDFRequest(BaseModel):
    """Reserved request body; generated report sections are read-only."""

    model_config = ConfigDict(extra="forbid")


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
