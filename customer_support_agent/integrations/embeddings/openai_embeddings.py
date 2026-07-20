"""OpenAI embedding provider (default provider for this project)."""

from __future__ import annotations

from typing import Any

from customer_support_agent.integrations.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Wraps ``langchain-openai``'s ``OpenAIEmbeddings``."""

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def as_langchain_embeddings(self) -> Any:
        from langchain_openai import OpenAIEmbeddings

        if not self.is_configured():
            raise RuntimeError(
                "OpenAI embedding provider selected but OPENAI_API_KEY is not set. "
                "Set it in your .env file."
            )

        return OpenAIEmbeddings(api_key=self._api_key, model=self._model)
