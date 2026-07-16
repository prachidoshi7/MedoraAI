# MedoraAI — Complete Implementation Plan (Updated v2)
# Dual-Model Medical AI Platform: Chest X-Ray + Brain Tumor Detection with LLM-Powered Reports

> **Goal:** Build MedoraAI from scratch — a unified medical imaging platform that supports **Chest X-Ray analysis** (EfficientNet-B4, 15-class) **AND Brain Tumor MRI detection** (MobileNetV2, binary), with **LLM-generated clinical reports** (via Groq/Claude/GPT API) that auto-download as PDF.

---

## What Changed from v1

| Area | v1 Plan | v2 Plan (Updated) |
|------|---------|-------------------|
| **Models** | Chest X-Ray only (EfficientNet-B4) | **Dual-model**: Chest X-Ray (EfficientNet-B4) + Brain Tumor MRI (MobileNetV2) |
| **Report Generation** | Jinja2 template (P0), LLM optional (P2) | **LLM is P0**: model output → LLM API prompt → clinical report → PDF. Jinja2 is fallback only |
| **LLM Provider** | Anthropic Claude only | **Multi-provider**: Groq (Llama 3.1) as primary (free/fast), Claude as secondary, OpenAI GPT as tertiary |
| **PDF Flow** | User clicks download → PDF generated | **Auto-download**: click "Download Report" → LLM generates report → PDF renders → browser auto-downloads |
| **Frontend** | Single upload mode | **Scan type selector**: "Chest X-Ray" or "Brain MRI" — routes to correct model |
| **Brain Tumor Source** | Not included | Integrated from [brain_tumor_analysis](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/brain_tumor_analysis) reference project |

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                     CLINICIAN BROWSER                              │
│          React 18 + TypeScript + Tailwind + Vite                   │
│                                                                    │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐   │
│  │  Login   │  │   Upload     │  │      Results Dashboard     │   │
│  │  Page    │  │   Page       │  │  ┌──────┐ ┌─────────────┐  │   │
│  │          │  │ [X-Ray|MRI]  │  │  │Scan  │ │Result Panel │  │   │
│  │          │  │ [Drag&Drop]  │  │  │Viewer│ │+ Confidence │  │   │
│  │          │  │ [Analyze]    │  │  │+Grad │ │+ Severity   │  │   │
│  │          │  │              │  │  │CAM   │ │+ Report     │  │   │
│  └──────────┘  └──────────────┘  │  └──────┘ │[Download PDF│  │   │
│                                   │           │ Auto-DL]    │  │   │
│                                   │           └─────────────┘  │   │
│                                   └────────────────────────────┘   │
└───────────────────────────┬────────────────────────────────────────┘
                            │ HTTP/REST (JSON)
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                     FastAPI BACKEND (port 8000)                    │
│                                                                    │
│  Routers: /auth  /scan  /report  /history                          │
│                                                                    │
│  ┌─────────── ML SERVICE LAYER ──────────────────────────────┐    │
│  │                                                            │    │
│  │  ┌──────────────────┐    ┌──────────────────────┐         │    │
│  │  │  CHEST X-RAY     │    │  BRAIN TUMOR MRI     │         │    │
│  │  │  EfficientNet-B4 │    │  MobileNetV2         │         │    │
│  │  │  (PyTorch/timm)  │    │  (TensorFlow/Keras)  │         │    │
│  │  │  15-class sigmoid│    │  Binary sigmoid      │         │    │
│  │  │  + Grad-CAM      │    │  + Grad-CAM (tf)     │         │    │
│  │  └────────┬─────────┘    └────────┬─────────────┘         │    │
│  │           │                       │                        │    │
│  │           └───────┬───────────────┘                        │    │
│  │                   ▼                                        │    │
│  │  ┌────────────────────────────────────────────────┐       │    │
│  │  │         LLM REPORT ENGINE                       │       │    │
│  │  │  Model Output + Clinical Prompt                 │       │    │
│  │  │        ↓                                        │       │    │
│  │  │  Groq (Llama 3.1) → fallback Claude → GPT      │       │    │
│  │  │        ↓                                        │       │    │
│  │  │  Structured Clinical Report (JSON)              │       │    │
│  │  │        ↓                                        │       │    │
│  │  │  Jinja2 HTML Template → WeasyPrint → PDF        │       │    │
│  │  └────────────────────────────────────────────────┘       │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌─────────── DATA LAYER ────────────────────────────────────┐    │
│  │  SQLite (app.db)  │  /data/ (uploads, heatmaps)  │ models/ │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

---

## LLM Report Generation Flow (Core Change)

This is the **primary report path** — not optional:

```
Step 1: User uploads image → selects scan type (Chest X-Ray / Brain MRI)
Step 2: Backend runs the correct model → gets:
        • Classification result (labels + confidence scores)
        • Severity assessment
        • Grad-CAM heatmap
        • Bounding boxes (if available)

Step 3: Backend constructs a CLINICAL PROMPT:
        ┌──────────────────────────────────────────────────┐
        │ SYSTEM PROMPT:                                    │
        │ "You are a board-certified radiologist writing    │
        │  a structured diagnostic report. Given the AI    │
        │  model's output, write professional Findings,    │
        │  Impression, and Recommendations sections.       │
        │  Use hedging language: 'consistent with',        │
        │  'suggestive of'. Output valid JSON with keys:   │
        │  findings, impression, recommendations."         │
        │                                                   │
        │ USER PROMPT:                                      │
        │ "Scan Type: Chest X-Ray                          │
        │  Primary Finding: Pneumonia (87.3%)              │
        │  Severity: Severe                                │
        │  Secondary Findings: Infiltration (31%),         │
        │    Effusion (23%)                                │
        │  Heatmap Region: Right lower lobe                │
        │  Generate a complete radiology report."          │
        └──────────────────────────────────────────────────┘

Step 4: Send to LLM API (try in order):
        Groq (Llama 3.1 70B) → Claude 3 Haiku → OpenAI GPT-4o-mini
        First available API key wins.

Step 5: LLM returns structured JSON:
        {
          "findings": "PA chest radiograph demonstrates...",
          "impression": "Findings are suggestive of...",
          "recommendations": "Clinical correlation recommended..."
        }

Step 6: Populate Jinja2 HTML template with LLM output + model data
Step 7: WeasyPrint converts HTML → PDF bytes
Step 8: Frontend receives PDF → auto-downloads to user's browser

FALLBACK: If NO LLM API key is configured, use template-based
          report generation (Jinja2 with model output directly).
```

