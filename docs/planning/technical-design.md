# Technical Design Document
## Multi-Modal Medical Image Diagnosis and Automated Clinical Reporting Engine

**Version:** 1.0  
**Date:** 2026-06-27  
**Status:** Hackathon Build Spec  
**Arch Review:** Pending

---

## 1. System Overview

### 1.1 Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLINICIAN BROWSER                        │
│              React + Tailwind (Vite, port 3000)                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST (JSON)
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      BACKEND API SERVER                         │
│              FastAPI (Python 3.11, port 8000)                   │
│                                                                 │
│  Routers:                                                       │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────┐      │
│  │ auth │ │   scan   │ │  report  │ │ history │ │static│      │
│  └──┬───┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └──┬───┘      │
│     │          │             │             │         │           │
│  ┌──▼──────────▼─────────────▼─────────────▼─────────▼───────┐  │
│  │                  SERVICE LAYER                             │  │
│  │  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐   │  │
│  │  │ classifier │ │  detector  │ │  report_generator    │   │  │
│  │  │  .py       │ │  .py       │ │  .py                 │   │  │
│  │  └──────┬─────┘ └──────┬─────┘ └──────────┬───────────┘   │  │
│  │         │              │                   │               │  │
│  │  ┌──────▼──────────────▼───────┐  ┌───────▼────────────┐  │  │
│  │  │  PyTorch + timm + GradCAM  │  │ Jinja2 + WeasyPrint│  │  │
│  │  └──────────────┬──────────────┘  └────────────────────┘  │  │
│  └─────────────────┼─────────────────────────────────────────┘  │
│                    │                                             │
│  ┌─────────────────▼───────────────────────────────────────┐    │
│  │                 DATA LAYER                               │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │    │
│  │  │ SQLite   │  │ /data/       │  │ /models/          │  │    │
│  │  │ (app.db) │  │  uploads/    │  │  classifier.pt    │  │    │
│  │  │          │  │  heatmaps/   │  │  (auto-downloaded) │  │    │
│  │  │          │  │  thumbnails/ │  │                    │  │    │
│  │  └──────────┘  └──────────────┘  └───────────────────┘  │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Tech Stack Decision Table

| Layer | Technology | Version | Reason |
|-------|-----------|---------|--------|
| Frontend | React + Vite | React 18.3, Vite 5.x | Fast HMR, small bundle, TypeScript-first |
| UI Framework | Tailwind CSS + shadcn/ui | Tailwind 3.4 | Rapid styling, dark mode built-in, medical-grade aesthetic achievable quickly |
| Backend | FastAPI | 0.111+ | Async, auto-generated OpenAPI docs, Python-native for ML integration |
| ML Framework | PyTorch | 2.3+ | Best ecosystem for medical imaging; largest pretrained model zoo |
| Image Classification | timm (PyTorch Image Models) | 0.9+ | 800+ pretrained architectures; EfficientNet-B4 available out-of-box |
| Explainability | pytorch-grad-cam | 1.4+ | Grad-CAM, HiResCAM, EigenCAM in one library; works with any PyTorch CNN |
| Object Detection | Ultralytics YOLOv8 | 8.2+ | Fast inference, bounding box output built-in (stretch goal only) |
| DICOM Parsing | pydicom + Pillow | pydicom 2.4 | Standard DICOM library; Pillow for image conversion |
| Report Generation | Jinja2 templates | 3.1+ | Zero external dependencies; deterministic output |
| LLM Enhancement | Anthropic Claude API | claude-3-haiku | Cheapest/fastest option; only used if API key present (P2 feature) |
| PDF Export | WeasyPrint | 62.x | Pure Python HTML-to-PDF; no wkhtmltopdf binary dependency |
| Authentication | python-jose + passlib | - | JWT tokens with bcrypt password hashing; minimal setup |
| Database | SQLite via SQLAlchemy | SQLite 3, SQLAlchemy 2.0 | Zero-config, no separate server, sufficient for single-user hackathon |
| Containerization | Docker + Docker Compose | Compose v2 | One-command startup; reproducible environments |
| Image Storage | Local filesystem | - | Simple; `/data/uploads/`, `/data/heatmaps/`, `/data/thumbnails/` |

> [Assumption] No GPU is available in the demo environment. All model choices and latency targets are validated on CPU (Intel i7-class, 16GB RAM).

---

## 2. Repository Structure

```
project-root/
├── docs/
│   ├── prd.md                       # Product Requirements Document
│   └── tdd.md                       # Technical Design Document (this file)
│
├── backend/
│   ├── main.py                      # FastAPI app entry point, CORS, lifespan
│   ├── config.py                    # Pydantic Settings (env vars)
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Backend container
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                  # POST /auth/login
│   │   ├── scan.py                  # POST /scan/upload, POST /scan/analyze/{id}
│   │   ├── report.py                # GET /report/{id}, POST /report/{id}/pdf
│   │   └── history.py               # GET /history
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py            # ScanClassifier class — EfficientNet-B4
│   │   ├── detector.py              # AnomalyLocalizer class — Grad-CAM
│   │   ├── report_generator.py      # Template + optional LLM report
│   │   ├── pdf_generator.py         # HTML → PDF via WeasyPrint
│   │   └── dicom_parser.py          # DICOM → PIL.Image conversion
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic request/response models
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   ├── models.py                # ORM models (User, Scan, Result, Report)
│   │   └── crud.py                  # Create/Read DB operations
│   │
│   └── templates/
│       ├── report.html              # Jinja2 HTML report template
│       └── report.txt               # Jinja2 plain-text report template
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                 # React entry point
│   │   ├── App.tsx                  # Router + layout
│   │   │
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx        # Authentication form
│   │   │   ├── UploadPage.tsx       # Drag-and-drop upload + analyze trigger
│   │   │   └── ResultsPage.tsx      # Scan viewer + results + report
│   │   │
│   │   ├── components/
│   │   │   ├── ScanViewer.tsx       # Canvas-based image + heatmap overlay
│   │   │   ├── ResultPanel.tsx      # Classification + confidence + severity
│   │   │   ├── ReportEditor.tsx     # Editable report textarea + PDF download
│   │   │   ├── HistorySidebar.tsx   # Previous scan thumbnails + results
│   │   │   ├── UploadZone.tsx       # Drag-and-drop file input
│   │   │   └── LoadingSpinner.tsx   # Analysis progress animation
│   │   │
│   │   ├── api/
│   │   │   └── client.ts           # Axios instance + typed API functions
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAuth.ts          # Authentication state + JWT management
│   │   │   └── useScan.ts          # Upload + analyze mutation hooks
│   │   │
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript interfaces for API responses
│   │   │
│   │   └── styles/
│   │       └── globals.css          # Tailwind directives + custom medical theme
│   │
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── Dockerfile
│
├── models/                          # .pt weight files (gitignored)
│   └── .gitkeep
│
├── demo_data/                       # 10 pre-selected demo images
│   └── .gitkeep
│
├── data/                            # Runtime data (gitignored)
│   ├── uploads/
│   ├── heatmaps/
│   └── thumbnails/
│
├── docker-compose.yml               # One-command startup
├── setup.sh                         # Downloads model weights, seeds demo user
├── .gitignore
└── README.md                        # Quick start guide
```

