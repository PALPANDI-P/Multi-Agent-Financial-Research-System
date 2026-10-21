"""Persistence operations for the ``document_chunks`` table."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document

__all__ = ["ChunkRepository"]


class ChunkRepository:
    """CRUD operations for :class:`~app.db.models.chunk.DocumentChunk`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def delete_by_document(self, document_id: UUID, *, commit: bool = True) -> int:
        """Delete every chunk of *document_id*; return the number of rows."""
        statement = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = self._session.execute(statement)
        if commit:
            self._session.commit()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``.

        The mapping is the input of
        :meth:`~app.embeddings.service.EmbeddingService.embed_texts_reusing`:
        a stored vector is only reused when its configuration hash still
        matches the current one.
        """
        statement = select(
            DocumentChunk.content_hash,
            DocumentChunk.embedding_config_hash,
            DocumentChunk.embedding,
        ).where(DocumentChunk.document_id == document_id)
        rows = self._session.execute(statement).all()
        return {row[0]: (row[1], list(row[2])) for row in rows}

    def count_by_document(self, document_id: UUID) -> int:
        """Return the number of chunks of *document_id*."""
        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        return int(self._session.execute(statement).scalar_one())

    def count_by_documents(self, document_ids: Sequence[UUID]) -> dict[UUID, int]:
        """Return ``{document_id: chunk_count}`` for the given documents.

        The counts are collected with **one** grouped statement - a
        per-document query would be an N+1 access pattern.
        """
        identifiers = list(document_ids)
        if not identifiers:
            return {}

        statement = (
            select(DocumentChunk.document_id, func.count())
            .where(DocumentChunk.document_id.in_(identifiers))
            .group_by(DocumentChunk.document_id)
        )
        rows = self._session.execute(statement).all()
        return {row[0]: int(row[1]) for row in rows}

    def count_by_workspace(self, workspace_id: UUID) -> int:
        """Return the number of chunks of every document of *workspace_id*."""
        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.workspace_id == workspace_id)
        )
        return int(self._session.execute(statement).scalar_one())

    def list_by_document(
        self,
        document_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[DocumentChunk]:
        """Return a page of the chunks of *document_id*."""
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(statement).scalars().all())