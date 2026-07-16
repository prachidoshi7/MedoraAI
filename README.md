# MedoraAI

MedoraAI is a local medical imaging demo platform for:

- Chest X-ray analysis with a fine-tuned EfficientNet-B4 15-class classifier
- Brain MRI tumor detection with a MobileNetV2 classifier
- Grad-CAM heatmap visualization
- LLM-assisted clinical report generation with template fallback
- PDF report download

This project is a clinical decision-support demo only. It is not a certified medical device and must not be used for standalone diagnosis.

## Current Local Status

The repo is configured to load these model files:

```text
models/chest_xray_efficientnet_b4.pt
models/chest_xray_efficientnet_b4.labels.json
models/brain_tumor_mobilenetv2.h5
```

The local `.env` should contain:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/brain_tumor_mobilenetv2.h5
```

The chest model was trained against this backend constructor:

```python
timm.create_model("efficientnet_b4", pretrained=True, num_classes=15)
```

## Prerequisites

- Python 3.11 recommended
- Node.js 20.19+ recommended for Vite
- PowerShell on Windows
- Docker Desktop only if running with Docker

## One-Time Setup

From the repo root:

```powershell
New-Item -ItemType Directory -Force data/uploads,data/heatmaps,data/thumbnails,models
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

Install backend dependencies:

```powershell
cd backend
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
cd ..
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

If you have `medoraai_chest_xray_model_export.zip`, extract it from the repo root:

```powershell
Expand-Archive -LiteralPath .\medoraai_chest_xray_model_export.zip -DestinationPath . -Force
```

## Verify Setup

Run from the repo root:

```powershell
python -m compileall backend
```

Check model files:

```powershell
python -c "from pathlib import Path; files=['models/chest_xray_efficientnet_b4.pt','models/chest_xray_efficientnet_b4.labels.json','models/brain_tumor_mobilenetv2.h5']; [print(f, Path(f).exists(), Path(f).stat().st_size if Path(f).exists() else 0) for f in files]"
```

Check frontend build:

```powershell
cd frontend
npm run build
cd ..
```

## Run Locally

Start the backend in terminal 1:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Start the frontend in terminal 2:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

Health check:

```text
http://127.0.0.1:8000/health
```

Expected health response includes:

```json
{
  "status": "ok",
  "models": {
    "chest_xray": "loaded",
    "brain_mri": "loaded"
  }
}
```

Demo login:

```text
username: demo
password: demo123
```

## Docker

```powershell
docker compose up --build
```

Open:

```text
http://localhost:3000
```

The backend API is exposed at `http://localhost:8000`; the frontend container proxies `/api/*`, `/static/*`, and `/health` to the backend.

## Core Flow

1. Sign in with the demo account.
2. Choose Chest X-Ray or Brain MRI.
3. Upload a PNG, JPEG, or DICOM image.
4. Run analysis.
5. Review classification, severity, Grad-CAM heatmap, and report.
6. Edit report text if needed and download the PDF.

## Notes

- Gemini is the preferred report provider because it receives the uploaded image plus ML context.
- If no LLM API key is configured, report generation uses the built-in template fallback.
- Vite may warn if Node.js is below 20.19.0. Upgrade Node to remove that warning.
- Do not commit real API keys from `.env`.

More setup detail is in `docs/guides/setup.md`.

For prediction quality checks, run `tools/evaluate_chest_model.py` and see `docs/guides/model-evaluation.md`.