---

## Brain Tumor Model Integration

Based on [brain_tumor_analysis](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/brain_tumor_analysis/README.md):

| Property | Details |
|----------|---------|
| **Model** | MobileNetV2 (pretrained ImageNet, fine-tuned on brain MRI) |
| **Framework** | TensorFlow / Keras (`.h5` or SavedModel format) |
| **Input** | 128×128 RGB MRI images, normalized 0–1 |
| **Output** | Binary sigmoid: Tumor (1) / No Tumor (0) |
| **Architecture** | MobileNetV2 → GlobalAvgPool → BatchNorm → Dense → Dropout → Sigmoid |
| **Performance** | 88.52% accuracy, 90.48% precision, 90.16% recall, 96.31% AUC |
| **Dataset** | Kaggle `navoneel/brain-mri-images-for-brain-tumor-detection` (yes/no folders) |
| **Grad-CAM** | TensorFlow Grad-CAM on last conv layer of MobileNetV2 |
| **Explainability** | Heatmap highlights tumor-focused MRI regions |

**Integration approach:**
- The brain tumor model runs in TensorFlow alongside the PyTorch chest X-ray model
- Backend loads both models at startup
- Frontend scan type selector routes to the correct model
- Each model has its own Grad-CAM implementation (PyTorch vs TensorFlow)
- LLM report prompt adapts based on scan type

---

# IMPLEMENTATION PHASES

---

## Phase 1 — Project Scaffolding & Dependencies

**Goal:** Set up monorepo structure, install all dependencies for both ML frameworks + LLM integration.

### Files to Create

#### [NEW] `backend/requirements.txt`
```
# API Framework
fastapi==0.111.0
uvicorn[standard]==0.30.1
python-multipart==0.0.9

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Database
sqlalchemy==2.0.31

# Image Processing
pillow==10.4.0
numpy==1.26.4
opencv-python-headless==4.10.0.84

# DICOM Support
pydicom==2.4.4

# ML — Chest X-Ray (PyTorch)
torch==2.3.1+cpu
torchvision==0.18.1+cpu
timm==0.9.16
pytorch-grad-cam==1.5.4

# ML — Brain Tumor (TensorFlow)
tensorflow-cpu==2.16.1
tf-keras==2.16.0

# Report Generation
jinja2==3.1.4
weasyprint==62.3

# LLM API Clients
httpx==0.27.0
groq==0.9.0
anthropic==0.31.0
openai==1.35.0

# Utilities
python-dotenv==1.0.1
```

#### [NEW] `backend/config.py`
- Pydantic `Settings` class with fields:
  - `SECRET_KEY: str`
  - `DATA_DIR: str = "./data"`
  - `CHEST_MODEL_PATH: str | None = None` (if None, use timm pretrained)
  - `BRAIN_MODEL_PATH: str = "./models/brain_tumor_mobilenetv2.h5"`
  - `GROQ_API_KEY: str | None = None` (primary LLM)
  - `ANTHROPIC_API_KEY: str | None = None` (secondary LLM)
  - `OPENAI_API_KEY: str | None = None` (tertiary LLM)
  - `DEMO_USER: str = "demo"`
  - `DEMO_PASSWORD: str = "demo123"`

#### [NEW] `.env.example`
```env
SECRET_KEY=medoraai-change-this-in-production
GROQ_API_KEY=gsk_your_groq_key_here
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEMO_USER=demo
DEMO_PASSWORD=demo123
```

#### [NEW] `docker-compose.yml`
- Backend service (Python 3.11, port 8000)
- Frontend service (Node 20, port 3000/5173)
- Volume mounts for models and data

#### [NEW] `setup.sh` / `setup.ps1`
- Create directories: `data/uploads`, `data/heatmaps`, `data/thumbnails`, `models/`
- Generate `.env` from `.env.example`
- Print setup instructions

#### Frontend scaffold (via Vite):
```bash
cd frontend
npx -y create-vite@latest ./ --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install axios react-router-dom
npm install -D @types/react-router-dom
```

#### [NEW] `frontend/package.json` — with all dependencies
#### [NEW] `frontend/vite.config.ts` — Vite config with Tailwind plugin and API proxy
#### [NEW] `frontend/tsconfig.json` — TypeScript config
#### [NEW] `frontend/index.html` — entry HTML with Inter font import, meta tags

### ✅ Phase 1 Verification
```bash
cd backend && pip install -r requirements.txt   # All deps install
cd frontend && npm install                       # All deps install
python -c "import torch; import tensorflow; print('Both ML frameworks loaded')"
```

---

## Phase 2 — Database Layer & Pydantic Schemas

**Goal:** Create SQLite database with ORM models, CRUD operations, and API request/response schemas.

### Files to Create

#### [NEW] `backend/db/__init__.py`
#### [NEW] `backend/db/database.py`
- SQLAlchemy engine: `sqlite:///./data/app.db`
- `SessionLocal` factory
- `get_db()` FastAPI dependency (yields session)
- `init_db()` — creates all tables via `Base.metadata.create_all()`

#### [NEW] `backend/db/models.py`
ORM models (4 tables):

**`User`** — id, username, hashed_password, created_at

