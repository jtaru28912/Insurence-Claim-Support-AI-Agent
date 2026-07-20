"""
Copilot orchestration service — the heart of the draft-generation pipeline.

Design notes
------------
Depends only on abstractions injected at construction time (``LLMProvider``,
``ChromaKnowledgeBase``, ``LangMemStore``) — Dependency Inversion. This
class contains ALL business logic for draft generation; Phase 3's routers
and ``DraftService`` call into this class and must not duplicate any of
this orchestration.

Pipeline (per spec, slide 6): memory retrieval -> knowledge retrieval ->
tool invocation through agent runtime -> system prompt composition -> user
prompt composition -> LLM-based draft generation -> fallback generation
logic if primary response empty -> structured context capture for
transparency.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from json import dumps

from langchain_core.messages import AIMessage, ToolMessage

from customer_support_agent.core.settings import Settings, get_settings
from customer_support_agent.integrations.llm.base import LLMProvider
from customer_support_agent.integrations.llm.factory import get_llm_provider
from customer_support_agent.integrations.memory.langmem_store import (
    LangMemStore,
    MemoryHit,
    get_memory_store,
)
from customer_support_agent.integrations.rag.chroma_kb import (
    ChromaKnowledgeBase,
    KnowledgeHit,
    get_knowledge_base,
)
from customer_support_agent.integrations.tools.claim_risk_tools import analyze_claim_risk
from customer_support_agent.integrations.tools.support_tools import (
    SUPPORT_TOOLS,
    lookup_customer_plan,
    lookup_open_ticket_load,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """You are an internal AI copilot assisting a human insurance claims \
adjuster / support agent. You draft a concise, grounded recommendation for handling a claim or \
support request. You are NOT the final decision-maker: a licensed human adjuster will review, \
edit, and approve or discard everything you write. Never state a final coverage approval or \
denial as fact — frame coverage positioning as a recommendation pending adjuster confirmation.

Use the tools available to you (lookup_customer_plan, lookup_open_ticket_load, \
analyze_claim_risk) whenever you need current plan/SLA/ticket-load facts or a quick fraud-risk \
screen instead of guessing.

Relevant prior claim history for this customer/company (may be empty):
{memory_context}

Relevant knowledge base guidance (may be empty):
{knowledge_context}

Structured tool outputs (may be empty):
{tool_context}

Write your recommendation as clear, plain-language guidance covering: a summary of the \
situation, what is confirmed vs. still pending, recommended next steps, and any required \
documents. Keep it concise (under 250 words) and edit-ready for a human reviewer."""

_FALLBACK_SYSTEM_PROMPT = """You are an internal AI copilot assisting a human insurance claims \
adjuster. Draft a brief, concise, edit-ready recommendation for the claim below. Do not state a \
final coverage decision — frame it as pending adjuster confirmation."""


@dataclass
class DraftGenerationRequest:
    customer_email: str
    company_name: str
    claim_narrative: str
    customer_name: str | None = None
    claim_type: str | None = None


@dataclass
class DraftGenerationResult:
    draft_text: str
    context_used: dict = field(default_factory=dict)


def _format_memory_context(hits: list[MemoryHit]) -> str:
    if not hits:
        return "(no relevant prior history found)"
    return "\n".join(f"- [{hit.scope}] {hit.content}" for hit in hits)


def _format_knowledge_context(hits: list[KnowledgeHit]) -> str:
    if not hits:
        return "(no relevant knowledge base guidance found)"
    return "\n".join(f"- ({hit.source}) {hit.content}" for hit in hits)


def _extract_tool_calls(messages: list) -> list[dict]:
    """Pull structured tool-call records out of an agent's message list."""
    return [
        {"tool": message.name, "output": message.content}
        for message in messages
        if isinstance(message, ToolMessage)
    ]


