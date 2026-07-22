"""
MedoraAI — Scan Upload & Analysis Router
Handles image upload, validation, and dual-model AI inference pipeline.
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db import crud
from models.schemas import UploadResponse, AnalysisResponse, ClassificationDetail, LocalizationDetail, BoundingBox
from routers.auth import get_current_user
from services.scan_type_verifier import ScanTypeVerification

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/jpg",
    "application/dicom", "application/octet-stream",
}


def _validate_file(file: UploadFile) -> None:
    """Validate uploaded file type and size."""
    # Check content type
    content_type = file.content_type or ""
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in settings.ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Accepted: PNG, JPEG, DICOM (.dcm)",
        )


def _validate_magic_bytes(file_bytes: bytes, filename: str) -> None:
    """Validate common image signatures before decoding."""
    ext = os.path.splitext(filename)[1].lower()
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    is_dicom = (
        ext == ".dcm"
        and (len(file_bytes) > 132 and file_bytes[128:132] == b"DICM")
    )

    if not (is_png or is_jpeg or is_dicom):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or invalid file content. Upload a valid PNG, JPEG, or DICOM image.",
        )


def _detect_modality(scan_type: str, filename: str) -> str:
    """Detect imaging modality from scan type and filename."""
    if scan_type == "brain_mri":
        return "MRI"
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".dcm":
        return "DICOM"
    return "X-ray"


def _reject_bad_scan(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _normalized_grayscale(image: Image.Image, size: tuple[int, int] = (256, 256)) -> np.ndarray:
    gray = np.asarray(image.resize(size).convert("L"), dtype=np.float32) / 255.0
    lo, hi = np.quantile(gray, [0.01, 0.99])
    if hi > lo:
        gray = np.clip((gray - lo) / (hi - lo), 0.0, 1.0)
    return gray


def _looks_like_centered_brain_slice(gray: np.ndarray) -> bool:
    """Detect common axial/sagittal MRI-like centered oval brain images."""
    mask = (gray > max(0.12, float(np.quantile(gray, 0.30)))).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return False

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x = int(stats[largest, cv2.CC_STAT_LEFT])
    y = int(stats[largest, cv2.CC_STAT_TOP])
    w = int(stats[largest, cv2.CC_STAT_WIDTH])
    h = int(stats[largest, cv2.CC_STAT_HEIGHT])
    area = float(stats[largest, cv2.CC_STAT_AREA])

    image_area = float(gray.shape[0] * gray.shape[1])
    area_ratio = area / image_area
    bbox_fill = area / max(float(w * h), 1.0)
    aspect = w / max(float(h), 1.0)
    center_x = x + w / 2.0
    center_y = y + h / 2.0
    centered = abs(center_x - gray.shape[1] / 2.0) < gray.shape[1] * 0.15 and abs(center_y - gray.shape[0] / 2.0) < gray.shape[0] * 0.18

    border = np.concatenate([gray[:16, :].ravel(), gray[-16:, :].ravel(), gray[:, :16].ravel(), gray[:, -16:].ravel()])
    dark_border = float(border.mean()) < 0.12

    return (
        centered
        and dark_border
        and 0.18 <= area_ratio <= 0.68
        and 0.65 <= aspect <= 1.45
        and bbox_fill >= 0.42
    )


def _has_chest_xray_lung_pattern(gray: np.ndarray) -> bool:
    """
    Check for coarse PA/AP chest projection structure:
    paired darker lung regions with a brighter central mediastinal column.
    """
    body_mask = gray > max(0.08, float(np.quantile(gray, 0.18)))
    body_ratio = float(body_mask.mean())
    if body_ratio < 0.42:
        return False

    left_lung = gray[70:190, 34:108]
    right_lung = gray[70:190, 148:222]
    center = gray[65:195, 110:146]
    upper_center = gray[35:95, 105:151]
    lower_center = gray[150:225, 82:174]

    lung_mean = float((left_lung.mean() + right_lung.mean()) / 2.0)
    center_mean = float(center.mean())
    upper_center_mean = float(upper_center.mean())
    lower_center_mean = float(lower_center.mean())

    dark_threshold = float(np.quantile(gray[body_mask], 0.38)) if body_mask.any() else 0.38
    left_dark = float((left_lung < dark_threshold).mean())
    right_dark = float((right_lung < dark_threshold).mean())
    paired_lungs = left_dark > 0.18 and right_dark > 0.18 and min(left_dark, right_dark) / max(left_dark, right_dark) > 0.35
    mediastinum_brighter = center_mean > lung_mean + 0.025 or upper_center_mean > lung_mean + 0.02
    lower_not_empty = lower_center_mean > lung_mean - 0.08

    return paired_lungs and mediastinum_brighter and lower_not_empty


def _validate_scan_matches_selected_type(image: Image.Image, scan_type: str, modality: str) -> None:
    """
    Validate basic image quality and authoritative DICOM modality metadata.

    Anatomy/modality verification for PNG/JPEG and body-part verification for
    DICOM are handled by the independent verifier after this cheap local gate.
    Fixed-region heuristics remain diagnostic-only because they reject valid
    projections and accept some wrong-modality images.
    """
    width, height = image.size
    if min(width, height) < 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too small for reliable analysis. Upload a higher-resolution medical image.",
        )

    modality_upper = (modality or "").upper()

    # DICOM modality tags are authoritative. Values synthesized from the
    # selected type for PNG/JPEG files naturally agree with this branch.
    if scan_type == "chest_xray" and modality_upper in {"MR", "MRI", "CT", "US", "NM", "PT"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected Chest X-Ray, but uploaded DICOM modality is {modality}. Select the correct scan type.",
        )
    if scan_type == "brain_mri" and modality_upper in {"CR", "DX", "DR", "XR", "RG"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected Brain MRI, but uploaded DICOM modality is {modality}. Select Chest X-Ray instead.",
        )

    arr = np.asarray(image.resize((256, 256)).convert("RGB"), dtype=np.float32) / 255.0
    channel_delta = float(
        np.mean(
            np.abs(arr[:, :, 0] - arr[:, :, 1])
            + np.abs(arr[:, :, 1] - arr[:, :, 2])
            + np.abs(arr[:, :, 0] - arr[:, :, 2])
        )
        / 3.0
    )
    gray_rgb = arr.mean(axis=2)
    contrast = float(gray_rgb.std())
    dynamic_range = float(np.quantile(gray_rgb, 0.95) - np.quantile(gray_rgb, 0.05))

    # Reject only inputs that are clearly unusable by either grayscale model.
    # The relaxed colour threshold tolerates scanner overlays and compression.
    if channel_delta > 0.14:
        _reject_bad_scan(
            "This does not look like a grayscale medical image. "
            "Upload the original chest X-ray or brain MRI image."
        )
    if contrast < 0.02 or dynamic_range < 0.07:
        _reject_bad_scan(
            "This image does not have enough contrast for reliable analysis. "
            "Upload the original diagnostic image rather than a blank or heavily compressed preview."
        )

    # These signals are useful for observability, but are not reliable enough
    # to reject a selected modality without a trained OOD/modality classifier.
    gray = _normalized_grayscale(image)
    logger.debug(
        "Upload anatomy signals for selected %s: brain_like=%s chest_like=%s",
        scan_type,
        _looks_like_centered_brain_slice(gray),
        _has_chest_xray_lung_pattern(gray),
    )


def _enforce_scan_type_verification(
    verification: ScanTypeVerification,
    selected_scan_type: str,
    min_confidence: float,
) -> None:
    """Reject anything except a confident, single-image exact type match."""
    selected = "Brain MRI" if selected_scan_type == "brain_mri" else "Chest X-Ray"
    required = (
        "one original brain MRI slice showing intracranial anatomy"
        if selected_scan_type == "brain_mri"
        else "one original frontal chest X-ray showing the full thorax and both lungs"
    )
    if not verification.is_single_diagnostic_image:
        _reject_bad_scan(
            f"This is not an acceptable {selected} image. Upload {required}. "
            "Screenshots, posters, collages, report pages, and images dominated by text or interface elements are rejected."
        )
    if not verification.anatomy_complete_enough:
        _reject_bad_scan(
            f"This {selected} image is too cropped, obscured, or low quality. Upload {required}."
        )
    if verification.category == "other":
        _reject_bad_scan(
            f"This is not a valid {selected} image. Upload {required}; no analysis was performed."
        )
    if verification.category == "uncertain" or verification.confidence < min_confidence:
        _reject_bad_scan(
            f"We could not verify this as a valid {selected} image. Upload {required}; no analysis was performed."
        )
    if verification.category != selected_scan_type:
        detected = "brain MRI" if verification.category == "brain_mri" else "chest X-ray"
        _reject_bad_scan(
            f"The uploaded image appears to be a {detected}, but {selected} is selected. "
            "Choose the matching scan type before continuing."
        )


# ============================================================
# UPLOAD ENDPOINT
# ============================================================

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_scan(
    request: Request,
    file: UploadFile = File(...),
    scan_type: str = Form(default="chest_xray"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Upload a medical image for analysis.
    
    Args:
        file: Image file (PNG/JPEG/DICOM)
        scan_type: "chest_xray" or "brain_mri"
    """
    _validate_file(file)

    # Validate scan_type
    if scan_type not in ("chest_xray", "brain_mri"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scan_type must be 'chest_xray' or 'brain_mri'",
        )

    # Read file bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB",
        )
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Generate scan ID
    scan_id = str(uuid.uuid4())
    filename = file.filename or f"scan_{scan_id[:8]}.png"
    _validate_magic_bytes(file_bytes, filename)
    modality = _detect_modality(scan_type, filename)

    # Process image
    try:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".dcm":
            from services.dicom_parser import parse_dicom
            image, dicom_meta = parse_dicom(file_bytes)
            modality = dicom_meta.get("modality", modality)
        else:
            from io import BytesIO
            image = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read image file: {str(e)}",
        )

    _validate_scan_matches_selected_type(image, scan_type, modality)

    if settings.STRICT_SCAN_TYPE_VALIDATION:
        verifier = getattr(request.app.state, "scan_type_verifier", None)
        if verifier is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scan type verification is unavailable. No analysis was performed.",
            )
        try:
            verification = await verifier.verify(image)
        except Exception as exc:
            logger.error("Scan type verification unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Image-type verification services are temporarily busy. No analysis was performed. "
                    "Please retry this same diagnostic image in a moment."
                ),
            )
        _enforce_scan_type_verification(
            verification,
            scan_type,
            settings.SCAN_TYPE_MIN_CONFIDENCE,
        )

    # Save original image as PNG
    file_path = os.path.join(settings.uploads_dir, f"{scan_id}.png")
    image.save(file_path, "PNG")

    # Generate thumbnail (128×128)
    thumbnail = image.copy()
    thumbnail.thumbnail((128, 128), Image.Resampling.LANCZOS)
    thumbnail_path = os.path.join(settings.thumbnails_dir, f"{scan_id}.png")
    thumbnail.save(thumbnail_path, "PNG")

    # Save to database
    scan = crud.create_scan(
        db=db,
        scan_id=scan_id,
        user_id=current_user.id,
        filename=filename,
        scan_type=scan_type,
        modality=modality,
        file_path=file_path,
        thumbnail_path=thumbnail_path,
        file_size_bytes=file_size,
    )

    logger.info(f"Scan uploaded: {scan_id[:8]} ({scan_type}, {file_size} bytes)")

    return UploadResponse(
        scan_id=scan_id,
        filename=filename,
        scan_type=scan_type,
        modality=modality,
        file_size_bytes=file_size,
        status="uploaded",
        uploaded_at=scan.uploaded_at.isoformat() if scan.uploaded_at else "",
        thumbnail_url=f"/static/thumbnails/{scan_id}.png",
    )


