#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p \
  "$ROOT_DIR/data/uploads" \
  "$ROOT_DIR/data/heatmaps" \
  "$ROOT_DIR/data/thumbnails" \
  "$ROOT_DIR/models"

if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example"
fi

cat <<'MSG'
MedoraAI setup complete.

Next steps:
  1. Add an LLM API key to .env if available. Groq is the recommended first option.
  2. Backend local dev:
       cd backend
       pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
       uvicorn main:app --reload --port 8000
  3. Frontend local dev:
       cd frontend
       npm install
       npm run dev
  4. Docker:
       docker compose up --build

Demo credentials:
  username: demo
  password: demo123
MSG
