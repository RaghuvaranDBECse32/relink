"""Custom orchestration (replaces Mastra):
safety(in) -> memory -> retrieve -> generate (stream) -> safety(out) -> persist -> progress."""
import json
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import Conversation, Message, StudyProgress
from app.services import ai_service, memory_service, retrieval_service, safety_service


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _track_progress(db, user_id: str, topic: str, grounded: bool) -> None:
    row = db.scalar(select(StudyProgress).where(
        StudyProgress.user_id == user_id, StudyProgress.topic == topic))
    if row is None:
        row = StudyProgress(user_id=user_id, topic=topic, questions_asked=0, grounded_answers=0)
        db.add(row)
    row.questions_asked += 1
    row.grounded_answers += 1 if grounded else 0
    row.last_studied_at = datetime.now(timezone.utc)


def run_chat(user_id: str, text: str, conversation_id: str | None) -> Iterator[str]:
    s = get_settings()
    db = SessionLocal()
    try:
        conv = db.get(Conversation, conversation_id) if conversation_id else None
        if conv is not None and conv.user_id != user_id:
            yield sse("error", {"message": "Conversation not found"})
            return
        if conv is None:
            conv = Conversation(user_id=user_id, title=text.strip()[:60] or "New conversation")
            db.add(conv)
            db.flush()
        history = memory_service.recent_history(db, conv.id)
        db.add(Message(conversation_id=conv.id, role="user", content=text))
        db.commit()
        yield sse("meta", {"conversation_id": conv.id})

        check = safety_service.check_input(text)
        if not check.is_safe:
            msg = Message(conversation_id=conv.id, role="assistant", content=safety_service.REFUSAL,
                          is_safe=False, safety_reason=check.reason, model="safety-engine", sources=[])
            db.add(msg)
            db.commit()
            yield sse("token", {"text": msg.content})
            yield sse("done", {"message_id": msg.id, "is_safe": False, "reason": check.reason, "sources": []})
            return

        hits = retrieval_service.search(db, user_id, text)
        sources = [h.to_dict() for h in hits]
        yield sse("sources", {"sources": sources})

        parts: list[str] = []
        for piece in ai_service.stream_answer(history, ai_service.build_prompt(text, hits), hits):
            parts.append(piece)
            yield sse("token", {"text": piece})
        answer = "".join(parts).strip() or ai_service.NO_NOTES

        verdict = safety_service.check_output(answer)
        if not verdict.is_safe:
            answer = safety_service.UNVERIFIED
            yield sse("replace", {"text": answer})

        model = s.gemini_model if s.gemini_api_key else "offline-fallback"
        msg = Message(conversation_id=conv.id, role="assistant", content=answer, sources=sources,
                      model=model, is_safe=verdict.is_safe, safety_reason=verdict.reason)
        db.add(msg)
        conv.updated_at = datetime.now(timezone.utc)
        _track_progress(db, user_id, hits[0].topic if hits else "Unmatched", bool(hits))
        db.commit()
        yield sse("done", {"message_id": msg.id, "is_safe": verdict.is_safe,
                           "reason": verdict.reason, "sources": sources, "model": model})
    except Exception as e:  # never leave the stream hanging
        db.rollback()
        yield sse("error", {"message": f"Something went wrong: {type(e).__name__}"})
    finally:
        db.close()
