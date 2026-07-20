"""Knowledge service — business logic for knowledge base ingestion and management."""

from __future__ import annotations

import logging

from customer_support_agent.integrations.rag.chroma_kb import get_knowledge_base

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Business logic for knowledge base ingestion, refresh, and querying."""

    def __init__(self) -> None:
        self._kb = get_knowledge_base()
        logger.debug("KnowledgeService initialized with cached knowledge base instance")

    def ingest_knowledge_base(self) -> dict:
        """Ingest/refresh the knowledge base from markdown files."""
        logger.info("Starting knowledge base ingestion")
        from customer_support_agent.core.settings import get_settings

        settings = get_settings()
        directory = settings.knowledge_base_path

        if not any(directory.glob("*.md")):
            logger.warning(
                "No markdown files found in configured KB path %s. Please verify the workspace knowledge base.",
                directory,
            )

        chunk_count = self._kb.ingest_directory(directory)

        logger.info(f"Knowledge base ingestion complete: {chunk_count} chunks indexed")
        return {
            "status": "ingested",
            "chunks_count": chunk_count,
            "collection_count": self.get_collection_stats()["collection_count"],
        }

    def query_knowledge_base(self, query: str, top_k: int | None = None) -> dict:
        """Search the knowledge base for relevant chunks."""
        logger.info("Knowledge base query requested")
        logger.debug("Knowledge query payload: query=%r top_k=%s", query, top_k)
        hits = self._kb.search(query, top_k=top_k)
        logger.info("Knowledge base query returned %d hit(s)", len(hits))
        return {
            "query": query,
            "hits_count": len(hits),
            "hits": [
                {
                    "content": hit.content,
                    "source": hit.source,
                    "chunk_index": hit.chunk_index,
                    "score": hit.score,
                }
                for hit in hits
            ],
        }

    def get_collection_stats(self) -> dict:
        """Get statistics about the knowledge base collection."""
        count = self._kb.get_collection_count()
        logger.debug("Knowledge base stats requested; collection_count=%d", count)
        return {
            "collection_count": count,
            "status": "ready" if count > 0 else "empty",
            "indexed_sources": self._kb.get_indexed_sources(),
        }


def get_knowledge_service() -> KnowledgeService:
    """Factory for KnowledgeService."""
    return KnowledgeService()
