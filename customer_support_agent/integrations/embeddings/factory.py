"""
Embedding provider factory.

Mirrors ``integrations/llm/factory.py``. The only place that maps
``Settings.embedding_provider`` to a concrete ``EmbeddingProvider``.
"""

from __future__ import annotations

from functools import lru_cache

from customer_support_agent.core.settings import EmbeddingProviderName, Settings, get_settings
from customer_support_agent.integrations.embeddings.base import EmbeddingProvider
from customer_support_agent.integrations.embeddings.chroma_default_embeddings import (
    ChromaDefaultEmbeddingProvider,
)
from customer_support_agent.integrations.embeddings.gemini_embeddings import (
    GeminiEmbeddingProvider,
)
from customer_support_agent.integrations.embeddings.openai_embeddings import (
    OpenAIEmbeddingProvider,
)


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Construct the embedding provider selected by ``settings.embedding_provider``."""
    if settings.embedding_provider == EmbeddingProviderName.OPENAI:
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
    if settings.embedding_provider == EmbeddingProviderName.GEMINI:
        return GeminiEmbeddingProvider(
            api_key=settings.google_api_key,
            model=settings.gemini_embedding_model,
        )
    if settings.embedding_provider == EmbeddingProviderName.CHROMA_DEFAULT:
        return ChromaDefaultEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Process-wide cached accessor, mirroring ``get_llm_provider()``."""
    return build_embedding_provider(get_settings())
