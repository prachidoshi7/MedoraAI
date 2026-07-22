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
