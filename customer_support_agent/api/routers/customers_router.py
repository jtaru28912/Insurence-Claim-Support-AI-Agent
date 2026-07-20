"""FastAPI router for customer endpoints."""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from customer_support_agent.data.database import Database, get_database
from customer_support_agent.data.repositories.customer_repository import CustomerRepository
from customer_support_agent.schemas.shared import (
    CustomerCreateRequest,
    CustomerListResponse,
    CustomerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    request: CustomerCreateRequest,
    database: Database = Depends(get_database),
) -> CustomerResponse:
    """Create a new customer."""
    logger.info("Create customer requested for email=%s", request.email)
    logger.debug("Create customer payload: %s", request.model_dump())
    repo = CustomerRepository(database)
    try:
        record = repo.create(
            email=request.email,
            name=request.name,
            phone=request.phone,
            address=request.address,
            company_name=request.company_name,
            plan_tier=request.plan_tier,
            sla_hours=request.sla_hours,
            policy_number=request.policy_number,
        )
        response = CustomerResponse(
            id=record.id,
            email=record.email,
            name=record.name,
            phone=record.phone,
            address=record.address,
            company_name=record.company_name,
            plan_tier=record.plan_tier,
            sla_hours=record.sla_hours,
            policy_number=record.policy_number,
            updated_at=record.updated_at,
            created_at=record.created_at,
        )
        logger.info("Customer created successfully: id=%s email=%s", record.id, record.email)
        return response
    except sqlite3.IntegrityError as e:
        logger.warning("Customer create conflict for email=%s", request.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with this email already exists",
        ) from e
    except ValueError as e:
        logger.warning("Customer create validation failure for email=%s: %s", request.email, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    database: Database = Depends(get_database),
) -> CustomerResponse:
    """Get a customer by ID."""
    logger.info("Get customer requested: customer_id=%s", customer_id)
    repo = CustomerRepository(database)
    record = repo.get_by_id(customer_id)
    if not record:
        logger.warning("Customer not found: customer_id=%s", customer_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    response = CustomerResponse(
        id=record.id,
        email=record.email,
        name=record.name,
        phone=record.phone,
        address=record.address,
        company_name=record.company_name,
        plan_tier=record.plan_tier,
        sla_hours=record.sla_hours,
        policy_number=record.policy_number,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )
    logger.debug("Customer retrieved: %s", response.model_dump())
    return response


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    database: Database = Depends(get_database),
) -> CustomerListResponse:
    """List all customers."""
    logger.info("List customers requested")
    repo = CustomerRepository(database)
    records = repo.list_all()
    customers = [
        CustomerResponse(
            id=record.id,
            email=record.email,
            name=record.name,
            phone=record.phone,
            address=record.address,
            company_name=record.company_name,
            plan_tier=record.plan_tier,
            sla_hours=record.sla_hours,
            policy_number=record.policy_number,
            updated_at=record.updated_at,
            created_at=record.created_at,
        )
        for record in records
    ]
    response = CustomerListResponse(customers=customers, count=len(customers))
    logger.info("List customers completed with %d result(s)", response.count)
    return response


@router.get("/email/{email}", response_model=CustomerResponse)
async def get_customer_by_email(
    email: str,
    database: Database = Depends(get_database),
) -> CustomerResponse:
    """Get a customer by email."""
    logger.info("Get customer by email requested: email=%s", email)
    repo = CustomerRepository(database)
    record = repo.get_by_email(email)
    if not record:
        logger.warning("Customer not found for email=%s", email)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    response = CustomerResponse(
        id=record.id,
        email=record.email,
        name=record.name,
        phone=record.phone,
        address=record.address,
        company_name=record.company_name,
        plan_tier=record.plan_tier,
        sla_hours=record.sla_hours,
        policy_number=record.policy_number,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )
    logger.debug("Customer retrieved by email: %s", response.model_dump())
    return response
