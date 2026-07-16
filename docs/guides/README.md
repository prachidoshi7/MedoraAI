# Guides

Practical how-to documentation for running and maintaining MedoraAI.

## Current Guides

- `setup.md` - local setup, model placement, verification, and run commands.
- `model-evaluation.md` - measure model accuracy/AUC and understand heatmap/report limitations.

## Common Commands

Backend:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Health:

```text
http://127.0.0.1:8000/health
```
