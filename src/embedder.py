"""Embedding model helper — fastembed, local, no API key required.

Model : nomic-ai/nomic-embed-text-v1.5
Dims  : 768
Notes :
  - Model is downloaded once (~270 MB) on first call and cached on disk.
  - fastembed.embed() returns numpy.ndarray objects; .tolist() converts to
    plain Python list[float] required by pgvector DB drivers.
  - fastembed is synchronous. Callers running inside an asyncio event loop
    must wrap with asyncio.to_thread(embed_texts, texts).
"""
from __future__ import annotations

from fastembed import TextEmbedding

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    """Return the singleton TextEmbedding model, loading it on first call."""
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)  # downloads on first call
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts. Returns a list of 768-dim vectors as plain Python lists.

    NOTE: fastembed.embed() returns numpy.ndarray objects, NOT Python lists.
    .tolist() is required here — pgvector drivers reject numpy arrays at insert time.
    """
    model = get_model()
    return [v.tolist() for v in model.embed(texts)]  # .tolist() converts ndarray → list[float]
