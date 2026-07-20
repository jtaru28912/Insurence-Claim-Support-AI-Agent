"""
Streamlit dashboard for the Insurance Claims AI Agent.

Provides UI for:
1. dashboard stats
2. customer lookup / creation
3. claim intake and claim listing
4. draft generation, editing, approval, discard, request-for-info
5. knowledge-base ingestion/query
6. memory probing and context visualization
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import requests
import streamlit as st

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Insurance Claims Support AI",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def extract_risk_signal(context_used: dict | None) -> dict | None:
    """Pull the structured risk-tool output from a draft's context payload."""
    if not isinstance(context_used, dict):
        return None
    for tool_call in context_used.get("tool_calls", []):
        if tool_call.get("tool") == "analyze_claim_risk":
            output = tool_call.get("output")
            return output if isinstance(output, dict) else None
    return None


def call_api(method: str, endpoint: str, data: dict | None = None) -> dict | list | None:
    """Make an HTTP call to the FastAPI backend."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=15)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=30)
        else:
            st.error(f"Unknown HTTP method: {method}")
            return None

        if response.status_code in (200, 201):
            logger.info("API %s %s succeeded with status=%s", method, endpoint, response.status_code)
            return response.json()

        logger.warning("API %s %s failed with status=%s body=%s", method, endpoint, response.status_code, response.text)
        st.error(f"API Error {response.status_code}: {response.text}")
        return None
    except requests.RequestException as exc:
        logger.exception("API %s %s raised a connection error", method, endpoint)
        st.error(f"Connection error: {exc}")
        return None


def get_dashboard_stats() -> dict:
    """Fetch dashboard stats, with safe defaults when backend is unavailable."""
    result = call_api("GET", "/dashboard/stats")
    if isinstance(result, dict):
        return result
    return {
        "total_customers": 0,
        "total_claims": 0,
        "open_claims": 0,
        "drafts_pending": 0,
        "drafts_needing_info": 0,
    }


def load_customer_tickets(customer_id: str) -> list[dict]:
    """Load all tickets for a given customer."""
    result = call_api("GET", f"/tickets/customer/{customer_id}")
    if isinstance(result, dict):
        logger.info(
            "Loaded %d ticket(s) for customer_id=%s",
            len(result.get("tickets", [])),
            customer_id,
        )
        return result.get("tickets", [])
    return []


def load_ticket_drafts(ticket_id: str) -> list[dict]:
    """Load all drafts for a given ticket."""
    result = call_api("GET", f"/drafts/ticket/{ticket_id}")
    if isinstance(result, dict):
        logger.info(
            "Loaded %d draft(s) for ticket_id=%s",
            len(result.get("drafts", [])),
            ticket_id,
        )
        return result.get("drafts", [])
    return []


def load_customer_by_email(email: str) -> dict | None:
    """Load a customer by email, returning None when not found."""
    encoded_email = quote(email.strip(), safe="")
    result = call_api("GET", f"/customers/email/{encoded_email}")
    return result if isinstance(result, dict) else None


def load_customer_drafts(customer_email: str) -> tuple[dict | None, list[dict], list[dict]]:
    """Resolve a customer email into customer, tickets, and drafts."""
    customer = load_customer_by_email(customer_email)
    if not customer:
        return None, [], []

    tickets = load_customer_tickets(customer["id"])
    drafts: list[dict] = []
    for ticket in tickets:
        ticket_drafts = load_ticket_drafts(ticket["id"])
        for draft in ticket_drafts:
            drafts.append(
                {
                    **draft,
                    "ticket_subject": ticket["subject"],
                    "ticket_status": ticket["status"],
                }
            )
    return customer, tickets, drafts


def render_identifier_panel(
    *,
    customer: dict | None = None,
    ticket: dict | None = None,
    draft: dict | None = None,
) -> None:
    """Render the currently relevant IDs so operators can reuse them quickly."""
    identifiers: list[tuple[str, str]] = []
    if customer and customer.get("id"):
        identifiers.append(("Customer ID", customer["id"]))
    if ticket and ticket.get("id"):
        identifiers.append(("Claim / Ticket ID", ticket["id"]))
    if draft and draft.get("id"):
        identifiers.append(("Draft ID", draft["id"]))

    if not identifiers:
        return

    columns = st.columns(len(identifiers))
    for column, (label, value) in zip(columns, identifiers, strict=False):
        column.caption(label)
        column.code(value)


def find_by_id(items: list[dict], item_id: str | None) -> dict | None:
    """Return the item matching item_id, or None when session state is stale."""
    if not item_id:
        return None
    return next((item for item in items if item.get("id") == item_id), None)


def clear_claim_intake_selection() -> None:
    """Clear Claim Intake page-specific selection state without removing saved customer data."""
    st.session_state.claim_intake_customer = None
    st.session_state.claim_selected_ticket_id = ""
    st.session_state.selected_ticket = None
    st.session_state.selected_draft = None


def apply_customer_ticket_selection(customer: dict, tickets: list[dict]) -> None:
    """Persist customer/ticket selection into shared session state."""
    st.session_state.selected_customer = customer
    st.session_state.selected_ticket = tickets[0] if tickets else None
    st.session_state.claim_intake_customer = customer
    if tickets:
        st.session_state.generate_selected_ticket_id = tickets[0]["id"]


if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = None
if "selected_ticket" not in st.session_state:
    st.session_state.selected_ticket = None
if "selected_draft" not in st.session_state:
    st.session_state.selected_draft = None
if "claim_intake_customer" not in st.session_state:
    st.session_state.claim_intake_customer = None
if "claim_selected_ticket_id" not in st.session_state:
    st.session_state.claim_selected_ticket_id = ""
if "generate_selected_ticket_id" not in st.session_state:
    st.session_state.generate_selected_ticket_id = ""
if "generate_customer_email" not in st.session_state:
    st.session_state.generate_customer_email = ""
if "known_draft_selection" not in st.session_state:
    st.session_state.known_draft_selection = ""


with st.sidebar:
    st.title("Insurance Claims AI")
    st.markdown("---")

    nav_selection = st.radio(
        "Navigation",
        [
            "Home",
            "Customer Lookup",
            "Claim Intake",
            "Draft Management",
            "Knowledge & Memory",
            "About",
        ],
    )
    st.session_state.current_page = nav_selection

    st.markdown("---")
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health_check.status_code == 200:
            st.success("Backend connected")
        else:
            st.error("Backend offline")
    except requests.RequestException:
        st.error("Backend offline")


if st.session_state.current_page == "Home":
    st.title("Insurance Claims Support AI")
    stats = get_dashboard_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Customers", stats["total_customers"])
    col2.metric("Claims", stats["total_claims"])
    col3.metric("Open Claims", stats["open_claims"])
    col4.metric("Drafts Pending", stats["drafts_pending"])
    col5.metric("Need Info", stats["drafts_needing_info"])

    tickets_result = call_api("GET", "/tickets")
    recent_tickets = tickets_result.get("tickets", [])[:5] if isinstance(tickets_result, dict) else []

    st.markdown("### Recent Claims")
    if recent_tickets:
        for ticket in recent_tickets:
            st.write(
                f"- {ticket['subject']} | status: {ticket['status']} | "
                f"type: {ticket.get('claim_type') or 'unspecified'}"
            )
    else:
        st.info("No claims available yet.")


elif st.session_state.current_page == "Customer Lookup":
    st.title("Customer Management")

    tab1, tab2 = st.tabs(["Search Customers", "Create Customer"])

    with tab1:
        st.subheader("Search Existing Customers")
        search_email = st.text_input("Search by Email", placeholder="customer@example.com")
        if search_email:
            encoded_email = quote(search_email, safe="")
            result = call_api("GET", f"/customers/email/{encoded_email}")
            if result:
                st.success("Customer found")
                st.session_state.selected_customer = result
                st.session_state.claim_intake_customer = result
                st.json(result)

                tickets = load_customer_tickets(result["id"])
                st.markdown("### Claim History")
                if tickets:
                    for ticket in tickets:
                        st.write(f"- {ticket['subject']} | {ticket['status']} | {ticket['created_at']}")
                    ticket_ids = [ticket["id"] for ticket in tickets]
                    if st.session_state.get("customer_lookup_selected_ticket_id") not in ["", *ticket_ids]:
                        st.session_state.customer_lookup_selected_ticket_id = ""
                    selected_customer_ticket_id = st.selectbox(
                        "Quick Select Claim For Next Steps",
                        options=[""] + ticket_ids,
                        key="customer_lookup_selected_ticket_id",
                        format_func=lambda ticket_id: next(
                            (
                                f"{ticket['subject']} ({ticket['status']}) - {ticket['id']}"
                                for ticket in tickets
                                if ticket["id"] == ticket_id
                            ),
                            "Choose a claim",
                        ),
                    )
                    if selected_customer_ticket_id:
                        selected_ticket = find_by_id(tickets, selected_customer_ticket_id)
                        if not selected_ticket:
                            st.warning("Selected claim is no longer available. Please choose another claim.")
                            st.stop()
                        st.session_state.selected_ticket = selected_ticket
                        st.session_state.generate_selected_ticket_id = selected_ticket["id"]
                        related_drafts = load_ticket_drafts(selected_ticket["id"])
                        st.session_state.selected_draft = related_drafts[0] if related_drafts else None
                        st.success("Claim selected for Claim Intake and Draft Management.")
                        render_identifier_panel(
                            customer=result,
                            ticket=selected_ticket,
                            draft=st.session_state.selected_draft,
                        )
                        if st.button("Go To Draft Management", key="goto_draft_management", use_container_width=True):
                            st.session_state.current_page = "Draft Management"
                            st.rerun()
                        if st.button("Go To Claim Intake", key="goto_claim_intake", use_container_width=True):
                            st.session_state.current_page = "Claim Intake"
                            st.rerun()
                else:
                    st.info("No claims found for this customer yet.")
        else:
            st.info("Enter an email address to search for a customer.")

    with tab2:
        st.subheader("Create New Customer")
        with st.form("create_customer_form"):
            name = st.text_input("Full Name", placeholder="John Doe")
            email = st.text_input("Email", placeholder="john@example.com")
            company_name = st.text_input("Company Name", placeholder="Acme Insurance Co")
            phone = st.text_input("Phone", placeholder="555-1234")
            address = st.text_area("Address", placeholder="123 Main St, City, State ZIP")

            if st.form_submit_button("Create Customer", use_container_width=True):
                if not name or not email or not company_name:
                    st.error("Name, Email, and Company Name are required")
                else:
                    result = call_api(
                        "POST",
                        "/customers",
                        {
                            "name": name,
                            "email": email,
                            "company_name": company_name,
                            "phone": phone,
                            "address": address,
                        },
                    )
                    if result:
                        st.success(f"Customer created: {result['id']}")
                        st.session_state.selected_customer = result
                        st.json(result)


elif st.session_state.current_page == "Claim Intake":
    st.title("New Claim Intake")
    st.subheader("Step 1: Select Customer")
    customer_email = st.text_input("Customer Email", key="claim_intake_email")

    if st.session_state.selected_customer:
        last_customer = st.session_state.selected_customer
        st.caption(
            "Previously selected customer available: "
            f"{last_customer['name']} ({last_customer['email']})."
        )
        if st.button("Use Previously Selected Customer", use_container_width=True):
            st.session_state.claim_intake_customer = last_customer
            st.success(f"Claim intake customer set to {last_customer['name']}")

    if st.button("Look up Customer", use_container_width=True):
        if not customer_email.strip():
            clear_claim_intake_selection()
            st.error("Enter a customer email first.")
        else:
            encoded_email = quote(customer_email.strip(), safe="")
            result = call_api("GET", f"/customers/email/{encoded_email}")
            if result:
                st.session_state.claim_intake_customer = result
                st.session_state.selected_customer = result
                st.session_state.selected_ticket = None
                st.session_state.selected_draft = None
                st.session_state.claim_selected_ticket_id = ""
                logger.info("Claim intake customer selected: customer_id=%s", result["id"])
                st.success(f"Customer ready: {result['name']}")
            else:
                clear_claim_intake_selection()
                st.error("Customer not found")

    selected_customer = st.session_state.claim_intake_customer
    if selected_customer:
        render_identifier_panel(customer=selected_customer)
        st.json(selected_customer)
        existing_tickets = load_customer_tickets(selected_customer["id"])
        st.markdown("### Existing Claims")
        if existing_tickets:
            existing_ticket_ids = [ticket["id"] for ticket in existing_tickets]
            if st.session_state.claim_selected_ticket_id not in ["", *existing_ticket_ids]:
                st.session_state.claim_selected_ticket_id = ""
            selected_ticket_id = st.selectbox(
                "Select an existing claim",
                options=[""] + existing_ticket_ids,
                key="claim_selected_ticket_id",
                format_func=lambda ticket_id: next(
                    (
                        f"{ticket['subject']} ({ticket['status']}) - {ticket['id']}"
                        for ticket in existing_tickets
                        if ticket["id"] == ticket_id
                    ),
                    "Create a new claim",
                ),
            )
            if selected_ticket_id:
                ticket_detail = call_api("GET", f"/tickets/{selected_ticket_id}")
                if ticket_detail:
                    st.session_state.selected_ticket = ticket_detail
                    ticket_drafts = load_ticket_drafts(selected_ticket_id)
                    st.session_state.selected_draft = ticket_drafts[0] if ticket_drafts else None
                    logger.info(
                        "Existing claim selected in intake: ticket_id=%s draft_count=%d",
                        selected_ticket_id,
                        len(ticket_drafts),
                    )
                    st.markdown("### Selected Claim Details")
                    render_identifier_panel(
                        customer=selected_customer,
                        ticket=ticket_detail,
                        draft=st.session_state.selected_draft,
                    )
                    st.write(f"**Subject:** {ticket_detail['subject']}")
                    st.write(f"**Status:** {ticket_detail['status']}")
                    st.write(f"**Claim Type:** {ticket_detail.get('claim_type') or 'Not set'}")
                    st.write("**Narrative:**")
                    st.write(ticket_detail["claim_narrative"])
                    if ticket_drafts:
                        st.success(
                            f"Latest draft found for this claim: {ticket_drafts[0]['id']} "
                            f"({ticket_drafts[0]['status']})"
                        )
                        st.caption(
                            "Open Draft Management to edit, approve, regenerate, or review "
                            "the listed draft IDs."
                        )
                        st.json(
                            {
                                "available_drafts": [
                                    {
                                        "id": draft["id"],
                                        "status": draft["status"],
                                        "updated_at": draft["updated_at"],
                                    }
                                    for draft in ticket_drafts
                                ]
                            }
                        )
                    else:
                        st.info("No draft exists for this claim yet. Generate one from Draft Management.")
            else:
                st.session_state.selected_ticket = None
                st.session_state.selected_draft = None
        else:
            st.info("No existing claims for this customer.")

        st.markdown("---")
        st.subheader("Step 2: Create New Claim")
        with st.form("claim_intake_form"):
            subject = st.text_input("Claim Subject", placeholder="Auto collision at intersection")
            claim_type = st.selectbox(
                "Claim Type",
                ["Auto Collision", "Auto Comprehensive", "Home Theft", "Home Water Damage", "Other"],
            )
            narrative = st.text_area(
                "Incident Narrative",
                placeholder="Describe what happened, when, where, and any injuries/damages...",
                height=180,
            )

            if st.form_submit_button("Create Ticket", use_container_width=True):
                if not subject or not narrative:
                    st.error("Subject and Narrative are required")
                else:
                    result = call_api(
                        "POST",
                        "/tickets",
                        {
                            "customer_id": selected_customer["id"],
                            "subject": subject,
                            "claim_type": claim_type,
                            "claim_narrative": narrative,
                        },
                    )
                    if result:
                        st.success(f"Ticket created: {result['id']}")
                        st.session_state.selected_ticket = result
                        st.session_state.selected_draft = None
                        st.session_state.claim_selected_ticket_id = ""
                        logger.info("New claim created from intake: ticket_id=%s", result["id"])
                        render_identifier_panel(customer=selected_customer, ticket=result)
                        st.json(result)
    else:
        st.info("Look up a customer first. Blank email will not auto-load an old customer anymore.")


elif st.session_state.current_page == "Draft Management":
    st.title("Draft Generation and Review")

    tab1, tab2 = st.tabs(["Generate Draft", "Review Draft"])

    with tab1:
        st.subheader("Generate AI Draft Response")
        st.caption(
            "Use a customer email to select the customer and claim. "
            "Typing UUIDs manually is optional."
        )

        generate_customer_email = st.text_input(
            "Customer Email",
            key="generate_customer_email",
            placeholder="customer@example.com",
        )
        if st.button("Find Customer Claims", use_container_width=True):
            if not generate_customer_email.strip():
                st.error("Customer email is required.")
            else:
                customer, tickets, drafts = load_customer_drafts(generate_customer_email)
                if customer:
                    apply_customer_ticket_selection(customer, tickets)
                    st.session_state.selected_draft = drafts[0] if drafts else None
                    logger.info(
                        "Generate-draft customer lookup resolved: email=%s ticket_count=%d draft_count=%d",
                        generate_customer_email,
                        len(tickets),
                        len(drafts),
                    )
                    st.success(f"Customer found: {customer['name']}")
                else:
                    st.error("No customer was found for this email.")

        available_generate_tickets = (
            load_customer_tickets(st.session_state.selected_customer["id"])
            if st.session_state.selected_customer
            else []
        )
        if st.session_state.selected_customer:
            st.caption(
                "Selected customer email: "
                f"{st.session_state.selected_customer['email']}"
            )
        if available_generate_tickets:
            generate_ticket_ids = [ticket["id"] for ticket in available_generate_tickets]
            if st.session_state.generate_selected_ticket_id not in generate_ticket_ids:
                st.session_state.generate_selected_ticket_id = generate_ticket_ids[0]
            selected_generate_ticket_id = st.selectbox(
                "Select Claim / Ticket",
                options=generate_ticket_ids,
                key="generate_selected_ticket_id",
                format_func=lambda ticket_id: next(
                    (
                        f"{ticket['subject']} ({ticket['status']}) - {ticket['id']}"
                        for ticket in available_generate_tickets
                        if ticket["id"] == ticket_id
                    ),
                    ticket_id,
                ),
            )
            selected_generate_ticket = find_by_id(available_generate_tickets, selected_generate_ticket_id)
            if not selected_generate_ticket:
                st.warning("Selected claim is no longer available. Please choose another claim.")
                st.stop()
            st.session_state.selected_ticket = selected_generate_ticket
            available_selected_ticket_drafts = load_ticket_drafts(selected_generate_ticket["id"])
            st.session_state.selected_draft = (
                available_selected_ticket_drafts[0] if available_selected_ticket_drafts else None
            )
            render_identifier_panel(
                customer=st.session_state.selected_customer,
                ticket=selected_generate_ticket,
                draft=st.session_state.selected_draft,
            )
            st.write(f"**Selected Claim:** {selected_generate_ticket['subject']}")
            st.write(f"**Claim Status:** {selected_generate_ticket['status']}")
            st.write(f"**Claim Type:** {selected_generate_ticket.get('claim_type') or 'Not set'}")
            if available_selected_ticket_drafts:
                st.write(f"**Draft Status:** {available_selected_ticket_drafts[0]['status']}")
                st.caption(
                    f"Existing draft available for this claim: {available_selected_ticket_drafts[0]['id']}"
                )
        else:
            selected_generate_ticket = st.session_state.selected_ticket
            if st.session_state.selected_customer:
                render_identifier_panel(customer=st.session_state.selected_customer)
                st.info("No claims found for this customer yet.")

        with st.expander("Manual IDs (advanced / fallback)"):
            col1, col2 = st.columns(2)
            with col1:
                ticket_id = st.text_input(
                    "Ticket ID",
                    value=selected_generate_ticket["id"] if selected_generate_ticket else "",
                )
            with col2:
                customer_id = st.text_input(
                    "Customer ID",
                    value=st.session_state.selected_customer["id"] if st.session_state.selected_customer else "",
                )

        ticket_id = selected_generate_ticket["id"] if selected_generate_ticket else ticket_id
        customer_id = (
            st.session_state.selected_customer["id"] if st.session_state.selected_customer else customer_id
        )

        regenerate = st.checkbox("Regenerate even if a draft already exists", value=False)

        if st.button("Generate Draft", use_container_width=True):
            if not ticket_id or not customer_id:
                st.error("Select a customer and claim by email, or enter the manual IDs.")
            else:
                with st.spinner("Generating AI draft..."):
                    result = call_api(
                        "POST",
                        "/drafts",
                        {
                            "ticket_id": ticket_id,
                            "customer_id": customer_id,
                            "regenerate": regenerate,
                        },
                    )
                    if result:
                        st.session_state.selected_draft = result
                        logger.info("Draft generated/loaded: draft_id=%s", result["id"])
                        st.success(f"Draft ready: {result['id']}")
                        render_identifier_panel(
                            customer=st.session_state.selected_customer,
                            ticket=st.session_state.selected_ticket,
                            draft=result,
                        )
                        st.json({"status": result["status"], "is_new": result.get("is_new"), "id": result["id"]})

    with tab2:
        st.subheader("Review, Edit, Approve, or Request More Info")
        st.caption(
            "You can use either a `Draft ID` or a customer email here. "
            "If you enter an email, the app will find the available drafts for that customer."
        )

        draft_lookup_value = st.text_input(
            "Draft ID or Customer Email",
            value=st.session_state.selected_draft["id"] if st.session_state.selected_draft else "",
            placeholder="draft UUID or customer@example.com",
        )

        if draft_lookup_value and st.button("Load Draft / Find By Email"):
            lookup_value = draft_lookup_value.strip()
            if "@" in lookup_value:
                customer, tickets, drafts = load_customer_drafts(lookup_value)
                if customer:
                    st.session_state.selected_customer = customer
                    st.session_state.selected_ticket = tickets[0] if tickets else None
                    st.session_state.selected_draft = drafts[0] if drafts else None
                    logger.info(
                        "Draft lookup by email resolved: email=%s ticket_count=%d draft_count=%d",
                        lookup_value,
                        len(tickets),
                        len(drafts),
                    )
                    st.success(f"Customer found: {customer['name']}")
                    render_identifier_panel(
                        customer=customer,
                        ticket=st.session_state.selected_ticket,
                        draft=st.session_state.selected_draft,
                    )
                    if drafts:
                        st.info(
                            f"Latest draft for {lookup_value}: {drafts[0]['id']} "
                            f"for claim '{drafts[0]['ticket_subject']}'"
                        )
                        st.json(
                            {
                                "available_drafts": [
                                    {
                                        "id": draft["id"],
                                        "status": draft["status"],
                                        "ticket_subject": draft["ticket_subject"],
                                        "updated_at": draft["updated_at"],
                                    }
                                    for draft in drafts
                                ]
                            }
                        )
                    elif tickets:
                        st.warning("Customer found with claims, but no draft has been generated yet.")
                    else:
                        st.warning("Customer found, but no claim has been created yet.")
            else:
                result = call_api("GET", f"/drafts/{lookup_value}")
                if result:
                    st.session_state.selected_draft = result
                    logger.info("Draft loaded manually: draft_id=%s", lookup_value)
                    st.success("Draft loaded")

        if st.session_state.selected_ticket:
            available_drafts = load_ticket_drafts(st.session_state.selected_ticket["id"])
            if available_drafts:
                draft_ids = [draft["id"] for draft in available_drafts]
                if st.session_state.known_draft_selection not in ["", *draft_ids]:
                    st.session_state.known_draft_selection = ""
                selected_known_draft_id = st.selectbox(
                    "Known Draft IDs for Selected Claim",
                    options=[""] + draft_ids,
                    format_func=lambda draft_id: next(
                        (
                            f"{draft['id']} ({draft['status']}, updated {draft['updated_at']})"
                            for draft in available_drafts
                            if draft["id"] == draft_id
                        ),
                        "Choose a draft to load",
                    ),
                    key="known_draft_selection",
                )
                if selected_known_draft_id:
                    matching_draft = find_by_id(available_drafts, selected_known_draft_id)
                    if not matching_draft:
                        st.warning("Selected draft is no longer available. Please choose another draft.")
                        st.stop()
                    st.session_state.selected_draft = matching_draft
                    logger.info("Draft pre-selected from known list: draft_id=%s", selected_known_draft_id)
                    st.info(f"Selected draft from current claim: {selected_known_draft_id}")

        if st.session_state.selected_draft:
            draft = st.session_state.selected_draft
            render_identifier_panel(
                customer=st.session_state.selected_customer,
                ticket=st.session_state.selected_ticket,
                draft=draft,
            )
            st.caption(
                "No separate user-management table is implemented in this project. "
                "For approval, enter your adjuster email or internal user ID below."
            )
            risk_summary = extract_risk_signal(draft.get("context_used"))

            if risk_summary:
                risk_level = (risk_summary.get("risk_level") or "").lower()
                if risk_level == "high":
                    st.error(
                        "High-risk claim signal detected. Review fraud indicators carefully before approval."
                    )
                elif risk_level == "medium":
                    st.warning(
                        "Medium-risk claim signal detected. Verify chronology and supporting documents."
                    )
                if risk_summary.get("fraud_signals"):
                    st.caption("Fraud-risk signals: " + "; ".join(risk_summary["fraud_signals"]))

            edited_text = st.text_area(
                "Draft Text",
                value=draft["draft_text"],
                height=250,
            )

            if st.button("Save Draft Edits", use_container_width=True):
                updated = call_api("PATCH", f"/drafts/{draft['id']}", {"draft_text": edited_text})
                if updated:
                    st.session_state.selected_draft = updated
                    draft = updated
                    st.success("Draft edits saved")

            st.markdown("### Context Used")
            if draft.get("context_used"):
                st.json(draft["context_used"])
            else:
                st.info("No context captured for this draft.")

            if st.button("Show Draft History", use_container_width=True):
                history = call_api("GET", f"/drafts/{draft['id']}/history")
                if history:
                    st.json(history)

            col1, col2, col3 = st.columns(3)

            with col1:
                approved_by = st.text_input(
                    "Approver User ID / Email",
                    placeholder="adjuster@company.com or ADJ-001",
                )
                adjuster_notes = st.text_area("Approval Notes", placeholder="Optional notes")
                if st.button("Approve Draft", type="primary", use_container_width=True):
                    if not approved_by:
                        st.error("Approved By is required")
                    else:
                        result = call_api(
                            "PUT",
                            f"/drafts/{draft['id']}/approve",
                            {"approved_by": approved_by, "adjuster_notes": adjuster_notes},
                        )
                        if result:
                            st.session_state.selected_draft = result
                            st.success("Draft approved and written to memory")

            with col2:
                regenerate_reason = st.text_area(
                    "Regenerate Reason",
                    placeholder="Why should the AI generate a fresh revision?",
                    key="regenerate_reason",
                )
                if st.button("Regenerate Draft", use_container_width=True):
                    result = call_api(
                        "POST",
                        f"/drafts/{draft['id']}/regenerate",
                        {"reason": regenerate_reason},
                    )
                    if result:
                        st.session_state.selected_draft = result
                        st.success("New draft revision generated")

                request_info_reason = st.text_area(
                    "Request-For-Info Reason",
                    placeholder="What information do you still need from the customer?",
                    key="request_info_reason",
                )
                if st.button("Request More Info", use_container_width=True):
                    if not request_info_reason:
                        st.error("A reason is required")
                    else:
                        result = call_api(
                            "PUT",
                            f"/drafts/{draft['id']}/request-info",
                            {"reason": request_info_reason},
                        )
                        if result:
                            st.session_state.selected_draft = result
                            st.success("Draft marked as needing more information")

            with col3:
                pending_reason = st.text_area(
                    "Return To Pending",
                    placeholder="Why should this draft move back to pending review?",
                    key="pending_reason",
                )
                if st.button("Mark Pending", use_container_width=True):
                    result = call_api(
                        "PUT",
                        f"/drafts/{draft['id']}/mark-pending",
                        {"reason": pending_reason},
                    )
                    if result:
                        st.session_state.selected_draft = result
                        st.success("Draft returned to pending")

                discard_reason = st.text_area(
                    "Discard Reason",
                    placeholder="Why is this draft being discarded?",
                    key="discard_reason",
                )
                if st.button("Discard Draft", use_container_width=True):
                    if not discard_reason:
                        st.error("A discard reason is required")
                    else:
                        result = call_api(
                            "PUT",
                            f"/drafts/{draft['id']}/discard",
                            {"reason": discard_reason},
                        )
                        if result:
                            st.session_state.selected_draft = result
                            st.success("Draft discarded")


elif st.session_state.current_page == "Knowledge & Memory":
    st.title("Knowledge Base and Memory Tools")

    tab1, tab2 = st.tabs(["Knowledge Base", "Memory Probe"])

    with tab1:
        st.subheader("Knowledge Base Status")
        stats = call_api("GET", "/knowledge/stats")
        if stats:
            st.json(stats)

        if st.button("Ingest / Refresh Knowledge Base", use_container_width=True):
            with st.spinner("Refreshing knowledge base..."):
                result = call_api("POST", "/knowledge/ingest", {})
                if result:
                    st.success("Knowledge base ingestion completed")
                    st.json(result)

        knowledge_query = st.text_input("Search Knowledge Base", placeholder="deductible guidelines")
        top_k = st.slider("Top K Results", min_value=1, max_value=10, value=4)
        if st.button("Query Knowledge Base", use_container_width=True):
            if not knowledge_query:
                st.error("Enter a search query first")
            else:
                result = call_api("POST", "/knowledge/query", {"query": knowledge_query, "top_k": top_k})
                if result:
                    st.json(result)

    with tab2:
        st.subheader("Probe Claim History Memory")
        memory_status = call_api("GET", "/memory/status")
        if isinstance(memory_status, dict):
            st.json(memory_status)
        default_email = (
            st.session_state.selected_customer["email"]
            if st.session_state.selected_customer
            else ""
        )
        default_company = (
            st.session_state.selected_customer["company_name"]
            if st.session_state.selected_customer
            else ""
        )
        memory_email = st.text_input("Customer Email", value=default_email)
        memory_company = st.text_input("Company Name", value=default_company)
        memory_query = st.text_area(
            "Memory Query",
            placeholder="Search for prior approved resolutions related to rear-end collisions.",
            height=120,
        )
        memory_limit = st.slider("Memory Results", min_value=1, max_value=10, value=5)

        if st.button("Probe Memory", use_container_width=True):
            if not memory_email or not memory_company or not memory_query:
                st.error("Customer email, company name, and query are required")
            else:
                encoded_email = quote(memory_email, safe="")
                encoded_company = quote(memory_company, safe="")
                encoded_query = quote(memory_query, safe="")
                result = call_api(
                    "GET",
                    f"/memory/probe?customer_email={encoded_email}&company_name={encoded_company}"
                    f"&query={encoded_query}&limit={memory_limit}",
                )
                if result:
                    st.json(result)


elif st.session_state.current_page == "About":
    st.title("About This Application")
    st.markdown(
        """
        This application combines:

        - FastAPI for backend workflows
        - SQLite for claims data
        - Streamlit for human-in-the-loop operations
        - ChromaDB for knowledge retrieval
        - LangMem for long-term memory

        Human review remains mandatory for final decisions.
        """
    )
