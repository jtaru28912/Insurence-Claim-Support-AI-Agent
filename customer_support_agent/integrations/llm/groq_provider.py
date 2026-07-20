"""Groq chat model provider.

Kept as a pluggable alternative because the source specification (the
project deck) originally used Groq via ``langchain-groq``. Selecting it is
a one-line .env change: ``LLM_PROVIDER=groq``.
"""

from __future__ import annotations

from typing import Any

from customer_support_agent.integrations.llm.base import LLMProvider


class GroqChatProvider(LLMProvider):
    """Wraps ``langchain-groq``'s ``ChatGroq`` behind the LLMProvider interface."""

    def __init__(self, api_key: str | None, model: str, temperature: float = 0.2) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def as_langchain_chat_model(self, **overrides: Any):
        from langchain_groq import ChatGroq

        if not self.is_configured():
            raise RuntimeError(
                "Groq provider selected but GROQ_API_KEY is not set. "
                "Set it in your .env file."
            )

        return ChatGroq(
            api_key=self._api_key,
            model=overrides.get("model", self._model),
            temperature=overrides.get("temperature", self._temperature),
        )
