"""Embedding backends.

- "sentence-transformers": real semantic embeddings (all-MiniLM-L6-v2, 384-d).
- "hash": dependency-free hashed bag-of-words/bigrams. This is LEXICAL, not semantic.
  It is a deterministic fallback so the app runs offline; switch to
  sentence-transformers for true semantic retrieval.
"""
import hashlib
import math
import re
from functools import lru_cache

from app.core.config import get_settings

_STOP = set(
    "a an the is are was were be been of in on at to for and or with by from as it its this that "
    "what which who how why when do does did can could should would explain tell me about give "
    "between difference please".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def _hash_embed(text: str, dim: int) -> list[float]:
    toks = tokenize(text)
    feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    vec = [0.0] * dim
    for f in feats:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@lru_cache
def _st_model():
    from sentence_transformers import SentenceTransformer  # optional dependency

    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if s.embedding_backend == "sentence-transformers":
        return [list(map(float, v)) for v in _st_model().encode(texts, normalize_embeddings=True)]
    return [_hash_embed(t, s.embedding_dim) for t in texts]


def backend_name() -> str:
    return get_settings().embedding_backend


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
