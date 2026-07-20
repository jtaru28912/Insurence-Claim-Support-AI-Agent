"""FastAPI router for ticket (claim) endpoints."""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from customer_support_agent.data.database import Database, get_database
from customer_support_agent.data.repositories.ticket_repository import TicketRepository
from customer_support_agent.schemas.shared import (
    TicketCreateRequest,
    TicketListResponse,
    TicketResponse,
    TicketUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: TicketCreateRequest,
    database: Database = Depends(get_database),
) -> TicketResponse:
    """Create a new ticket (claim)."""
    logger.info("Create ticket requested for customer_id=%s", request.customer_id)
    logger.debug("Create ticket payload: %s", request.model_dump())
    repo = TicketRepository(database)
    try:
        record = repo.create(
            customer_id=request.customer_id,
            subject=request.subject,
            claim_narrative=request.claim_narrative,
            claim_type=request.claim_type,
        )
        response = TicketResponse(
            id=record.id,
            customer_id=record.customer_id,
            subject=record.subject,
            claim_narrative=record.claim_narrative,
            claim_type=record.claim_type,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        logger.info("Ticket created successfully: ticket_id=%s", record.id)
        return response
    except ValueError as e:
        logger.warning("Ticket creation validation failure: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except sqlite3.IntegrityError as e:
        logger.warning("Ticket creation failed because customer was not found: %s", request.customer_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer not found for ticket creation",
        ) from e


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: str,
    database: Database = Depends(get_database),
) -> TicketResponse:
    """Get a ticket by ID."""
    logger.info("Get ticket requested: ticket_id=%s", ticket_id)
    repo = TicketRepository(database)
    record = repo.get_by_id(ticket_id)
    if not record:
        logger.warning("Ticket not found: ticket_id=%s", ticket_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    response = TicketResponse(
        id=record.id,
        customer_id=record.customer_id,
        subject=record.subject,
        claim_narrative=record.claim_narrative,
        claim_type=record.claim_type,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
    logger.debug("Ticket retrieved: %s", response.model_dump())
    return response


@router.get("/customer/{customer_id}", response_model=TicketListResponse)
async def list_customer_tickets(
    customer_id: str,
    database: Database = Depends(get_database),
) -> TicketListResponse:
    """List all tickets for a customer."""
    logger.info("List customer tickets requested: customer_id=%s", customer_id)
    repo = TicketRepository(database)
    records = repo.list_by_customer(customer_id)
    tickets = [
        TicketResponse(
            id=record.id,
            customer_id=record.customer_id,
            subject=record.subject,
            claim_narrative=record.claim_narrative,
            claim_type=record.claim_type,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    response = TicketListResponse(tickets=tickets, count=len(tickets))
    logger.info("Customer ticket list completed with %d result(s)", response.count)
    return response


@router.get("", response_model=TicketListResponse)
async def list_all_tickets(
    database: Database = Depends(get_database),
) -> TicketListResponse:
    """List all claim tickets for dashboard selection views."""
    logger.info("List all tickets requested")
    repo = TicketRepository(database)
    records = repo.list_all()
    tickets = [
        TicketResponse(
            id=record.id,
            customer_id=record.customer_id,
            subject=record.subject,
            claim_narrative=record.claim_narrative,
            claim_type=record.claim_type,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    response = TicketListResponse(tickets=tickets, count=len(tickets))
    logger.info("List all tickets completed with %d result(s)", response.count)
    return response


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: str,
    request: TicketUpdateRequest,
    database: Database = Depends(get_database),
) -> TicketResponse:
    """Update ticket status."""
    logger.info("Update ticket requested: ticket_id=%s new_status=%s", ticket_id, request.status)
    repo = TicketRepository(database)
    record = repo.get_by_id(ticket_id)
    if not record:
        logger.warning("Ticket not found during update: ticket_id=%s", ticket_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    repo.update_status(ticket_id, request.status)
    updated = repo.get_by_id(ticket_id)
    assert updated is not None

    response = TicketResponse(
        id=updated.id,
        customer_id=updated.customer_id,
        subject=updated.subject,
        claim_narrative=updated.claim_narrative,
        claim_type=updated.claim_type,
        status=updated.status,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
    logger.info("Ticket updated successfully: ticket_id=%s status=%s", updated.id, updated.status)
    return response