**`Scan`** — id (UUID), user_id (FK), filename, modality, **scan_type** (`"chest_xray"` or `"brain_mri"`), file_path, heatmap_path, thumbnail_path, file_size_bytes, status (`uploaded` / `analyzing` / `analyzed` / `failed`), uploaded_at

**`Result`** — id, scan_id (FK unique), top_label, confidence, severity, all_scores (JSON text), localization_type, bounding_boxes (JSON text), analysis_time_ms, analyzed_at

**`Report`** — id, scan_id (FK unique), patient_id, **llm_provider** (which LLM generated the report), report_json (full structured report as JSON text), edited_findings, edited_impression, generated_at

> **Note:** `scan_type` field is **new** — differentiates chest X-ray from brain MRI throughout the pipeline.

#### [NEW] `backend/db/crud.py`
- `create_user()`, `get_user_by_username()`
- `create_scan()`, `get_scan()`, `update_scan_status()`, `update_scan_heatmap()`
- `create_result()`, `get_result_by_scan()`
- `create_report()`, `get_report_by_scan()`, `update_report_edits()`
- `get_user_scans()` — for history endpoint (returns list ordered by uploaded_at DESC)

#### [NEW] `backend/models/__init__.py`
#### [NEW] `backend/models/schemas.py`
Pydantic v2 models:

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800

class UploadRequest:  # multipart form
    file: UploadFile
    scan_type: str  # "chest_xray" or "brain_mri"

class UploadResponse(BaseModel):
    scan_id: str
    filename: str
    scan_type: str
    modality: str
    file_size_bytes: int
    status: str
    uploaded_at: str
    thumbnail_url: str

class BoundingBox(BaseModel):
    x1: int; y1: int; x2: int; y2: int
    label: str; confidence: float

class ClassificationDetail(BaseModel):
    top_label: str
    confidence: float
    severity: Literal["Normal", "Mild", "Moderate", "Severe"]
    all_scores: dict[str, float]

class LocalizationDetail(BaseModel):
    type: str  # "heatmap"
    heatmap_url: str
    bounding_boxes: list[BoundingBox]

class AnalysisResponse(BaseModel):
    scan_id: str
    scan_type: str
    status: str
    classification: ClassificationDetail
    localization: LocalizationDetail
    analysis_time_ms: int
    analyzed_at: str

class ReportData(BaseModel):
    patient_id: str
    scan_date: str
    scan_type: str
    modality: str
    findings: str
    impression: str
    recommendations: str
    severity: str
    llm_provider: str  # "groq" / "claude" / "openai" / "template"
    disclaimer: str
    generated_at: str

class ReportResponse(BaseModel):
    scan_id: str
    report: ReportData

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
```

### ✅ Phase 2 Verification
```python
# Run a test script that:
# 1. Creates all tables
# 2. Inserts a demo user
# 3. Creates a scan record
# 4. Queries it back
# All operations succeed without errors
```

---

## Phase 3 — ML Pipeline: Dual-Model Engine

**Goal:** Build both ML models — Chest X-Ray classifier (PyTorch) and Brain Tumor detector (TensorFlow) — each with Grad-CAM explainability.

### Files to Create

#### [NEW] `backend/services/__init__.py`

#### [NEW] `backend/services/chest_classifier.py`
**ChestXRayClassifier** class (PyTorch):

```python
CLASS_LABELS = [
    "Atelectasis", "Cardiomegaly", "Effusion", "Infiltration",
    "Mass", "Nodule", "Pneumonia", "Pneumothorax",
    "Consolidation", "Edema", "Emphysema", "Fibrosis",
    "Pleural Thickening", "Hernia", "No Finding"
]

@dataclass
class ClassificationResult:
    top_label: str              # e.g., "Pneumonia"
    confidence: float           # 0.0 – 1.0
    all_scores: dict[str, float]  # all 15 class scores
    severity: str               # "Normal" / "Mild" / "Moderate" / "Severe"
    scan_type: str = "chest_xray"

class ChestXRayClassifier:
    def __init__(self, model_path=None, device="cpu"):
        # Load EfficientNet-B4 via timm, replace head with 15-class sigmoid
        self.model = timm.create_model('efficientnet_b4', pretrained=True, num_classes=15)
        # If model_path provided, load fine-tuned weights
        self.model.eval()
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
        ])

    def predict(self, image: PIL.Image) -> ClassificationResult:
        # Preprocess → forward pass → sigmoid → map to ClassificationResult
        # Apply severity mapping: No Finding→Normal, <0.4→Mild, 0.4-0.7→Moderate, >0.7→Severe

    def get_model(self): return self.model
    def get_transform(self): return self.transform
```

#### [NEW] `backend/services/brain_classifier.py`
**BrainTumorClassifier** class (TensorFlow/Keras):

```python
BRAIN_LABELS = ["No Tumor", "Tumor"]

@dataclass
class BrainClassificationResult:
    top_label: str              # "Tumor" or "No Tumor"
    confidence: float           # 0.0 – 1.0
    all_scores: dict[str, float]  # {"Tumor": 0.92, "No Tumor": 0.08}
    severity: str               # "Normal" / "Mild" / "Moderate" / "Severe"
    scan_type: str = "brain_mri"

class BrainTumorClassifier:
    def __init__(self, model_path=None):
        if model_path and os.path.exists(model_path):
            # Load saved .h5 model
            self.model = tf.keras.models.load_model(model_path)
        else:
            # Build MobileNetV2 architecture from scratch (same as notebook)
            base = tf.keras.applications.MobileNetV2(
                input_shape=(128,128,3), include_top=False,
                weights='imagenet'
            )
            base.trainable = False
            model = tf.keras.Sequential([
                base,
                tf.keras.layers.GlobalAveragePooling2D(),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.Dense(128, activation='relu'),
                tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(1, activation='sigmoid')
            ])
            self.model = model

    def predict(self, image: PIL.Image) -> BrainClassificationResult:
        # Resize to 128×128, normalize 0-1, expand dims
        # Forward pass → sigmoid output
        # confidence = output for tumor, 1-output for no tumor
        # Apply severity mapping

    def get_model(self): return self.model
