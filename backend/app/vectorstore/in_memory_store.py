"""TEST-ONLY in-memory vector store for isolated unit tests.

.. warning::

   **TEST-ONLY in-memory vector store for isolated unit tests.  It is NOT a
   production store.**

The store keeps every chunk in a plain Python dictionary and computes the
similarity with NumPy.  It exists so that unit tests can exercise the
retrieval logic without a database; it has no persistence, no concurrency
control and no durability guarantees whatsoever.

The production implementation is
:class:`~app.vectorstore.pgvector_store.PgVectorStore`.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import numpy as np

from app.core.exceptions import VectorStoreError
from app.vectorstore.base import (
    SearchHit,
    VectorRecord,
    clamp_limit,
    resolve_chunk_indexes,
)

__all__ = ["InMemoryVectorStore"]


class _StoredChunk:
    """One chunk held by the in-memory store."""

    __slots__ = (
        "chunk_id",
        "chunk_type",
        "content",
        "document_id",
        "metadata",
        "page_end",
        "page_start",
        "section_heading",
        "vector",
        "workspace_id",
    )

    def __init__(
        self,
        record: VectorRecord,
        chunk_index: int,
        vector: np.ndarray,
    ) -> None:
        """Store *record* under *chunk_index* with the pre-validated *vector*."""
        self.chunk_id = record.chunk_id
        self.document_id = record.document_id
        self.workspace_id = record.workspace_id
        self.content = record.content
        self.vector = vector
        self.page_start = record.page_start
        self.page_end = record.page_end
        self.section_heading = record.section_heading
        self.chunk_type = record.chunk_type
        self.metadata = dict(record.metadata)


class InMemoryVectorStore:
    """A dictionary backed :class:`~app.vectorstore.base.VectorStore`.

    The store is intentionally simple: it is not thread safe and it is not
    meant to hold more than a few hundred chunks.
    """

    def __init__(self, dimension: int | None = None) -> None:
        """Create an empty store.

        Parameters
        ----------
        dimension:
            Optional expected embedding length.  When given, an embedding of
            a different length is rejected with
            :class:`~app.core.exceptions.VectorStoreError`.
        """
        self.dimension = dimension
        self._chunks: dict[tuple[UUID, int], _StoredChunk] = {}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _validate_embedding(self, embedding: Sequence[float]) -> np.ndarray:
        """Return *embedding* as a NumPy array after validating it."""
        values = np.asarray([float(value) for value in embedding], dtype=np.float64)
        if values.ndim != 1:
            raise VectorStoreError(
                "embedding must be a one dimensional sequence",
                code="embedding_dimension_mismatch",
                details={"expected": self.dimension},
            )
        if self.dimension is not None and values.shape[0] != self.dimension:
            raise VectorStoreError(
                "embedding dimension does not match the store configuration",
                code="embedding_dimension_mismatch",
                details={"expected": self.dimension, "actual": int(values.shape[0])},
            )
        if not bool(np.all(np.isfinite(values))):
            raise VectorStoreError(
                "embedding contains a non-finite value",
                code="embedding_not_finite",
                details={"dimension": self.dimension},
            )
        return values

    @staticmethod
    def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Return the cosine similarity of *query* against every row of *matrix*."""
        query_norm = float(np.linalg.norm(query))
        norms = np.linalg.norm(matrix, axis=1)
        denominator = norms * query_norm
        similarities = np.zeros(matrix.shape[0], dtype=np.float64)
        non_zero = denominator > 0.0
        if bool(np.any(non_zero)):
            similarities[non_zero] = (
                matrix[non_zero] @ query
            ) / denominator[non_zero]
        return np.clip(similarities, -1.0, 1.0)

    # ------------------------------------------------------------------
    # VectorStore protocol
    # ------------------------------------------------------------------
    def upsert_chunks(self, records: Sequence[VectorRecord]) -> int:
        """Insert or update *records*; return the number of rows written.

        The key is ``(document_id, chunk_index)``, so writing the same
        records twice leaves exactly one chunk per key.
        """
        batch = list(records)
        if not batch:
            return 0
        chunk_indexes = resolve_chunk_indexes(batch)
        for record, chunk_index in zip(batch, chunk_indexes, strict=True):
            vector = self._validate_embedding(record.embedding)
            stored = _StoredChunk(record, chunk_index, vector)
            self._chunks[(record.document_id, chunk_index)] = stored
        return len(batch)

    def search(
        self,
        embedding: Sequence[float],
        workspace_id: UUID,
        *,
        limit: int = 10,
        document_ids: Sequence[UUID] | None = None,
        chunk_types: Sequence[str] | None = None,
    ) -> list[SearchHit]:
        """Return the closest chunks of *workspace_id*."""
        effective_limit = clamp_limit(limit)
        query = self._validate_embedding(embedding)

        wanted_documents = None if document_ids is None else set(document_ids)
        wanted_types = None if chunk_types is None else set(chunk_types)

        candidates = [
            chunk
            for chunk in self._chunks.values()
            if chunk.workspace_id == workspace_id
            and (wanted_documents is None or chunk.document_id in wanted_documents)
            and (wanted_types is None or chunk.chunk_type in wanted_types)
        ]
        if not candidates:
            return []

        matrix = np.vstack([chunk.vector for chunk in candidates])
        similarities = self._cosine_similarity(query, matrix)

        ranked = sorted(
            zip(candidates, similarities, strict=True),
            key=lambda item: (-float(item[1]), str(item[0].chunk_id)),
        )
        return [
            SearchHit(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                workspace_id=chunk.workspace_id,
                content=chunk.content,
                score=float(score),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_heading=chunk.section_heading,
                chunk_type=chunk.chunk_type,
                metadata=dict(chunk.metadata),
            )
            for chunk, score in ranked[:effective_limit]
        ]

    def delete_document_chunks(self, document_id: UUID) -> int:
        """Delete every chunk of *document_id* and return the row count."""
        keys = [key for key in self._chunks if key[0] == document_id]
        for key in keys:
            del self._chunks[key]
        return len(keys)

    def count_chunks(self, document_id: UUID | None = None) -> int:
        """Return the number of stored chunks, optionally of one document."""
        if document_id is None:
            return len(self._chunks)
        return sum(1 for key in self._chunks if key[0] == document_id)

    def get_existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return an empty mapping: the test store keeps no embedding state."""
        return {}

    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``.

        The method is an alias of :meth:`get_existing_embeddings`; it exists
        so that the store satisfies the ``ExistingEmbeddingSource`` protocol
        of :mod:`app.ingestion.pipeline`.  The test store keeps no embedding
        state, therefore the mapping is always empty.
        """
        return self.get_existing_embeddings(document_id)
