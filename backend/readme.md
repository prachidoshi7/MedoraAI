# MedoraAI Backend

FastAPI backend for authentication, uploads, ML inference, Grad-CAM generation, LLM-assisted reports, and PDF export.

## Setup

From the repo root:

```powershell
cd backend
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Required Model Paths

The backend reads model paths from `.env` in the repo root:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/best_brain_model.keras
LUNG_MODEL_PATH=./models/cnn_lung_model.pth
KIDNEY_MODEL_PATH=./models/cnn_Kidney_Stone_model.pth
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
lung_ct: loaded
kidney_us: loaded
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

Additional seeded credentials:

```text
patient / patient123
dr.sharma / doctor123
lab.tech / lab123
```
