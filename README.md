# MedoraAI

MedoraAI is a multi-role hospital diagnostic workflow platform connecting patients, doctors, lab technicians, and explainable AI. It covers appointment booking, consultation, diagnostic ordering, scan analysis, doctor sign-off, prescriptions, native-language patient communication, and final case-study export.

> **Clinical safety notice:** MedoraAI is an experimental decision-support project, not a certified medical device. Its output is preliminary and must be reviewed against the complete source examination by a qualified clinician. Do not use it as the sole basis for diagnosis or treatment.

## Features

- Chest X-ray multi-label classification using RAD-DINO with a 14-label CheXpert head
- Four-class brain MRI classification with EfficientNetB3: Glioma, Meningioma, No Tumor, and Pituitary
- Five-class lung CT classification and kidney ultrasound stone screening using the bundled PyTorch models
- Patient, doctor, and lab-technician portals with role-bearing JWT authentication
- Department/doctor selection, scheduled appointment requests, clinical notes, and lab diagnostic orders
- Doctor report review/release, prescriptions, specialist forwarding, and complete case-study PDFs
- Class-targeted RAD-DINO token attribution for chest X-rays and Grad-CAM/Grad-CAM++ for convolutional models
- Local-first scan-type verification that rejects obvious screenshots, documents, mismatched anatomy, and unusable images before diagnostic inference
- Independent vision-service fallback for ambiguous chest-versus-brain verification
- Structured, editable clinician report with Technique, Comparison, Findings, Impression, Differential, Recommendations, and Communication
- Grounding rules that prevent unsupported MRI sequence, contrast, enhancement, diffusion, comparison, and measurement claims
- Patient-friendly explanations with Sarvam translation and an internal fallback path
- Native ReportLab PDF generation that works on Windows without GTK/Pango
- JWT authentication, scan history, thumbnails, and generated-report storage
- Responsive React interface based on the Medora prototype design

## Technology

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Axios |
| API | FastAPI, Pydantic, SQLAlchemy, SQLite |
| Chest model | PyTorch, Hugging Face Transformers, RAD-DINO + CheXpert |
| Brain model | TensorFlow/Keras, EfficientNetB3 |
| Imaging | Pillow, OpenCV, pydicom |
| Explainability | RAD-DINO patch-token attribution, Grad-CAM and multi-scale Grad-CAM++ |
| Reports | Image-aware language model with grounded template fallbacks |
| Translation | Sarvam translation with bounded fallback |
| PDF | ReportLab |

## Repository Layout

```text
MedoraAI/
├── backend/                 FastAPI application, classifiers and tests
│   ├── routers/             Auth, appointment, diagnostic, report and case routes
│   ├── services/            Models, validation, attribution, reports and PDF
│   ├── templates/           Text/HTML report templates
│   └── tests/               Validation, report and PDF regression tests
├── frontend/                React and TypeScript user interface
├── models/                  Runtime model artifacts and model instructions
├── .env.example             Safe environment-variable template
└── docker-compose.yml       Local container deployment
```

## Required Model Files

Place the current model artifacts in `models/`:

```text
models/best_brain_model.keras
models/cnn_lung_model.pth
models/cnn_Kidney_Stone_model.pth
```

The three bundled runtime model binaries are versioned with Git LFS. Install Git LFS before cloning so the real model files—not only their small pointer files—are downloaded. The pinned RAD-DINO CheXpert checkpoint is downloaded from Hugging Face on first backend startup and then reused from the local cache.

## Prerequisites

- Python 3.11 recommended
- Node.js 20.19+ or Node.js 22.12+
- PowerShell on Windows
- Git, Git LFS, and GitHub CLI for repository publishing
- Optional: Docker Desktop

## Local Setup

Clone and enter the repository:

```powershell
git clone https://github.com/AcID3r/MEDORAAA_AI.git
cd MEDORAAA_AI
git lfs pull
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
notepad .env
```

At minimum, set a strong `SECRET_KEY` and the API keys needed by your deployment. Bundled model paths already have safe defaults:

```env
SECRET_KEY=replace-with-a-long-random-secret

CHEST_MODEL_ID=kaan-ylmn/rad-dino-chexpert
CHEST_MODEL_REVISION=db02e1b7234dd83c6d7c4485963ef5b22df9e5db
CHEST_DEVICE=auto
BRAIN_MODEL_PATH=./models/best_brain_model.keras
LUNG_MODEL_PATH=./models/cnn_lung_model.pth
KIDNEY_MODEL_PATH=./models/cnn_Kidney_Stone_model.pth

GROQ_API_KEY=
GEMINI_API_KEY=
SARVAM_API_KEY=
```

High-confidence scan types are verified locally. With strict validation enabled, ambiguous images require at least one configured vision-service key. Never commit `.env`; it is ignored by Git.

Install the backend:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
cd ..
```

Install the frontend:

```powershell
cd frontend
npm install
cd ..
```

## Run the Application

Backend terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

The API starts without external LLM keys by using its grounded template report
fallback. A Git/LFS clone includes the brain, lung, and kidney models. The first
chest-model startup needs internet access to cache the pinned 346 MB RAD-DINO
CheXpert checkpoint; later starts can use `CHEST_MODEL_LOCAL_FILES_ONLY=true`.

Role-specific development logins:

```text
Patient: patient / patient123
Doctor: dr.sharma / doctor123
Lab technician: lab.tech / lab123
Pharmacy: pharmacy / pharmacy123
Administrator: admin / admin123
Legacy clinician: demo / demo123
```

Change the demo credentials before sharing or deploying the application.

## Validation and Tests

Run the backend regression suite:

```powershell
cd backend
python -m unittest discover -s tests -v
```

Build and lint the frontend:

```powershell
cd frontend
npm run build
npm run lint
```

The regression suite covers strict scan-type rejection, local/provider fallback behavior, grounded report content, patient translation fallback, and professional multi-page PDF generation.

## Docker

After creating `.env` and pulling the bundled Git LFS model files:

```powershell
docker compose up --build
```

Open `http://localhost:3000`. The backend health endpoint is available at `http://localhost:8000/health`.

## Medical Data and Secrets

- Do not commit API keys, `.env`, SQLite databases, uploaded scans, heatmaps, thumbnails, or patient-identifiable information.
- Runtime data under `backend/data/` is ignored.
- Use de-identified test images only.
- Model-attribution heatmaps show regions that influenced a prediction; they do not prove lesion localization.
- A single uploaded image is not equivalent to a complete radiology examination.

## Documentation

Additional setup, design, evaluation and project-planning documents are available under [`docs/`](docs/).