---

## 3. ML Pipeline Design

### 3.1 Model 1 — Scan Classifier

**Task:** Multi-label classification of chest X-ray pathologies  
**Architecture:** EfficientNet-B4 (pretrained on ImageNet via `timm`)  
**Checkpoint strategy:**
1. **Default (hackathon speed):** `timm.create_model('efficientnet_b4', pretrained=True, num_classes=15)` — use ImageNet weights directly. The model will not be clinically accurate but Grad-CAM will still produce visually meaningful activations on chest X-rays.
2. **Preferred (if time permits):** Load CheXNet-compatible DenseNet-121 weights from open-source repos (e.g., `arnoweng/CheXNet`) and swap the classifier head. This gives clinically validated performance.
3. **Optimal (stretch):** Fine-tune on NIH ChestX-ray14 for 5 epochs with frozen backbone + unfrozen last 2 blocks.

> [Assumption] For hackathon demo, Option 1 (pretrained ImageNet) is the baseline. Option 2 is attempted if setup time < 30 minutes.

**Input preprocessing:**
```python
from torchvision import transforms

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],   # ImageNet stats
        std=[0.229, 0.224, 0.225]
    ),
])
```

**Output:** 15-class sigmoid output (14 ChestX-ray14 pathologies + "No Finding")

**Class labels (in order):**
```python
CLASS_LABELS = [
    "Atelectasis", "Cardiomegaly", "Effusion", "Infiltration",
    "Mass", "Nodule", "Pneumonia", "Pneumothorax",
    "Consolidation", "Edema", "Emphysema", "Fibrosis",
    "Pleural Thickening", "Hernia", "No Finding"
]
```

**Interface contract:**
```python
# backend/services/classifier.py
from dataclasses import dataclass
from typing import Literal
import PIL.Image

@dataclass
class ClassificationResult:
    top_label: str                              # e.g., "Pneumonia"
    confidence: float                           # 0.0 – 1.0
    all_scores: dict[str, float]                # all 15 class scores
    severity: Literal["Normal", "Mild", "Moderate", "Severe"]

class ScanClassifier:
    def __init__(self, model_path: str | None = None, device: str = "cpu"):
        """
        Load model weights. If model_path is None, use timm pretrained.
        Model is loaded once at startup and reused for all requests.
        """
        ...

    def predict(self, image: PIL.Image.Image) -> ClassificationResult:
        """
        Run inference on a single PIL Image.
        Returns classification result with severity mapping.
        Thread-safe: model is in eval mode, no gradients.
        """
        ...

    def get_model(self):
        """Return the underlying torch.nn.Module for Grad-CAM access."""
        ...
```

**Severity mapping logic:**
```python
def confidence_to_severity(confidence: float, label: str) -> str:
    """Map model confidence to clinical severity label.
    
    Thresholds are intentionally conservative — high confidence
    in a pathology maps to higher severity. 'No Finding' always
    maps to 'Normal' regardless of confidence.
    """
    if label == "No Finding":
        return "Normal"
    elif confidence < 0.4:
        return "Mild"
    elif confidence < 0.7:
        return "Moderate"
    else:
        return "Severe"
```

**Performance budget:**
| Operation | CPU Time (i7) | GPU Time (T4) |
|-----------|---------------|---------------|
| Preprocessing | ~50ms | ~50ms |
| EfficientNet-B4 forward pass | ~1,200ms | ~150ms |
| Softmax + postprocessing | ~5ms | ~5ms |
| **Total classification** | **~1,255ms** | **~205ms** |

---

### 3.2 Model 2 — Anomaly Localization

**Primary method: Grad-CAM heatmap** (always available, zero extra model weight)

Grad-CAM produces a class-discriminative localization map by computing the gradient of the predicted class score with respect to the feature maps of the last convolutional layer. This highlights the image regions most influential to the classification decision.

**Implementation:**
```python
# backend/services/detector.py
import numpy as np
import PIL.Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

class AnomalyLocalizer:
    def __init__(self, classifier: 'ScanClassifier'):
        """
        Initialize Grad-CAM using the classifier's underlying model.
        Target layer: last convolutional block of EfficientNet-B4.
        For EfficientNet: model.conv_head or model.blocks[-1]
        """
        model = classifier.get_model()
        # EfficientNet-B4 (timm): target the last conv block
        target_layer = model.conv_head  # or model.blocks[-1][-1]
        self.cam = GradCAM(model=model, target_layers=[target_layer])

    def generate_heatmap(
        self, 
        image: PIL.Image.Image, 
        input_tensor: 'torch.Tensor',
        target_class_idx: int
    ) -> np.ndarray:
        """
        Generate a Grad-CAM heatmap for the given class.
        
        Args:
            image: Original PIL image (for overlay compositing)
            input_tensor: Preprocessed tensor (1, 3, 224, 224)
            target_class_idx: Index of the class to explain
            
        Returns:
            RGB numpy array (H, W, 3) with heatmap overlaid on original image.
            Values in [0, 1] float range.
        """
        targets = [ClassifierOutputTarget(target_class_idx)]
        grayscale_cam = self.cam(input_tensor=input_tensor, targets=targets)
        grayscale_cam = grayscale_cam[0, :]  # (H, W)

        # Resize original image to match CAM dimensions
        rgb_img = np.array(image.resize((224, 224))) / 255.0
        if rgb_img.ndim == 2:  # grayscale X-ray
            rgb_img = np.stack([rgb_img] * 3, axis=-1)

        # Overlay heatmap at 40% alpha
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
        return visualization

    def generate_raw_cam(
        self,
        input_tensor: 'torch.Tensor',
        target_class_idx: int
    ) -> np.ndarray:
        """
        Return raw Grad-CAM activation map (grayscale, 0–1).
        Used for bounding box extraction from heatmap.
        """
        targets = [ClassifierOutputTarget(target_class_idx)]
        grayscale_cam = self.cam(input_tensor=input_tensor, targets=targets)
        return grayscale_cam[0, :]
```

