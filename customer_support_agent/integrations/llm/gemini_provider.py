"""Gemini chat model provider.

Kept pluggable for parity with the original deck, which used Gemini for
embeddings (and Gemini is a natural LLM alternative on the same
GOOGLE_API_KEY). Selecting it is a one-line .env change:
``LLM_PROVIDER=gemini``.
"""

from __future__ import annotations

from typing import Any

from customer_support_agent.integrations.llm.base import LLMProvider


class GeminiChatProvider(LLMProvider):
    """Wraps ``langchain-google-genai``'s ``ChatGoogleGenerativeAI``."""

    def __init__(self, api_key: str | None, model: str, temperature: float = 0.2) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def as_langchain_chat_model(self, **overrides: Any):
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not self.is_configured():
            raise RuntimeError(
                "Gemini provider selected but GOOGLE_API_KEY is not set. "
                "Set it in your .env file."
            )

        return ChatGoogleGenerativeAI(
            google_api_key=self._api_key,
            model=overrides.get("model", self._model),
            temperature=overrides.get("temperature", self._temperature),
        )
