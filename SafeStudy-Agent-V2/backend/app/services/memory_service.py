from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message


def recent_history(db: Session, conversation_id: str, limit: int = 8) -> list[dict]:
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc()).limit(limit)
    ).all()
    return [{"role": m.role, "content": m.content[:1500]} for m in reversed(rows)]
