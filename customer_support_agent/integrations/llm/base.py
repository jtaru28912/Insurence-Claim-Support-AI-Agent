"""
LLM provider abstraction.

Design pattern: Strategy + Dependency Inversion.

Every concrete provider (OpenAI, Groq, Gemini, ...) implements this same
narrow interface. Nothing upstream (services/copilot_service.py, the
LangChain agent runtime) ever imports a concrete provider class directly —
it depends on ``LLMProvider`` only, and receives a concrete instance from
``integrations/llm/factory.py``. This is what makes the LLM backend
swappable purely through configuration (see core/settings.py::llm_provider).

Every implementation must expose a LangChain-compatible chat model via
``as_langchain_chat_model()`` because the rest of the codebase (LangGraph
agent, LangMem) is built on top of LangChain's chat model interface. This
keeps the abstraction thin: we are not reinventing a chat protocol, only
standardizing *provider construction and configuration*.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class every chat/completion provider must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short machine-readable identifier, e.g. 'openai', 'groq', 'gemini'."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The concrete model identifier in use, e.g. 'gpt-4o'."""

    @abstractmethod
    def as_langchain_chat_model(self, **overrides: Any):
        """
        Return a LangChain ``BaseChatModel`` instance ready to be used by
        ``langchain.agents.create_agent`` / LangGraph.

        Parameters
        ----------
        **overrides:
            Optional per-call overrides (e.g. temperature) that take
            precedence over the provider's configured defaults.
        """

    def is_configured(self) -> bool:
        """Whether this provider has the credentials it needs to run.

        Concrete providers override this when they have a required API key.
        Defaults to True for providers that need no credentials.
        """
        return True
