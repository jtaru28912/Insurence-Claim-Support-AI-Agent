"""Memory service for claim-history probing."""

from __future__ import annotations

import logging

from customer_support_agent.integrations.memory.langmem_store import get_memory_store

logger = logging.getLogger(__name__)


class MemoryService:
    """Thin service wrapper around LangMem probing for dashboard/API use."""

    def __init__(self) -> None:
        self._memory_store = get_memory_store()
        logger.debug("MemoryService initialized with cached memory store")

    def probe_memories(
        self,
        *,
        customer_email: str,
        company_name: str,
        query: str,
        limit: int | None = None,
    ) -> dict:
        logger.info("Memory probe requested for customer_email=%s", customer_email)
        logger.debug(
            "Memory probe payload: customer_email=%s company_name=%s query=%r limit=%s",
            customer_email,
            company_name,
            query,
            limit,
        )
        result = self._memory_store.retrieve_relevant_memories(
            customer_email=customer_email,
            company_name=company_name,
            query=query,
            limit=limit,
        )
        logger.info(
            "Memory probe completed for customer_email=%s with %d hit(s)",
            customer_email,
            len(result.hits),
        )
        return {
            "customer_email": customer_email,
            "company_name": company_name,
            "query": query,
            "semantic_search_used": result.semantic_search_used,
            "hits_count": len(result.hits),
            "hits": [
                {
                    "memory_id": hit.memory_id,
                    "content": hit.content,
                    "scope": hit.scope,
                    "score": hit.score,
                    "metadata": hit.metadata,
                }
                for hit in result.hits
            ],
            "error": result.error,
        }

    def get_backend_status(self) -> dict:
        """Return memory backend status for health/debug visibility."""
        status = self._memory_store.get_backend_status()
        status["status"] = "ready"
        logger.debug("Memory backend status requested: %s", status)
        return status


def get_memory_service() -> MemoryService:
    """Factory for MemoryService."""
    return MemoryService()