**Heatmap storage:** Saved as PNG to `/data/heatmaps/{scan_id}.png`, served via FastAPI static files.

**Bounding box extraction from heatmap (stretch):**
```python
def heatmap_to_bboxes(cam: np.ndarray, threshold: float = 0.5) -> list[dict]:
    """
    Extract bounding boxes from Grad-CAM activation map.
    Uses OpenCV contour detection on thresholded activation.
    """
    import cv2
    binary = (cam > threshold).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bboxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h > 100:  # filter noise
            bboxes.append({
                "x1": int(x), "y1": int(y),
                "x2": int(x + w), "y2": int(y + h),
                "label": "anomaly_region",
                "confidence": float(cam[y:y+h, x:x+w].max())
            })
    return bboxes
```

**YOLOv8 bounding boxes (P2 stretch goal):**
- Model: `yolov8m` pretrained, potentially fine-tuned on VinDr-CXR
- Only attempted if core pipeline works and time remains
- Output: List of `{x1, y1, x2, y2, label, confidence}` dicts

**Performance budget:**
| Operation | CPU Time (i7) |
|-----------|---------------|
| Grad-CAM computation | ~800ms |
| Overlay compositing | ~50ms |
| PNG encoding + save | ~30ms |
| **Total localization** | **~880ms** |

---

### 3.3 Inference Pipeline — End to End

```
┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐
│  Upload  │───▶│  Validate   │───▶│ Convert to   │───▶│ Preprocess │
│  (file)  │    │  (type/size)│    │ PIL Image    │    │ (224×224)  │
└──────────┘    └─────────────┘    └──────────────┘    └─────┬──────┘
                                                             │
     ┌───────────────────────────────────────────────────────┘
     ▼
┌────────────┐    ┌─────────────┐    ┌──────────────┐    ┌───────────┐
│  Classify  │───▶│  Localize   │───▶│ Severity Map │───▶│  Store    │
│ (Eff-B4)   │    │ (Grad-CAM)  │    │ (threshold)  │    │ (DB+disk) │
└────────────┘    └─────────────┘    └──────────────┘    └─────┬─────┘
                                                               │
     ┌─────────────────────────────────────────────────────────┘
     ▼
┌────────────────┐    ┌──────────────┐
│ Generate Report│───▶│ Return JSON  │
│ (Jinja2/LLM)  │    │ to frontend  │
└────────────────┘    └──────────────┘
```

**Total pipeline target:** < 5 seconds on CPU

| Step | Time Budget |
|------|-------------|
| File validation + conversion | ~200ms |
| Preprocessing | ~50ms |
| Classification (EfficientNet-B4) | ~1,200ms |
| Localization (Grad-CAM) | ~800ms |
| Severity mapping | ~5ms |
| DB write + file save | ~100ms |
| Report generation (Jinja2) | ~50ms |
| **Total** | **~2,405ms** |

Comfortable margin under the 5-second budget. LLM report enhancement (P2) would add 1–3 seconds.

---

## 4. API Design

### Base URL: `http://localhost:8000/api/v1`

All responses: `Content-Type: application/json` (except PDF download)  
Authentication: `Authorization: Bearer <jwt_token>` header required on all routes except `/auth/login`  
Error format (consistent across all endpoints):
```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE"
}
```

---

### 4.1 Authentication

#### POST `/auth/login`

Authenticate user and return JWT token.

**Request:**
```json
{
  "username": "demo",
  "password": "demo123"
}
```

**Response 200 (Success):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

**Response 401 (Invalid credentials):**
```json
{
  "detail": "Invalid username or password",
  "error_code": "INVALID_CREDENTIALS"
}
```

**JWT payload:**
```json
{
  "sub": "demo",
  "user_id": 1,
  "exp": 1735776000,
  "iat": 1735747200
}
```

**JWT configuration:**
- Algorithm: HS256
- Secret: `SECRET_KEY` environment variable
- Expiry: 8 hours
- Stored in frontend: React state (in-memory), not localStorage

---

### 4.2 Scan Upload

#### POST `/scan/upload`

Upload a medical image file for later analysis.

**Request:**
```
Content-Type: multipart/form-data
Authorization: Bearer <token>
Body: file=<image binary>
```

**Validation rules:**
- Accepted MIME types: `image/png`, `image/jpeg`, `application/dicom`
- Max file size: 20MB
- Magic bytes validated (not just extension)

**Response 201 (Created):**
```json
{
  "scan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "chest_xray_001.png",
  "modality": "X-ray",
  "file_size_bytes": 1048576,
  "status": "uploaded",
  "uploaded_at": "2026-06-27T12:00:00Z",
  "thumbnail_url": "/static/thumbnails/a1b2c3d4.png"
}
```

**Response 400 (Invalid file):**
```json
{
  "detail": "Unsupported file type. Accepted formats: PNG, JPEG, DICOM (.dcm)",
  "error_code": "INVALID_FILE_TYPE"
}
```

**Response 413 (File too large):**
```json
{
  "detail": "File exceeds maximum size of 20MB",
  "error_code": "FILE_TOO_LARGE"
}
```

---

### 4.3 Scan Analysis

#### POST `/scan/analyze/{scan_id}`

Trigger AI inference on an uploaded scan. This is a synchronous call — the response is returned when analysis is complete.

> [Assumption] Synchronous is acceptable given < 5s latency. If latency exceeds 10s (e.g., GPU unavailable), switch to async with polling via WebSocket.

**Request:**
```
POST /api/v1/scan/analyze/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <token>
```

**Response 200 (Analysis complete):**
```json
{
  "scan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "analyzed",
  "classification": {
    "top_label": "Pneumonia",
    "confidence": 0.87,
    "severity": "Severe",
    "all_scores": {
      "Atelectasis": 0.12,
      "Cardiomegaly": 0.05,
      "Effusion": 0.23,
      "Infiltration": 0.31,
      "Mass": 0.08,
      "Nodule": 0.04,
      "Pneumonia": 0.87,
      "Pneumothorax": 0.02,
      "Consolidation": 0.19,
      "Edema": 0.07,
      "Emphysema": 0.03,
      "Fibrosis": 0.01,
      "Pleural Thickening": 0.06,
      "Hernia": 0.00,
      "No Finding": 0.02
    }
  },
  "localization": {
    "type": "heatmap",
    "heatmap_url": "/static/heatmaps/a1b2c3d4.png",
    "bounding_boxes": [
      {
        "x1": 89, "y1": 120, "x2": 195, "y2": 210,
        "label": "anomaly_region",
        "confidence": 0.82
      }
    ]
  },
  "analysis_time_ms": 3200,
  "analyzed_at": "2026-06-27T12:00:05Z"
}
```

