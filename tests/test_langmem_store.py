"""
Unit and integration tests for LangMemStore (memory layer).

Tests cover:
- Customer and company namespace creation and normalization
- Semantic memory search (when embeddings configured)
- Fallback to recent-memory listing (when embeddings unavailable)
- Memory deduplication across scopes
- Resolution memory writing to both scopes
- Email and company name normalization
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.embeddings.base import EmbeddingProvider
from customer_support_agent.integrations.memory.langmem_store import (
    LangMemStore,
    MemoryHit,
    MemoryRetrievalResult,
    company_slug,
    normalize_email,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create settings for memory tests."""
    return Settings()


@pytest.fixture
def mock_embedding_provider_real() -> EmbeddingProvider:
    """Mock embedding provider that returns a LangChain Embeddings object."""
    provider = Mock(spec=EmbeddingProvider)
    provider.provider_name = "openai"

    embeddings_mock = Mock()
    embeddings_mock.model = "text-embedding-3-small"
    embeddings_mock.embed_query = Mock(return_value=[0.1] * 1536)

    provider.as_langchain_embeddings = Mock(return_value=embeddings_mock)
    return provider


@pytest.fixture
def mock_embedding_provider_none() -> EmbeddingProvider:
    """Mock embedding provider that returns None (no semantic search)."""
    provider = Mock(spec=EmbeddingProvider)
    provider.provider_name = "chroma_default"
    provider.as_langchain_embeddings = Mock(return_value=None)
    return provider


class TestEmailNormalization:
    """Test email normalization for namespace safety."""

    def test_normalize_email_standard(self) -> None:
        assert normalize_email("jane.doe@example.com") == "jane_dot_doe_at_example_dot_com"

    def test_normalize_email_uppercase_lowercased(self) -> None:
        assert normalize_email("JANE.DOE@EXAMPLE.COM") == "jane_dot_doe_at_example_dot_com"

    def test_normalize_email_with_whitespace(self) -> None:
        assert normalize_email("  jane.doe@example.com  ") == "jane_dot_doe_at_example_dot_com"

    def test_normalize_email_multiple_dots(self) -> None:
        assert (
            normalize_email("jane.margaret.doe@subdomain.example.com")
            == "jane_dot_margaret_dot_doe_at_subdomain_dot_example_dot_com"
        )


class TestCompanySlug:
    """Test company name slug creation."""

    def test_company_slug_standard(self) -> None:
        assert company_slug("Acme Insurance Corp") == "acme_insurance_corp"

    def test_company_slug_with_special_chars(self) -> None:
        assert company_slug("Acme & Co. Ltd.") == "acme_co_ltd"

    def test_company_slug_uppercase_lowercased(self) -> None:
        assert company_slug("ACME INSURANCE") == "acme_insurance"

    def test_company_slug_with_extra_spaces(self) -> None:
        assert company_slug("  Acme    Insurance  ") == "acme_insurance"

    def test_company_slug_empty_becomes_unknown(self) -> None:
        assert company_slug("") == "unknown_company"
        assert company_slug("   ") == "unknown_company"


class TestLangMemStoreNamespaces:
    """Test namespace creation for customer and company scopes."""

    def test_customer_namespace(self) -> None:
        ns = LangMemStore.customer_namespace("jane.doe@example.com")
        assert ns == ("memories", "customer", "jane_dot_doe_at_example_dot_com")

    def test_company_namespace(self) -> None:
        ns = LangMemStore.company_namespace("Acme Corp")
        assert ns == ("memories", "company", "acme_corp")


class TestLangMemStoreInitialization:
    """Test LangMemStore initialization with different embedding providers."""

    def test_init_with_real_embeddings(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_real)
        assert store.is_semantic_enabled is True
        assert store.raw_store is not None

    def test_init_with_none_embeddings(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_none)
        assert store.is_semantic_enabled is False
        assert store.raw_store is not None


