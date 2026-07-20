"""
Unit and integration tests for ChromaKnowledgeBase (RAG layer).

Tests cover:
- Document loading from markdown files
- Semantic search with real/mocked embeddings
- Fallback to Chroma's default embeddings when provider yields None
- Error handling and graceful degradation
- Collection count verification
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from customer_support_agent.core.settings import Settings
from customer_support_agent.integrations.embeddings.base import EmbeddingProvider
from customer_support_agent.integrations.rag.chroma_kb import ChromaKnowledgeBase, KnowledgeHit


@pytest.fixture
def temp_kb_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample markdown files."""
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    # Create sample markdown files
    (kb_dir / "doc1.md").write_text(
        """# Auto Insurance Claims

## First Notice of Loss (FNOL)

FNOL is the first report of a loss to an insurance company.
It must be reported within 30 days.

### Required Documents
- Driver's license
- Insurance card
- Police report (if applicable)
"""
    )

    (kb_dir / "doc2.md").write_text(
        """# Deductible Guidelines

## Standard Deductibles

- Comprehensive: $500 default
- Collision: $1000 default
- Comprehensive + Collision: $1500 combined

Customers can lower deductibles by paying higher premiums.
"""
    )

    return kb_dir


@pytest.fixture
def mock_settings(temp_kb_dir: Path, tmp_path: Path) -> Settings:
    """Create settings pointing to temp KB directory."""
    settings = Settings()
    settings.knowledge_base_path = temp_kb_dir
    settings.vector_store_path = tmp_path / "vector_store"
    settings.rag_chunk_size = 200
    settings.rag_chunk_overlap = 50
    settings.rag_top_k = 2
    settings.chroma_collection_name = f"test_collection_{tmp_path.name}"
    return settings


@pytest.fixture
def mock_embedding_provider_real() -> EmbeddingProvider:
    """Mock embedding provider that returns a LangChain Embeddings object."""
    provider = Mock(spec=EmbeddingProvider)
    provider.provider_name = "openai"

    # Real LangChain embeddings mock (would normally come from OpenAI)
    embeddings_mock = Mock()
    embeddings_mock.embed_documents = Mock(side_effect=lambda docs: [[0.1] * 1536 for _ in docs])
    embeddings_mock.embed_query = Mock(return_value=[0.1] * 1536)
    embeddings_mock.model = "text-embedding-3-small"

    provider.as_langchain_embeddings = Mock(return_value=embeddings_mock)
    return provider


@pytest.fixture
def mock_embedding_provider_none() -> EmbeddingProvider:
    """Mock embedding provider that returns None (Chroma default embeddings)."""
    provider = Mock(spec=EmbeddingProvider)
    provider.provider_name = "chroma_default"
    provider.as_langchain_embeddings = Mock(return_value=None)
    return provider


class TestChromaKnowledgeBaseInitialization:
    """Test ChromaKnowledgeBase initialization and collection setup."""

    def test_init_with_real_embeddings(
        self, mock_settings: Settings, mock_embedding_provider_real: EmbeddingProvider
    ) -> None:
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        assert kb._settings == mock_settings
        assert kb._embedding_provider == mock_embedding_provider_real
        assert kb._collection is not None

    def test_init_with_none_embeddings(
        self, mock_settings: Settings, mock_embedding_provider_none: EmbeddingProvider
    ) -> None:
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_none)
        assert kb._settings == mock_settings
        assert kb._embedding_provider == mock_embedding_provider_none
        assert kb._collection is not None