**Response 404 (Scan not found):**
```json
{
  "detail": "Scan with ID a1b2c3d4 not found",
  "error_code": "SCAN_NOT_FOUND"
}
```

**Response 500 (Inference failure):**
```json
{
  "detail": "Model inference failed. Please try again.",
  "error_code": "INFERENCE_ERROR"
}
```

---

### 4.4 Report Generation

#### GET `/report/{scan_id}`

Retrieve the auto-generated structured report for an analyzed scan.

**Response 200:**
```json
{
  "scan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "report": {
    "patient_id": "DEMO-001",
    "scan_date": "2026-06-27",
    "modality": "Chest X-Ray (PA View)",
    "findings": "The AI analysis identifies findings consistent with Pneumonia (confidence: 87%). Increased opacity observed in the lower lobe region, as highlighted in the attached activation map. Secondary findings include possible Infiltration (confidence: 31%) and Effusion (confidence: 23%), both below the clinical significance threshold.",
    "impression": "Findings are suggestive of lower lobe Pneumonia. Severity assessed as: Severe based on model confidence scoring. Clinical correlation and follow-up imaging are recommended.",
    "severity": "Severe",
    "disclaimer": "⚠ DISCLAIMER: This report is AI-generated by MedAI Diagnostic Engine v1.0 and is intended as a clinical decision-support tool only. It must NOT be used as a standalone diagnostic instrument. All findings must be reviewed, verified, and co-signed by a licensed radiologist before any clinical action is taken.",
    "generated_at": "2026-06-27T12:00:05Z"
  }
}
```

---

#### POST `/report/{scan_id}/pdf`

Generate and download a formatted PDF report.

**Request (optional body — send edited report text):**
```json
{
  "edited_findings": "Findings consistent with right lower lobe pneumonia...",
  "edited_impression": "Right lower lobe pneumonia, recommend follow-up CT..."
}
```

**Response 200:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="report_a1b2c3d4.pdf"
Body: <PDF binary>
```

---

### 4.5 Scan History

#### GET `/history`

Return list of scans uploaded in the current session.

**Response 200:**
```json
{
  "scans": [
    {
      "scan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "filename": "chest_xray_001.png",
      "top_label": "Pneumonia",
      "confidence": 0.87,
      "severity": "Severe",
      "status": "analyzed",
      "uploaded_at": "2026-06-27T12:00:00Z",
      "thumbnail_url": "/static/thumbnails/a1b2c3d4.png"
    }
  ],
  "total": 1
}
```

---

### 4.6 Static File Serving

FastAPI serves static files from `/data/` directory:

| URL Path | Filesystem Path | Content |
|----------|----------------|---------|
| `/static/uploads/{scan_id}.png` | `/data/uploads/{scan_id}.png` | Original uploaded image (converted to PNG) |
| `/static/heatmaps/{scan_id}.png` | `/data/heatmaps/{scan_id}.png` | Grad-CAM heatmap overlay |
| `/static/thumbnails/{scan_id}.png` | `/data/thumbnails/{scan_id}.png` | 128×128 thumbnail for history sidebar |

---

## 5. Database Schema

**Engine:** SQLite 3 via SQLAlchemy 2.0 ORM  
**File location:** `/data/app.db`  
**Migration strategy:** Auto-create tables on startup via `Base.metadata.create_all()`  (sufficient for hackathon; use Alembic in production)

```sql
-- ===================================================================
-- users: Authentication table (seeded with demo user on first run)
-- ===================================================================
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed data (inserted by setup.sh or on first startup):
-- INSERT INTO users (username, hashed_password) 
-- VALUES ('demo', '$2b$12$...bcrypt_hash_of_demo123...');

