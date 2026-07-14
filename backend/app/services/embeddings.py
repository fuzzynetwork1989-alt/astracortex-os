"""Embeddings via xAI-compatible API, with local deterministic fallback."""

from __future__ import annotations

import hashlib

import numpy as np
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import logger


def _local_embed(text: str, dim: int) -> list[float]:
    """Stable pseudo-embedding for offline/dev without an embedding API."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng_seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(rng_seed)
    # Mix content length into vector so similar lengths cluster slightly
    vec = rng.standard_normal(dim).astype(np.float64)
    for i, ch in enumerate(text[:256]):
        vec[i % dim] += (ord(ch) % 31) * 0.01
    norm = np.linalg.norm(vec) or 1.0
    return (vec / norm).tolist()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not texts:
        return []
    if not settings.xai_api_key:
        return [_local_embed(t, settings.embedding_dim) for t in texts]

    client = AsyncOpenAI(api_key=settings.xai_api_key, base_url=settings.xai_base_url)
    try:
        resp = await client.embeddings.create(model=settings.xai_embedding_model, input=texts)
        vectors = [item.embedding for item in resp.data]
        # Pad/truncate if provider dim differs
        out: list[list[float]] = []
        for v in vectors:
            if len(v) < settings.embedding_dim:
                v = v + [0.0] * (settings.embedding_dim - len(v))
            out.append(v[: settings.embedding_dim])
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding API failed: %s — local fallback", exc)
        return [_local_embed(t, settings.embedding_dim) for t in texts]


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(np.dot(va, vb) / denom)
