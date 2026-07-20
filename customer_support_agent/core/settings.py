"""
Centralized application configuration.

Design notes
------------
This module is the single source of truth for runtime configuration. It
follows the *Dependency Inversion Principle*: nothing else in the codebase
reads environment variables directly — every component depends on this
typed ``Settings`` object instead.

Provider independence:
    ``LLM_PROVIDER`` and ``EMBEDDING_PROVIDER`` select which concrete
    implementation the integrations/llm and integrations/embeddings
    factories will construct (see integrations/llm/factory.py and
    integrations/embeddings/factory.py). Swapping providers is therefore a
    configuration change (edit .env), never a code change — satisfying the
    Open/Closed Principle.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (customer_support_agent/core/settings.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMProviderName(str, Enum):
    """Supported chat/completion LLM backends."""

    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"


class EmbeddingProviderName(str, Enum):
    """Supported embedding backends."""

    OPENAI = "openai"
    GEMINI = "gemini"
    CHROMA_DEFAULT = "chroma_default"


class Settings(BaseSettings):
    """
    Strongly typed application settings, loaded from environment variables
    and/or a local ``.env`` file. See ``.env.example`` for the full list of
    supported keys.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------- App
    app_name: str = "Insurance Claims Support AI Agent"
    app_env: str = Field(default="development")  # development | production | test
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # ------------------------------------------------------ Provider choice
    llm_provider: LLMProviderName = Field(default=LLMProviderName.OPENAI)
    embedding_provider: EmbeddingProviderName = Field(default=EmbeddingProviderName.OPENAI)

    # ------------------------------------------------------------- OpenAI
    openai_api_key: str | None = Field(default=None)
    openai_chat_model: str = Field(default="gpt-4o")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # --------------------------------------------------------------- Groq
    groq_api_key: str | None = Field(default=None)
    groq_chat_model: str = Field(default="llama-3.3-70b-versatile")

    # ------------------------------------------------------------- Gemini
    google_api_key: str | None = Field(default=None)
    gemini_chat_model: str = Field(default="gemini-1.5-flash")
    gemini_embedding_model: str = Field(default="models/text-embedding-004")

    # ------------------------------------------------------------- Storage
    sqlite_db_path: Path = Field(default=PROJECT_ROOT / "storage" / "db" / "app.db")
    vector_store_path: Path = Field(default=PROJECT_ROOT / "storage" / "vector_store")
    knowledge_base_path: Path = Field(default=PROJECT_ROOT / "knowledge_base")

    # --------------------------------------------------------------- RAG
    rag_chunk_size: int = Field(default=800)
    rag_chunk_overlap: int = Field(default=120)
    rag_top_k: int = Field(default=4)
    chroma_collection_name: str = Field(default="insurance_knowledge_base")

    # ------------------------------------------------------------ Memory
    memory_top_k: int = Field(default=5)

    # --------------------------------------------------------------- CORS
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    def ensure_storage_directories(self) -> None:
        """Create any storage directories that do not yet exist.

        Called once during application startup (see api/app_factory.py) so
        that a fresh checkout works without any manual `mkdir` steps.
        """
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self.knowledge_base_path.mkdir(parents=True, exist_ok=True)

    def active_llm_api_key(self) -> str | None:
        """Return the API key relevant to the currently selected LLM provider."""
        return {
            LLMProviderName.OPENAI: self.openai_api_key,
            LLMProviderName.GROQ: self.groq_api_key,
            LLMProviderName.GEMINI: self.google_api_key,
        }[self.llm_provider]

    def active_embedding_api_key(self) -> str | None:
        """Return the API key relevant to the currently selected embedding provider."""
        return {
            EmbeddingProviderName.OPENAI: self.openai_api_key,
            EmbeddingProviderName.GEMINI: self.google_api_key,
            EmbeddingProviderName.CHROMA_DEFAULT: None,
        }[self.embedding_provider]


@lru_cache
def get_settings() -> Settings:
    """
    Return a process-wide cached ``Settings`` instance.

    ``lru_cache`` guarantees the .env file is parsed once and the same
    object is reused everywhere it is depended upon (FastAPI dependency
    injection, services, integrations).
    """
    return Settings()
