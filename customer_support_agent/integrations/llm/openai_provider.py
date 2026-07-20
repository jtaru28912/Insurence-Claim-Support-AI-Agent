"""OpenAI chat model provider (default provider for this project)."""

from __future__ import annotations

from typing import Any

from customer_support_agent.integrations.llm.base import LLMProvider


class OpenAIChatProvider(LLMProvider):
    """Wraps ``langchain-openai``'s ``ChatOpenAI`` behind the LLMProvider interface."""

    def __init__(self, api_key: str | None, model: str, temperature: float = 0.2) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def as_langchain_chat_model(self, **overrides: Any):
        # Imported lazily so environments that only use another provider
        # are not forced to install/import langchain-openai.
        from langchain_openai import ChatOpenAI

        if not self.is_configured():
            raise RuntimeError(
                "OpenAI provider selected but OPENAI_API_KEY is not set. "
                "Set it in your .env file."
            )

        return ChatOpenAI(
            api_key=self._api_key,
            model=overrides.get("model", self._model),
            temperature=overrides.get("temperature", self._temperature),
        )
