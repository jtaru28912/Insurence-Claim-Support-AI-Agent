"""Pydantic request/response schemas for customers, tickets, and drafts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ========================================================================
# Customer Schemas
# ========================================================================


class CustomerCreateRequest(BaseModel):
    """Request to create a new customer."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "john@gmail.com",
                    "name": "John Doe",
                    "phone": "555-1234",
                    "address": "123 Main St, Pune, MH",
                    "company_name": "XYZ Insurance",
                    "plan_tier": "Standard Auto",
                    "sla_hours": 48,
                    "policy_number": "POL-AUTO-88421",
                }
            ]
        }
    )

    email: str = Field(..., description="Customer email address")
    name: str = Field(..., description="Customer full name")
    phone: str | None = Field(default=None, description="Customer phone number")
    address: str | None = Field(default=None, description="Customer address")
    company_name: str = Field(..., description="Company/organization name")
    plan_tier: str = Field(default="Standard Auto", description="Insurance plan tier")
    sla_hours: int = Field(default=48, description="SLA response hours")
    policy_number: str | None = Field(default=None, description="Insurance policy number")


class CustomerResponse(BaseModel):
    """Response representing a customer."""

    id: str
    email: str
    name: str | None
    phone: str | None
    address: str | None
    company_name: str
    plan_tier: str
    sla_hours: int
    policy_number: str | None
    updated_at: str
    created_at: str


class CustomerListResponse(BaseModel):
    """Response for customer list endpoint."""

    customers: list[CustomerResponse]
    count: int


# ========================================================================
# Ticket Schemas
# ========================================================================


class TicketCreateRequest(BaseModel):
    """Request to create a new ticket (claim)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_id": "paste-customer-id-from-create-customer",
                    "subject": "Vehicle damage during heated riots",
                    "claim_narrative": (
                        "My vehicle was parked near the market when a heated riot broke out. "
                        "The windshield and left side doors were damaged. I have photos and a police report."
                    ),
                    "claim_type": "Auto Comprehensive",
                }
            ]
        }
    )

    customer_id: str = Field(..., description="ID of the customer filing the claim")
    subject: str = Field(..., description="Ticket subject line")
    claim_narrative: str = Field(..., description="Detailed claim narrative")
    claim_type: str | None = Field(
        default=None, description="Type of claim (e.g., auto_collision, comprehensive)"
    )


class TicketResponse(BaseModel):
    """Response representing a ticket (claim)."""

    id: str
    customer_id: str
    subject: str
    claim_narrative: str
    claim_type: str | None
    status: str
    created_at: str
    updated_at: str


class TicketListResponse(BaseModel):
    """Response for ticket list endpoint."""

    tickets: list[TicketResponse]
    count: int


class TicketUpdateRequest(BaseModel):
    """Request to update ticket status."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "closed",
                    "notes": "Claim ticket closed after adjuster completed final review.",
                },
                {
                    "status": "pending_info",
                    "notes": "Waiting for photos and police report from customer.",
                },
            ]
        }
    )

    status: str = Field(..., description="New ticket status (e.g., open, in_progress, closed)")
    notes: str | None = Field(default=None, description="Optional update notes")


# ========================================================================
# Draft Schemas
# ========================================================================


class DraftCreateRequest(BaseModel):
    """Request to generate an AI draft for a ticket."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ticket_id": "paste-ticket-id-from-create-ticket",
                    "customer_id": "paste-customer-id-from-create-customer",
                    "regenerate": False,
                }
            ]
        }
    )

    ticket_id: str = Field(..., description="ID of the ticket to draft for")
    customer_id: str = Field(..., description="ID of the customer")
    regenerate: bool = Field(
        default=False, description="If true, regenerate even if a draft exists"
    )


class DraftResponse(BaseModel):
    """Response representing an AI-generated draft."""

    id: str
    ticket_id: str
    customer_id: str | None = None
    draft_text: str
    context_used: dict[str, Any]
    status: str  # pending | approved | discarded | needs_info
    is_new: bool | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    adjuster_notes: str | None
    created_at: str
    updated_at: str


class DraftListResponse(BaseModel):
    """Response for draft list endpoint."""

    drafts: list[DraftResponse]
    count: int


class DraftApprovalRequest(BaseModel):
    """Request to approve a draft and write it to memory."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "approved_by": "adjuster@company.com",
                    "adjuster_notes": (
                        "Reviewed customer documents and police report. Approved the draft recommendation."
                    ),
                }
            ]
        }
    )

    approved_by: str = Field(..., description="Email/ID of approving adjuster")
    adjuster_notes: str | None = Field(default=None, description="Optional adjuster notes")


class DraftRegenerateRequest(BaseModel):
    """Request to regenerate a draft."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reason": "Need a clearer explanation of required documents and next steps.",
                }
            ]
        }
    )

    reason: str | None = Field(default=None, description="Reason for regeneration")


class DraftMarkPendingRequest(BaseModel):
    """Request to move a draft back to pending review."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reason": "Returning to pending after receiving updated customer documents.",
                }
            ]
        }
    )

    reason: str | None = Field(default=None, description="Optional reason for returning to pending")


class DraftUpdateRequest(BaseModel):
    """Request to save an edited draft body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "draft_text": (
                        "Dear customer, we reviewed your vehicle damage claim. "
                        "Please provide photos, repair estimate, and the police report so the adjuster can continue review."
                    )
                }
            ]
        }
    )

    draft_text: str = Field(..., min_length=1, description="Edited draft text")


class DraftDiscardRequest(BaseModel):
    """Request to discard a draft."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reason": "Draft does not match the latest claim facts and should not be used.",
                }
            ]
        }
    )

    reason: str = Field(..., description="Reason for discarding")


class DraftRequestInfoRequest(BaseModel):
    """Request to mark a draft as waiting on more customer information."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reason": "Need photos of the vehicle damage and a copy of the police report.",
                }
            ]
        }
    )

    reason: str = Field(..., description="Reason more information is required")


class KnowledgeQueryRequest(BaseModel):
    """Request to search the knowledge base."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "required documents for auto comprehensive claim",
                    "top_k": 4,
                },
                {
                    "query": "fraud indicators for vehicle damage claim",
                    "top_k": 5,
                },
            ]
        }
    )

    query: str = Field(..., min_length=1, description="Natural-language search query")
    top_k: int | None = Field(default=None, ge=1, le=20)


class MemoryProbeResponse(BaseModel):
    """Response returned by the memory probe endpoint."""

    customer_email: str
    company_name: str
    query: str
    semantic_search_used: bool
    hits_count: int
    hits: list[dict[str, Any]]
    error: str | None = None


class MemoryStatusResponse(BaseModel):
    """Health/debug information for the configured memory backend."""

    status: str
    backend: str
    semantic_search_enabled: bool
    embedding_provider: str
    embedding_model: str | None = None
    memory_top_k: int


class DashboardStatsResponse(BaseModel):
    """High-level metrics for the Streamlit home screen."""

    total_customers: int
    total_claims: int
    open_claims: int
    drafts_pending: int
    drafts_needing_info: int


class LoggingLevelUpdateRequest(BaseModel):
    """Request to change the runtime application log level."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "level": "DEBUG",
                }
            ]
        }
    )

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingLevelResponse(BaseModel):
    """Response describing the active runtime log level."""

    level: str
