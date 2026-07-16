# MedoraAI Frontend

React + TypeScript + Vite frontend for the MedoraAI demo.

## Setup

```powershell
cd frontend
npm install
```

## Run

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

The dev server proxies backend requests to `http://localhost:8000`:

```text
/api
/static
/health
```

Start the backend before using the app.

## Build

```powershell
npm run build
```

Vite recommends Node.js 20.19+ or 22.12+. Older Node versions may still build but show a warning.

## Demo Login

```text
username: demo
password: demo123
```
