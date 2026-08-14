# MedoraAI Backend

FastAPI backend for authentication, uploads, ML inference, model attribution, LLM-assisted reports, and PDF export.

## Setup

From the repo root:

```powershell
cd backend
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Model Configuration

The backend reads model settings from `.env` in the repo root. The chest model
uses a pinned Hugging Face RAD-DINO CheXpert checkpoint; the other classifiers
use bundled local artifacts:

```env
CHEST_MODEL_ID=kaan-ylmn/rad-dino-chexpert
CHEST_MODEL_REVISION=db02e1b7234dd83c6d7c4485963ef5b22df9e5db
CHEST_DEVICE=auto
BRAIN_MODEL_PATH=./models/best_brain_model.keras
LUNG_MODEL_PATH=./models/cnn_lung_model.pth
KIDNEY_MODEL_PATH=./models/cnn_Kidney_Stone_model.pth
```

Relative local paths are resolved from the repo root by `backend/config.py`.
The first chest inference setup downloads about 346 MB; subsequent starts reuse
the Hugging Face cache. Set `CHEST_MODEL_LOCAL_FILES_ONLY=true` after caching for
an offline deployment.

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
pharmacy / pharmacy123
admin / admin123
```