```

#### [NEW] `backend/services/chest_gradcam.py`
**ChestGradCAM** — PyTorch Grad-CAM for EfficientNet-B4:
```python
class ChestGradCAM:
    def __init__(self, classifier: ChestXRayClassifier):
        model = classifier.get_model()
        target_layer = model.conv_head  # EfficientNet-B4 last conv
        self.cam = GradCAM(model=model, target_layers=[target_layer])

    def generate_heatmap(self, image, input_tensor, target_class_idx) -> np.ndarray:
        # Returns RGB overlay (H, W, 3) with heatmap at 40% alpha

    def generate_raw_cam(self, input_tensor, target_class_idx) -> np.ndarray:
        # Returns grayscale activation map for bbox extraction

    def heatmap_to_bboxes(self, cam, threshold=0.5) -> list[dict]:
        # OpenCV contour detection → bounding boxes
```

#### [NEW] `backend/services/brain_gradcam.py`
**BrainGradCAM** — TensorFlow Grad-CAM for MobileNetV2:
```python
class BrainGradCAM:
    def __init__(self, classifier: BrainTumorClassifier):
        self.model = classifier.get_model()
        # Find last conv layer in MobileNetV2
        for layer in reversed(self.model.layers):
            if isinstance(layer, tf.keras.layers.Conv2D):
                self.target_layer = layer.name
                break

    def generate_heatmap(self, image, preprocessed_input) -> np.ndarray:
        # TensorFlow GradientTape-based Grad-CAM:
        # 1. Create gradient model (input → [conv_output, predictions])
        # 2. Record gradients with GradientTape
        # 3. Compute weighted feature map
        # 4. Apply ReLU + normalize
        # 5. Overlay on original image at 40% alpha
        # Returns RGB overlay (H, W, 3)
```

#### [NEW] `backend/services/dicom_parser.py`
```python
def parse_dicom(file_bytes: bytes) -> tuple[PIL.Image, dict]:
    # Uses pydicom to read DICOM, extract metadata, convert to PIL Image
    # Returns (image, {"patient_id": ..., "modality": ..., "study_date": ...})
```

### ✅ Phase 3 Verification
```python
# Test 1: Load a chest X-ray PNG → ChestXRayClassifier.predict() returns 15 scores in <2s
# Test 2: Load a brain MRI JPG → BrainTumorClassifier.predict() returns binary result in <1s
# Test 3: ChestGradCAM.generate_heatmap() returns valid RGB array
# Test 4: BrainGradCAM.generate_heatmap() returns valid RGB array
```

---

## Phase 4 — LLM Report Engine & PDF Export

**Goal:** Build the LLM-powered report generator that takes model output, constructs a clinical prompt, calls LLM API, and produces a downloadable PDF.

### Files to Create

#### [NEW] `backend/services/llm_report_engine.py`
This is the **core new component**:

```python
class LLMReportEngine:
    """Generates clinical reports using LLM APIs.
    
    Flow: Model Output → Clinical Prompt → LLM API → Structured Report → PDF
    
    Provider priority: Groq (fastest/free) → Claude → OpenAI → Template fallback
    """
    
    SYSTEM_PROMPT = """You are a board-certified radiologist with 20 years of experience.
You are writing a structured diagnostic draft report based on AI model analysis results.

RULES:
- Write in professional radiology report language
- Use hedging language: "consistent with", "suggestive of", "cannot exclude"
- Do NOT make definitive diagnoses
- Be specific about anatomical locations when possible
- Include relevant clinical context
- Keep each section to 3-5 sentences
- The report is AI-generated and must be reviewed by a licensed radiologist

OUTPUT FORMAT (strict JSON):
{
  "findings": "Detailed radiological findings...",
  "impression": "Clinical impression summary...",
  "recommendations": "Recommended follow-up actions..."
}

Output ONLY valid JSON. No markdown, no explanation, no extra text."""

    def _build_user_prompt(self, result, scan_type: str) -> str:
        """Build the user prompt from model output."""
        if scan_type == "chest_xray":
            return f"""SCAN TYPE: Chest X-Ray (PA View)
PRIMARY FINDING: {result.top_label} (Confidence: {result.confidence*100:.1f}%)
SEVERITY ASSESSMENT: {result.severity}
ALL CLASSIFICATION SCORES:
{self._format_scores(result.all_scores)}

Generate a complete radiology report for this chest X-ray analysis."""

        elif scan_type == "brain_mri":
            return f"""SCAN TYPE: Brain MRI
PRIMARY FINDING: {result.top_label} (Confidence: {result.confidence*100:.1f}%)
SEVERITY ASSESSMENT: {result.severity}
CLASSIFICATION: {result.all_scores}

Generate a complete neuroradiology report for this brain MRI analysis."""

    async def generate_report(self, result, scan_type: str) -> dict:
        """Try LLM providers in priority order. Return structured report dict."""
        # Try Groq first (fastest, free tier available)
        if self.groq_key:
            report = await self._call_groq(result, scan_type)
            if report: return {**report, "llm_provider": "groq"}
        
        # Try Claude second
        if self.anthropic_key:
            report = await self._call_claude(result, scan_type)
            if report: return {**report, "llm_provider": "claude"}
        
        # Try OpenAI third
        if self.openai_key:
            report = await self._call_openai(result, scan_type)
            if report: return {**report, "llm_provider": "openai"}
        
        # Fallback: template-based generation (no LLM)
        return self._generate_template_report(result, scan_type)

    async def _call_groq(self, result, scan_type) -> dict | None:
        """Call Groq API with Llama 3.1 70B."""
        # POST https://api.groq.com/openai/v1/chat/completions
        # model: "llama-3.1-70b-versatile"
        # Returns parsed JSON or None on failure

    async def _call_claude(self, result, scan_type) -> dict | None:
        """Call Anthropic Claude API."""
        # model: "claude-3-haiku-20240307"
        # Returns parsed JSON or None on failure

    async def _call_openai(self, result, scan_type) -> dict | None:
        """Call OpenAI API."""
        # model: "gpt-4o-mini"
        # Returns parsed JSON or None on failure

    def _generate_template_report(self, result, scan_type) -> dict:
        """Jinja2 template fallback when no LLM API key available."""
        # Returns same structure as LLM but with template-generated text
        # llm_provider: "template"
