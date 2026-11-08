from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.database.session import get_db
from app.models import Conversation, Feedback, Message, StudyProgress, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    topics = db.scalars(select(StudyProgress).where(StudyProgress.user_id == user.id)
                        .order_by(StudyProgress.questions_asked.desc())).all()
    questions = sum(t.questions_asked for t in topics)
    grounded = sum(t.grounded_answers for t in topics)
    convs = db.scalar(select(func.count()).select_from(Conversation)
                      .where(Conversation.user_id == user.id)) or 0
    since = date.today() - timedelta(days=6)
    rows = db.execute(
        select(Message.created_at).join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user.id, Message.role == "user")).all()
    per_day = {(since + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    for (ts,) in rows:
        key = ts.date().isoformat()
        if key in per_day:
            per_day[key] += 1
    up = db.scalar(select(func.count()).select_from(Feedback)
                   .where(Feedback.user_id == user.id, Feedback.rating > 0)) or 0
    down = db.scalar(select(func.count()).select_from(Feedback)
                     .where(Feedback.user_id == user.id, Feedback.rating < 0)) or 0
    return {
        "questions": questions, "conversations": convs,
        "grounded_rate": round(grounded / questions, 2) if questions else None,
        "helpful": up, "not_helpful": down,
        "topics": [{"topic": t.topic, "questions": t.questions_asked, "grounded": t.grounded_answers,
                    "last": t.last_studied_at.isoformat()} for t in topics],
        "activity": [{"day": d, "questions": n} for d, n in per_day.items()],
    }