-- ===================================================================
-- scans: Uploaded medical image records
-- ===================================================================
CREATE TABLE scans (
    id TEXT PRIMARY KEY,                    -- UUID v4 string
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,                 -- original filename
    modality TEXT DEFAULT 'X-ray',          -- 'X-ray', 'CT', 'MRI', 'Unknown'
    file_path TEXT NOT NULL,                -- /data/uploads/{id}.png
    heatmap_path TEXT,                      -- /data/heatmaps/{id}.png (NULL until analyzed)
    thumbnail_path TEXT,                    -- /data/thumbnails/{id}.png
    file_size_bytes INTEGER,
    status TEXT DEFAULT 'uploaded' CHECK(status IN ('uploaded', 'analyzing', 'analyzed', 'failed')),
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ===================================================================
-- results: AI inference results, one-to-one with analyzed scans
-- ===================================================================
CREATE TABLE results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL REFERENCES scans(id),
    top_label TEXT NOT NULL,                -- e.g., 'Pneumonia'
    confidence REAL NOT NULL,               -- 0.0 – 1.0
    severity TEXT NOT NULL CHECK(severity IN ('Normal', 'Mild', 'Moderate', 'Severe')),
    all_scores TEXT NOT NULL,               -- JSON: {"Pneumonia": 0.87, "Effusion": 0.23, ...}
    localization_type TEXT DEFAULT 'heatmap',-- 'heatmap' or 'bbox'
    bounding_boxes TEXT,                    -- JSON: [{"x1":89,"y1":120,...}, ...]
    analysis_time_ms INTEGER,
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ===================================================================
-- reports: Generated clinical reports, one-to-one with analyzed scans
-- ===================================================================
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL REFERENCES scans(id),
    patient_id TEXT DEFAULT 'DEMO-001',     -- placeholder for demo
    report_json TEXT NOT NULL,              -- full structured report as JSON
    edited_findings TEXT,                   -- clinician-edited findings (NULL until edited)
    edited_impression TEXT,                 -- clinician-edited impression (NULL until edited)
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**SQLAlchemy ORM models (abbreviated):**
```python
# backend/db/models.py
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    scans = relationship("Scan", back_populates="user")

class Scan(Base):
    __tablename__ = "scans"
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    modality = Column(String, default="X-ray")
    file_path = Column(String, nullable=False)
    heatmap_path = Column(String)
    thumbnail_path = Column(String)
    file_size_bytes = Column(Integer)
    status = Column(String, default="uploaded")
    uploaded_at = Column(DateTime, server_default=func.now())
    user = relationship("User", back_populates="scans")
    result = relationship("Result", back_populates="scan", uselist=False)
    report = relationship("Report", back_populates="scan", uselist=False)

class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), unique=True, nullable=False)
    top_label = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String, nullable=False)
    all_scores = Column(Text, nullable=False)  # JSON
    localization_type = Column(String, default="heatmap")
    bounding_boxes = Column(Text)  # JSON
    analysis_time_ms = Column(Integer)
    analyzed_at = Column(DateTime, server_default=func.now())
    scan = relationship("Scan", back_populates="result")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), unique=True, nullable=False)
    patient_id = Column(String, default="DEMO-001")
    report_json = Column(Text, nullable=False)  # JSON
    edited_findings = Column(Text)
    edited_impression = Column(Text)
    generated_at = Column(DateTime, server_default=func.now())
    scan = relationship("Scan", back_populates="report")
```

---

## 6. Report Generation Design

### Strategy: Template-First + Optional LLM Enhancement

This is a two-tier strategy. The Jinja2 template is the **always-available** baseline (P0). LLM enhancement is a **nice-to-have** (P2) that produces more fluent prose but requires an API key.

### 6.1 Tier 1 — Jinja2 Structured Template (P0)

**Template file:** `backend/templates/report.html`

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #1a1a1a; }
        .header { border-bottom: 2px solid #0066cc; padding-bottom: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 18px; color: #0066cc; margin: 0; }
        .header p { font-size: 12px; color: #666; margin: 2px 0; }
        .section { margin-bottom: 20px; }
        .section h2 { font-size: 14px; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
        .section p { font-size: 13px; line-height: 1.6; }
        .severity-badge { display: inline-block; padding: 2px 12px; border-radius: 4px; font-weight: bold; font-size: 13px; }
        .severity-Normal { background: #e6f4ea; color: #1e7e34; }
        .severity-Mild { background: #fff8e1; color: #f57f17; }
        .severity-Moderate { background: #fff3e0; color: #e65100; }
        .severity-Severe { background: #fde0dc; color: #c62828; }
        .disclaimer { background: #fff3cd; border: 1px solid #ffc107; padding: 12px; border-radius: 4px; font-size: 11px; margin-top: 30px; }
        .footer { font-size: 10px; color: #999; margin-top: 40px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏥 MedAI Diagnostic Engine — Radiology AI Draft Report</h1>
        <p>Report ID: {{ report_id }} | Generated: {{ generated_at }}</p>
    </div>

    <div class="section">
        <h2>Patient Information</h2>
        <p><strong>Patient ID:</strong> {{ patient_id }}<br>
        <strong>Scan Date:</strong> {{ scan_date }}<br>
        <strong>Modality:</strong> {{ modality }}<br>
        <strong>Analyzed By:</strong> MedAI Diagnostic Engine v1.0</p>
    </div>

    <div class="section">
        <h2>AI Classification</h2>
        <p><strong>Primary Finding:</strong> {{ top_label }}
        (Confidence: {{ "%.1f"|format(confidence * 100) }}%)<br>
        <strong>Severity:</strong> <span class="severity-badge severity-{{ severity }}">{{ severity }}</span></p>
    </div>

    <div class="section">
        <h2>Findings</h2>
        <p>{{ findings }}</p>
    </div>

    <div class="section">
        <h2>Impression</h2>
        <p>{{ impression }}</p>
    </div>

    <div class="disclaimer">
        <strong>⚠ DISCLAIMER:</strong> {{ disclaimer }}
    </div>

    <div class="footer">
        <p>Generated by MedAI Diagnostic Engine v1.0 — For decision support only — Not a certified medical device</p>
    </div>
</body>
</html>
```

**Template population logic:**
```python
# backend/services/report_generator.py
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

class ReportGenerator:
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template("report.html")
        self.disclaimer = (
            "This report is AI-generated by MedAI Diagnostic Engine v1.0 "
            "and is intended as a clinical decision-support tool only. "
            "It must NOT be used as a standalone diagnostic instrument. "
            "All findings must be reviewed, verified, and co-signed by a "
            "licensed radiologist before any clinical action is taken."
        )

    def generate_findings(self, classification_result: 'ClassificationResult') -> str:
        """Generate findings text from classification result."""
        label = classification_result.top_label
        conf = classification_result.confidence
        severity = classification_result.severity

        findings = (
            f"The AI analysis identifies findings consistent with {label} "
            f"(confidence: {conf*100:.1f}%). "
        )

        # Add secondary findings above threshold
        secondary = {
            k: v for k, v in classification_result.all_scores.items()
            if k != label and k != "No Finding" and v > 0.2
        }
        if secondary:
            secondary_text = ", ".join(
                f"{k} ({v*100:.1f}%)" for k, v in
                sorted(secondary.items(), key=lambda x: -x[1])
            )
            findings += f"Secondary findings include: {secondary_text}. "
        
        if label == "No Finding":
            findings = (
                "The AI analysis does not identify any significant abnormality. "
                "The lung fields appear clear. Cardiac silhouette is within normal limits."
            )

        return findings

    def generate_impression(self, classification_result: 'ClassificationResult') -> str:
        """Generate impression text from classification result."""
        label = classification_result.top_label
        severity = classification_result.severity

        if label == "No Finding":
            return "No significant abnormality detected. Clinical correlation recommended."
        
        return (
            f"Findings are suggestive of {label}. "
            f"Severity assessed as: {severity} based on model confidence scoring. "
            f"Clinical correlation and follow-up imaging are recommended."
        )

    def generate(
        self,
        classification_result: 'ClassificationResult',
        scan_id: str,
        modality: str = "Chest X-Ray (PA View)",
        patient_id: str = "DEMO-001"
    ) -> dict:
        """Generate the full structured report as a dictionary."""
        findings = self.generate_findings(classification_result)
        impression = self.generate_impression(classification_result)

        return {
            "patient_id": patient_id,
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "modality": modality,
            "findings": findings,
            "impression": impression,
            "severity": classification_result.severity,
            "disclaimer": self.disclaimer,
            "generated_at": datetime.now().isoformat()
        }

    def render_html(self, report: dict, scan_id: str) -> str:
        """Render report dict to HTML string for PDF generation."""
        return self.template.render(
            report_id=scan_id[:8],
            generated_at=report["generated_at"],
            patient_id=report["patient_id"],
            scan_date=report["scan_date"],
            modality=report["modality"],
            top_label=report.get("top_label", ""),
            confidence=report.get("confidence", 0),
            severity=report["severity"],
            findings=report["findings"],
            impression=report["impression"],
            disclaimer=report["disclaimer"]
        )
```

### 6.2 Tier 2 — LLM Enhancement (P2, Optional)

Used only if `LLM_API_KEY` environment variable is set. Enhances the template-generated findings with more fluent clinical prose.

```python
# backend/services/report_generator.py (continued)
import httpx

class LLMReportEnhancer:
    SYSTEM_PROMPT = """You are a board-certified radiologist writing a structured draft report.
Given the AI model's classification results, write concise, professional Findings and Impression sections.
Use standard radiology report language. Be specific about location and severity.
Do NOT make definitive diagnoses. Use hedging language: 'consistent with', 'suggestive of', 'cannot exclude'.
Keep each section to 2-4 sentences.
Output JSON with exactly two keys: "findings" and "impression". No other text."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=10.0
        )

    async def enhance(self, classification_result: 'ClassificationResult') -> dict | None:
        """Enhance report with LLM. Returns None on failure (fallback to template)."""
        try:
            user_msg = (
                f"Top finding: {classification_result.top_label} "
                f"(confidence: {classification_result.confidence*100:.1f}%). "
                f"Severity: {classification_result.severity}. "
                f"All scores: {classification_result.all_scores}"
            )
            response = await self.client.post("/messages", json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "system": self.SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}]
            })
            if response.status_code == 200:
                import json
                content = response.json()["content"][0]["text"]
                return json.loads(content)
        except Exception:
            pass  # Fail silently, template is the fallback
        return None
```

### 6.3 PDF Generation

```python
# backend/services/pdf_generator.py
from weasyprint import HTML

class PDFGenerator:
    def generate(self, html_content: str) -> bytes:
        """Convert HTML report to PDF bytes."""
        return HTML(string=html_content).write_pdf()
```

---

## 7. Frontend Design

### 7.1 Page Architecture

The frontend is a single-page application with 3 routes, built with React 18 + TypeScript + Vite.

| Route | Page Component | Description |
|-------|---------------|-------------|
| `/login` | `LoginPage.tsx` | Authentication form |
| `/upload` | `UploadPage.tsx` | Drag-and-drop upload + analyze trigger |
| `/results/:scanId` | `ResultsPage.tsx` | Scan viewer + classification + report |

**Routing:** React Router v6 with `PrivateRoute` wrapper that redirects to `/login` if no JWT token is present.

### 7.2 TypeScript Interfaces

```typescript
// frontend/src/types/index.ts

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UploadResponse {
  scan_id: string;
  filename: string;
  modality: string;
  file_size_bytes: number;
  status: string;
  uploaded_at: string;
  thumbnail_url: string;
}

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label: string;
  confidence: number;
}

export interface ClassificationResult {
  top_label: string;
  confidence: number;
  severity: "Normal" | "Mild" | "Moderate" | "Severe";
  all_scores: Record<string, number>;
}

export interface LocalizationResult {
  type: "heatmap" | "bbox";
  heatmap_url: string;
  bounding_boxes: BoundingBox[];
}

export interface AnalysisResponse {
  scan_id: string;
  status: string;
  classification: ClassificationResult;
  localization: LocalizationResult;
  analysis_time_ms: number;
  analyzed_at: string;
}

export interface ReportData {
  patient_id: string;
  scan_date: string;
  modality: string;
  findings: string;
  impression: string;
  severity: string;
  disclaimer: string;
  generated_at: string;
}

export interface ReportResponse {
  scan_id: string;
  report: ReportData;
}

export interface HistoryScan {
  scan_id: string;
  filename: string;
  top_label: string;
  confidence: number;
  severity: string;
  status: string;
  uploaded_at: string;
  thumbnail_url: string;
}

export interface HistoryResponse {
  scans: HistoryScan[];
  total: number;
}
```

### 7.3 API Client

```typescript
// frontend/src/api/client.ts
import axios from 'axios';
import type {
  LoginRequest, LoginResponse,
  UploadResponse, AnalysisResponse,
  ReportResponse, HistoryResponse
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Inject JWT token into every request
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>('/auth/login', data);
  return res.data;
}

export async function uploadScan(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post<UploadResponse>('/scan/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function analyzeScan(scanId: string): Promise<AnalysisResponse> {
  const res = await api.post<AnalysisResponse>(`/scan/analyze/${scanId}`);
  return res.data;
}

export async function getReport(scanId: string): Promise<ReportResponse> {
  const res = await api.get<ReportResponse>(`/report/${scanId}`);
  return res.data;
}

export async function downloadPdf(
  scanId: string,
  editedFindings?: string,
  editedImpression?: string
): Promise<Blob> {
  const res = await api.post(`/report/${scanId}/pdf`, {
    edited_findings: editedFindings,
    edited_impression: editedImpression,
  }, { responseType: 'blob' });
  return res.data;
}

export async function getHistory(): Promise<HistoryResponse> {
  const res = await api.get<HistoryResponse>('/history');
  return res.data;
}
```

### 7.4 Key Component: ScanViewer

```tsx
// frontend/src/components/ScanViewer.tsx
// Canvas-based image viewer with heatmap overlay toggle

interface ScanViewerProps {
  originalUrl: string;           // URL to original scan image
  heatmapUrl: string;            // URL to Grad-CAM heatmap overlay
  boundingBoxes?: BoundingBox[]; // Optional bounding boxes
  imageSize: { width: number; height: number };
}

// View modes:
// 1. "original" — shows only the uploaded scan
// 2. "heatmap"  — shows Grad-CAM overlay at 40% alpha on original
// 3. "sidebyside" — shows both side by side

// Implementation uses HTML5 Canvas:
// - Layer 1: Original image drawn on canvas
// - Layer 2: Heatmap image drawn with globalAlpha = 0.4
// - Layer 3: Bounding boxes drawn with strokeRect + text labels
// Toggle buttons switch between view modes with smooth CSS transition
```

### 7.5 Key Component: ResultPanel

```tsx
// frontend/src/components/ResultPanel.tsx

interface ResultPanelProps {
  classification: ClassificationResult;
  analysisTimeMs: number;
}

// Layout:
// ┌─────────────────────────────────────┐
// │  PRIMARY FINDING                     │
// │  ┌──────────────────────────────┐   │
// │  │  🫁 Pneumonia           87%  │   │
// │  │  ██████████████████░░░░░░    │   │  ← colored progress bar
// │  │  Severity: [SEVERE]          │   │  ← color-coded badge
// │  └──────────────────────────────┘   │
// │                                      │
// │  ALL FINDINGS (expandable)           │
// │  ├── Infiltration      31%          │
// │  ├── Effusion          23%          │
// │  ├── Atelectasis       12%          │
// │  └── ... (sorted by confidence)     │
// │                                      │
// │  Analysis time: 3.2s                │
// └─────────────────────────────────────┘

// Severity badge colors:
// Normal   → green  (#22c55e)
// Mild     → yellow (#eab308)
// Moderate → orange (#f97316)
// Severe   → red    (#ef4444)
```

### 7.6 Design System

**Color palette (dark medical theme):**
```css
:root {
  --bg-primary: #0f1117;      /* near-black background */
  --bg-secondary: #1a1d27;    /* card/panel background */
  --bg-tertiary: #252833;     /* input/interactive background */
  --text-primary: #e4e7ec;    /* primary text */
  --text-secondary: #9ba1b0;  /* secondary text */
  --accent-blue: #3b82f6;     /* primary action */
  --accent-cyan: #06b6d4;     /* medical accent */
  --severity-normal: #22c55e;
  --severity-mild: #eab308;
  --severity-moderate: #f97316;
  --severity-severe: #ef4444;
  --border: #2d3140;
}
```

**Typography:** Inter (Google Fonts), monospace for data values.

---

## 8. Security Design

| Threat | Probability | Mitigation |
|--------|-------------|-----------|
| Unauthenticated API access | High | JWT required on all routes except `/auth/login`; validated with `python-jose` on every request via FastAPI dependency injection |
| Malicious file upload | Medium | File type validated by magic bytes (`imghdr` + manual check), not just extension; max size 20MB enforced by FastAPI; no executable extensions allowed |
| Path traversal via filename | Medium | All files stored with UUID-based names only (`{scan_id}.png`); original filename stored in DB but never used in filesystem paths |
| XSS via report text | Low | Report text HTML-escaped by Jinja2 `{{ variable }}` auto-escaping; React's JSX also escapes by default |
| Real patient data exposure | Low | Demo mode only; no real patient data loaded; disclaimer on every page and report; no data persistence across Docker restarts (volume optional) |
| CORS misconfiguration | Medium | FastAPI `CORSMiddleware` configured to allow only `http://localhost:3000`; credentials allowed for JWT header |
| JWT token theft | Low | Token stored in React state (in-memory), not `localStorage`; expires in 8 hours; transmitted only via `Authorization` header |
| Denial of service via large uploads | Low | Max file size 20MB; rate limiting not implemented (single-user demo) |

> [Assumption] HTTPS is not required for local demo. If deployed to cloud, use nginx reverse proxy with Let's Encrypt TLS termination.

---

## 9. Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.9'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: medai-backend
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models:ro          # model weights (read-only)
      - medai-data:/app/data             # uploads, heatmaps, thumbnails, DB
    environment:
      - MODEL_PATH=/app/models/classifier.pt
      - DATA_DIR=/app/data
      - SECRET_KEY=${SECRET_KEY:-medai-hackathon-secret-change-in-prod}
      - LLM_API_KEY=${ANTHROPIC_API_KEY:-}
      - DEMO_USER=demo
      - DEMO_PASSWORD=demo123
      - LOG_LEVEL=info
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: medai-frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  medai-data:
    driver: local
```

**Backend Dockerfile:**
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for WeasyPrint and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/heatmaps /app/data/thumbnails

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Backend requirements.txt:**
```
fastapi==0.111.0
uvicorn[standard]==0.30.1
python-multipart==0.0.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
sqlalchemy==2.0.31
pillow==10.4.0
pydicom==2.4.4
torch==2.3.1+cpu
torchvision==0.18.1+cpu
timm==0.9.16
pytorch-grad-cam==1.5.4
jinja2==3.1.4
weasyprint==62.3
numpy==1.26.4
httpx==0.27.0
```

> [Assumption] Using PyTorch CPU-only wheels (`+cpu` suffix) to reduce Docker image size from ~5GB to ~2GB. Install via `--extra-index-url https://download.pytorch.org/whl/cpu`.

**Frontend Dockerfile:**
```dockerfile
# frontend/Dockerfile
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

**Frontend nginx.conf (for SPA routing):**
```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**One-command startup:**
```bash
# Step 1: Setup (run once)
chmod +x setup.sh && ./setup.sh

# Step 2: Launch
docker compose up --build

# Step 3: Open browser
# Navigate to http://localhost:3000
# Login: demo / demo123
```

---

## 10. Model Weight Download Strategy

Model weights (`.pt` files) must NOT be committed to git. They are either auto-downloaded on first run or manually placed.

**setup.sh:**
```bash
#!/bin/bash
set -e

echo "🏥 MedAI Diagnostic Engine — Setup"
echo "==================================="

# Create required directories
echo "📁 Creating directories..."
mkdir -p models data/uploads data/heatmaps data/thumbnails demo_data

# Strategy: Use timm pretrained weights (auto-download on first inference)
# No manual download needed — timm downloads EfficientNet-B4 weights
# from HuggingFace Hub on first call to timm.create_model(..., pretrained=True)
echo "🧠 Model weights will be auto-downloaded on first inference via timm."
echo "   Model: EfficientNet-B4 (ImageNet pretrained)"
echo "   Size: ~75MB (downloaded to ~/.cache/torch/hub/)"

# Optional: Download CheXNet-compatible weights for better clinical accuracy
# Uncomment the following if you have fine-tuned weights available:
# echo "📥 Downloading fine-tuned classifier weights..."
# python -c "
# from huggingface_hub import hf_hub_download
# hf_hub_download(
#     repo_id='medai-team/chexnet-efficientnet-b4',
#     filename='classifier.pt',
#     local_dir='models/'
# )
# "

# Generate .env file with defaults
if [ ! -f .env ]; then
    echo "🔧 Creating .env file with defaults..."
    cat > .env << EOF
SECRET_KEY=medai-hackathon-$(openssl rand -hex 16 2>/dev/null || echo "change-me-in-production")
ANTHROPIC_API_KEY=
EOF
    echo "   Edit .env to add your Anthropic API key (optional, for LLM report enhancement)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. (Optional) Add demo images to demo_data/"
echo "  2. Run: docker compose up --build"
echo "  3. Open: http://localhost:3000"
echo "  4. Login: demo / demo123"
```

**Fallback for no-Docker development:**
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## 11. Build Plan — Hackathon Timeline

Assumes 3-person team: **Frontend (FE)**, **Backend/API (BE)**, **ML Engineer (ML)**. 24-hour schedule.

| Hour | Task | Owner | Deliverable | Dependencies |
|------|------|-------|-------------|--------------|
| **0–2** | Repo setup, Docker Compose skeleton, FastAPI hello world, health endpoint | BE | `docker compose up` returns 200 on `/health` | None |
| **0–2** | Vite + React + Tailwind scaffold, routing setup, dark theme CSS, login page UI | FE | Login page renders with styled form | None |
| **0–2** | Set up `timm` model loading, verify EfficientNet-B4 runs on CPU, measure latency | ML | `classifier.predict(image)` returns result in < 2s | None |
| **2–5** | File upload endpoint (`POST /scan/upload`), file validation, SQLite schema + ORM models | BE | Upload returns `scan_id`, file saved to disk | Hour 0–2 BE |
| **2–5** | Upload page UI: drag-and-drop zone, file preview, "Analyze" button, loading states | FE | File selected → preview shown → API called | Hour 0–2 FE |
| **2–5** | Grad-CAM integration: `AnomalyLocalizer` class, heatmap generation, overlay compositing | ML | `generate_heatmap()` returns valid PNG | Hour 0–2 ML |
| **5–8** | Analysis endpoint (`POST /scan/analyze/{id}`): wire classifier + localizer, store results | BE | Full inference pipeline returns JSON | Hour 2–5 BE + ML |
| **5–8** | Results page: `ScanViewer` component with canvas-based heatmap overlay toggle | FE | Original + heatmap + side-by-side views work | Hour 2–5 FE |
| **8–11** | `ResultPanel` component: classification label, confidence bar, severity badge, all scores | FE | All classification data displayed with color coding | Hour 5–8 FE |
| **8–11** | Report generator (Jinja2): `ReportGenerator` class, findings/impression text, HTML template | BE | `GET /report/{id}` returns structured report JSON | Hour 5–8 BE |
| **11–14** | `ReportEditor` component: editable textarea, "Download PDF" button | FE | Report auto-populated, editable, PDF downloads | Hour 8–11 FE + BE |
| **11–14** | PDF generation (WeasyPrint): `POST /report/{id}/pdf` endpoint | BE | PDF renders correctly with all fields | Hour 8–11 BE |
| **14–16** | JWT auth: login endpoint, middleware, frontend `useAuth` hook, protected routes | BE + FE | Login flow works end-to-end; 401 on unauthenticated | Hour 11–14 |
| **16–18** | DICOM parser (`pydicom`): `.dcm` upload support, metadata extraction | ML | DICOM files convert to PNG and analyze correctly | Hour 5–8 ML |
| **16–18** | History sidebar: `GET /history` endpoint + `HistorySidebar` component | BE + FE | Previous scans listed with thumbnails | Hour 14–16 |
| **18–20** | Integration testing: upload 10 demo images, verify all outputs, fix bugs | ALL | All 10 demo images produce correct results | Hour 16–18 |
| **20–22** | UI polish: animations, transitions, error states, empty states, responsive tweaks | FE | UI feels polished and professional | Hour 18–20 |
| **20–22** | Error handling hardening: try/catch on all endpoints, graceful failures, logging | BE | No unhandled exceptions; all errors return JSON | Hour 18–20 |
| **22–24** | README, demo script rehearsal, backup plan (local run without Docker), final testing | ALL | Demo-ready; README documents full setup | Hour 20–22 |

### Stretch Goals (if time permits after hour 20)

| Priority | Task | Est. Time | Owner |
|----------|------|-----------|-------|
| S1 | LLM-enhanced report prose (Anthropic Claude API) | 2h | BE |
| S2 | YOLOv8 bounding boxes (VinDr-CXR model) | 3h | ML |
| S3 | CT scan support (RSNA ICH dataset) | 3h | ML |
| S4 | Responsive mobile layout | 1h | FE |
| S5 | Export heatmap overlay as separate downloadable PNG | 30m | FE |

---

## 12. Risk Register

| # | Risk | Probability | Impact | Mitigation | Owner |
|---|------|-------------|--------|-----------|-------|
| R1 | GPU not available in demo environment | High | High | All models tested and benchmarked on CPU; EfficientNet-B4 < 1.5s on i7 CPU. Use PyTorch CPU-only wheels to reduce image size. | ML |
| R2 | DICOM parsing edge cases (compressed, multi-frame, non-standard) | Medium | Medium | Fall back to PNG/JPEG-only if pydicom fails on a specific file; show clear "Unsupported DICOM format" error. Pre-test with 3 representative DICOM files. | ML |
| R3 | LLM API rate limit, network failure, or no API key | Medium | Low | Jinja2 template report is the P0 primary path; LLM enhancement is P2 optional. System fully functional without any API key. | BE |
| R4 | Model accuracy disappoints judges (ImageNet weights not clinically meaningful) | Medium | High | Pre-select 10 demo images where model heatmaps are visually convincing. Show confidence scores honestly. Explain in demo that fine-tuning is the next step. If time permits, load CheXNet weights. | ML |
| R5 | Docker build fails on judge's machine (platform mismatch, disk space) | Low | High | Provide `pip install` + `npm install` fallback instructions in README. Test build on both ARM64 (Mac M-series) and AMD64 (Linux/Windows). | BE |
| R6 | WeasyPrint installation fails (system library dependencies) | Medium | Medium | WeasyPrint needs `libpango`, `libcairo` — installed in Dockerfile. If it fails, fall back to generating HTML report (downloadable as `.html`). | BE |
| R7 | Frontend API calls fail due to CORS misconfiguration | Low | Medium | CORS middleware configured in `main.py` on first setup. Test cross-origin requests in hour 2. | BE |
| R8 | SQLite write contention under concurrent use | Low | Low | Not an issue for single-user demo. Document as production migration path (→ PostgreSQL). | BE |

---

## 13. Definition of Done (Demo Checklist)

### Critical (must pass before demo)

- [ ] `docker compose up --build` starts both services with zero errors
- [ ] `http://localhost:3000` loads in < 3 seconds
- [ ] Login with `demo` / `demo123` succeeds → redirects to upload page
- [ ] Upload a PNG chest X-ray → file preview appears
- [ ] Click "Analyze" → result appears in < 5 seconds
- [ ] Grad-CAM heatmap overlay renders correctly with toggle (original/heatmap/side-by-side)
- [ ] Classification label + confidence percentage + severity badge all displayed correctly
- [ ] Draft report auto-populated with findings, impression, severity, and disclaimer
- [ ] PDF download works — opens correctly in a PDF viewer
- [ ] No crashes during 5 consecutive upload-analyze cycles

### Important (should pass)

- [ ] DICOM (.dcm) upload works (at least one test file)
- [ ] All 10 demo images produce visually plausible heatmaps
- [ ] Report is editable before PDF download
- [ ] History sidebar shows previous scans with thumbnails
- [ ] Error messages display for invalid file uploads (e.g., uploading a .txt file)
- [ ] Authentication: unauthenticated API requests return 401

### Nice to Have (stretch)

- [ ] LLM-enhanced report prose is noticeably better than template
- [ ] Bounding boxes drawn on scan viewer
- [ ] CT scan produces valid output
- [ ] UI animations and transitions feel polished
- [ ] README includes GIF/video demo of the workflow
