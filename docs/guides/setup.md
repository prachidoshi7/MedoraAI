# Setup Guide

This guide documents the current local MedoraAI setup on Windows PowerShell.

## Prerequisites

- Python 3.11 recommended
- Node.js 20.19+ recommended
- Git
- Docker Desktop, optional

## Environment File

Create `.env` from the repo root:

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

Required local model settings:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/brain_tumor_mobilenetv2.h5
```

Optional report providers are checked in this order:

```text
Gemini image-aware report -> Groq -> Anthropic -> OpenAI -> template fallback
```

Never commit real API keys.

For image-aware reports, set:

```env
GEMINI_API_KEY=your_google_ai_studio_key
```

## Model Files

Expected files:

```text
models/chest_xray_efficientnet_b4.pt
models/chest_xray_efficientnet_b4.labels.json
models/brain_tumor_mobilenetv2.h5
```

If the chest model export zip is in the repo root, extract it:

```powershell
Expand-Archive -LiteralPath .\medoraai_chest_xray_model_export.zip -DestinationPath . -Force
```

Verify model files:

```powershell
python -c "from pathlib import Path; files=['models/chest_xray_efficientnet_b4.pt','models/chest_xray_efficientnet_b4.labels.json','models/brain_tumor_mobilenetv2.h5']; [print(f, Path(f).exists(), Path(f).stat().st_size if Path(f).exists() else 0) for f in files]"
```

The chest labels must be:

```text
Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass, Nodule,
Pneumonia, Pneumothorax, Consolidation, Edema, Emphysema, Fibrosis,
Pleural Thickening, Hernia, No Finding
```

## Backend Setup

From the repo root:

```powershell
cd backend
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
cd ..
```

Sanity check:

```powershell
python -m compileall backend
```

Start backend:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected:

```text
status: ok
chest_xray: loaded
brain_mri: loaded
```

## Frontend Setup

From the repo root:

```powershell
cd frontend
npm install
npm run build
```

Start frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies:

```text
/api    -> http://localhost:8000
/static -> http://localhost:8000
/health -> http://localhost:8000
```

## Demo Login

```text
username: demo
password: demo123
```

## Stop Servers

Press `Ctrl+C` in each terminal.

If a background process is stuck:

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess
Stop-Process -Id <PID> -Force
```

## Troubleshooting

If backend health says a model is not loaded, check `.env` and the model files under `models/`.

If frontend build warns about Node version, upgrade to Node.js 20.19+ or 22.12+.

If report generation fails because no API key is configured, the app should fall back to the local report template.
