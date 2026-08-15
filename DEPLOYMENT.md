# MedoraAI production deployment

MedoraAI uses three production services:

1. **Vercel** — React/Vite frontend
2. **Neon** — PostgreSQL database for accounts, appointments, reports, and workflow metadata
3. **Container backend with persistent storage** — FastAPI, ML models, uploaded scans, heatmaps, and avatars

The ML backend should not run as a Vercel Function. It loads PyTorch, TensorFlow, Transformers, and multiple model artifacts at startup, generates reports in background tasks, and writes medical-image files to disk.

## 1. Neon

1. Create a Neon project.
2. In **Connect**, enable **Connection pooling**.
3. Copy the pooled connection string. Its hostname contains `-pooler`.
4. Store it as `DATABASE_URL` on the backend host. Never add it to Git.

The backend creates the schema and demo records on its first successful startup.

## 2. Container backend

Build from the repository root:

```bash
docker build -f backend/Dockerfile -t medoraai-api .
```

Required production environment variables:

```text
DATABASE_URL=<pooled Neon connection string>
SECRET_KEY=<long random value>
CORS_ORIGINS=["https://YOUR-VERCEL-DOMAIN.vercel.app"]
DATA_DIR=/app/data
MAIRA_API_URL=<stable public MAIRA-2 service URL>
```

Add any configured provider secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`, `SARVAM_API_KEY`, and `HF_TOKEN`) through the host's secret manager.

Mount a persistent disk at `/app/data`. Without that disk, uploaded scans, generated heatmaps, thumbnails, and profile images disappear on redeploy.

Use `/health` as the health-check path. The container respects the host-provided `PORT` value.

The complete model set needs substantially more than a 512 MB free instance. Start with at least 4 GB RAM and verify real peak memory during startup and inference.

## 3. Vercel frontend

Import the GitHub repository and configure:

```text
Root Directory: frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

Add this Vercel environment variable for Production and Preview:

```text
VITE_API_BASE_URL=https://YOUR-BACKEND-DOMAIN
```

Do not include `/api/v1` or a trailing slash. Redeploy after changing the value.

## 4. Complete CORS

After Vercel assigns the production URL, set the backend value exactly:

```text
CORS_ORIGINS=["https://YOUR-VERCEL-DOMAIN.vercel.app"]
```

Then redeploy the backend and test:

1. `https://YOUR-BACKEND-DOMAIN/health`
2. Patient registration and login
3. Profile image upload
4. Scan upload and analysis
5. Heatmap display
6. Report generation and download
