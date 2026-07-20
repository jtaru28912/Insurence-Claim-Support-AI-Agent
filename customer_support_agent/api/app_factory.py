"""
FastAPI application factory.

Design pattern: Factory Method + centralized lifespan management.

``create_app()`` is the single place where the FastAPI app is assembled:
middleware, routers, and startup/shutdown behavior. Routers, services, and
integrations are added here incrementally as later phases build them out —
this file itself does not contain business logic.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from customer_support_agent.api.routers.customers_router import router as customers_router
from customer_support_agent.api.routers.dashboard_router import router as dashboard_router
from customer_support_agent.api.routers.drafts_router import router as drafts_router
from customer_support_agent.api.routers.health_router import router as health_router
from customer_support_agent.api.routers.knowledge_router import router as knowledge_router
from customer_support_agent.api.routers.logging_router import router as logging_router
from customer_support_agent.api.routers.memory_router import router as memory_router
from customer_support_agent.api.routers.tickets_router import router as tickets_router
from customer_support_agent.core.logging_config import configure_logging
from customer_support_agent.core.settings import get_settings
from customer_support_agent.data.database import Database
from customer_support_agent.data.repositories.customer_repository import CustomerRepository
from customer_support_agent.integrations.tools.customer_data_gateway import (
    set_customer_data_gateway,
)
from customer_support_agent.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown hook.

    On startup:
      - configure logging
      - ensure storage directories (SQLite dir, vector store dir, KB dir) exist
      - initialize the SQLite schema
      - ingest knowledge base into ChromaDB

    Shutdown:
      - cleanup logging
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_storage_directories()
    logger.info(
        "Starting %s (env=%s, llm_provider=%s, embedding_provider=%s)",
        settings.app_name,
        settings.app_env,
        settings.llm_provider.value,
        settings.embedding_provider.value,
    )

    # Initialize database schema
    db = Database(settings)
    db.initialize_schema()
    set_customer_data_gateway(CustomerRepository(db))
    logger.info("Database schema initialized")

    # Refresh the knowledge base on startup so stale/out-of-scope sources
    # from older runs do not remain queryable in the persistent Chroma store.
    if settings.app_env.lower() != "test":
        knowledge_service = KnowledgeService()
        logger.info("Refreshing knowledge base on startup...")
        stats = knowledge_service.ingest_knowledge_base()
        logger.info(
            "Knowledge base refresh completed (chunks=%d collection_count=%d)",
            stats.get("chunks_count", 0),
            stats.get("collection_count", 0),
        )
    else:
        logger.info("Skipping knowledge base ingestion in test environment")

    yield

    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Backend API for the Insurance Claims Support AI Agent.\n\n"
            "Use this Swagger page to test the end-to-end flow:\n"
            "1. Create a customer with `POST /customers`.\n"
            "2. Create a claim ticket with `POST /tickets` using the returned customer ID.\n"
            "3. Generate a draft with `POST /drafts` using the customer ID and ticket ID.\n"
            "4. Review or edit the draft, then approve it with `PUT /drafts/{draft_id}/approve`.\n"
            "5. Probe memory with `GET /memory/probe` while the backend process is still running.\n\n"
            "Draft approval means the adjuster approved the generated recommendation; it does not "
            "automatically settle or close the claim ticket."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(logging_router)
    app.include_router(dashboard_router)
    app.include_router(customers_router)
    app.include_router(tickets_router)
    app.include_router(drafts_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)

    return app
