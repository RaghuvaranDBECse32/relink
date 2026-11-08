from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.database.session import get_db
from app.models import Document, User
from app.schemas import DocumentOut
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _out(d: Document) -> DocumentOut:
    o = DocumentOut.model_validate(d)
    o.builtin = d.owner_id is None
    return o


@router.get("", response_model=list[DocumentOut])
def list_documents(q: str | None = None, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    stmt = select(Document).where(or_(Document.owner_id == user.id, Document.owner_id.is_(None)))
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%") | Document.topic.ilike(f"%{q}%"))
    return [_out(d) for d in db.scalars(stmt.order_by(Document.created_at.desc())).all()]


@router.post("", response_model=DocumentOut, status_code=201)
async def upload(file: UploadFile = File(...), topic: str = Form("General"),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
    name = file.filename or "upload.txt"
    try:
        text = document_service.extract_text(name, data)
        doc = document_service.ingest(db, owner_id=user.id, title=name.rsplit(".", 1)[0],
                                      topic=topic.strip()[:120] or "General", filename=name, text=text)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _out(doc)


@router.delete("/{doc_id}", status_code=204)
def remove(doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None or doc.owner_id != user.id:
        raise HTTPException(404, "Document not found")
    document_service.delete_document(db, doc)
