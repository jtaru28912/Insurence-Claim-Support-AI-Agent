"""Health check endpoint.

Used by Docker healthchecks, the CI/CD deploy workflow's post-deploy
verification step, and load balancers — so its response should stay cheap
and dependency-free (no DB/LLM calls).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from customer_support_agent.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(settings: Settings = Depends(get_settings)) -> dict:
    """Lightweight liveness/readiness probe."""
    logger.debug(
        "Health check requested (env=%s, llm_provider=%s, embedding_provider=%s)",
        settings.app_env,
        settings.llm_provider.value,
        settings.embedding_provider.value,
    )
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "llm_provider": settings.llm_provider.value,
        "embedding_provider": settings.embedding_provider.value,
    }