def _format_tool_context(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "(no structured tool output available)"
    return "\n".join(
        f"- {tool_call['tool']}: {dumps(tool_call['output'], ensure_ascii=True)}"
        for tool_call in tool_calls
    )


def _invoke_tool(tool_obj, **payload_context: str | None) -> dict:
    for payload in (payload_context, payload_context.get("customer_email")):
        if payload is None:
            continue
        try:
            return tool_obj.invoke(payload)
        except TypeError:
            continue
    return tool_obj.invoke(payload_context)


def _run_support_tools(
    customer_email: str,
    claim_narrative: str,
    claim_type: str | None,
) -> list[dict]:
    tool_calls: list[dict] = []
    for tool_obj in (lookup_customer_plan, lookup_open_ticket_load, analyze_claim_risk):
        tool_calls.append(
            {
                "tool": tool_obj.name,
                "output": _invoke_tool(
                    tool_obj,
                    customer_email=customer_email,
                    claim_narrative=claim_narrative,
                    claim_type=claim_type,
                ),
            }
        )
    return tool_calls


class CopilotService:
    """Orchestrates the full memory -> RAG -> tools -> LLM draft-generation pipeline."""

    def __init__(
        self,
        settings: Settings,
        llm_provider: LLMProvider,
        knowledge_base: ChromaKnowledgeBase,
        memory_store: LangMemStore,
        tools: list | None = None,
    ) -> None:
        self._settings = settings
        self._llm_provider = llm_provider
        self._knowledge_base = knowledge_base
        self._memory_store = memory_store
        self._tools = tools if tools is not None else SUPPORT_TOOLS

    def generate_draft(self, request: DraftGenerationRequest) -> DraftGenerationResult:
        errors: list[str] = []
        tool_calls: list[dict] = []

        # ------------------------------------------------------- 1. memory
        memory_start = time.perf_counter()
        memory_result = None
        try:
            memory_result = self._memory_store.retrieve_relevant_memories(
                customer_email=request.customer_email,
                company_name=request.company_name,
                query=request.claim_narrative,
            )
            if memory_result.error:
                errors.append(f"memory_search_partial_error: {memory_result.error}")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Memory retrieval failed")
            errors.append(f"memory_search_failed: {exc}")
        memory_query_ms = round((time.perf_counter() - memory_start) * 1000, 2)
        memory_hits = memory_result.hits if memory_result else []

        # ---------------------------------------------------- 2. knowledge
        try:
            knowledge_hits = self._knowledge_base.search(request.claim_narrative)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Knowledge base retrieval failed")
            errors.append(f"knowledge_search_failed: {exc}")
            knowledge_hits = []

        # ----------------------------------------------- 3. prompt compose
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            memory_context=_format_memory_context(memory_hits),
            knowledge_context=_format_knowledge_context(knowledge_hits),
            tool_context=_format_tool_context(tool_calls),
        )
        user_prompt = (
            f"Customer: {request.customer_name or request.customer_email}\n"
            f"Company: {request.company_name}\n"
            f"Claim type: {request.claim_type or 'unspecified'}\n\n"
            f"Claim narrative:\n{request.claim_narrative}"
        )

        # --------------------------------------------- 4/5. agent generation
        draft_text = ""
        try:
            from langchain.agents import create_agent

            chat_model = self._llm_provider.as_langchain_chat_model()
            agent = create_agent(
                model=chat_model,
                tools=self._tools,
                system_prompt=system_prompt,
                store=self._memory_store.raw_store,
            )
            result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
            messages = result.get("messages", [])
            tool_calls = _extract_tool_calls(messages)
            if messages:
                last_message = messages[-1]
                if isinstance(last_message, AIMessage):
                    draft_text = (last_message.content or "").strip()
        except Exception as exc:
            logger.exception("Primary agent draft generation failed")
            errors.append(f"agent_generation_failed: {exc}")

        if not tool_calls:
            try:
                tool_calls = _run_support_tools(
                    request.customer_email,
                    request.claim_narrative,
                    request.claim_type,
                )
            except Exception as exc:
                logger.exception("Direct tool execution failed")
                errors.append(f"tool_execution_failed: {exc}")
        risk_tool_output = next(
            (
                tool_call.get("output")
                for tool_call in tool_calls
                if tool_call.get("tool") == analyze_claim_risk.name
            ),
            None,
        )

        fallback_user_prompt = (
            f"{user_prompt}\n\n"
            f"Relevant prior claim history:\n{_format_memory_context(memory_hits)}\n\n"
            f"Relevant knowledge base guidance:\n{_format_knowledge_context(knowledge_hits)}\n\n"
            f"Structured tool outputs:\n{_format_tool_context(tool_calls)}"
        )

        # ----------------------------------------------- 6. fallback logic
        if not draft_text:
            try:
                chat_model = self._llm_provider.as_langchain_chat_model()
                fallback_response = chat_model.invoke(
                    [
                        {"role": "system", "content": _FALLBACK_SYSTEM_PROMPT},
                        {"role": "user", "content": fallback_user_prompt},
                    ]
                )
                draft_text = (fallback_response.content or "").strip()
                if draft_text:
                    errors.append("primary_generation_empty_used_fallback")
            except Exception as exc:
                logger.exception("Fallback draft generation failed")
                errors.append(f"fallback_generation_failed: {exc}")
                draft_text = (
                    "Unable to generate an AI draft at this time. Please review the claim "
                    "manually and consult the knowledge base directly."
                )

        # ---------------------------------------------------- 7. context_used
        context_used = {
            "memory_hits": [
                {
                    "memory_id": hit.memory_id,
                    "content": hit.content,
                    "scope": hit.scope,
                    "score": hit.score,
                }
                for hit in memory_hits
            ],
            "knowledge_hits": [
                {
                    "content": hit.content,
                    "source": hit.source,
                    "chunk_index": hit.chunk_index,
                    "score": hit.score,
                }
                for hit in knowledge_hits
            ],
            "tool_calls": tool_calls,
            "errors": errors,
            "signals": {
                "memory_enabled": True,
                "memory_backend": "langgraph_in_memory_store",
                "memory_semantic_search": self._memory_store.is_semantic_enabled,
                "memory_query_time_ms": memory_query_ms,
                "llm_provider": self._llm_provider.provider_name,
                "llm_model": self._llm_provider.model_name,
                "risk_level": risk_tool_output.get("risk_level")
                if isinstance(risk_tool_output, dict)
                else None,
            },
        }

        return DraftGenerationResult(draft_text=draft_text, context_used=context_used)


@lru_cache
def get_copilot_service() -> CopilotService:
    """Process-wide cached accessor, mirroring the other integration factories."""
    return CopilotService(
        settings=get_settings(),
        llm_provider=get_llm_provider(),
        knowledge_base=get_knowledge_base(),
        memory_store=get_memory_store(),
    )
