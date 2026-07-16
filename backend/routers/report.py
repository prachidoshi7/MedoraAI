"""
MedoraAI — Report Router
Retrieve LLM-generated reports and download as PDF.
"""

import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
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
            findings=findings,
            impression=impression,
            recommendations=report_data.get("recommendations", ""),
            severity=report_data.get("severity", ""),
            disclaimer=report_data.get("disclaimer", ""),
            generated_at=report.generated_at.isoformat() if report.generated_at else "",
        ),
    )


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
            edited_findings = pdf_request.edited_findings
            edited_impression = pdf_request.edited_impression
            edited_recommendations = pdf_request.edited_recommendations

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
            edited_findings=edited_findings,
            edited_impression=edited_impression,
            edited_recommendations=edited_recommendations,
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
