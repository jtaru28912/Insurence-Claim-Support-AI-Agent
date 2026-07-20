"""FastAPI router for claim-history memory probing."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from customer_support_agent.schemas.shared import MemoryProbeResponse, MemoryStatusResponse
from customer_support_agent.services.memory_service import MemoryService, get_memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/status", response_model=MemoryStatusResponse)
async def memory_status(
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryStatusResponse:
    """Return memory backend health/debug information."""
    logger.debug("Memory status endpoint requested")
    return MemoryStatusResponse(**memory_service.get_backend_status())


@router.get("/probe", response_model=MemoryProbeResponse)
async def probe_memory(
    customer_email: str = Query(
        ...,
        min_length=3,
        examples=["john@gmail.com"],
        description="Customer email used when the approved draft was saved to memory.",
    ),
    company_name: str = Query(
        ...,
        min_length=1,
        examples=["XYZ Insurance"],
        description="Customer company name used for company-scoped memory search.",
    ),
    query: str = Query(
        ...,
        min_length=1,
        examples=["vehicle damage heated riots"],
        description="Natural-language search query for prior approved draft resolutions.",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=20,
        examples=[5],
        description="Maximum number of memory hits to return.",
    ),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryProbeResponse:
    """Probe customer/company memory for claim-history context."""
    logger.info("Memory probe endpoint requested for customer_email=%s", customer_email)
    logger.debug(
        "Memory probe query params: customer_email=%s company_name=%s query=%r limit=%s",
        customer_email,
        company_name,
        query,
        limit,
    )
    return MemoryProbeResponse(
        **memory_service.probe_memories(
            customer_email=customer_email,
            company_name=company_name,
            query=query,
            limit=limit,
        )
    )
