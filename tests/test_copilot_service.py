"""
Unit and integration tests for CopilotService (agent orchestration).

Tests cover:
- Draft generation with full orchestration pipeline
- Memory, knowledge, and tool integration
- Fallback generation logic when primary response empty
- Context tracking and signals
- Error handling and graceful degradation
- Dependency injection and composition
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.llm.base import LLMProvider
from customer_support_agent.integrations.memory.langmem_store import LangMemStore, MemoryHit
from customer_support_agent.integrations.rag.chroma_kb import ChromaKnowledgeBase, KnowledgeHit
from customer_support_agent.services.copilot_service import (
    CopilotService,
    DraftGenerationRequest,
    DraftGenerationResult,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create minimal settings for tests."""
    return Settings()


@pytest.fixture
def mock_llm_provider() -> LLMProvider:
    """Mock LLM provider that returns a reasonable draft."""
    provider = Mock(spec=LLMProvider)
    provider.provider_name = "openai"
    provider.model_name = "gpt-4o"

    # Mock chat model
    chat_model = Mock()
    chat_model.invoke = Mock(
        return_value=Mock(
            content="This is a test draft recommendation based on the provided context."
        )
    )

    provider.as_langchain_chat_model = Mock(return_value=chat_model)
    return provider


@pytest.fixture
def mock_embedding_provider() -> Mock:
    """Mock embedding provider."""
    provider = Mock()
    provider.provider_name = "openai"
    embeddings_mock = Mock()
    embeddings_mock.model = "text-embedding-3-small"
    provider.as_langchain_embeddings = Mock(return_value=embeddings_mock)
    return provider


@pytest.fixture
def mock_knowledge_base() -> ChromaKnowledgeBase:
    """Mock knowledge base that returns sample hits."""
    kb = Mock(spec=ChromaKnowledgeBase)
    kb.search = Mock(
        return_value=[
            KnowledgeHit(
                content="Auto collision claims require police report within 48 hours.",
                source="insurance-auto-required-documents-by-claim-type.md",
                chunk_index=0,
                score=0.92,
            ),
            KnowledgeHit(
                content="Premium tier customers receive 24-hour SLA.",
                source="insurance-claims-settlement-sla-and-communication.md",
                chunk_index=1,
                score=0.88,
            ),
        ]
    )
    return kb


@pytest.fixture
def mock_memory_store(mock_embedding_provider: Mock) -> LangMemStore:
    """Mock memory store that returns sample memories."""
    store = Mock(spec=LangMemStore)
    store.is_semantic_enabled = True
    store.raw_store = Mock()

    # Mock retrieval result
    result_mock = Mock()
    result_mock.hits = [
        MemoryHit(
            memory_id="mem_1",
            content="Customer had a windshield replacement claim in 2023 (approved).",
            scope="customer",
            score=0.89,
        ),
        MemoryHit(
            memory_id="mem_2",
            content="Company policy: collision deductible $1000, comprehensive $500.",
            scope="company",
            score=0.85,
        ),
    ]
    result_mock.error = None
    result_mock.semantic_search_used = True

    store.retrieve_relevant_memories = Mock(return_value=result_mock)
    return store


class TestDraftGenerationRequest:
    """Test DraftGenerationRequest dataclass."""

    def test_create_basic_request(self) -> None:
        request = DraftGenerationRequest(
            customer_email="jane.doe@example.com",
            company_name="Acme Insurance",
            claim_narrative="Car hit a parked vehicle on Main Street.",
        )

        assert request.customer_email == "jane.doe@example.com"
        assert request.company_name == "Acme Insurance"
        assert request.claim_narrative == "Car hit a parked vehicle on Main Street."
        assert request.customer_name is None
        assert request.claim_type is None

    def test_create_full_request(self) -> None:
        request = DraftGenerationRequest(
            customer_email="jane.doe@example.com",
            company_name="Acme Insurance",
            claim_narrative="Collision damage reported.",
            customer_name="Jane Doe",
            claim_type="auto_collision",
        )

        assert request.customer_name == "Jane Doe"
        assert request.claim_type == "auto_collision"


class TestDraftGenerationResult:
    """Test DraftGenerationResult dataclass."""

    def test_create_result_with_context(self) -> None:
        context_used = {
            "memory_hits": [{"memory_id": "m1", "content": "test"}],
            "knowledge_hits": [{"content": "guidance", "source": "file.md"}],
            "tool_calls": [{"tool": "lookup_customer_plan", "output": "data"}],
            "errors": [],
            "signals": {"memory_enabled": True},
        }

        result = DraftGenerationResult(
            draft_text="This is a draft.",
            context_used=context_used,
        )

        assert result.draft_text == "This is a draft."
        assert result.context_used == context_used


