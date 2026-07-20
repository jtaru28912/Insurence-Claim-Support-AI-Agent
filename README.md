# Insurance Claims Support AI Agent

An internal AI copilot for insurance claims adjusters and support agents handling FNOL and related claim-support workflows. The system retrieves prior memory, searches insurance guidance with RAG, uses structured support tools, and generates an editable draft recommendation that a human reviewer must approve before use.

The implementation follows the original project deck with one deliberate extension: the LLM and embedding layers are provider-agnostic. OpenAI is the default, while Groq and Gemini remain pluggable alternatives.

---

## Architecture Overview

Core flow:

1. retrieve customer/company memory from LangMem
2. retrieve policy/process guidance from ChromaDB
3. invoke structured support tools
4. generate an editable draft recommendation
5. require human review and approval
6. write approved resolutions back into memory

Main stack:

- FastAPI backend
- SQLite for customers, tickets, drafts
- Streamlit dashboard
- ChromaDB for knowledge retrieval
- LangMem + LangGraph `InMemoryStore` for memory
- OpenAI by default, with Groq/Gemini support retained

---

## Project Structure

```text
Insurance Claim Support AI Agent/
|-- app.py                              # Root Streamlit entrypoint
|-- customer_support_agent/
|   |-- api/
|   |   |-- app_factory.py
|   |   `-- routers/
|   |-- app.py                         # Streamlit dashboard implementation
|   |-- core/
|   |-- data/
|   |   |-- database.py
|   |   `-- repositories/
|   |-- integrations/
|   |   |-- embeddings/
|   |   |-- llm/
|   |   |-- memory/
|   |   |-- rag/
|   |   `-- tools/
|   |-- schemas/
|   |   `-- shared.py                  # Consolidated Pydantic models
|   |-- services/
|   `-- main.py
|-- knowledge_base/
|-- tests/
|-- requirements.txt
|-- requirements-dev.txt
`-- .env.example
```

---

## Build Roadmap

- [x] **Phase 1 - Setup & Environment Configuration**
  - project skeleton, settings, provider abstraction, FastAPI bootstrap, health endpoint
- [x] **Phase 2 - Memory, RAG, and Tool-Calling Flow**
  - Chroma knowledge retrieval, LangMem memory, support tools, copilot orchestration
- [x] **Phase 3 - Modular FastAPI Backend & Streamlit Dashboard**
  - SQLite database layer, repositories, customer/ticket/draft routers, supporting services, and the Streamlit dashboard are complete
- [x] **Phase 4 - Testing, Dockerization, CI/CD, EC2 Deployment**
  - added Phase 4 tests, Docker packaging, Docker Compose, CI workflow, deploy workflow, and EC2 deployment docs with rollback guidance

---

## Current Status Notes

- The customer, ticket, draft, dashboard, knowledge, and memory flows are implemented.
- Bonus assignments 1-3 are implemented: claim risk analysis, memory backend status visibility, and draft revision/history workflows.
- `Dockerfile` and `docker-compose.yml` support running the FastAPI backend and Streamlit dashboard together.
- GitHub Actions now runs Ruff and pytest in CI, and a manual EC2 deploy workflow is included with health-check verification and rollback support.
- Human approval in this project means the adjuster approved the AI-generated draft recommendation. It does not automatically settle, deny, or close the underlying insurance claim.
- Claim/ticket status and draft status are separate. A draft can be `approved` while its claim/ticket remains `open`.
- Customer policy data uses `plan_tier` and `policy_number`; there is no required `policy_name` field in the current backend schema.
- The memory layer uses LangGraph `InMemoryStore`, so approved-resolution memories are available during the running backend process. Restarting the backend clears memory entries unless a persistent memory backend is added later.

## Bonus Features

- `analyze_claim_risk` adds deterministic fraud-risk screening with `risk_level`, `confidence`, `fraud_signals`, `summary`, and `recommended_action`.
- `/memory/status` exposes the active memory backend, semantic-search status, embedding provider/model, and configured top-k value.
- Draft workflows now support regeneration, returning a draft to pending, and draft-history lookup for the same ticket.

---

## Getting Started

### Prerequisites

- Python 3.11+
- A valid provider API key
  - default: `OPENAI_API_KEY`

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
```

Update `.env` with the provider credentials you want to use.

### Run the API

```bash
python -m customer_support_agent.main
```

Health check:

```bash

curl http://localhost:8000/health
```

### Test The Backend In Swagger

After the API is running, open:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- ReDoc: `http://localhost:8000/redoc`

Swagger includes sample JSON bodies for the main workflow:

1. `POST /customers` - create a customer and copy the returned `id`.
2. `POST /tickets` - create a claim ticket using that customer ID and copy the returned `id`.
3. `POST /drafts` - generate an AI draft using the customer ID and ticket ID.
4. `PUT /drafts/{draft_id}/approve` - approve the draft recommendation and write it to memory.
5. `GET /memory/probe` - search approved-resolution memory while the backend is still running.

### Backend Endpoint Reference