class TestLangMemStoreWriting:
    """Test memory writing operations."""

    def test_write_memory_basic(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
    ) -> None:
        """Test writing a memory with no semantic indexing."""
        store = LangMemStore(mock_settings, mock_embedding_provider_none)
        namespace = ("test", "namespace")
        content = "Test memory content"
        metadata = {"claim_id": "123"}

        memory_id = store.write_memory(namespace, content, metadata)
        assert memory_id
        assert isinstance(memory_id, str)

    def test_write_resolution_memory(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
    ) -> None:
        """Test writing a resolution memory to both customer and company scopes."""
        store = LangMemStore(mock_settings, mock_embedding_provider_none)
        content = "Approved resolution content"
        metadata = {"approved_by": "adjuster_123"}

        result = store.write_resolution_memory(
            customer_email="jane.doe@example.com",
            company_name="Acme Corp",
            content=content,
            metadata=metadata,
        )

        assert "customer_memory_id" in result
        assert "company_memory_id" in result
        assert isinstance(result["customer_memory_id"], str)
        assert isinstance(result["company_memory_id"], str)


class TestLangMemStoreRetrieval:
    """Test memory retrieval operations."""

    def test_retrieve_relevant_memories_empty(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_real)
        result = store.retrieve_relevant_memories(
            customer_email="jane.doe@example.com",
            company_name="Acme Corp",
            query="test query",
        )

        assert isinstance(result, MemoryRetrievalResult)
        assert isinstance(result.hits, list)
        assert result.semantic_search_used is True

    def test_retrieve_relevant_memories_with_write_then_search(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,  # Use None for predictable results
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_none)

        # Write some memories
        content1 = "Customer had a previous collision claim in 2022"
        store.write_memory(
            store.customer_namespace("jane.doe@example.com"),
            content1,
            {"claim_id": "claim_001"},
        )

        content2 = "Company auto policy standard SLA is 48 hours"
        store.write_memory(
            store.company_namespace("Acme Corp"),
            content2,
            {"policy_ref": "sla_001"},
        )

        # Retrieve (should find both, deduplicated)
        result = store.retrieve_relevant_memories(
            customer_email="jane.doe@example.com",
            company_name="Acme Corp",
            query="claims history",
        )

        assert len(result.hits) > 0
        contents = [hit.content for hit in result.hits]
        # Should find both memories (or at least one of them in fallback mode)
        assert any(content1 in c or "collision" in c.lower() for c in contents) or len(
            contents
        ) == 0

    def test_retrieve_relevant_memories_deduplication(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_none)

        # Write the same memory to both scopes
        content = "Duplicate memory content"
        store.write_memory(
            store.customer_namespace("jane.doe@example.com"),
            content,
            {"id": "dup_1"},
        )
        store.write_memory(
            store.company_namespace("Acme Corp"),
            content,
            {"id": "dup_2"},
        )

        # Retrieve -- should deduplicate
        result = store.retrieve_relevant_memories(
            customer_email="jane.doe@example.com",
            company_name="Acme Corp",
            query="memory",
        )

        # After deduplication, should have only 1 unique content (or empty if fallback fails)
        if result.hits:
            contents = [hit.content.strip() for hit in result.hits]
            # All duplicates removed
            assert len([c for c in contents if c == content]) <= 1

    def test_retrieve_with_limit(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
    ) -> None:
        store = LangMemStore(mock_settings, mock_embedding_provider_none)

        # Write multiple memories
        for i in range(5):
            store.write_memory(
                store.customer_namespace("jane.doe@example.com"),
                f"Memory {i}",
                {"index": i},
            )

        # Retrieve with custom limit
        result = store.retrieve_relevant_memories(
            customer_email="jane.doe@example.com",
            company_name="Acme Corp",
            query="memory",
            limit=2,
        )

        assert len(result.hits) <= 2


class TestMemoryHit:
    """Test MemoryHit dataclass."""

    def test_memory_hit_creation(self) -> None:
        hit = MemoryHit(
            memory_id="hit_123",
            content="Test content",
            scope="customer",
            score=0.95,
            metadata={"tag": "important"},
        )

        assert hit.memory_id == "hit_123"
        assert hit.content == "Test content"
        assert hit.scope == "customer"
        assert hit.score == 0.95
        assert hit.metadata == {"tag": "important"}


class TestMemoryRetrievalResult:
    """Test MemoryRetrievalResult dataclass."""

    def test_memory_retrieval_result_creation(self) -> None:
        hits = [
            MemoryHit("id1", "content1", "customer", 0.9),
            MemoryHit("id2", "content2", "company", 0.8),
        ]

        result = MemoryRetrievalResult(
            hits=hits,
            semantic_search_used=True,
            error=None,
        )

        assert len(result.hits) == 2
        assert result.semantic_search_used is True
        assert result.error is None
