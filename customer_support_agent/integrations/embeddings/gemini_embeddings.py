"""Gemini embedding provider.

This mirrors the ORIGINAL deck specification: "If GOOGLE_API_KEY is
configured, semantic memory search / RAG uses Gemini embeddings." Kept
pluggable so a learner can switch back to it with
``EMBEDDING_PROVIDER=gemini`` without touching any other code.
"""

from __future__ import annotations

from typing import Any

from customer_support_agent.integrations.embeddings.base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Wraps ``langchain-google-genai``'s ``GoogleGenerativeAIEmbeddings``."""

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def as_langchain_embeddings(self) -> Any:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not self.is_configured():
            raise RuntimeError(
                "Gemini embedding provider selected but GOOGLE_API_KEY is not set. "
                "Set it in your .env file."
            )

        return GoogleGenerativeAIEmbeddings(google_api_key=self._api_key, model=self._model)
