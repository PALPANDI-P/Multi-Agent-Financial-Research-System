"""pgvector backed implementation of the :class:`VectorStore` protocol.

The store talks to the ``document_chunks`` table through an *injected* session
factory, so it never owns a global engine: the caller decides which engine
(and therefore which database) is used.  ``app.db.session.SessionLocal`` is
only a convenience default for production wiring.

Design notes
------------
* **Workspace isolation is enforced in SQL.**  The ``documents`` table is
  joined into every search and ``documents.workspace_id = :workspace_id`` is
  part of the ``WHERE`` clause.  The filter is never applied in Python, so a
  bug in the calling code cannot leak another workspace's data.
* **All values are bound parameters.**  Nothing is interpolated into the SQL
  text; the optional ``IN`` lists use ``bindparam(..., expanding=True)``.
* **Idempotent writes.**  ``upsert_chunks`` uses
  ``INSERT ... ON CONFLICT (document_id, chunk_index) DO UPDATE`` so a re-run
  of the pipeline never creates duplicate chunks.
* **One transaction per operation.**  The store opens a session per call,
  commits on success, rolls back on error and always closes the session.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import String, Text, bindparam, cast, delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.types import Integer, UserDefinedType

from app.core.enums import ChunkType
from app.core.exceptions import VectorStoreError
from app.db.models.chunk import EMBEDDING_DIMENSION, DocumentChunk
from app.db.models.document import Document
from app.db.session import SessionLocal
from app.vectorstore.base import (
    SearchHit,
    VectorRecord,
    clamp_limit,
    record_content_hash,
    record_embedding_config_hash,
    record_token_count,
    resolve_chunk_indexes,
)

__all__ = ["PgVectorStore"]


class _VectorType(UserDefinedType):
    """The PostgreSQL ``vector`` type without a dimension modifier.

    It is used for ``CAST(:query_embedding AS vector)``: the bound parameter
    is a plain text value, and the cast lets PostgreSQL parse it with the
    vector input function.
    """

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        """Return the SQL type name used inside ``CAST``."""
        return "vector"


def _vector_literal(values: Sequence[float]) -> str:
    """Return the PostgreSQL text representation of *values*."""
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _default_config_hash(dimension: int) -> str:
    """Return the hash that identifies the default embedding configuration."""
    payload = f"pgvector:dimension={dimension}".encode()
    return hashlib.sha256(payload).hexdigest()


class PgVectorStore:
    """A :class:`~app.vectorstore.base.VectorStore` backed by PostgreSQL/pgvector."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        embedding_config_hash: str | None = None,
    ) -> None:
        """Create a store.

        Parameters
        ----------
        session_factory:
            Callable that returns a fresh :class:`~sqlalchemy.orm.Session`.
            The store owns the session lifecycle: it closes every session it
            opened, so the factory must return a session that the store may
            dispose of.
        dimension:
            Expected length of every embedding.  Defaults to the configured
            ``EMBEDDING_DIMENSION`` (384), which is the width of the
            ``document_chunks.embedding`` column.
        embedding_config_hash:
            Hash that identifies the embedding configuration.  It is stored
            next to every vector so that a later run can tell whether the
            stored vectors were produced with the same model.  When omitted a
            deterministic hash is derived from *dimension*.
        """
        if dimension < 1:
            raise VectorStoreError(
                "embedding dimension must be positive",
                code="embedding_dimension_mismatch",
                details={"dimension": dimension},
            )
        self._session_factory = session_factory
        self.dimension = dimension
        self.embedding_config_hash = embedding_config_hash or _default_config_hash(
            dimension
        )

    # ------------------------------------------------------------------
    # infrastructure
    # ------------------------------------------------------------------
    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Open a session, commit on success, roll back on error, always close."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _validated_embedding(self, embedding: Sequence[float]) -> list[float]:
        """Return *embedding* as a list of floats after validating it."""
        values = [float(value) for value in embedding]
        if len(values) != self.dimension:
            raise VectorStoreError(
                "embedding dimension does not match the store configuration",
                code="embedding_dimension_mismatch",
                details={"expected": self.dimension, "actual": len(values)},
            )
        for value in values:
            if not math.isfinite(value):
                raise VectorStoreError(
                    "embedding contains a non-finite value",
                    code="embedding_not_finite",
                    details={"dimension": self.dimension},
                )
        return values

    @staticmethod
    def _validated_chunk_type(chunk_type: str) -> str:
        """Return the canonical value of *chunk_type*."""
        try:
            return ChunkType(chunk_type).value
        except ValueError as exc:
            allowed = ", ".join(member.value for member in ChunkType)
            raise VectorStoreError(
                f"unknown chunk type {chunk_type!r}",
                code="invalid_chunk_type",
                details={"chunk_type": chunk_type, "allowed": allowed},
            ) from exc

    @staticmethod
    def _metadata_json(record: VectorRecord) -> dict[str, Any]:
        """Return the JSON serialisable metadata of *record*."""
        metadata = dict(record.metadata)
        try:
            json.dumps(metadata)
        except (TypeError, ValueError) as exc:
            raise VectorStoreError(
                "chunk metadata is not JSON serialisable",
                code="invalid_metadata",
                details={"document_id": str(record.document_id)},
            ) from exc
        return metadata

    # ------------------------------------------------------------------
    # VectorStore protocol
    # ------------------------------------------------------------------
    def upsert_chunks(self, records: Sequence[VectorRecord]) -> int:
        """Insert or update *records*; return the number of rows written.

        The whole batch is written in a single transaction.  Re-upserting the
        same records updates the existing rows instead of creating new ones,
        so exactly one row per ``(document_id, chunk_index)`` survives.
        """
        batch = list(records)
        if not batch:
            return 0

        chunk_indexes = resolve_chunk_indexes(batch)
        values: list[dict[str, Any]] = []
        for record, chunk_index in zip(batch, chunk_indexes, strict=True):
            values.append(
                {
                    "id": record.chunk_id,
                    "document_id": record.document_id,
                    "chunk_index": chunk_index,
                    "content": record.content,
                    "content_hash": record_content_hash(record),
                    "page_start": record.page_start,
                    "page_end": record.page_end,
                    "section_heading": record.section_heading,
                    "chunk_type": self._validated_chunk_type(record.chunk_type),
                    "token_count": record_token_count(record),
                    "metadata_json": self._metadata_json(record),
                    "embedding": self._validated_embedding(record.embedding),
                    "embedding_config_hash": record_embedding_config_hash(
                        record, self.embedding_config_hash
                    ),
                }
            )

        with self._session_scope() as session:
            insert_stmt = pg_insert(DocumentChunk).values(values)
            excluded = insert_stmt.excluded
            update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[DocumentChunk.document_id, DocumentChunk.chunk_index],
                set_={
                    "id": excluded.id,
                    "content": excluded.content,
                    "content_hash": excluded.content_hash,
                    "page_start": excluded.page_start,
                    "page_end": excluded.page_end,
                    "section_heading": excluded.section_heading,
                    "chunk_type": excluded.chunk_type,
                    "token_count": excluded.token_count,
                    "metadata_json": excluded.metadata_json,
                    "embedding": excluded.embedding,
                    "embedding_config_hash": excluded.embedding_config_hash,
                },
            )
            session.execute(update_stmt)
        return len(values)

    def search(
        self,
        embedding: Sequence[float],
        workspace_id: UUID,
        *,
        limit: int = 10,
        document_ids: Sequence[UUID] | None = None,
        chunk_types: Sequence[str] | None = None,
    ) -> list[SearchHit]:
        """Return the closest chunks of *workspace_id*.

        ``workspace_id`` is mandatory and is applied by PostgreSQL, not by
        the caller.  ``limit`` is clamped to ``1..100``; a limit below ``1``
        raises :class:`~app.core.exceptions.VectorStoreError`.
        """
        effective_limit = clamp_limit(limit)
        query_vector = self._validated_embedding(embedding)

        if document_ids is not None and not list(document_ids):
            return []
        if chunk_types is not None and not list(chunk_types):
            return []

        query = cast(bindparam("query_embedding", type_=Text), _VectorType())
        distance = DocumentChunk.embedding.cosine_distance(query)
        score = (literal(1.0) - distance).label("score")

        statement = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.document_id.label("document_id"),
                Document.workspace_id.label("workspace_id"),
                DocumentChunk.content.label("content"),
                score,
                DocumentChunk.page_start.label("page_start"),
                DocumentChunk.page_end.label("page_end"),
                DocumentChunk.section_heading.label("section_heading"),
                DocumentChunk.chunk_type.label("chunk_type"),
                DocumentChunk.metadata_json.label("metadata_json"),
                Document.document_title.label("document_title"),
                Document.company_name.label("company_name"),
                Document.document_type.label("document_type"),
                Document.fiscal_period.label("fiscal_period"),
            )
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.workspace_id == bindparam("workspace_id"))
        )

        parameters: dict[str, Any] = {
            "query_embedding": _vector_literal(query_vector),
            "workspace_id": workspace_id,
            "limit": effective_limit,
        }

        if document_ids is not None:
            statement = statement.where(
                Document.id.in_(bindparam("document_ids", expanding=True))
            )
            parameters["document_ids"] = list(document_ids)

        if chunk_types is not None:
            normalised = [self._validated_chunk_type(chunk_type) for chunk_type in chunk_types]
            statement = statement.where(
                DocumentChunk.chunk_type.in_(
                    bindparam("chunk_types", type_=String, expanding=True)
                )
            )
            parameters["chunk_types"] = normalised

        statement = statement.order_by(distance).limit(bindparam("limit", type_=Integer))

        with self._session_scope() as session:
            rows = session.execute(statement, parameters).all()

        return [
            SearchHit(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                workspace_id=row.workspace_id,
                content=row.content,
                score=float(row.score),
                page_start=row.page_start,
                page_end=row.page_end,
                section_heading=row.section_heading,
                chunk_type=row.chunk_type,
                metadata=row.metadata_json or {},
                document_title=row.document_title,
                company_name=row.company_name,
                document_type=row.document_type,
                fiscal_period=row.fiscal_period,
            )
            for row in rows
        ]

    def delete_document_chunks(self, document_id: UUID) -> int:
        """Delete every chunk of *document_id* and return the row count."""
        statement = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        with self._session_scope() as session:
            result = session.execute(statement)
            return int(result.rowcount or 0)

    def count_chunks(self, document_id: UUID | None = None) -> int:
        """Return the number of stored chunks, optionally of one document."""
        statement = select(func.count()).select_from(DocumentChunk)
        if document_id is not None:
            statement = statement.where(DocumentChunk.document_id == document_id)
        with self._session_scope() as session:
            return int(session.execute(statement).scalar_one())

    def get_existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``."""
        statement = select(
            DocumentChunk.content_hash,
            DocumentChunk.embedding_config_hash,
            DocumentChunk.embedding,
        ).where(DocumentChunk.document_id == document_id)
        with self._session_scope() as session:
            rows = session.execute(statement).all()
        return {
            row.content_hash: (row.embedding_config_hash, list(row.embedding))
            for row in rows
        }

    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``.

        The method is an alias of :meth:`get_existing_embeddings`; it exists
        so that the store satisfies the ``ExistingEmbeddingSource`` protocol
        of :mod:`app.ingestion.pipeline` and can therefore be injected into
        the pipeline directly.
        """
        return self.get_existing_embeddings(document_id)
