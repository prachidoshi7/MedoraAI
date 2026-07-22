"""
MedoraAI — Report Router
Retrieve LLM-generated reports and download as PDF.
"""

import json
import logging
import os
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from PIL import Image
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db import crud
from models.schemas import (
    PDFRequest,
    PatientSummaryRequest,
    PatientSummaryResponse,
    ReportData,
    ReportResponse,
)
from routers.auth import get_current_user
from services.llm_report_engine import LLMReportEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# GET REPORT
# ============================================================

@router.get("/{scan_id}", response_model=ReportResponse)
async def get_report(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Retrieve the generated clinical report for a scan.
    Returns the clinician-facing report data.
    """
    # Verify scan belongs to user
    scan = crud.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get report from DB
    report = crud.get_report_by_scan(db, scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated. Run analysis first.")

    # Parse stored JSON
    try:
        report_data = json.loads(report.report_json)
    except json.JSONDecodeError:
        report_data = {}
    report_data = LLMReportEngine._ground_report_to_available_input(
        report_data,
        report_data.get("scan_type", scan.scan_type),
    )

    # Use edited versions if clinician has made edits
    findings = report.edited_findings or report_data.get("findings", "")
    impression = report.edited_impression or report_data.get("impression", "")

    return ReportResponse(
        scan_id=scan_id,
        report=ReportData(
            patient_id=report.patient_id or "DEMO-001",
            scan_date=report_data.get("scan_date", ""),
            scan_type=report_data.get("scan_type", scan.scan_type),
            modality=report_data.get("modality", scan.modality),
            top_label=report_data.get("top_label", ""),
            confidence=report_data.get("confidence", 0.0),
            all_scores=report_data.get("all_scores", {}),
            clinical_history=report_data.get("clinical_history", "Not provided."),
            technique=report_data.get("technique", ""),
            comparison=report_data.get("comparison", "No prior imaging was supplied for comparison."),
            image_quality=report_data.get("image_quality", ""),
            findings=findings,
            impression=impression,
            differential_diagnosis=report_data.get("differential_diagnosis", ""),
            recommendations=report_data.get("recommendations", ""),
            critical_communication=report_data.get("critical_communication", "No critical communication generated."),
            severity=report_data.get("severity", ""),
            disclaimer=report_data.get("disclaimer", ""),
            generated_at=report.generated_at.isoformat() if report.generated_at else "",
            heatmap_target_label=report_data.get("heatmap_target_label", ""),
            is_low_confidence=report_data.get("is_low_confidence", False),
            methodology=report_data.get("methodology", ""),
            limitations=report_data.get("limitations", ""),
        ),
    )


@router.post("/{scan_id}/regenerate", response_model=ReportResponse)
async def regenerate_report(
    scan_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rebuild a stored clinical draft without rerunning image classification."""
    scan = crud.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    stored_result = crud.get_result_by_scan(db, scan_id)
    if not stored_result:
        raise HTTPException(status_code=409, detail="Analyze the scan before generating a report")

    try:
        scores = json.loads(stored_result.all_scores or "{}")
    except json.JSONDecodeError:
        scores = {}
    sorted_secondary = [
        {"label": label, "score": float(score)}
        for label, score in sorted(scores.items(), key=lambda item: -float(item[1]))
        if label != stored_result.top_label and float(score) >= 0.20
    ][:3]
    result = SimpleNamespace(
        top_label=stored_result.top_label,
        confidence=float(stored_result.confidence),
        severity=stored_result.severity,
        all_scores=scores,
        is_low_confidence=float(stored_result.confidence) < 0.50,
        heatmap_target_label=stored_result.top_label,
        secondary_findings=sorted_secondary,
    )

    image_path = scan.file_path
    if not os.path.isabs(image_path):
        image_path = os.path.abspath(image_path)
    if not os.path.exists(image_path):
        image_path = os.path.join(settings.uploads_dir, f"{scan_id}.png")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Stored scan image is unavailable")

    try:
        with Image.open(image_path) as source:
            image = source.copy()
        report_data = await request.app.state.report_engine.generate_report(
            result=result,
            scan_type=scan.scan_type,
            modality=scan.modality,
            image=image,
        )
        crud.replace_report(
            db=db,
            scan_id=scan_id,
            report_data=report_data,
            llm_provider=report_data.get("llm_provider", "template"),
        )
        logger.info("Clinical report regenerated for %s", scan_id[:8])
        return await get_report(scan_id=scan_id, db=db, current_user=current_user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Report regeneration failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not regenerate the clinical report")


# ============================================================
# DOWNLOAD PDF
# ============================================================

@router.post("/{scan_id}/pdf")
async def download_pdf(
    scan_id: str,
    request: Request,
    pdf_request: PDFRequest = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate and download a PDF report.
    
    Accepts optional edited findings/impression/recommendations.
    Returns PDF binary with Content-Disposition: attachment for auto-download.
    """
    # Verify scan belongs to user
    scan = crud.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get report from DB
    report = crud.get_report_by_scan(db, scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    try:
        report_data = json.loads(report.report_json)
    except json.JSONDecodeError:
        report_data = {}
    report_data = LLMReportEngine._ground_report_to_available_input(
        report_data,
        report_data.get("scan_type", scan.scan_type),
    )

    # Save edits if provided
    if pdf_request:
        if pdf_request.edited_findings or pdf_request.edited_impression:
            crud.update_report_edits(
                db, scan_id,
                edited_findings=pdf_request.edited_findings,
                edited_impression=pdf_request.edited_impression,
            )

    # Generate PDF with edits applied
    pdf_generator = request.app.state.pdf_generator

    try:
        edited_findings = None
        edited_impression = None
        edited_recommendations = None

        if pdf_request:
            edited_clinical_history = pdf_request.edited_clinical_history
            edited_technique = pdf_request.edited_technique
            edited_comparison = pdf_request.edited_comparison
            edited_image_quality = pdf_request.edited_image_quality
            edited_findings = pdf_request.edited_findings
            edited_impression = pdf_request.edited_impression
            edited_differential_diagnosis = pdf_request.edited_differential_diagnosis
            edited_recommendations = pdf_request.edited_recommendations
            edited_critical_communication = pdf_request.edited_critical_communication
        else:
            edited_clinical_history = None
            edited_technique = None
            edited_comparison = None
            edited_image_quality = None
            edited_differential_diagnosis = None
            edited_critical_communication = None

        # Also check DB for previously saved edits
        if not edited_findings and report.edited_findings:
            edited_findings = report.edited_findings
        if not edited_impression and report.edited_impression:
            edited_impression = report.edited_impression

        # Resolve heatmap path for PDF embedding
        heatmap_path = os.path.join(settings.heatmaps_dir, f"{scan_id}.png")
        if not os.path.exists(heatmap_path):
            heatmap_path = ""

        pdf_bytes = pdf_generator.generate_pdf_with_edits(
            report_data=report_data,
            scan_id=scan_id,
            edited_clinical_history=edited_clinical_history,
            edited_technique=edited_technique,
            edited_comparison=edited_comparison,
            edited_image_quality=edited_image_quality,
            edited_findings=edited_findings,
            edited_impression=edited_impression,
            edited_differential_diagnosis=edited_differential_diagnosis,
            edited_recommendations=edited_recommendations,
            edited_critical_communication=edited_critical_communication,
            heatmap_path=heatmap_path,
        )

        filename = f"MedoraAI_Report_{scan_id[:8]}.pdf"

        logger.info(f"PDF generated for scan {scan_id[:8]} ({len(pdf_bytes)} bytes)")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}",
        )


# ============================================================
# PATIENT-FRIENDLY SUMMARY
# ============================================================

SUPPORTED_LANGUAGES = [
    "English", "Hindi", "Tamil", "Telugu", "Marathi",
    "Bengali", "Kannada", "Gujarati", "Malayalam", "Punjabi", "Urdu",
]


@router.post("/{scan_id}/patient-summary", response_model=PatientSummaryResponse)
async def get_patient_summary(
    scan_id: str,
    body: PatientSummaryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate a patient-friendly summary of the medical report.

    Takes a language parameter and returns a simplified, non-technical
    explanation that patients can understand in their native language.
    """
    # Validate language
    language = body.language.strip().title()
    if language not in SUPPORTED_LANGUAGES:
        language = "English"

    # Verify scan belongs to user
    scan = crud.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get report from DB
    report = crud.get_report_by_scan(db, scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    try:
        report_data = json.loads(report.report_json)
    except json.JSONDecodeError:
        report_data = {}
    report_data = LLMReportEngine._ground_report_to_available_input(
        report_data,
        report_data.get("scan_type", scan.scan_type),
    )

    if report.edited_findings:
        report_data["findings"] = report.edited_findings
    if report.edited_impression:
        report_data["impression"] = report.edited_impression

    # Generate patient summary
    report_engine = request.app.state.report_engine
    try:
        summary = await report_engine.generate_patient_report(
            report_data=report_data,
            language=language,
        )

        logger.info(f"Patient summary generated for {scan_id[:8]} in {language}")

        return {
            "scan_id": scan_id,
            "language": language,
            "summary": summary,
            "supported_languages": SUPPORTED_LANGUAGES,
        }

    except Exception as e:
        logger.error(f"Patient summary failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not generate patient summary. Please try again.",
        )
