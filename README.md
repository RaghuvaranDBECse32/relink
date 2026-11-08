# SafeStudy-Agent V2: Independent AI Learning Platform

A source-grounded CS study tutor. **No Mastra.** React + TypeScript + Tailwind frontend, FastAPI backend with a small in-house orchestration layer, PostgreSQL (or SQLite locally) for application data, in-database vector search, and Gemini for answers.

Keep `main` (the original Mastra app) untouched and build this on the `version-b1` branch.

## What changed from V1

| V1 (Mastra) | V2 |
|---|---|
| Mastra Agent + workflow | `services/chat_service.py`: safety → memory → retrieve → generate → safety → persist |
| No persistence | Users, conversations, messages, documents, document_chunks, study_progress, feedback |
| Random "pseudo" vectors | Embeddings stored in the database and searched by cosine similarity |
| Single-turn Q&A | Conversation memory (last 8 turns) and streamed answers |
| Plain chat page | X-style three-column UI, citations, history search, Library, Progress, Settings, dark/light/system themes, optional study music |
| Qdrant key in the repo | Secrets only in environment variables (`.env` is git-ignored) |

> **Rotate your old Qdrant key.** It was exposed in V1. Deleting the file does not remove it from Git history.

## Requirements

- Python 3.11+ and Node.js 20+
- Optional: a free Gemini API key (see below)

## Run locally (Windows PowerShell)

Open two terminals in the `SafeStudy-Agent-V2` folder.

**Terminal 1: backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use the virtual environment as shown. A broken global package (for example `click`) can otherwise stop the server from starting.

Check it: http://127.0.0.1:8000/api/health and the API docs at http://127.0.0.1:8000/docs

**Terminal 2: frontend**

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173, create an account, and ask: `Explain 2NF with an example`.

Mac/Linux: activate with `source .venv/bin/activate`, then run `uvicorn app.main:app --reload`.

By default the backend uses a local SQLite file, so no database setup is needed.

## Where is the `.env` file?

There is no `.env` until you create one. Use `.env.example` as the template.

| How you run it | Create the file here |
|---|---|
| Local (steps above) | `backend\.env` (the backend reads `.env` from the folder it starts in) |
| Docker Compose | `.env` in the project root |

```powershell
copy .env.example backend\.env
```

Then edit `backend\.env` and restart the backend. Never commit `.env` or put keys in frontend files.

Useful settings:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
JWT_SECRET=a-long-random-string
EMBEDDING_BACKEND=hash
```

## Free AI option (Gemini)

The app supports Google Gemini. Get a key at https://aistudio.google.com/apikey and put it in `GEMINI_API_KEY`. Google offers a free tier for eligible models, but model availability, usage limits and regional terms change, so check Google AI Studio for what applies to you.

**With no key**, the app still works in **offline fallback mode**: you can register, chat, keep history, upload documents and see progress and citations, but answers are short extracts from your notes instead of AI-written text. The Settings page shows which mode you are in.

## Features

- Streaming answers with clickable `[1]` source citations
- Conversation memory, searchable history, Markdown export
- Library: upload PDF, TXT or MD files; they become citable sources
- Progress dashboard: questions, topics, 7-day activity, helpful ratings
- Safety engine: input screening and output validation (local rules, optional Enkrypt AI)
- Dark, light and system themes
- Study music button (see below)

## Background music

A floating **Music** button opens YouTube's official embedded player (video ID `pidL4XYP_II`). To use another video, set `VITE_BGM_VIDEO_ID` in `frontend/.env`.

- Browsers block autoplay, so press play inside the player.
- Closing the panel stops the music.
- Nothing is downloaded or stored. It needs internet access and a video whose owner allows embedding; if it doesn't, the panel shows an "Open on YouTube" link.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
cd ..\frontend
npm run build
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Opens at http://localhost:8000 with Postgres. The container runs `alembic upgrade head`, then serves the API and the built React app from one URL.

## Deploy on Render

1. Push to GitHub. Run `git status` first and confirm `.env` is not listed.
2. In Render choose New → Blueprint and select the repo (it reads `render.yaml`: a Docker web service plus Postgres).
3. Set `GEMINI_API_KEY` in the Render environment if you want AI answers.
4. If your Render URL differs from the one in `render.yaml`, update `CORS_ORIGINS`.

## Status

- Verified on Windows: dependencies install, the backend starts and `/api/health` is healthy, the frontend builds, and the sign-in screen loads.
- Not yet verified: answers from a live Gemini key, the Docker setup, the Render deploy, and the automated API tests.

## Honest notes

- **Embeddings:** the default `hash` backend is a lexical fallback. It matches on wording, not meaning. For true semantic search set `EMBEDDING_BACKEND=sentence-transformers` (uncomment it in `backend/requirements.txt`). If you switch, delete and re-upload your documents so the vectors match.
- **Safety:** pattern-based checks, not a guarantee.
- **Auth:** email and password with bcrypt and JWT (24 hours). The token is stored in `localStorage`; for a hardened deployment move it to an httpOnly cookie. OAuth, refresh tokens and password reset are not built.
- **Not built yet:** Redis caching and rate limiting.

## API

`POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me` · `POST /api/chat/stream` (events: `meta`, `sources`, `token`, `replace`, `done`, `error`) · `GET/DELETE /api/conversations[/{id}]` · `GET /api/conversations/{id}/export` · `POST /api/feedback` · `GET/POST/DELETE /api/documents` · `GET /api/analytics/summary` · `GET /api/health`