```

#### [NEW] `backend/services/pdf_generator.py`
```python
class PDFGenerator:
    def __init__(self, template_dir="templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.report_template = self.env.get_template("report.html")

    def generate_pdf(self, report_data: dict, scan_data: dict) -> bytes:
        """
        Render report data into HTML template, convert to PDF bytes.
        
        report_data: LLM output (findings, impression, recommendations, etc.)
        scan_data: scan metadata (scan_id, filename, scan_type, etc.)
        
        Returns: PDF as bytes for direct download
        """
        html = self.report_template.render(**report_data, **scan_data)
        return HTML(string=html).write_pdf()
```

#### [NEW] `backend/templates/report.html`
Professional Jinja2 HTML report template:
- **Header**: MedoraAI logo, report ID, generation date, LLM provider badge
- **Patient Info**: patient ID, scan date, modality, scan type
- **AI Classification**: primary finding, confidence bar, severity badge (color-coded)
- **Findings**: LLM-generated findings text (editable before PDF)
- **Impression**: LLM-generated impression text
- **Recommendations**: LLM-generated recommendations
- **All Scores Table**: full classification breakdown (for chest X-ray)
- **Disclaimer**: mandatory AI disclaimer with warning styling
- **Footer**: "Generated by MedoraAI — For decision support only"
- **Styling**: Professional medical report CSS (Segoe UI, blue accents, severity colors)

#### [NEW] `backend/templates/report.txt`
- Plain text fallback template

### ✅ Phase 4 Verification
```python
# Test 1: With Groq API key → LLMReportEngine.generate_report() returns structured report
# Test 2: Without any API key → falls back to template, still returns valid report
# Test 3: PDFGenerator.generate_pdf() → returns valid PDF bytes, opens in viewer
# Test 4: Report contains all sections: findings, impression, recommendations, disclaimer
```

---

## Phase 5 — FastAPI Backend Server

**Goal:** Wire up all services into REST API endpoints with JWT auth, file upload, dual-model analysis, LLM report, and PDF download.

### Files to Create

#### [NEW] `backend/main.py`
```python
# FastAPI app with lifespan events:
# - Startup: load both ML models, init DB, seed demo user
# - Shutdown: cleanup

app = FastAPI(title="MedoraAI API", version="1.0.0")

# CORS: allow localhost:3000 and localhost:5173
# Static files: mount /static → /data
# Include routers: auth, scan, report, history under /api/v1
# Health endpoint: GET /health → {"status": "ok", "models_loaded": {...}}
```

**Startup sequence:**
1. Create data directories if not exist
2. Initialize SQLite database (create tables)
3. Seed demo user (`demo` / `demo123`) if not exists
4. Load ChestXRayClassifier (EfficientNet-B4, ~75MB download first time)
5. Load BrainTumorClassifier (MobileNetV2, from .h5 or fresh with ImageNet weights)
6. Initialize ChestGradCAM and BrainGradCAM
7. Initialize LLMReportEngine (auto-detects available API keys)
8. Initialize PDFGenerator
9. Store all services in `app.state` for dependency injection

#### [NEW] `backend/routers/__init__.py`

#### [NEW] `backend/routers/auth.py`
```
POST /api/v1/auth/login
  Request: {"username": "demo", "password": "demo123"}
  Response: {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 28800}

Dependency: get_current_user() — extracts JWT from Authorization header, validates, returns user
```

#### [NEW] `backend/routers/scan.py`
```
POST /api/v1/scan/upload
  Request: multipart/form-data (file + scan_type)
  - Validates file type (PNG/JPEG/DICOM), size (<20MB), magic bytes
  - Saves to /data/uploads/{scan_id}.png
  - Generates 128×128 thumbnail → /data/thumbnails/{scan_id}.png
  - Creates DB scan record
  Response: UploadResponse

POST /api/v1/scan/analyze/{scan_id}
  - Loads image from disk
  - Routes to correct model based on scan_type:
    • "chest_xray" → ChestXRayClassifier + ChestGradCAM
    • "brain_mri" → BrainTumorClassifier + BrainGradCAM
  - Runs classification → Grad-CAM → severity mapping
  - Saves heatmap to /data/heatmaps/{scan_id}.png
  - Extracts bounding boxes from activation map
  - Stores results in DB
  - Generates LLM report (async call to LLMReportEngine)
  - Stores report in DB
  Response: AnalysisResponse (includes classification + localization + timing)
```

#### [NEW] `backend/routers/report.py`
```
GET /api/v1/report/{scan_id}
  - Returns stored report JSON (LLM-generated or template)
  Response: ReportResponse

POST /api/v1/report/{scan_id}/pdf
  - Accepts optional edited findings/impression
  - Renders HTML template with report data + any edits
  - Converts to PDF via WeasyPrint
  - Returns PDF binary with Content-Disposition: attachment
  Response: application/pdf (auto-download)
```

#### [NEW] `backend/routers/history.py`
```
GET /api/v1/history
  - Returns list of user's scans with results
  Response: HistoryResponse
```

#### [NEW] `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
# System deps for WeasyPrint, OpenCV, TensorFlow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev libcairo2 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu
COPY . .
RUN mkdir -p /app/data/uploads /app/data/heatmaps /app/data/thumbnails
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### ✅ Phase 5 Verification
```bash
# Start server
cd backend
uvicorn main:app --reload --port 8000

# Test 1: Health check
curl http://localhost:8000/health
# → {"status": "ok", "models": {"chest_xray": "loaded", "brain_mri": "loaded"}}

# Test 2: Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'
# → {"access_token": "eyJ...", ...}

# Test 3: Upload chest X-ray
curl -X POST http://localhost:8000/api/v1/scan/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@chest_xray.png" -F "scan_type=chest_xray"
# → {"scan_id": "abc123...", ...}

# Test 4: Analyze
curl -X POST http://localhost:8000/api/v1/scan/analyze/abc123 \
  -H "Authorization: Bearer <token>"
# → Full analysis response in <5 seconds

# Test 5: Get report (LLM-generated)
curl http://localhost:8000/api/v1/report/abc123 \
  -H "Authorization: Bearer <token>"
# → {"report": {"findings": "...", "llm_provider": "groq", ...}}

# Test 6: Download PDF
curl -X POST http://localhost:8000/api/v1/report/abc123/pdf \
  -H "Authorization: Bearer <token>" -o report.pdf
# → PDF file saved, opens correctly
```

---

## Phase 6 — Frontend: Core Layout & Design System

**Goal:** Set up React app with dark medical theme, routing, API client, auth hooks, and scan type selector infrastructure.

### Files to Create

#### [NEW] `frontend/src/styles/globals.css`
```css
@import "tailwindcss";

/* Dark Medical Theme */
:root {
  --bg-primary: #0f1117;
  --bg-secondary: #1a1d27;
  --bg-tertiary: #252833;
  --text-primary: #e4e7ec;
  --text-secondary: #9ba1b0;
  --accent-blue: #3b82f6;
  --accent-cyan: #06b6d4;
  --severity-normal: #22c55e;
  --severity-mild: #eab308;
  --severity-moderate: #f97316;
  --severity-severe: #ef4444;
  --border: #2d3140;
}

/* Glassmorphism utility */
.glass { backdrop-filter: blur(12px); background: rgba(26,29,39,0.8); }

/* Smooth transitions everywhere */
* { transition: all 0.2s ease; }
```

#### [NEW] `frontend/src/types/index.ts`
- All TypeScript interfaces matching Phase 2 Pydantic schemas
- Includes `scan_type`, `llm_provider`, `recommendations` fields

#### [NEW] `frontend/src/api/client.ts`
- Axios instance with base URL `http://localhost:8000/api/v1`
- `setAuthToken()`, `login()`, `uploadScan(file, scanType)`, `analyzeScan()`, `getReport()`, `downloadPdf()`, `getHistory()`
- `downloadPdf()` triggers browser auto-download via `window.URL.createObjectURL(blob)`

#### [NEW] `frontend/src/hooks/useAuth.ts`
- AuthContext provider: token, user, login(), logout(), isAuthenticated

#### [NEW] `frontend/src/hooks/useScan.ts`
- Upload + analyze hooks with loading, error, progress states

#### [NEW] `frontend/src/App.tsx`
- Routes: `/login`, `/upload`, `/results/:scanId`
- PrivateRoute wrapper, layout with nav header

#### [NEW] `frontend/src/main.tsx`
- Entry point: AuthProvider → BrowserRouter → App

### ✅ Phase 6 Verification
```bash
cd frontend && npm run dev
# App loads at localhost:5173 with dark theme
# Routing works, unauthenticated → redirect to /login
```

---

## Phase 7 — Login Page (Premium UI)

**Goal:** Beautiful, glassmorphism login page with medical theme.

#### [NEW] `frontend/src/pages/LoginPage.tsx`
- Dark gradient background with subtle animated medical icons
- Glassmorphism login card (backdrop-blur, semi-transparent)
- MedoraAI branding: "🏥 MedoraAI" with tagline "AI-Powered Medical Image Diagnosis"
- Username + Password inputs with floating labels and focus animations
- "Sign In" button with gradient, hover scale, loading spinner
- Error toast for invalid credentials
- Smooth fade-in entrance animation

### ✅ Phase 7 Verification
- Login with `demo/demo123` → redirects to upload
- Wrong credentials → error displays with red text
- UI looks premium (glassmorphism, gradients, animations)

---

## Phase 8 — Upload Page (Dual Scan Type)

**Goal:** Drag-and-drop upload with scan type selector (Chest X-Ray / Brain MRI).

#### [NEW] `frontend/src/pages/UploadPage.tsx`
- **Scan Type Selector** (top): two large cards side by side:
  - 🫁 "Chest X-Ray Analysis" — EfficientNet-B4, 15 pathologies, NIH ChestX-ray14
  - 🧠 "Brain Tumor Detection" — MobileNetV2, binary classification, Brain MRI
  - Selected card glows with accent border
- **Upload Zone** (center): appears after scan type selected
- **Recent Scans** (bottom): last 5 scans with thumbnails

#### [NEW] `frontend/src/components/UploadZone.tsx`
- Large drag-and-drop zone with dashed animated border
- Accepts PNG/JPEG/DICOM
- File preview: thumbnail of selected image with metadata (name, size, format)
- "🔬 Analyze Scan" button — disabled until file selected, gradient + pulse animation
- On click: upload → analyze → redirect to `/results/:scanId`
- Full loading overlay during analysis with stages:
  - "📤 Uploading scan..."
  - "🔬 Running AI classification..."
  - "🌡️ Generating heatmap..."
  - "📝 Generating clinical report via AI..."
  - "✅ Analysis complete!"

#### [NEW] `frontend/src/components/LoadingSpinner.tsx`
- Medical-themed progress: animated DNA helix or brain pulse
- Step-by-step progress stages
- Estimated time remaining

### ✅ Phase 8 Verification
- Select "Chest X-Ray" → upload zone appears
- Drag PNG → preview shows → click "Analyze" → loading stages play → redirect to results
- Same flow works for "Brain MRI" selection

---

## Phase 9 — Results Dashboard (Core View)

**Goal:** The main diagnostic dashboard — scan viewer with heatmap toggle, classification results, severity assessment, and report with PDF auto-download.

#### [NEW] `frontend/src/pages/ResultsPage.tsx`
- Fetches analysis data + report on mount
- Two-panel layout (60% left / 40% right on desktop, stacked on mobile)
- **Left panel:** ScanViewer component
- **Right panel:** ResultPanel + ReportEditor (scrollable)
- **Action bar (bottom):** "📥 Download PDF Report", "🔬 New Scan", "🖼️ Export Heatmap"
- Loading skeletons while data fetches

#### [NEW] `frontend/src/components/ScanViewer.tsx`
- HTML5 Canvas-based image viewer
- **Three view modes** (toggle buttons at top):
  1. **Original** — uploaded scan only
  2. **Heatmap** — Grad-CAM overlay at 40% alpha on original
  3. **Side-by-Side** — both images adjacent
- Bounding box overlay with labels and confidence scores
- Smooth crossfade transitions between modes
- Scan type badge (🫁 Chest X-Ray / 🧠 Brain MRI)

#### [NEW] `frontend/src/components/ResultPanel.tsx`
- **Primary Finding Card:**
  - Large label text (e.g., "Pneumonia" or "Tumor Detected")
  - Animated confidence progress bar (0–100%, color matches severity)
  - Severity badge: Normal (green) / Mild (yellow) / Moderate (orange) / Severe (red)
  - Pulse animation on severe findings
- **All Findings (expandable):**
  - For chest X-ray: sorted list of all 15 class scores with mini progress bars
  - For brain MRI: binary result with confidence
- **Analysis metadata:** inference time, model used, scan type
- **LLM Provider badge:** "Report by: Groq Llama 3.1" or "Claude" etc.

#### [NEW] `frontend/src/components/ReportEditor.tsx`
- **Auto-populated sections** (from LLM report):
  - Findings (editable textarea)
  - Impression (editable textarea)
  - Recommendations (editable textarea)
- **Read-only sections:** Patient ID, Scan Date, Modality, Severity, Disclaimer
- **"📥 Download PDF Report" button:**
  - Click → sends edits to `POST /report/{id}/pdf`
  - Receives PDF blob → auto-triggers browser download
  - Button shows "Generating PDF..." spinner during generation
  - File downloads as `MedoraAI_Report_{scan_id}.pdf`
- **"↩️ Reset to AI-generated" button** — restores original LLM text
- **Report source indicator:** "🤖 Generated by Groq Llama 3.1 70B" (or whichever provider)

```typescript
// PDF auto-download implementation in ReportEditor:
const handleDownloadPdf = async () => {
  setDownloading(true);
  try {
    const blob = await downloadPdf(scanId, editedFindings, editedImpression);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `MedoraAI_Report_${scanId.slice(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } finally {
    setDownloading(false);
  }
};
```

#### [NEW] `frontend/src/components/HistorySidebar.tsx`
- Vertical list of previous scans
- Each item: thumbnail, scan type icon (🫁/🧠), top label, severity badge, timestamp
- Click to navigate to that scan's results
- "Clear History" button

### ✅ Phase 9 Verification
1. Upload chest X-ray → analyze → results page shows all elements
2. Upload brain MRI → analyze → results page shows binary classification
3. Toggle heatmap views (Original / Heatmap / Side-by-Side)
4. Edit report findings → click "Download PDF" → PDF auto-downloads
5. PDF opens correctly with all sections (findings, impression, recommendations, disclaimer)
6. History sidebar shows all previous scans
7. Report shows LLM provider badge (e.g., "Generated by Groq")

---

## Phase 10 — Docker, Polish & Demo Readiness

**Goal:** Containerize everything, add final UI polish, harden error handling, verify end-to-end.

### Files to Create/Modify

#### [NEW] `frontend/Dockerfile`
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

#### [NEW] `frontend/nginx.conf`
- SPA routing (try_files → /index.html)
- API proxy: `/api/` → `http://backend:8000/api/`

#### [MODIFY] `docker-compose.yml`
- Finalize with health checks, env vars, volume mounts

#### [MODIFY] `README.md`
Complete quickstart with:
- Prerequisites (Docker, or Python 3.11 + Node 20 for local dev)
- One-command Docker setup: `docker compose up --build`
- Local dev setup (uvicorn + npm run dev)
- Demo credentials: `demo` / `demo123`
- API key setup for LLM reports (Groq recommended — free tier)
- Screenshots / flow description

### UI Polish Tasks
- [ ] Fade-in/slide-up entrance animations on all pages
- [ ] Skeleton loading states during API calls
- [ ] Error boundaries with friendly error messages
- [ ] Empty states ("No scans yet — upload your first scan!")
- [ ] Toast notifications for success/error events
- [ ] Responsive layout (mobile stacking)
- [ ] Keyboard navigation support
- [ ] File validation error messages ("Unsupported format", "File too large")

### Error Handling Hardening
- [ ] Try/catch on every backend endpoint → descriptive JSON errors
- [ ] ML model failures → graceful degradation with error message
- [ ] LLM API failures → automatic fallback to template report
- [ ] Network timeout handling on frontend (30s timeout, retry button)
- [ ] File validation by magic bytes, not just extension

### ✅ Phase 10 — Final Demo Checklist

**Critical (must pass):**
- [ ] `docker compose up --build` OR `uvicorn + npm run dev` starts without errors
- [ ] Login with `demo` / `demo123` → redirects to upload
- [ ] **Chest X-Ray flow:** select type → upload PNG → analyze → heatmap + classification + report → download PDF
- [ ] **Brain MRI flow:** select type → upload JPG → analyze → heatmap + tumor/no-tumor → download PDF
- [ ] LLM report generates successfully (findings, impression, recommendations in clinical language)
- [ ] PDF downloads automatically and opens correctly
- [ ] Grad-CAM heatmap renders with toggle (original/heatmap/side-by-side)
- [ ] Classification + confidence + severity all displayed correctly
- [ ] No crashes during 5 consecutive upload-analyze cycles
- [ ] Report shows which LLM generated it (Groq/Claude/GPT/Template)

**Important (should pass):**
- [ ] LLM fallback works (remove API key → template report still generates)
- [ ] Invalid file upload shows descriptive error (not crash)
- [ ] History sidebar shows all previous scans
- [ ] Report is editable before PDF download
- [ ] Edited report text is reflected in downloaded PDF

---

## Complete File List (All ~55 Files)

| # | File | Phase | Description |
|---|------|-------|-------------|
| 1 | `backend/requirements.txt` | 1 | Python deps (PyTorch + TensorFlow + LLM clients) |
| 2 | `backend/config.py` | 1 | Pydantic Settings with all config |
| 3 | `.env.example` | 1 | Template env vars (Groq/Claude/OpenAI keys) |
| 4 | `docker-compose.yml` | 1 | Backend + Frontend services |
| 5 | `setup.sh` | 1 | Directory creation + env setup |
| 6 | `frontend/package.json` | 1 | Node dependencies |
| 7 | `frontend/vite.config.ts` | 1 | Vite + Tailwind config |
| 8 | `frontend/tsconfig.json` | 1 | TypeScript config |
| 9 | `frontend/index.html` | 1 | HTML entry with fonts + meta |
| 10 | `backend/db/__init__.py` | 2 | Package init |
| 11 | `backend/db/database.py` | 2 | SQLAlchemy engine + sessions |
| 12 | `backend/db/models.py` | 2 | User, Scan, Result, Report ORM |
| 13 | `backend/db/crud.py` | 2 | All CRUD operations |
| 14 | `backend/models/__init__.py` | 2 | Package init |
| 15 | `backend/models/schemas.py` | 2 | Pydantic request/response models |
| 16 | `backend/services/__init__.py` | 3 | Package init |
| 17 | `backend/services/chest_classifier.py` | 3 | EfficientNet-B4 classifier |
| 18 | `backend/services/brain_classifier.py` | 3 | MobileNetV2 brain tumor classifier |
| 19 | `backend/services/chest_gradcam.py` | 3 | PyTorch Grad-CAM for chest |
| 20 | `backend/services/brain_gradcam.py` | 3 | TensorFlow Grad-CAM for brain |
| 21 | `backend/services/dicom_parser.py` | 3 | DICOM → PIL Image conversion |
| 22 | `backend/services/llm_report_engine.py` | 4 | **Core: LLM-powered report generator** |
| 23 | `backend/services/pdf_generator.py` | 4 | WeasyPrint HTML → PDF |
| 24 | `backend/templates/report.html` | 4 | Jinja2 HTML report template |
| 25 | `backend/templates/report.txt` | 4 | Plain text report fallback |
| 26 | `backend/main.py` | 5 | FastAPI app entry + lifespan |
| 27 | `backend/routers/__init__.py` | 5 | Package init |
| 28 | `backend/routers/auth.py` | 5 | JWT login endpoint |
| 29 | `backend/routers/scan.py` | 5 | Upload + analyze endpoints |
| 30 | `backend/routers/report.py` | 5 | Report + PDF download endpoints |
| 31 | `backend/routers/history.py` | 5 | Scan history endpoint |
| 32 | `backend/Dockerfile` | 5 | Backend container |
| 33 | `frontend/src/styles/globals.css` | 6 | Tailwind + dark medical theme |
| 34 | `frontend/src/types/index.ts` | 6 | TypeScript interfaces |
| 35 | `frontend/src/api/client.ts` | 6 | Axios API client + auto-download |
| 36 | `frontend/src/hooks/useAuth.ts` | 6 | Auth context + JWT management |
| 37 | `frontend/src/hooks/useScan.ts` | 6 | Upload + analyze hooks |
| 38 | `frontend/src/App.tsx` | 6 | Router + layout |
| 39 | `frontend/src/main.tsx` | 6 | React entry point |
| 40 | `frontend/src/pages/LoginPage.tsx` | 7 | Glassmorphism login |
| 41 | `frontend/src/pages/UploadPage.tsx` | 8 | Scan type selector + upload |
| 42 | `frontend/src/components/UploadZone.tsx` | 8 | Drag-and-drop + preview |
| 43 | `frontend/src/components/LoadingSpinner.tsx` | 8 | Analysis progress stages |
| 44 | `frontend/src/pages/ResultsPage.tsx` | 9 | Main results dashboard |
| 45 | `frontend/src/components/ScanViewer.tsx` | 9 | Canvas image + heatmap toggle |
| 46 | `frontend/src/components/ResultPanel.tsx` | 9 | Classification + severity |
| 47 | `frontend/src/components/ReportEditor.tsx` | 9 | LLM report + PDF auto-download |
| 48 | `frontend/src/components/HistorySidebar.tsx` | 9 | Previous scans list |
| 49 | `frontend/Dockerfile` | 10 | Frontend container |
| 50 | `frontend/nginx.conf` | 10 | SPA routing + API proxy |
| 51 | `README.md` | 10 | Complete quickstart guide |

---

## Open Questions

> [!IMPORTANT]
> **1. Which LLM API key do you have?** Groq is recommended (free tier, fastest). Do you have a Groq API key, or should we use Claude/OpenAI?

> [!IMPORTANT]
> **2. Brain tumor trained model (.h5 file):** The `brain_tumor_analysis` repo has the notebook but no exported `.h5` model file. Should we:
> - **(A)** Train the model from the notebook and export `.h5` (requires the Kaggle dataset download) — OR —
> - **(B)** Use fresh MobileNetV2 with ImageNet weights (works but less accurate for demo)?

> [!IMPORTANT]
> **3. Docker or local first?** Want me to build for local development first (`uvicorn` + `npm run dev`) and add Docker at the end?
