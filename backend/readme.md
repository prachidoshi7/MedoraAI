# MedoraAI Backend

FastAPI backend for authentication, uploads, ML inference, Grad-CAM generation, LLM-assisted reports, and PDF export.

## Setup

From the repo root:

```powershell
cd backend
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

## Required Model Paths

The backend reads model paths from `.env` in the repo root:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/brain_tumor_mobilenetv2.h5
```

Relative paths are resolved from the repo root by `backend/config.py`.

## Run

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected model status:

```text
chest_xray: loaded
brain_mri: loaded
```

## Runtime Data

The backend creates runtime data under:

```text
data/uploads
data/heatmaps
data/thumbnails
```

The SQLite database is:

```text
data/app.db
```

## Demo Credentials

Configured in `.env`:

```env
DEMO_USER=demo
DEMO_PASSWORD=demo123
```
