"""Text embedders for RAG (S2.4, ruling D4).

Each embedder has a stable `name` that is stored on every embedded row. Vectors from different
embedders are not comparable even when the dimension matches (hash and MiniLM are both 384-d), so
retrieval refuses to search rows embedded with another model.

- MiniLMEmbedder: local sentence-transformers all-MiniLM-L6-v2 on CPU. Semantic.
- HashEmbedder: deterministic feature hashing. LEXICAL only; used solely as a labelled fallback
  when the semantic model is unavailable, and decisions report rag_status="lexical_fallback".
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Protocol

import numpy as np

logger = logging.getLogger("finshield.rag")

EMBEDDING_DIM = 384
MINILM = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder(Protocol):
    name: str
    dim: int
    semantic: bool

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Feature hashing over unigrams + bigrams into EMBEDDING_DIM signed buckets, L2-normalised.
    Cosine similarity approximates lexical overlap; it does not capture meaning."""
    name = "hash-v1"
    dim = EMBEDDING_DIM
    semantic = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        for feat in tokens + [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]:
            h = hashlib.md5(feat.encode("utf-8")).digest()
            vec[int.from_bytes(h[:4], "big") % self.dim] += 1.0 if h[4] % 2 == 0 else -1.0
        norm = np.linalg.norm(vec)
        return (vec / norm if norm > 0 else vec).tolist()


class MiniLMEmbedder:
    semantic = True
    dim = EMBEDDING_DIM

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(MINILM, device="cpu")
        if self._model.get_embedding_dimension() != self.dim:
            raise RuntimeError(f"{MINILM} produced {self._model.get_embedding_dimension()}-d vectors, expected {self.dim}")
        self.name = "all-MiniLM-L6-v2"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def load_embedder() -> Embedder:
    """RAG_EMBEDDER=minilm (default) or hash. Falls back to hash, loudly, if MiniLM cannot load."""
    choice = os.getenv("RAG_EMBEDDER", "minilm").lower()
    if choice == "hash":
        return HashEmbedder()
    try:
        return MiniLMEmbedder()
    except Exception as e:
        logger.warning("Semantic embedder unavailable (%s: %s); RAG falls back to LEXICAL hash embeddings and "
                       "decisions report rag_status=lexical_fallback", type(e).__name__, e)
        return HashEmbedder()