class TestChromaKnowledgeBaseIngestion:
    """Test document loading, chunking, and ingestion."""

    def test_ingest_directory_with_real_embeddings(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test ingesting documents with real (mocked) embeddings."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        ingested_count = kb.ingest_directory(temp_kb_dir)
        assert ingested_count > 0
        assert kb.get_collection_count() == ingested_count

    def test_ingest_directory_with_none_embeddings(
        self,
        mock_settings: Settings,
        mock_embedding_provider_none: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test ingesting documents with Chroma default embeddings."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_none)
        ingested_count = kb.ingest_directory(temp_kb_dir)
        assert ingested_count > 0
        assert kb.get_collection_count() == ingested_count

    def test_ingest_empty_directory(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        tmp_path: Path,
    ) -> None:
        """Test ingesting from an empty directory."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        ingested_count = kb.ingest_directory(empty_dir)
        assert ingested_count == 0

    def test_ingest_nonexistent_directory(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        tmp_path: Path,
    ) -> None:
        """Test ingesting from a nonexistent directory."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        nonexistent = tmp_path / "nonexistent"
        ingested_count = kb.ingest_directory(nonexistent)
        assert ingested_count == 0

    def test_ingest_refresh_prefers_insurance_sources_and_clears_stale_content(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test refreshes rebuild the collection using only in-scope insurance files when present."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        kb.ingest_directory(temp_kb_dir)

        (temp_kb_dir / "insurance-coverage-test.md").write_text(
            "# Coverage\n\nCollision deductible is $500 and photos are required.",
            encoding="utf-8",
        )
        (temp_kb_dir / "progress.md").write_text(
            "Work items delivered and architecture notes should never appear in KB search.",
            encoding="utf-8",
        )

        refreshed_count = kb.ingest_directory(temp_kb_dir)
        results = kb.search("collision deductible", top_k=3)

        assert refreshed_count > 0
        assert kb.get_collection_count() == refreshed_count
        assert kb.get_indexed_sources() == ["insurance-coverage-test.md"]
        assert results
        assert {hit.source for hit in results} == {"insurance-coverage-test.md"}


class TestChromaKnowledgeBaseSearch:
    """Test semantic search and retrieval."""

    def test_search_after_ingestion(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test searching for documents after ingestion."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        kb.ingest_directory(temp_kb_dir)

        results = kb.search("FNOL deductible requirements", top_k=2)
        assert isinstance(results, list)
        assert len(results) > 0
        for hit in results:
            assert isinstance(hit, KnowledgeHit)
            assert hit.content
            assert hit.source
            assert hit.chunk_index >= 0

    def test_search_no_results(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
    ) -> None:
        """Test search on empty collection."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        results = kb.search("some query")
        assert results == []

    def test_search_with_custom_top_k(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test search respects custom top_k."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        kb.ingest_directory(temp_kb_dir)

        results_k1 = kb.search("insurance", top_k=1)
        results_k3 = kb.search("insurance", top_k=3)
        assert len(results_k1) <= 1
        assert len(results_k3) <= 3
        assert len(results_k1) <= len(results_k3)

    def test_search_handles_embedding_failure(
        self,
        mock_settings: Settings,
        temp_kb_dir: Path,
    ) -> None:
        """Test search gracefully handles embedding provider failure."""
        provider = Mock(spec=EmbeddingProvider)
        provider.provider_name = "openai"

        embeddings_mock = Mock()
        embeddings_mock.embed_query = Mock(side_effect=RuntimeError("API error"))
        provider.as_langchain_embeddings = Mock(return_value=embeddings_mock)

        kb = ChromaKnowledgeBase(mock_settings, provider)
        results = kb.search("test query")
        assert results == []  # Gracefully degraded to empty result


class TestChromaKnowledgeBaseMetadata:
    """Test metadata tracking and source attribution."""

    def test_search_results_include_source(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test that search results include source file metadata."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        kb.ingest_directory(temp_kb_dir)

        results = kb.search("FNOL")
        assert len(results) > 0

        # At least one result should be from doc1.md
        sources = {hit.source for hit in results}
        assert len(sources) > 0

    def test_search_results_include_chunk_index(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test that search results include chunk index."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        kb.ingest_directory(temp_kb_dir)

        results = kb.search("FNOL")
        assert all(hit.chunk_index >= 0 for hit in results)


class TestChromaKnowledgeBaseCollectionCount:
    """Test collection counting for verification."""

    def test_get_collection_count_empty(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
    ) -> None:
        """Test collection count on empty collection."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        assert kb.get_collection_count() == 0

    def test_get_collection_count_after_ingestion(
        self,
        mock_settings: Settings,
        mock_embedding_provider_real: EmbeddingProvider,
        temp_kb_dir: Path,
    ) -> None:
        """Test collection count increases after ingestion."""
        kb = ChromaKnowledgeBase(mock_settings, mock_embedding_provider_real)
        initial_count = kb.get_collection_count()
        kb.ingest_directory(temp_kb_dir)
        final_count = kb.get_collection_count()
        assert final_count > initial_count