# ============================================================
# ANALYZE ENDPOINT
# ============================================================

@router.post("/analyze/{scan_id}", response_model=AnalysisResponse)
async def analyze_scan(
    scan_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Trigger AI inference on an uploaded scan.
    Runs classification → Grad-CAM → severity → report generation.
    """
    # Get scan from DB
    scan = crud.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID {scan_id[:8]} not found",
        )

    if scan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Update status
    crud.update_scan_status(db, scan_id, "analyzing")

    start_time = time.time()

    try:
        # Load image
        image = Image.open(scan.file_path).convert("RGB")

        # Route to correct model
        if scan.scan_type == "chest_xray":
            classification_result, heatmap_overlay, bboxes = _analyze_chest_xray(
                request, image, scan_id
            )
        elif scan.scan_type == "brain_mri":
            classification_result, heatmap_overlay, bboxes = _analyze_brain_mri(
                request, image, scan_id
            )
        else:
            raise ValueError(f"Unknown scan type: {scan.scan_type}")

        # Calculate analysis time
        analysis_time_ms = int((time.time() - start_time) * 1000)

        # Save heatmap (already at 512×512 from Grad-CAM generator)
        heatmap_path = os.path.join(settings.heatmaps_dir, f"{scan_id}.png")
        heatmap_image = Image.fromarray(heatmap_overlay)
        heatmap_image.save(heatmap_path, "PNG")

        # Update scan with heatmap path
        crud.update_scan_heatmap(db, scan_id, heatmap_path)
        crud.update_scan_status(db, scan_id, "analyzed")

        # Store result in DB
        crud.create_result(
            db=db,
            scan_id=scan_id,
            top_label=classification_result.top_label,
            confidence=classification_result.confidence,
            severity=classification_result.severity,
            all_scores=classification_result.all_scores,
            bounding_boxes=bboxes,
            analysis_time_ms=analysis_time_ms,
        )

        # Generate LLM report
        report_data = await request.app.state.report_engine.generate_report(
            result=classification_result,
            scan_type=scan.scan_type,
            modality=scan.modality,
            image=image,
        )

        # Store report in DB
        crud.replace_report(
            db=db,
            scan_id=scan_id,
            report_data=report_data,
            llm_provider=report_data.get("llm_provider", "template"),
        )

        logger.info(
            f"Analysis complete: {scan_id[:8]} → {classification_result.top_label} "
            f"({classification_result.confidence * 100:.1f}%) in {analysis_time_ms}ms"
        )

        return AnalysisResponse(
            scan_id=scan_id,
            scan_type=scan.scan_type,
            status="analyzed",
            classification=ClassificationDetail(
                top_label=classification_result.top_label,
                confidence=classification_result.confidence,
                severity=classification_result.severity,
                all_scores=classification_result.all_scores,
            ),
            localization=LocalizationDetail(
                type="heatmap",
                heatmap_url=f"/static/heatmaps/{scan_id}.png",
                bounding_boxes=[BoundingBox(**b) for b in bboxes] if bboxes else [],
            ),
            analysis_time_ms=analysis_time_ms,
            analyzed_at=datetime.now().isoformat() if True else "",
        )

    except Exception as e:
        crud.update_scan_status(db, scan_id, "failed")
        logger.error(f"Analysis failed for {scan_id[:8]}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


def _analyze_chest_xray(request: Request, image: Image.Image, scan_id: str):
    """Run chest X-ray analysis pipeline."""
    from datetime import datetime

    classifier = request.app.state.chest_classifier
    gradcam = request.app.state.chest_gradcam

    # Classify
    result = classifier.predict(image)

    # Always generate a real Grad-CAM heatmap targeting the highest-scoring
    # pathology class. Even when the final label is "No Finding", this shows
    # where the model's attention was focused and WHY it found nothing significant.
    input_tensor = classifier.preprocess(image)
    heatmap_target_idx = result.heatmap_target_idx
    heatmap_target_label = result.heatmap_target_label

    heatmap_overlay = gradcam.generate_heatmap(
        image, input_tensor, heatmap_target_idx, target_label=heatmap_target_label,
    )
    raw_cam = gradcam.generate_raw_cam(input_tensor, heatmap_target_idx, image=image)
    bboxes = gradcam.heatmap_to_bboxes(raw_cam, threshold=0.6)

    return result, heatmap_overlay, bboxes


def _analyze_brain_mri(request: Request, image: Image.Image, scan_id: str):
    """Run brain tumor analysis pipeline."""
    from datetime import datetime

    classifier = request.app.state.brain_classifier
    gradcam = request.app.state.brain_gradcam

    # Classify
    result = classifier.predict(image)

    # Generate Grad-CAM heatmap
    preprocessed = classifier.preprocess(image)
    heatmap_overlay = gradcam.generate_heatmap(image, preprocessed)

    # Extract bounding boxes
    raw_cam = gradcam.generate_raw_cam(preprocessed)
    bboxes = gradcam.heatmap_to_bboxes(raw_cam, threshold=0.5)

    return result, heatmap_overlay, bboxes


# Need datetime for the endpoint
from datetime import datetime
