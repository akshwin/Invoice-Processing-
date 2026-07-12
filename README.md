# AI-Powered Invoice Processing System

Two implementations of the same pipeline live in this repo:

- **`invoice-processing/`** — the original Streamlit app (single process, both UI and pipeline
  logic together). See its own `README.md` for details.
- **`backend/` + `frontend/`** — a FastAPI + Next.js split, built to deploy as a real persistent
  backend (Render/Railway/Fly) plus a separately-hosted frontend (Vercel), rather than a single
  Streamlit process.

Both share the identical business logic (extraction, PO matching, validation rules BR-1–BR-5,
decision reasoning) — `backend/src/` is the same pipeline code as `invoice-processing/src/`, just
with the run-history storage swapped from a flat JSON file to SQLite (see "Why SQLite" below).

## Architecture (FastAPI + Next.js split)

```
┌─────────────────────┐        HTTP + SSE        ┌──────────────────────────┐
│  Next.js frontend    │ ───────────────────────▶ │  FastAPI backend         │
│  (Vercel)            │ ◀─────────────────────── │  (Render)                │
│  - Run page          │                           │  - POST /api/runs        │
│  - Dashboard page     │                           │  - GET  /api/runs/:id/stream (SSE) │
└─────────────────────┘                           │  - GET  /api/runs         │
                                                    │  - GET  /api/runs/:id     │
                                                    │  ↓                       │
                                                    │  src/pipeline.py         │
                                                    │  (same LangGraph 4-node  │
                                                    │   pipeline, unchanged)   │
                                                    │  ↓                       │
                                                    │  SQLite (run_history/)   │
                                                    └──────────────────────────┘
```

**Why the split needed more than a UI rewrite:**
- **Live stage-by-stage progress** (a BRD requirement, not cosmetic) needed a real push mechanism
  once the UI moved to a separate process. `pipeline.stream()` runs in a background thread per
  request; each yielded step is pushed onto a `queue.Queue`, and a Server-Sent-Events endpoint
  drains that queue and streams it to the browser as it happens. The frontend's `EventSource`
  consumes it and drives the same stepper UI the Streamlit app had — genuinely live, not polled.
- **Why SQLite instead of the JSON file:** the Streamlit app is single-user-per-session, so a
  flat-file read-modify-write was never actually at risk of concurrent writes. A real API serving
  arbitrary concurrent requests is a different story — SQLite is still one file (no separate DB
  service to run), but handles concurrent access safely where raw JSON read-modify-write would risk
  corruption. `backend/src/storage.py` exposes the exact same `load_history()` / `append_run()`
  interface as the original, so `pipeline.py` and `validation.py` needed zero changes.

## Local development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
uvicorn main:app --reload --port 8000
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev
```

Visit `http://localhost:3000`. Run the backend's tests with `cd backend && python -m pytest tests/ -v`
(same 18 tests as the Streamlit app's — deterministic, no API calls).

## Deployment

### Backend → Render

1. Push this repo to GitHub (already done if you're deploying from the same repo used for the
   Streamlit Cloud attempt).
2. On [render.com](https://render.com): **New +** → **Web Service** → connect this GitHub repo.
3. Settings:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment** tab → add `GROQ_API_KEY` (your key) and `PYTHON_VERSION` = `3.12.7` (pins the
   Python version explicitly — Render's default can drift to a version whose prebuilt wheels for
   some dependency don't exist yet, the same class of problem hit on Streamlit Cloud with Python
   3.14; being explicit here avoids repeating that).
5. Deploy. Once live, note the backend's URL (`https://<your-app>.onrender.com`) — the frontend
   needs it next. Confirm it's up: `curl https://<your-app>.onrender.com/api/health`.

A `render.yaml` blueprint is included at the repo root if you'd rather use Render's
**New + → Blueprint** flow instead of manual settings — it encodes the same configuration above.

**Free tier note:** Render's free web services spin down after inactivity and cold-start on the
next request (similar to Streamlit Cloud's sleep behavior) — expect a ~30–60s delay on the first
request after idle time, not a broken deployment.

### Frontend → Vercel

1. On [vercel.com](https://vercel.com): **Add New** → **Project** → import this GitHub repo.
2. In the import screen, set **Root Directory** to `frontend` (Vercel auto-detects Next.js once
   pointed at the right folder — no `vercel.json` needed).
3. **Environment Variables** → add `NEXT_PUBLIC_API_BASE_URL` = your Render backend's URL from
   above (e.g. `https://invoice-processing-api.onrender.com`).
4. Deploy. Vercel gives you a `https://<project>.vercel.app` URL — that's the app.

### Order matters

Deploy the backend first and get its URL before deploying the frontend, since the frontend's
`NEXT_PUBLIC_API_BASE_URL` env var needs to point at the live backend. `NEXT_PUBLIC_*` variables
are baked in at build time, so changing the backend URL later means redeploying the frontend, not
just editing an env var at runtime.

## Deviations and assumptions (carried over from the Streamlit build)

- **Groq (Llama), not Claude** — the BRD names Claude as non-negotiable; this build uses Groq at
  explicit request since no Anthropic key was available. See `invoice-processing/README.md` for
  the full note — it applies unchanged here, since `backend/src/extraction.py` and `decision.py`
  are the same code.
- **CORS is wide open** (`allow_origins=["*"]`) in `backend/main.py` — a reasonable simplification
  for a demo with no auth/cookies involved. Tighten to the specific Vercel domain if this goes
  beyond a demo.
- **SQLite lives on the backend's local disk** — fine for a demo (persists for the life of the
  running instance), but Render's free tier disk is not guaranteed to survive a redeploy. For
  anything beyond a demo, that's the next thing to swap for a managed Postgres.
