"""
Embedding provider abstraction.

Mirrors ``integrations/llm/base.py`` — same Strategy + Dependency
Inversion pattern, applied to embeddings instead of chat models. The RAG
layer (integrations/rag/chroma_kb.py) depends only on ``EmbeddingProvider``
and never imports a concrete embeddings class directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EmbeddingProvider(ABC):
    """Abstract base class every embedding backend must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short machine-readable identifier, e.g. 'openai', 'gemini', 'chroma_default'."""

    @abstractmethod
    def as_langchain_embeddings(self) -> Any:
        """
        Return a LangChain ``Embeddings``-compatible object (implements
        ``embed_documents`` / ``embed_query``), or ``None`` if this provider
        represents "use Chroma's built-in default embedding function"
        (i.e. no LangChain embeddings object is needed).
        """

    def is_configured(self) -> bool:
        """Whether this provider has the credentials it needs to run."""
        return True
