"""LLM routing via real documented HTTP APIs. Nothing is simulated: if no provider is configured, callers get None.

Provider order:
  1. Bifrost (Maxim AI) — OpenAI-compatible gateway:  POST {BIFROST_BASE_URL}/v1/chat/completions, model "provider/model".
     Using it with a Gemini model ("gemini/<model>") routes Google models through Bifrost.
  2. Gemini API directly — POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
Verify endpoints/model names against the providers' current docs before relying on them in production.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error

def provider() -> str | None:
    if os.environ.get("BIFROST_BASE_URL"): return "bifrost"
    if os.environ.get("GEMINI_API_KEY"): return "gemini"
    return None

def _post(url, payload, headers, timeout=45):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode())

def complete_json(system: str, user: str) -> dict | None:
    """Return parsed JSON from the configured model, or None when unavailable. Raises RuntimeError on provider failure."""
    p = provider()
    try:
        if p == "bifrost":
            base = os.environ["BIFROST_BASE_URL"].rstrip("/")
            hdr = {"Authorization": "Bearer " + os.environ["BIFROST_API_KEY"]} if os.environ.get("BIFROST_API_KEY") else {}
            model = os.environ.get("BIFROST_MODEL", "gemini/gemini-2.5-flash")
            d = _post(base + "/v1/chat/completions", {"model": model, "temperature": 0,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, hdr)
            text = d["choices"][0]["message"]["content"]
        elif p == "gemini":
            model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            d = _post(os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com") + f"/v1beta/models/{model}:generateContent",
                      {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                       "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                      {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
            text = d["candidates"][0]["content"]["parts"][0]["text"]
        else: return None
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as e:
        raise RuntimeError(f"{p} request failed: {type(e).__name__}")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try: return json.loads(text)
    except ValueError: raise RuntimeError(f"{p} returned non-JSON output")