- `GET /health` - backend health check.
- `POST /customers` - create a customer.
- `GET /customers` - list customers.
- `GET /customers/{customer_id}` - get customer by ID.
- `GET /customers/email/{email}` - get customer by email.
- `POST /tickets` - create a claim ticket.
- `GET /tickets` - list tickets.
- `GET /tickets/{ticket_id}` - get ticket by ID.
- `GET /tickets/customer/{customer_id}` - list tickets for one customer.
- `PATCH /tickets/{ticket_id}` - update claim/ticket status.
- `POST /drafts` - generate an AI draft.
- `GET /drafts/{draft_id}` - get draft details.
- `GET /drafts/ticket/{ticket_id}` - list drafts for one ticket.
- `GET /drafts/{draft_id}/history` - list draft revisions.
- `PATCH /drafts/{draft_id}` - save edited draft text.
- `PUT /drafts/{draft_id}/approve` - approve draft and write resolution to memory.
- `PUT /drafts/{draft_id}/discard` - discard draft.
- `PUT /drafts/{draft_id}/request-info` - mark draft as needing more customer information.
- `PUT /drafts/{draft_id}/mark-pending` - return draft to pending review.
- `POST /drafts/{draft_id}/regenerate` - generate a fresh draft revision.
- `GET /knowledge/stats` - view knowledge-base stats.
- `POST /knowledge/ingest` - refresh knowledge-base ingestion.
- `POST /knowledge/query` - search insurance knowledge base.
- `GET /memory/status` - view memory backend status.
- `GET /memory/probe` - search approved-resolution memory.
- `GET /dashboard/stats` - dashboard metrics.
- `GET /logging/level` - view runtime log level.
- `PUT /logging/level` - update runtime log level.

### Run the Streamlit Dashboard

```bash
streamlit run app.py
```

### Run With Docker Compose

```bash
docker compose up --build
```

Then open:

- FastAPI: `http://localhost:8000/health`
- Streamlit: `http://localhost:8501`

Docker Compose overrides local Windows paths from `.env` with container paths:

- `KNOWLEDGE_BASE_PATH=/app/knowledge_base`
- `SQLITE_DB_PATH=/app/storage/db/app.db`
- `VECTOR_STORE_PATH=/app/storage/vector_store`

This keeps knowledge-base ingestion working inside Docker while still allowing local `.env` paths for non-Docker runs.

---

## Configuration

Important `.env` settings:

- `APP_ENV`
- `API_HOST`
- `API_PORT`
- `LLM_PROVIDER`
- `EMBEDDING_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `GROQ_API_KEY`
- `GROQ_CHAT_MODEL`
- `GOOGLE_API_KEY`
- `GEMINI_CHAT_MODEL`
- `GEMINI_EMBEDDING_MODEL`
- `RAG_CHUNK_SIZE`
- `RAG_CHUNK_OVERLAP`
- `RAG_TOP_K`
- `CHROMA_COLLECTION_NAME`
- `MEMORY_TOP_K`

All settings are loaded through `customer_support_agent/core/settings.py`.

---

## Knowledge Base

The insurance files currently used for this project are:

- `insurance-auto-claims-fnol-intake-checklist.md`
- `insurance-auto-coverage-and-deductible-guidelines.md`
- `insurance-auto-required-documents-by-claim-type.md`
- `insurance-claims-fraud-risk-indicators.md`
- `insurance-claims-settlement-sla-and-communication.md`

Only files matching `knowledge_base/insurance-*.md` are indexed when those files exist. The backend rebuilds the Chroma collection on startup and on manual refresh so out-of-scope content such as project documentation or banking markdown files does not appear in knowledge-base query results.

There are also banking markdown files in `knowledge_base/`, but they are out of scope for this insurance project unless explicitly requested.

To test the knowledge base quickly, run queries like:

- `deductible guidelines`
- `FNOL checklist`
- `required documents for collision`
- `fraud risk indicators`
- `claim settlement SLA`

You should see sources from the five insurance markdown files above.

## IDs And Approval Inputs

- `Customer ID` is created automatically when you create a customer.
- `Claim / Ticket ID` is created automatically when you create a claim.
- `Draft ID` is created automatically when you generate a draft.
- The Streamlit dashboard now shows these IDs directly in Customer Lookup, Claim Intake, and Draft Management so they can be reused without digging through raw JSON.
- `approved_by` is not linked to a separate users table in this project. Enter the adjuster's email or internal user ID, for example `adjuster@company.com` or `ADJ-001`.
- To inspect another customer's drafts, open Draft Management, enter that customer's email, click **Find Customer Claims**, select a claim, then use **Review Draft** to load or approve the draft.
- To verify approval, check **Draft Status** in Draft Management. **Claim Status** is the ticket workflow status and may still show `open`.

---

## Verification

Verified on July 19, 2026 from the local `.venv`:

- `python -m compileall app.py customer_support_agent tests`
- `pytest tests -q`
- `ruff check .`
- `docker compose config`
