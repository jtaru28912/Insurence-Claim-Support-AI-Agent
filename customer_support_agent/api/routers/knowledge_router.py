"""FastAPI router for knowledge-base ingestion and querying."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from customer_support_agent.schemas.shared import KnowledgeQueryRequest
from customer_support_agent.services.knowledge_service import (
    KnowledgeService,
    get_knowledge_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/stats")
async def get_knowledge_stats(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """Return knowledge-base collection statistics."""
    logger.debug("Knowledge stats endpoint requested")
    return knowledge_service.get_collection_stats()


@router.post("/ingest")
async def ingest_knowledge_base(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """Ingest or refresh the knowledge base from markdown files."""
    logger.info("Knowledge ingest endpoint requested")
    return knowledge_service.ingest_knowledge_base()


@router.post("/query")
async def query_knowledge_base(
    request: KnowledgeQueryRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """Search the knowledge base for relevant chunks."""
    logger.info("Knowledge query endpoint requested")
    logger.debug("Knowledge query request body: %s", request.model_dump())
    return knowledge_service.query_knowledge_base(request.query, request.top_k)
