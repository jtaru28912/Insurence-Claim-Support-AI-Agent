"""FastAPI router for runtime logging inspection and control."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from customer_support_agent.core.logging_config import get_log_level, set_log_level
from customer_support_agent.schemas.shared import LoggingLevelResponse, LoggingLevelUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logging", tags=["logging"])


@router.get("/level", response_model=LoggingLevelResponse)
async def get_runtime_log_level() -> LoggingLevelResponse:
    """Return the current runtime log level."""
    level = get_log_level()
    logger.debug("Runtime log level requested: %s", level)
    return LoggingLevelResponse(level=level)


@router.put("/level", response_model=LoggingLevelResponse)
async def update_runtime_log_level(
    request: LoggingLevelUpdateRequest,
) -> LoggingLevelResponse:
    """Update the root logger level without restarting the app."""
    try:
        applied = set_log_level(request.level)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    logger.info("Runtime log level changed to %s", applied)
    return LoggingLevelResponse(level=applied)
