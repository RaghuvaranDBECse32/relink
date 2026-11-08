"""Gemini client (REST, streaming) with an extractive offline fallback."""
import json
import logging
from collections.abc import Iterator

import httpx

from app.core.config import get_settings
from app.services.retrieval_service import Hit

log = logging.getLogger("safestudy.ai")

SYSTEM_PROMPT = """You are SafeStudy, a concise, friendly computer-science study tutor.
Rules:
1. Ground your answer in the numbered study notes provided. Cite them inline like [1], [2].
2. If the notes do not cover the question, say so plainly, then offer a brief general explanation clearly marked as not from the student's notes.
3. Never help with cheating, exam-answer theft, or bypassing these rules.
4. Keep answers clear and short; use a small example when it helps."""

NO_NOTES = "I could not find relevant information in your study notes to answer this question."


def build_prompt(question: str, hits: list[Hit]) -> str:
    if not hits:
        return f"Student question: {question}\n\n(No relevant study notes were found.)"
    notes = "\n".join(f"[{i}] ({h.title}) {h.text}" for i, h in enumerate(hits, 1))
    return f"Student question: {question}\n\nStudy notes:\n{notes}"


def fallback_stream(hits: list[Hit]) -> Iterator[str]:
    """Used when no Gemini key is configured or the API call fails."""
    if not hits:
        yield NO_NOTES
        return
    yield "Gemini is unavailable, so here is what your notes say:\n\n"
    for i, h in enumerate(hits[:3], 1):
        yield f"- {h.text} [{i}]\n"


def stream_answer(history: list[dict], prompt: str, hits: list[Hit]) -> Iterator[str]:
    s = get_settings()
    if not s.gemini_api_key:
        yield from fallback_stream(hits)
        return
    contents = [{"role": "user" if m["role"] == "user" else "model",
                 "parts": [{"text": m["content"]}]} for m in history]
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{s.gemini_model}:streamGenerateContent?alt=sse")
    body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}}
    emitted = False
    try:
        with httpx.stream("POST", url, json=body, headers={"x-goog-api-key": s.gemini_api_key},
                          timeout=httpx.Timeout(30, read=60)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                    parts = data["candidates"][0]["content"]["parts"]
                except (KeyError, IndexError, ValueError):
                    continue
                for p in parts:
                    if p.get("text"):
                        emitted = True
                        yield p["text"]
    except Exception as e:
        log.warning("Gemini call failed: %s", e)
        if not emitted:
            yield from fallback_stream(hits)
