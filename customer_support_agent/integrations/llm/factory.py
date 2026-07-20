"""
LLM provider factory.

Design pattern: Factory Method.

This is the ONLY place in the codebase that maps
``Settings.llm_provider`` (a config value) to a concrete ``LLMProvider``
implementation. Every other module asks for an ``LLMProvider`` through
this function — never imports OpenAIChatProvider/GroqChatProvider/
GeminiChatProvider directly. That indirection is what lets us add a fourth
provider later by writing one new class and one new branch here, without
touching services, routers, or the agent orchestration logic
(Open/Closed Principle).
"""

from __future__ import annotations

from functools import lru_cache

from customer_support_agent.core.settings import LLMProviderName, Settings, get_settings
from customer_support_agent.integrations.llm.base import LLMProvider
from customer_support_agent.integrations.llm.gemini_provider import GeminiChatProvider
from customer_support_agent.integrations.llm.groq_provider import GroqChatProvider
from customer_support_agent.integrations.llm.openai_provider import OpenAIChatProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the LLM provider selected by ``settings.llm_provider``."""
    if settings.llm_provider == LLMProviderName.OPENAI:
        return OpenAIChatProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
        )
    if settings.llm_provider == LLMProviderName.GROQ:
        return GroqChatProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_chat_model,
        )
    if settings.llm_provider == LLMProviderName.GEMINI:
        return GeminiChatProvider(
            api_key=settings.google_api_key,
            model=settings.gemini_chat_model,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Process-wide cached accessor, mirroring ``get_settings()``.

    FastAPI routes/services should depend on this function (or better, on
    ``LLMProvider`` injected via FastAPI's dependency system) rather than
    constructing providers themselves.
    """
    return build_llm_provider(get_settings())
