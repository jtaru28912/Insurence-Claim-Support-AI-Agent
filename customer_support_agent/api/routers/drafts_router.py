"""FastAPI router for draft (auto-generated claim response) endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from customer_support_agent.data.database import Database, get_database
from customer_support_agent.data.repositories.draft_repository import DraftRepository
from customer_support_agent.data.repositories.ticket_repository import TicketRepository
from customer_support_agent.schemas.shared import (
    DraftApprovalRequest,
    DraftCreateRequest,
    DraftDiscardRequest,
    DraftListResponse,
    DraftMarkPendingRequest,
    DraftRegenerateRequest,
    DraftRequestInfoRequest,
    DraftResponse,
    DraftUpdateRequest,
)
from customer_support_agent.services.draft_service import DraftService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _build_draft_response(
    record,
    *,
    customer_id: str | None = None,
    is_new: bool | None = None,
) -> DraftResponse:
    return DraftResponse(
        id=record.id,
        ticket_id=record.ticket_id,
        customer_id=customer_id,
        draft_text=record.draft_text,
        status=record.status,
        context_used=record.context_used,
        is_new=is_new,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        adjuster_notes=record.adjuster_notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _map_service_value_error(exc: ValueError) -> None:
    detail = str(exc)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in detail.lower()
        else status.HTTP_400_BAD_REQUEST
    )
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    request: DraftCreateRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Generate a draft response for a ticket."""
    logger.info(
        "Draft generation endpoint requested: ticket_id=%s customer_id=%s regenerate=%s",
        request.ticket_id,
        request.customer_id,
        request.regenerate,
    )
    logger.debug("Draft generation request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        result = draft_service.generate_draft(
            ticket_id=request.ticket_id,
            customer_id=request.customer_id,
            regenerate=request.regenerate,
        )
        repo = DraftRepository(database)
        record = repo.get_by_id(result["draft_id"])
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        return _build_draft_response(
            record,
            customer_id=request.customer_id,
            is_new=result["is_new"],
        )
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Draft generation endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: str,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Get a draft by ID."""
    logger.info("Get draft endpoint requested: draft_id=%s", draft_id)
    repo = DraftRepository(database)
    ticket_repo = TicketRepository(database)
    record = repo.get_by_id(draft_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    ticket = ticket_repo.get_by_id(record.ticket_id)
    return _build_draft_response(record, customer_id=ticket.customer_id if ticket else None)


@router.get("/ticket/{ticket_id}", response_model=DraftListResponse)
async def list_ticket_drafts(
    ticket_id: str,
    database: Database = Depends(get_database),
) -> DraftListResponse:
    """List all drafts for a ticket."""
    logger.info("List ticket drafts endpoint requested: ticket_id=%s", ticket_id)
    repo = DraftRepository(database)
    ticket_repo = TicketRepository(database)
    records = repo.list_by_ticket(ticket_id)
    ticket = ticket_repo.get_by_id(ticket_id)
    drafts = [
        _build_draft_response(record, customer_id=ticket.customer_id if ticket else None)
        for record in records
    ]
    return DraftListResponse(drafts=drafts, count=len(drafts))


@router.get("/{draft_id}/history", response_model=DraftListResponse)
async def get_draft_history(
    draft_id: str,
    database: Database = Depends(get_database),
) -> DraftListResponse:
    """List all draft revisions for the same ticket as the supplied draft."""
    logger.info("Draft history endpoint requested: draft_id=%s", draft_id)
    try:
        draft_service = DraftService(database)
        records = draft_service.get_draft_history(draft_id)
        ticket_repo = TicketRepository(database)
        drafts = []
        for record in records:
            ticket = ticket_repo.get_by_id(record.ticket_id)
            drafts.append(
                _build_draft_response(record, customer_id=ticket.customer_id if ticket else None)
            )
        return DraftListResponse(drafts=drafts, count=len(drafts))
    except ValueError as e:
        _map_service_value_error(e)


@router.put("/{draft_id}/approve", response_model=DraftResponse)
async def approve_draft(
    draft_id: str,
    request: DraftApprovalRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Approve a draft (transitions to approved status + saves to memory)."""
    logger.info("Approve draft endpoint requested: draft_id=%s", draft_id)
    logger.debug("Approve draft request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        draft_service.approve_draft(
            draft_id=draft_id,
            approved_by=request.approved_by,
            adjuster_notes=request.adjuster_notes,
        )

        repo = DraftRepository(database)
        record = repo.get_by_id(draft_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(record, customer_id=ticket.customer_id if ticket else None, is_new=False)
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Approve draft endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{draft_id}/regenerate", response_model=DraftResponse)
async def regenerate_draft(
    draft_id: str,
    request: DraftRegenerateRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Create a new revision of an existing draft."""
    logger.info("Regenerate draft endpoint requested: draft_id=%s", draft_id)
    logger.debug("Regenerate draft request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        result = draft_service.regenerate_draft(draft_id=draft_id, reason=request.reason)
        repo = DraftRepository(database)
        record = repo.get_by_id(result["draft_id"])
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(record, customer_id=ticket.customer_id if ticket else None, is_new=True)
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Regenerate draft endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{draft_id}/discard", response_model=DraftResponse)
async def discard_draft(
    draft_id: str,
    request: DraftDiscardRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Discard a draft."""
    logger.info("Discard draft endpoint requested: draft_id=%s", draft_id)
    logger.debug("Discard draft request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        draft_service.discard_draft(draft_id=draft_id, reason=request.reason)

        repo = DraftRepository(database)
        record = repo.get_by_id(draft_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(record, customer_id=ticket.customer_id if ticket else None, is_new=False)
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Discard draft endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: str,
    request: DraftUpdateRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Persist human edits to a draft prior to approval/discard."""
    logger.info("Update draft endpoint requested: draft_id=%s", draft_id)
    logger.debug("Update draft request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        draft_service.update_draft_text(draft_id=draft_id, draft_text=request.draft_text)

        repo = DraftRepository(database)
        record = repo.get_by_id(draft_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(record, customer_id=ticket.customer_id if ticket else None)
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Update draft endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{draft_id}/request-info", response_model=DraftResponse)
async def request_more_info(
    draft_id: str,
    request: DraftRequestInfoRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Mark a draft as waiting on more customer information."""
    logger.info("Request more info endpoint requested: draft_id=%s", draft_id)
    logger.debug("Request more info body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        draft_service.request_more_info(draft_id=draft_id, reason=request.reason)

        repo = DraftRepository(database)
        record = repo.get_by_id(draft_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(
            record,
            customer_id=ticket.customer_id if ticket else None,
            is_new=False,
        )
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Request more info endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{draft_id}/mark-pending", response_model=DraftResponse)
async def mark_pending(
    draft_id: str,
    request: DraftMarkPendingRequest,
    database: Database = Depends(get_database),
) -> DraftResponse:
    """Return a draft to pending for another review cycle."""
    logger.info("Mark pending endpoint requested: draft_id=%s", draft_id)
    logger.debug("Mark pending request body: %s", request.model_dump())
    try:
        draft_service = DraftService(database)
        draft_service.mark_pending(draft_id=draft_id, reason=request.reason)

        repo = DraftRepository(database)
        record = repo.get_by_id(draft_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        ticket = TicketRepository(database).get_by_id(record.ticket_id)
        return _build_draft_response(
            record,
            customer_id=ticket.customer_id if ticket else None,
            is_new=False,
        )
    except ValueError as e:
        _map_service_value_error(e)
    except Exception as e:
        logger.exception("Mark pending endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
