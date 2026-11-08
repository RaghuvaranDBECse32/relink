# SafeStudy-Agent V2: Independent AI Learning Platform

A source-grounded CS study tutor. **No Mastra.** React + TypeScript + Tailwind frontend, FastAPI backend with a small in-house orchestration layer, PostgreSQL for application data, in-database vector retrieval, Gemini for answers.

Build this on the `version-b1` branch and leave `main` (the original Mastra app) untouched.

## What changed from V1

| V1 (Mastra) | V2 |
|---|---|
| Mastra Agent + workflow | `services/chat_service.py` (safety → memory → retrieve → generate → safety → persist) |
| No persistence | PostgreSQL: users, conversations, messages, documents, document_chunks, study_progress, feedback |
| Random "pseudo" vectors | Embeddings (see note below) stored in the database and searched by cosine similarity |
| Single-turn Q&A | Conversation memory (last 8 turns) and SSE token streaming |
| Plain chat page | X-style three-column UI, citations, history search, Library, Progress, Settings, dark/light/system |
| Qdrant key in the repo | Secrets only via env vars (`.env` is git-ignored) |

> **Rotate your old Qdrant key** (exposed in V1) even though V2 no longer uses Qdrant. Deleting the file does not remove it from Git history.

## Run locally

```bash
cp .env.example .env            # add GEMINI_API_KEY; the app also works without it (offline fallback)
# Backend (SQLite by default: set DATABASE_URL in .env for Postgres)
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs
# Frontend (second terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Full stack with Postgres: `docker compose up --build` → http://localhost:8000

Tests: `cd backend && pytest`

## Deploy on Render

1. Push to GitHub (`git status` must not list `.env`).
2. Render → New → Blueprint → select the repo (uses `render.yaml`: Docker web service + Postgres).
3. Set `GEMINI_API_KEY`.
4. Update `CORS_ORIGINS` in `render.yaml` to your actual Render URL if it differs.

The container runs `alembic upgrade head`, then serves the API and the built React app from one URL.

## Background music

A floating **Music** button opens YouTube’s official embedded player (video ID `pidL4XYP_II`, change it with `VITE_BGM_VIDEO_ID`). Browsers block autoplay, so press play in the player. Closing the panel stops the music. Nothing is downloaded or stored, and playback needs internet access and a video that allows embedding.

## Honest notes

- **Embeddings:** the default `hash` backend is a dependency-free *lexical* fallback so the app runs anywhere. For true semantic search set `EMBEDDING_BACKEND=sentence-transformers` (uncomment it in `requirements.txt`; 384-d MiniLM). If you switch backends, delete and re-upload documents so vectors match.
- **Safety:** local pattern rules on input and output, plus optional Enkrypt AI on output. These are heuristics, not a guarantee.
- **Auth:** email + password, bcrypt, JWT (24h). OAuth and refresh tokens are not implemented. The token is kept in `localStorage`; for a hardened deployment move it to an httpOnly cookie.
- **Not yet built:** Redis caching/rate limiting, password reset, OAuth.

## API

`POST /api/auth/register|login` · `GET /api/auth/me` · `POST /api/chat/stream` (SSE: `meta`, `sources`, `token`, `replace`, `done`, `error`) · `GET/DELETE /api/conversations[/{id}]` · `GET /api/conversations/{id}/export` · `POST /api/feedback` · `GET/POST/DELETE /api/documents` · `GET /api/analytics/summary` · `GET /api/health`