class TestCopilotServiceInitialization:
    """Test CopilotService instantiation."""

    def test_init_with_all_dependencies(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        assert service._settings == mock_settings
        assert service._llm_provider == mock_llm_provider
        assert service._knowledge_base == mock_knowledge_base
        assert service._memory_store == mock_memory_store


class TestDraftGeneration:
    """Test draft generation pipeline."""

    def test_generate_draft_successful(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test successful draft generation with full pipeline."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="jane.doe@example.com",
            company_name="Acme Insurance",
            claim_narrative="Vehicle collision on Main Street.",
            customer_name="Jane Doe",
            claim_type="auto_collision",
        )

        result = service.generate_draft(request)

        assert isinstance(result, DraftGenerationResult)
        assert result.draft_text  # Should have generated text
        assert hasattr(result, "context_used")
        assert isinstance(result.context_used, dict)

    def test_context_used_structure(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that context_used has all required keys."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        context = result.context_used
        assert "memory_hits" in context
        assert "knowledge_hits" in context
        assert "tool_calls" in context
        assert "errors" in context
        assert "signals" in context

    def test_signals_include_llm_info(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that signals include LLM provider and model info."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        signals = result.context_used.get("signals", {})
        assert "llm_provider" in signals
        assert signals["llm_provider"] == "openai"
        assert "llm_model" in signals
        assert signals["llm_model"] == "gpt-4o"

    def test_signals_include_memory_info(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that signals include memory backend and semantic search status."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        signals = result.context_used.get("signals", {})
        assert "memory_enabled" in signals
        assert "memory_backend" in signals
        assert "memory_semantic_search" in signals
        assert "memory_query_time_ms" in signals
        assert "risk_level" in signals


class TestFallbackGeneration:
    """Test fallback draft generation when primary fails."""

    def test_fallback_when_primary_empty(
        self,
        mock_settings: Settings,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test fallback generation triggers when primary LLM returns empty."""
        # Create a provider that returns empty on first call, then fallback
        provider = Mock(spec=LLMProvider)
        provider.provider_name = "openai"
        provider.model_name = "gpt-4o"

        fallback_response = Mock(content="Fallback-generated recommendation")
        chat_model = Mock()
        chat_model.invoke = Mock(return_value=fallback_response)

        provider.as_langchain_chat_model = Mock(return_value=chat_model)

        service = CopilotService(
            settings=mock_settings,
            llm_provider=provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        assert result.draft_text == "Fallback-generated recommendation"
        assert any(
            error.startswith("agent_generation_failed:")
            for error in result.context_used.get("errors", [])
        )
        assert "primary_generation_empty_used_fallback" in result.context_used.get("errors", [])


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_memory_retrieval_failure_graceful(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that memory retrieval failure doesn't block draft generation."""
        # Mock memory store to raise error
        mock_memory_store.retrieve_relevant_memories = Mock(
            side_effect=RuntimeError("Memory store error")
        )

        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        # Should still generate a draft despite memory error
        assert result.draft_text
        # Error should be recorded
        assert any(
            "memory" in str(e).lower() for e in result.context_used.get("errors", [])
        )

    def test_knowledge_retrieval_failure_graceful(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that knowledge retrieval failure doesn't block draft generation."""
        # Mock knowledge base to raise error
        mock_knowledge_base.search = Mock(side_effect=RuntimeError("KB error"))

        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        # Should still generate a draft despite KB error
        assert result.draft_text
        # Error should be recorded
        assert any(
            "knowledge" in str(e).lower() for e in result.context_used.get("errors", [])
        )


class TestContextFormatting:
    """Test context formatting in prompts."""

    def test_memory_context_formatting(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that memory context is properly formatted in prompt."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        # Check that memory hits are captured in context_used
        memory_hits = result.context_used.get("memory_hits", [])
        assert len(memory_hits) > 0
        assert all("content" in hit for hit in memory_hits)
        assert all("scope" in hit for hit in memory_hits)

    def test_knowledge_context_formatting(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        """Test that knowledge context is properly formatted in context_used."""
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Test claim",
        )

        result = service.generate_draft(request)

        # Check that knowledge hits are captured in context_used
        knowledge_hits = result.context_used.get("knowledge_hits", [])
        assert len(knowledge_hits) > 0
        assert all("content" in hit for hit in knowledge_hits)
        assert all("source" in hit for hit in knowledge_hits)

    def test_risk_tool_output_is_captured(
        self,
        mock_settings: Settings,
        mock_llm_provider: LLMProvider,
        mock_knowledge_base: ChromaKnowledgeBase,
        mock_memory_store: LangMemStore,
    ) -> None:
        service = CopilotService(
            settings=mock_settings,
            llm_provider=mock_llm_provider,
            knowledge_base=mock_knowledge_base,
            memory_store=mock_memory_store,
        )

        request = DraftGenerationRequest(
            customer_email="test@example.com",
            company_name="Test Co",
            claim_narrative="Late night hit and run with no witnesses and urgent payout request.",
            claim_type="Auto Collision",
        )

        result = service.generate_draft(request)

        risk_call = next(
            tool_call
            for tool_call in result.context_used["tool_calls"]
            if tool_call["tool"] == "analyze_claim_risk"
        )
        assert risk_call["output"]["risk_level"] in {"medium", "high"}
        assert result.context_used["signals"]["risk_level"] == risk_call["output"]["risk_level"]
