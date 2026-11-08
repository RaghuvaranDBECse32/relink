from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.database.session import get_db
from app.models import Conversation, Feedback, Message, User
from app.schemas import ChatIn, ConversationDetail, ConversationOut, FeedbackIn
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
def chat_stream(body: ChatIn, user: User = Depends(current_user)):
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    gen = chat_service.run_chat(user.id, body.message.strip(), body.conversation_id)
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _own(db: Session, user: User, cid: str) -> Conversation:
    conv = db.get(Conversation, cid)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(q: str | None = None, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    stmt = select(Conversation).where(Conversation.user_id == user.id)
    if q:
        stmt = stmt.where(Conversation.title.ilike(f"%{q}%"))
    return db.scalars(stmt.order_by(Conversation.updated_at.desc()).limit(100)).all()


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def get_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _own(db, user, cid)


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, cid))
    db.commit()


@router.get("/conversations/{cid}/export", response_class=PlainTextResponse)
def export_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _own(db, user, cid)
    lines = [f"# {conv.title}", ""]
    for m in conv.messages:
        lines.append(f"**{'You' if m.role == 'user' else 'SafeStudy'}:** {m.content}\n")
        for i, s in enumerate(m.sources or [], 1):
            lines.append(f"> [{i}] {s.get('title')}: {s.get('text')}")
        lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.post("/feedback", status_code=201)
def feedback(body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    msg = db.get(Message, body.message_id)
    if msg is None or msg.conversation.user_id != user.id:
        raise HTTPException(404, "Message not found")
    db.add(Feedback(message_id=msg.id, user_id=user.id, rating=body.rating, comment=body.comment))
    db.commit()
    return {"ok": True}
