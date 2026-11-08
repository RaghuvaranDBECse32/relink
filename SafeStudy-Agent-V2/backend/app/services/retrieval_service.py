"""Retrieval: cosine search over embeddings stored in the database."""
from dataclasses import dataclass, asdict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services import embeddings

MIN_SCORE = 0.12


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    title: str
    topic: str
    text: str
    score: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score, 3)
        return d


def search(db: Session, user_id: str, query: str, top_k: int = 4) -> list[Hit]:
    vec = embeddings.embed([query])[0]
    rows = db.execute(
        select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
        .where(or_(Document.owner_id == user_id, Document.owner_id.is_(None)))
    ).all()
    hits = [Hit(c.id, d.id, d.title, d.topic, c.text, embeddings.cosine(vec, c.embedding))
            for c, d in rows if c.embedding]
    hits.sort(key=lambda h: h.score, reverse=True)
    return [h for h in hits[:top_k] if h.score >= MIN_SCORE]
