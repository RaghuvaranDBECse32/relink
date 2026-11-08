import io
import re

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services import embeddings


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        while len(p) > size:  # hard-split very long paragraphs
            cut = p.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 2 else size
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(p[:cut].strip())
            p = p[max(cut - overlap, 0):].strip() if cut - overlap > 0 else p[cut:].strip()
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) > 20]


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Upload PDF, TXT or MD.")


def ingest(db: Session, *, owner_id: str | None, title: str, topic: str,
           filename: str | None, text: str, chunks: list[str] | None = None) -> Document:
    pieces = chunks if chunks is not None else chunk_text(text)
    if not pieces:
        raise ValueError("No readable text found in the document.")
    vectors = embeddings.embed(pieces)
    doc = Document(owner_id=owner_id, title=title, topic=topic, filename=filename,
                   chunk_count=len(pieces))
    db.add(doc)
    db.flush()
    rows = [DocumentChunk(document_id=doc.id, position=i, text=t, embedding=v)
            for i, (t, v) in enumerate(zip(pieces, vectors))]
    db.add_all(rows)
    db.commit()
    return doc


def delete_document(db: Session, doc: Document) -> None:
    db.delete(doc)
    db.commit()
