"""Chroma default embedding "provider".

This is the deck's documented fallback: "Otherwise, it falls back to
Chroma's default embedding function." Chroma's default function
(ONNX MiniLM, all-MiniLM-L6-v2) is applied automatically by ChromaDB
itself when no LangChain ``Embeddings`` object is supplied to the
collection — so this provider intentionally returns ``None`` from
``as_langchain_embeddings()``. The RAG layer treats ``None`` as the signal
to let Chroma manage embeddings internally.
"""

from __future__ import annotations

from typing import Any

import chromadb.utils.embedding_functions as embedding_functions
from langchain_core.embeddings import Embeddings

from customer_support_agent.integrations.embeddings.base import EmbeddingProvider


class ChromaDefaultEmbeddings(Embeddings):
    """Wraps Chroma's default embedding function in a LangChain-compatible interface."""

    def __init__(self) -> None:
        self._ef = embedding_functions.DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._ef(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._ef([text])[0]


class ChromaDefaultEmbeddingProvider(EmbeddingProvider):
    """No-credentials-required fallback embedding provider."""

    @property
    def provider_name(self) -> str:
        return "chroma_default"

    def is_configured(self) -> bool:
        # Always available — no API key required.
        return True

    def as_langchain_embeddings(self) -> Any:
        return ChromaDefaultEmbeddings()

