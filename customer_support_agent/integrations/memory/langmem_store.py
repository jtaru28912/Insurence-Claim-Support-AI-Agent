"""
LangMem-based long-term memory layer.

Design notes
------------
Wraps LangGraph's ``InMemoryStore`` + LangMem tool factories behind a
small, purpose-built interface for this project's two memory scopes
(customer, company).

Semantic search is enabled by attaching an ``index`` configuration to the
store, built from the currently configured ``EmbeddingProvider``
(Dependency Inversion — this class never imports a concrete embeddings
SDK). The original spec ties semantic memory strictly to `GOOGLE_API_KEY`
/ Gemini; per user decision this build generalizes that check to "any
embedding provider that yields a usable LangChain ``Embeddings`` object"
(OpenAI or Gemini) so switching ``EMBEDDING_PROVIDER`` in `.env` is
enough to enable/disable it — no code change required.

When semantic search is unavailable (no provider configured, or a query
returns no semantic matches), retrieval falls back to a plain
recency-ordered listing of the same namespace — matching the deck's
documented behavior: "falls back to recent-memory listing... preserves
operation continuity even when semantic indexing unavailable."
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from langgraph.store.memory import InMemoryStore

from customer_support_agent.core.settings import Settings, get_settings
from customer_support_agent.integrations.embeddings.base import EmbeddingProvider
from customer_support_agent.integrations.embeddings.factory import get_embedding_provider

logger = logging.getLogger(__name__)

# Known embedding output dimensions, used to configure LangGraph's
# InMemoryStore vector index. Extend this mapping when adding a new
# embedding model to core/settings.py.
_KNOWN_EMBEDDING_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "models/text-embedding-004": 768,
}
_DEFAULT_EMBEDDING_DIMS = 1536


def normalize_email(email: str) -> str:
    """Normalize an email into a LangGraph-namespace-safe token.

    LangGraph namespace labels cannot contain periods, so '.' -> '_dot_'
    and '@' -> '_at_'. Lowercased and stripped for consistent scoping
    regardless of how the email was capitalized at intake.
    """
    cleaned = email.strip().lower()
    return cleaned.replace("@", "_at_").replace(".", "_dot_")


def company_slug(company_name: str) -> str:
    """Normalize a company name into a namespace-safe slug (``company::<slug>``)."""
    slug = re.sub(r"[^a-z0-9]+", "_", company_name.strip().lower()).strip("_")
    return slug or "unknown_company"


@dataclass
class MemoryHit:
    """A single retrieved memory item."""

    memory_id: str
    content: str
    scope: str  # "customer" | "company"
    score: float | None  # cosine similarity (higher = more relevant), or None if not semantic
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryRetrievalResult:
    hits: list[MemoryHit]
    semantic_search_used: bool
    error: str | None = None


class LangMemStore:
    """Customer/company-scoped long-term memory, backed by LangGraph's InMemoryStore."""

    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        self._settings = settings
        self._embedding_provider = embedding_provider
        self._semantic_enabled = False
        self._store = self._build_store()

    # -------------------------------------------------------------- setup
    def _build_store(self) -> InMemoryStore:
        embeddings = self._embedding_provider.as_langchain_embeddings()
        if embeddings is None:
            # chroma_default (or any provider not yielding a LangChain
            # Embeddings object) cannot back LangGraph's vector index.
            logger.info("Semantic memory search disabled (no LangChain Embeddings available).")
            return InMemoryStore()

        model_name = getattr(embeddings, "model", None) or ""
        dims = _KNOWN_EMBEDDING_DIMS.get(model_name, _DEFAULT_EMBEDDING_DIMS)
        self._semantic_enabled = True
        logger.info(
            "Semantic memory search enabled via %s (model=%s, dims=%d)",
            self._embedding_provider.provider_name,
            model_name or "unknown",
            dims,
        )
        return InMemoryStore(index={"dims": dims, "embed": embeddings, "fields": ["content"]})

    @property
    def is_semantic_enabled(self) -> bool:
        return self._semantic_enabled

    @property
    def raw_store(self) -> InMemoryStore:
        """Expose the underlying BaseStore for LangMem tool factories / create_agent(store=...)."""
        return self._store

    def get_backend_status(self) -> dict:
        """Return lightweight observability details for health/debug endpoints."""
        embeddings = self._embedding_provider.as_langchain_embeddings()
        model_name = getattr(embeddings, "model", None) if embeddings is not None else None
        return {
            "backend": "langgraph_in_memory_store",
            "semantic_search_enabled": self._semantic_enabled,
            "embedding_provider": self._embedding_provider.provider_name,
            "embedding_model": model_name,
            "memory_top_k": self._settings.memory_top_k,
        }

    # ---------------------------------------------------------- namespaces
    @staticmethod
    def customer_namespace(email: str) -> tuple[str, ...]:
        return ("memories", "customer", normalize_email(email))

    @staticmethod
    def company_namespace(company_name: str) -> tuple[str, ...]:
        return ("memories", "company", company_slug(company_name))

    # --------------------------------------------------------------- write
    def write_memory(
        self, namespace: tuple[str, ...], content: str, metadata: dict | None = None
    ) -> str:
        """Persist a memory into the given namespace. Returns the memory id.

        ``index=["content"]`` is safe to pass even when the store has no
        semantic index configured — LangGraph documents that index
        arguments are simply ignored in that case.
        """
        memory_id = str(uuid.uuid4())
        value = {"content": content, **(metadata or {})}
        self._store.put(namespace, memory_id, value, index=["content"])
        return memory_id

    def write_resolution_memory(
        self,
        *,
        customer_email: str,
        company_name: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict[str, str]:
        """
        Write an approved claim resolution into BOTH the customer and
        company scopes, per spec: "accepted recommendations written into
        these scopes as reusable claim-resolution memories."
        """
        customer_id = self.write_memory(self.customer_namespace(customer_email), content, metadata)
        company_id = self.write_memory(self.company_namespace(company_name), content, metadata)
        return {"customer_memory_id": customer_id, "company_memory_id": company_id}

    # -------------------------------------------------------------- search
    def _search_namespace(
        self, namespace: tuple[str, ...], query: str, limit: int, scope_label: str
    ) -> tuple[list[MemoryHit], str | None]:
        try:
            results = self._store.search(namespace, query=query, limit=limit)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Memory search failed for namespace=%s", namespace)
            return [], str(exc)

        if not results:
            # Fallback: recency-ordered listing, no query ranking — this
            # is the "recent-memory listing" behavior the spec describes.
            try:
                results = self._store.search(namespace, limit=limit)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Fallback memory listing failed for namespace=%s", namespace)
                return [], str(exc)

        hits = [
            MemoryHit(
                memory_id=item.key,
                content=item.value.get("content", ""),
                scope=scope_label,
                score=getattr(item, "score", None),
                metadata={k: v for k, v in item.value.items() if k != "content"},
            )
            for item in results
        ]
        return hits, None

    def retrieve_relevant_memories(
        self,
        *,
        customer_email: str,
        company_name: str,
        query: str,
        limit: int | None = None,
    ) -> MemoryRetrievalResult:
        """
        Search both the customer and company scopes for ``query``,
        deduplicate overlapping hits (by content), and return a combined,
        score-ordered result — per spec: "supports customer/company scope
        retrieval... deduplicates repeated hits across scopes."
        """
        limit = limit or self._settings.memory_top_k

        customer_hits, customer_error = self._search_namespace(
            self.customer_namespace(customer_email), query, limit, scope_label="customer"
        )
        company_hits, company_error = self._search_namespace(
            self.company_namespace(company_name), query, limit, scope_label="company"
        )

        combined = customer_hits + company_hits
        deduplicated: list[MemoryHit] = []
        seen_content: set[str] = set()
        for hit in combined:
            normalized_content = hit.content.strip()
            if normalized_content and normalized_content not in seen_content:
                seen_content.add(normalized_content)
                deduplicated.append(hit)

        # Cosine similarity: higher = more relevant. Items without a score
        # (non-semantic fallback listing) sort last.
        if self._semantic_enabled and any(h.score is not None for h in deduplicated):
            deduplicated.sort(
                key=lambda h: h.score if h.score is not None else -1.0, reverse=True
            )

        deduplicated = deduplicated[:limit]

        error = customer_error or company_error
        return MemoryRetrievalResult(
            hits=deduplicated, semantic_search_used=self._semantic_enabled, error=error
        )


@lru_cache
def get_memory_store() -> LangMemStore:
    """Process-wide cached accessor, mirroring the other integration factories."""
    return LangMemStore(get_settings(), get_embedding_provider())
