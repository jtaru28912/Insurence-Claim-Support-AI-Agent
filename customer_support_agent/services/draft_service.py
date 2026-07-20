"""Draft service — business logic for draft management and generation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from customer_support_agent.data.database import Database
from customer_support_agent.data.repositories.customer_repository import CustomerRepository
from customer_support_agent.data.repositories.draft_repository import DraftRepository
from customer_support_agent.data.repositories.ticket_repository import TicketRepository
from customer_support_agent.integrations.memory.langmem_store import get_memory_store

if TYPE_CHECKING:
    from customer_support_agent.services.copilot_service import CopilotService

logger = logging.getLogger(__name__)


class DraftService:
    """Business logic for draft generation, approval, and memory persistence."""

    def __init__(
        self,
        database: Database,
        copilot_service: CopilotService | None = None,
    ) -> None:
        self._database = database
        if copilot_service is None:
            from customer_support_agent.services.copilot_service import get_copilot_service

            copilot_service = get_copilot_service()
        self._copilot_service = copilot_service
        self._draft_repo = DraftRepository(database)
        self._ticket_repo = TicketRepository(database)
        self._customer_repo = CustomerRepository(database)
        self._memory_store = get_memory_store()

    def generate_draft(
        self,
        ticket_id: str,
        customer_id: str,
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """
        Generate an AI draft recommendation for a ticket.

        If a draft already exists and regenerate=False, return the existing one.
        Otherwise, call copilot_service to generate a new draft.
        """
        logger.info(
            "Draft generation requested: ticket_id=%s customer_id=%s regenerate=%s",
            ticket_id,
            customer_id,
            regenerate,
        )
        ticket = self._ticket_repo.get_by_id(ticket_id)
        if not ticket:
            logger.warning("Draft generation failed; ticket not found: %s", ticket_id)
            raise ValueError(f"Ticket {ticket_id} not found")

        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            logger.warning("Draft generation failed; customer not found: %s", customer_id)
            raise ValueError(f"Customer {customer_id} not found")

        # Check for existing draft
        if not regenerate:
            existing_drafts = self._draft_repo.list_by_ticket(ticket_id)
            if existing_drafts:
                draft = existing_drafts[0]  # Most recent first
                logger.info(f"Returned existing draft {draft.id} for ticket {ticket_id}")
                logger.debug("Existing draft context keys: %s", list(draft.context_used.keys()))
                return {
                    "draft_id": draft.id,
                    "draft_text": draft.draft_text,
                    "context_used": draft.context_used,
                    "status": draft.status,
                    "is_new": False,
                }

        # Generate new draft
        logger.info(f"Generating new draft for ticket {ticket_id}")
        from customer_support_agent.services.copilot_service import DraftGenerationRequest

        request = DraftGenerationRequest(
            customer_email=customer.email,
            company_name=customer.company_name,
            claim_narrative=ticket.claim_narrative,
            customer_name=customer.name,
            claim_type=ticket.claim_type,
        )

        result = self._copilot_service.generate_draft(request)
        logger.debug("Copilot draft context signals: %s", result.context_used.get("signals", {}))

        # Persist the draft
        draft = self._draft_repo.create(
            ticket_id=ticket_id,
            draft_text=result.draft_text,
            context_used=result.context_used,
        )

        logger.info(f"Created draft {draft.id} for ticket {ticket_id}")
        logger.debug("Created draft context keys: %s", list(draft.context_used.keys()))

        return {
            "draft_id": draft.id,
            "draft_text": draft.draft_text,
            "context_used": draft.context_used,
            "status": draft.status,
            "is_new": True,
        }

    def approve_draft(
        self,
        draft_id: str,
        approved_by: str,
        adjuster_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Approve a draft and persist the resolution into memory.

        Updates draft status to 'approved' and writes the resolution to both
        customer and company scopes in LangMem.
        """
        logger.info("Approve draft requested: draft_id=%s approved_by=%s", draft_id, approved_by)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Approve draft failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        if draft.status == "approved":
            logger.warning(f"Draft {draft_id} already approved")
            return {"status": "already_approved", "draft_id": draft_id}

        # Get ticket and customer for context
        ticket = self._ticket_repo.get_by_id(draft.ticket_id)
        customer = self._customer_repo.get_by_id(ticket.customer_id) if ticket else None

        # Write to memory with approval metadata
        metadata = {
            "approved_by": approved_by,
            "claim_type": ticket.claim_type if ticket else None,
            "adjuster_notes": adjuster_notes,
            "draft_id": draft_id,
        }

        memory_ids = self._memory_store.write_resolution_memory(
            customer_email=customer.email if customer else "unknown@example.com",
            company_name=customer.company_name if customer else "Unknown",
            content=draft.draft_text,
            metadata=metadata,
        )

        # Update draft status
        self._draft_repo.approve(draft_id, approved_by, adjuster_notes)

        logger.info(
            f"Approved draft {draft_id}; written to memory with IDs {memory_ids}"
        )

        return {
            "status": "approved",
            "draft_id": draft_id,
            "memory_ids": memory_ids,
        }

    def discard_draft(
        self,
        draft_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Mark a draft as discarded (not approved, not memory-persisted)."""
        logger.info("Discard draft requested: draft_id=%s", draft_id)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Discard draft failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        self._draft_repo.discard(draft_id, reason)
        logger.info(f"Discarded draft {draft_id} (reason: {reason})")

        return {
            "status": "discarded",
            "draft_id": draft_id,
        }

    def update_draft_text(self, draft_id: str, draft_text: str) -> dict[str, Any]:
        """Persist human edits to a draft without approving it."""
        logger.info("Update draft text requested: draft_id=%s", draft_id)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Update draft text failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        self._draft_repo.update_text(draft_id, draft_text)
        logger.info("Updated draft text for %s", draft_id)
        return {"status": "updated", "draft_id": draft_id}

    def request_more_info(self, draft_id: str, reason: str) -> dict[str, Any]:
        """Mark a draft and ticket as waiting on additional customer information."""
        logger.info("Request more info requested: draft_id=%s", draft_id)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Request more info failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        self._draft_repo.request_info(draft_id, reason)
        self._ticket_repo.update_status(draft.ticket_id, "pending_info")
        logger.info("Marked draft %s as needs_info", draft_id)
        return {"status": "needs_info", "draft_id": draft_id}

    def regenerate_draft(self, draft_id: str, reason: str | None = None) -> dict[str, Any]:
        """Create a fresh pending draft for the same ticket/customer context."""
        logger.info("Draft regeneration requested: draft_id=%s", draft_id)
        logger.debug("Draft regeneration reason: %r", reason)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Regenerate draft failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        ticket = self._ticket_repo.get_by_id(draft.ticket_id)
        if not ticket:
            logger.warning("Regenerate draft failed; ticket not found: %s", draft.ticket_id)
            raise ValueError(f"Ticket {draft.ticket_id} not found")

        customer = self._customer_repo.get_by_id(ticket.customer_id)
        if not customer:
            logger.warning("Regenerate draft failed; customer not found: %s", ticket.customer_id)
            raise ValueError(f"Customer {ticket.customer_id} not found")

        regenerated = self.generate_draft(
            ticket_id=ticket.id,
            customer_id=customer.id,
            regenerate=True,
        )
        record = self._draft_repo.get_by_id(regenerated["draft_id"])
        if record is None:
            raise ValueError("Regenerated draft could not be loaded after creation")

        updated_context = {
            **record.context_used,
            "regeneration": {
                "prior_draft_id": draft_id,
                "reason": reason,
            },
        }
        self._draft_repo.update_context(regenerated["draft_id"], updated_context)
        logger.info("Regenerated draft %s from %s", regenerated["draft_id"], draft_id)
        return {
            "status": "regenerated",
            "draft_id": regenerated["draft_id"],
        }

    def mark_pending(self, draft_id: str, reason: str | None = None) -> dict[str, Any]:
        """Move a draft back to pending for another review cycle."""
        logger.info("Mark pending requested: draft_id=%s", draft_id)
        logger.debug("Mark pending reason: %r", reason)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Mark pending failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")

        self._draft_repo.update_status(draft_id, "pending", reason)
        logger.info("Marked draft %s back to pending", draft_id)
        return {"status": "pending", "draft_id": draft_id}

    def get_draft_history(self, draft_id: str) -> list:
        """Return all drafts associated with the same ticket, newest first."""
        logger.info("Draft history requested: draft_id=%s", draft_id)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.warning("Draft history failed; draft not found: %s", draft_id)
            raise ValueError(f"Draft {draft_id} not found")
        history = self._draft_repo.list_by_ticket(draft.ticket_id)
        logger.info("Draft history returned %d revision(s)", len(history))
        return history


def get_draft_service(database: Database) -> DraftService:
    """Factory for DraftService."""
    return DraftService(database)
