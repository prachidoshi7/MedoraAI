"""
MedoraAI — FastAPI Application Entry Point
Main server with lifespan events, CORS, routing, and service initialization.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from db.database import init_db, get_session_factory
from db import crud

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Startup: create dirs, init DB, seed user, load ML models, init services.
    Shutdown: cleanup.
    """
    logger.info("=" * 60)
    logger.info("🏥 MedoraAI Diagnostic Engine — Starting Up")
    logger.info("=" * 60)

    # 1. Create data directories
    for dir_path in [settings.uploads_dir, settings.heatmaps_dir, settings.thumbnails_dir]:
        os.makedirs(dir_path, exist_ok=True)
    os.makedirs("models", exist_ok=True)
    logger.info("📁 Data directories ready.")

    # 2. Initialize database
    init_db(settings.database_url)
    logger.info("🗄️ Database initialized.")

    # 3. Seed departments and role-specific demo identities
    _seed_hospital_demo()
    logger.info("👥 Hospital demo identities ready.")

    # 4. Load ML models
    logger.info("🧠 Loading ML models...")

    # Chest X-Ray classifier and heatmap ported from the madora reference.
    app.state.chest_classifier = None
    app.state.chest_gradcam = None
    try:
        from services.chest_classifier import ChestXRayClassifier
        from services.chest_gradcam import ChestGradCAM

        chest_classifier = ChestXRayClassifier(
            model_path=settings.chest_model_path,
            device="cpu",
        )
        app.state.chest_classifier = chest_classifier
        app.state.chest_gradcam = ChestGradCAM(chest_classifier)
        logger.info("  ✅ Chest X-Ray classifier (RAD-DINO, 3-class) loaded.")
    except Exception as exc:
        logger.warning("  ⚠️ RAD-DINO chest classifier unavailable: %s", exc)

    # Brain Tumor Classifier (TensorFlow)
    from services.brain_classifier import BrainTumorClassifier
    brain_classifier = BrainTumorClassifier(
        model_path=settings.brain_model_path,
    )
    app.state.brain_classifier = brain_classifier
    logger.info("  ✅ Brain Tumor classifier (EfficientNetB3, 4-class) loaded.")

    # Multi-organ classifiers (PyTorch). Keep startup resilient if a local
    # weight file has not been downloaded in a fresh development checkout.
    try:
        from services.lung_classifier import LungClassifier
        app.state.lung_classifier = LungClassifier(settings.lung_model_path, device="cpu")
        logger.info("  ✅ Lung CT classifier (5-class CNN) loaded.")
    except Exception as exc:
        app.state.lung_classifier = None
        logger.warning("  ⚠️ Lung CT classifier unavailable: %s", exc)

    try:
        from services.kidney_classifier import KidneyClassifier
        app.state.kidney_classifier = KidneyClassifier(settings.kidney_model_path, device="cpu")
        logger.info("  ✅ Kidney ultrasound classifier (2-class CNN) loaded.")
    except Exception as exc:
        app.state.kidney_classifier = None
        logger.warning("  ⚠️ Kidney ultrasound classifier unavailable: %s", exc)

    # 5. Initialize remaining model explainability engines.
    from services.brain_gradcam import BrainGradCAM

    app.state.brain_gradcam = BrainGradCAM(brain_classifier)
    if app.state.lung_classifier:
        from services.lung_gradcam import LungGradCAM
        app.state.lung_gradcam = LungGradCAM(app.state.lung_classifier)
    if app.state.kidney_classifier:
        from services.kidney_gradcam import KidneyGradCAM
        app.state.kidney_gradcam = KidneyGradCAM(app.state.kidney_classifier)
    logger.info("  ✅ Model explainability engines initialized.")

    # 6. Initialize the independent, fail-closed scan type gate.
    from services.scan_type_verifier import ScanTypeVerifier
    app.state.scan_type_verifier = ScanTypeVerifier(
        api_key=settings.GEMINI_API_KEY,
        model=settings.SCAN_TYPE_VERIFIER_MODEL or settings.GEMINI_MODEL,
        min_confidence=settings.SCAN_TYPE_MIN_CONFIDENCE,
        groq_api_key=settings.GROQ_API_KEY,
        groq_model=settings.SCAN_TYPE_GROQ_MODEL,
    )
    logger.info("  ✅ Strict pre-inference scan type verification ready.")

    # 7. Initialize LLM Report Engine
    from services.llm_report_engine import LLMReportEngine
    app.state.report_engine = LLMReportEngine(
        maira_api_url=settings.MAIRA_API_URL,
        maira_timeout_seconds=settings.MAIRA_TIMEOUT_SECONDS,
        gemini_api_key=settings.GEMINI_API_KEY,
        gemini_model=settings.GEMINI_MODEL,
        sarvam_api_key=settings.SARVAM_API_KEY,
        sarvam_translate_model=settings.SARVAM_TRANSLATE_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    logger.info("  ✅ Clinical report and patient-language services ready.")

    # 8. Initialize PDF Generator
    from services.pdf_generator import PDFGenerator
    app.state.pdf_generator = PDFGenerator()
    logger.info("  ✅ PDF Generator ready.")

    logger.info("=" * 60)
    logger.info("MedoraAI backend is ready. Local frontend: http://localhost:5173")
    logger.info("=" * 60)

    yield  # App runs here

    # Shutdown
    app.state.report_engine.close()
    logger.info("🛑 MedoraAI shutting down.")


def _seed_hospital_demo():
    """Seed departments and deterministic multi-role hackathon accounts."""
    from passlib.context import CryptContext
    from medicine_catalog import MEDICINE_CATALOG

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        department_specs = [
            ("General Medicine", "Primary consultation and coordinated care", "✦"),
            ("Neurology", "Brain and nervous system care", "◉"),
            ("Pulmonology", "Respiratory and lung care", "◌"),
            ("Nephrology", "Kidney and renal care", "◇"),
            ("Radiology", "Medical imaging and diagnostic services", "⌁"),
        ]
        departments = {
            name: crud.get_or_create_department(db, name, description, icon)
            for name, description, icon in department_specs
        }
        demo_users = [
            (settings.DEMO_USER, settings.DEMO_PASSWORD, "doctor", "Demo Clinician", "MBBS, MD (Medicine)", "Internal Medicine", "General Medicine"),
            ("patient", "patient123", "patient", "Amit Patient", "", "", None),
            ("dr.sharma", "doctor123", "doctor", "Dr. Priya Sharma", "MBBS, MD (Medicine)", "Internal Medicine", "General Medicine"),
            ("dr.patel", "doctor123", "doctor", "Dr. Rajesh Patel", "MBBS, DM (Neurology)", "Neurologist", "Neurology"),
            ("dr.kumar", "doctor123", "doctor", "Dr. Anil Kumar", "MBBS, MD (Pulmonary Medicine)", "Pulmonologist", "Pulmonology"),
            ("dr.singh", "doctor123", "doctor", "Dr. Manpreet Singh", "MBBS, DM (Nephrology)", "Nephrologist", "Nephrology"),
            ("lab.tech", "lab123", "lab_tech", "Ravi Technician", "", "Diagnostic Imaging", "Radiology"),
            ("pharmacy", "pharmacy123", "pharmacy", "Medora Care Pharmacy", "", "Ground Floor · Medora Hospital", None),
            ("admin", "admin123", "admin", "Medora Administrator", "", "Hospital Operations", None),
        ]
        for username, password, role, full_name, qualification, specialization, department_name in demo_users:
            department_id = departments[department_name].id if department_name else None
            existing = crud.get_user_by_username(db, username)
            if existing:
                existing.role = role
                existing.full_name = existing.full_name or full_name
                existing.specialization = existing.specialization or specialization
                existing.qualification = existing.qualification or qualification
                existing.department_id = existing.department_id or department_id
            else:
                crud.create_user(
                    db,
                    username=username,
                    hashed_password=pwd_context.hash(password),
                    role=role,
                    full_name=full_name,
                    specialization=specialization,
                    qualification=qualification,
                    department_id=department_id,
                )
            if role == "pharmacy":
                existing = crud.get_user_by_username(db, username)
                existing.email = existing.email or "pharmacy@medora.local"
                existing.phone = existing.phone or "+91 98765 43210"
        crud.seed_medicine_catalog(db, MEDICINE_CATALOG)
        crud.link_legacy_prescriptions_to_catalog(db)
        db.commit()
    finally:
        db.close()


# ============================================================
# CREATE FASTAPI APP
# ============================================================

app = FastAPI(
    title="MedoraAI API",
    description="AI-Powered Medical Image Diagnosis and Clinical Reporting Engine",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (uploads, heatmaps, thumbnails)
os.makedirs(settings.DATA_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.DATA_DIR), name="static")


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "models": {
            "chest_xray": "loaded" if getattr(app.state, "chest_classifier", None) else "not_loaded",
            "brain_mri": "loaded" if (
                hasattr(app.state, "brain_classifier")
                and app.state.brain_classifier.get_model() is not None
            ) else "not_loaded",
            "lung_ct": "loaded" if getattr(app.state, "lung_classifier", None) else "not_loaded",
            "kidney_us": "loaded" if getattr(app.state, "kidney_classifier", None) else "not_loaded",
        },
    }


# ============================================================
# REGISTER ROUTERS
# ============================================================

from routers import appointment, auth, case_study, diagnostic, doctors, history, pharmacy, prescription, report, scan

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(report.router, prefix="/api/v1/report", tags=["Report"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(doctors.router, prefix="/api/v1", tags=["Hospital Directory"])
app.include_router(appointment.router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(diagnostic.router, prefix="/api/v1/diagnostic", tags=["Diagnostics"])
app.include_router(prescription.router, prefix="/api/v1/prescriptions", tags=["Prescriptions"])
app.include_router(pharmacy.router, prefix="/api/v1/pharmacy", tags=["Pharmacy"])
app.include_router(case_study.router, prefix="/api/v1/case-study", tags=["Case Studies"])
