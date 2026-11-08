from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import analytics, auth, chat, documents
from app.core.config import get_settings
from app.database.session import Base, SessionLocal, engine
from app.services import embeddings, seed_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_service.seed_library(db)
    yield


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, chat.router, documents.router, analytics.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "status": "ok", "version": "2.0.0",
        "llm": settings.gemini_model if settings.gemini_api_key else "offline-fallback",
        "vector_store": "database",
        "embeddings": embeddings.backend_name(),
    }


# Single-service deploy: serve the built React app if present.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
