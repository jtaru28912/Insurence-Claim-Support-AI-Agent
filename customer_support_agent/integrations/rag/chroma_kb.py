"""
Knowledge base ingestion and retrieval via ChromaDB (RAG layer).

Design notes
------------
Uses the injected ``EmbeddingProvider`` (Dependency Inversion) rather than
importing a concrete embeddings SDK directly. When the active embedding
provider yields a LangChain ``Embeddings`` object (OpenAI/Gemini),
embeddings are computed explicitly here and passed to Chroma as raw
vectors. When the provider is ``chroma_default`` (no API key configured),
embeddings are omitted entirely so Chroma computes them itself with its
bundled local ONNX model — this is the spec's documented fallback
behavior ("otherwise, it falls back to Chroma's default embedding
function"), generalized across providers instead of hard-coded to Gemini.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from customer_support_agent.core.settings import Settings, get_settings
from customer_support_agent.integrations.embeddings.base import EmbeddingProvider
from customer_support_agent.integrations.embeddings.factory import get_embedding_provider

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeHit:
    """A single retrieved knowledge base chunk."""

    content: str
    source: str
    chunk_index: int
    score: float | None  # Chroma distance (lower = more relevant)


class ChromaKnowledgeBase:
    """RAG layer over the insurance ``knowledge_base/`` markdown files."""

    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        self._settings = settings
        self._embedding_provider = embedding_provider
        self._client = chromadb.PersistentClient(path=str(settings.vector_store_path))
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        self._allowed_sources = self._discover_allowed_sources(settings.knowledge_base_path)

    @property
    def _collection(self):
        return self._client.get_or_create_collection(name=self._settings.chroma_collection_name)

    def _langchain_embeddings(self):
        return self._embedding_provider.as_langchain_embeddings()

    def get_collection_count(self) -> int:
        """Return the current document count for verification and health reporting."""
        return self._collection.count()

    def get_indexed_sources(self) -> list[str]:
        """Return the markdown sources that are currently in scope for this project."""
        if not self._allowed_sources:
            self._allowed_sources = self._discover_allowed_sources(self._settings.knowledge_base_path)
        return sorted(self._allowed_sources)

    def reset_collection(self) -> None:
        """Drop the collection so refreshes remove stale or out-of-scope documents."""
        try:
            self._client.delete_collection(name=self._settings.chroma_collection_name)
            logger.info("Reset knowledge collection %s", self._settings.chroma_collection_name)
        except Exception:
            logger.debug(
                "Knowledge collection %s was not present during reset",
                self._settings.chroma_collection_name,
            )

    def _discover_allowed_sources(self, directory: Path) -> set[str]:
        return {file.name for file in self._select_markdown_files(directory)}

    @staticmethod
    def _select_markdown_files(directory: Path) -> list[Path]:
        md_files = sorted(directory.glob("*.md"))
        insurance_files = [file for file in md_files if file.name.startswith("insurance-")]
        if insurance_files:
            return insurance_files
        return md_files

    # ------------------------------------------------------------ ingest
    def ingest_directory(self, directory: Path | None = None) -> int:
        """
        Load every ``*.md`` file under ``directory`` (default:
        ``settings.knowledge_base_path``), chunk it, embed it, and upsert
        it into the Chroma collection. Returns the number of chunks
        ingested. Safe to call repeatedly — ``upsert`` overwrites chunks
        with the same id instead of duplicating them.
        """
        directory = directory or self._settings.knowledge_base_path
        md_files = self._select_markdown_files(directory)
        if not md_files:
            logger.warning("No knowledge base markdown files found in %s", directory)
            self._allowed_sources = set()
            return 0
        if not any(file.name.startswith("insurance-") for file in md_files):
            logger.warning(
                "No insurance-marked knowledge base files found in %s; ingesting all markdown files instead",
                directory,
            )
        self._allowed_sources = {file.name for file in md_files}
        self.reset_collection()

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for file_path in md_files:
            text = file_path.read_text(encoding="utf-8")
            chunks = self._splitter.split_text(text)
            for i, chunk in enumerate(chunks):
                ids.append(f"{file_path.stem}::chunk::{i}")
                documents.append(chunk)
                metadatas.append({"source": file_path.name, "chunk_index": i})

        embeddings = self._langchain_embeddings()
        if embeddings is not None:
            vectors = embeddings.embed_documents(documents)
            self._collection.upsert(
                ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors
            )
        else:
            # Let Chroma's own default (local ONNX) embedding function handle it.
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        logger.info(
            "Ingested %d chunks from %d knowledge base files: %s",
            len(ids),
            len(md_files),
            ", ".join(sorted(self._allowed_sources)),
        )
        return len(ids)

    # ------------------------------------------------------------ search
    def search(self, query: str, top_k: int | None = None) -> list[KnowledgeHit]:
        """
        Return the top-k most relevant knowledge base chunks for ``query``.

        Never raises: retrieval failures are logged and result in an empty
        list, so a knowledge base outage degrades gracefully instead of
        blocking draft generation.
        """
        top_k = top_k or self._settings.rag_top_k
        query_results = top_k * 5 if self._allowed_sources else top_k
        try:
            embeddings = self._langchain_embeddings()
            if embeddings is not None:
                query_vector = embeddings.embed_query(query)
                result = self._collection.query(
                    query_embeddings=[query_vector],
                    n_results=query_results,
                )
            else:
                result = self._collection.query(query_texts=[query], n_results=query_results)
        except Exception:
            logger.exception("Knowledge base search failed for query=%r", query)
            return []

        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        hits: list[KnowledgeHit] = []
        for doc, meta, dist in zip(documents[0], metadatas[0], distances[0], strict=False):
            source = meta.get("source", "unknown")
            if self._allowed_sources and source not in self._allowed_sources:
                logger.info("Skipping out-of-scope knowledge hit from source=%s", source)
                continue
            hits.append(
                KnowledgeHit(
                    content=doc,
                    source=source,
                    chunk_index=meta.get("chunk_index", -1),
                    score=dist,
                )
            )
            if len(hits) >= top_k:
                break
        return hits


@lru_cache
def get_knowledge_base() -> ChromaKnowledgeBase:
    """Process-wide cached accessor, mirroring get_llm_provider()/get_embedding_provider()."""
    return ChromaKnowledgeBase(get_settings(), get_embedding_provider())
