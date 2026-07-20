"""FastAPI router for high-level dashboard metrics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from customer_support_agent.data.database import Database, get_database
from customer_support_agent.schemas.shared import DashboardStatsResponse
from customer_support_agent.services.dashboard_service import get_dashboard_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    database: Database = Depends(get_database),
) -> DashboardStatsResponse:
    """Return top-level metrics for the Streamlit dashboard home page."""
    logger.info("Dashboard stats endpoint requested")
    service = get_dashboard_service(database)
    response = DashboardStatsResponse(**service.get_stats())
    logger.debug("Dashboard stats response: %s", response.model_dump())
    return response
