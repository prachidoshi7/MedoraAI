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

    # 3. Seed demo user
    _seed_demo_user()
    logger.info(f"👤 Demo user ready: {settings.DEMO_USER}")

    # 4. Load ML models
    logger.info("🧠 Loading ML models...")

    # Chest X-Ray Classifier (PyTorch)
    from services.chest_classifier import ChestXRayClassifier
    chest_classifier = ChestXRayClassifier(
        model_path=settings.chest_model_path,
        device="cpu",
    )
    app.state.chest_classifier = chest_classifier
    logger.info("  ✅ Chest X-Ray classifier (EfficientNet-B4) loaded.")

    # Brain Tumor Classifier (TensorFlow)
    from services.brain_classifier import BrainTumorClassifier
    brain_classifier = BrainTumorClassifier(
        model_path=settings.brain_model_path,
    )
    app.state.brain_classifier = brain_classifier
    logger.info("  ✅ Brain Tumor classifier (EfficientNetB3, 4-class) loaded.")

    # 5. Initialize Grad-CAM engines
    from services.chest_gradcam import ChestGradCAM
    from services.brain_gradcam import BrainGradCAM

    app.state.chest_gradcam = ChestGradCAM(chest_classifier)
    app.state.brain_gradcam = BrainGradCAM(brain_classifier)
    logger.info("  ✅ Grad-CAM engines initialized.")

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
    logger.info("🛑 MedoraAI shutting down.")


def _seed_demo_user():
    """Create the demo user if it doesn't exist."""
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        existing = crud.get_user_by_username(db, settings.DEMO_USER)
        if not existing:
            hashed = pwd_context.hash(settings.DEMO_PASSWORD)
            crud.create_user(db, settings.DEMO_USER, hashed)
            logger.info(f"  Created demo user: {settings.DEMO_USER}/{settings.DEMO_PASSWORD}")
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
            "chest_xray": "loaded" if hasattr(app.state, "chest_classifier") else "not_loaded",
            "brain_mri": "loaded" if hasattr(app.state, "brain_classifier") else "not_loaded",
        },
    }


# ============================================================
# REGISTER ROUTERS
# ============================================================

from routers import auth, scan, report, history

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(report.router, prefix="/api/v1/report", tags=["Report"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
