"""Seeds the built-in CS library (the original SafeStudy notes) once."""
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document
from app.services import document_service

NOTES = Path(__file__).resolve().parents[2] / "data" / "seed_notes.json"


def seed_library(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Document).where(Document.owner_id.is_(None))):
        return 0
    notes = json.loads(NOTES.read_text(encoding="utf-8"))
    by_topic: dict[str, list[str]] = {}
    for n in notes:
        by_topic.setdefault(n["topic"], []).append(n["content"])
    for topic, items in by_topic.items():
        document_service.ingest(db, owner_id=None, title=f"{topic} - core notes", topic=topic,
                                filename=None, text="", chunks=items)
    return len(notes)
