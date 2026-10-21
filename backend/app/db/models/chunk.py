"""Document chunk ORM model.

A chunk is a retrievable slice of a document.  It carries the embedded
vector, the provenance metadata (page range, section heading) and a hash of
the embedding configuration that produced the vector.

IMPORTANT - the embedding dimension is a *configuration* value, not a
constant.  It is read from ``EMBEDDING_DIMENSION`` (via
``app.core.config.get_settings()``) when this module is imported, and the
Alembic migration ``0001_initial`` must use exactly the same value.  The
migration reads ``os.getenv("EMBEDDING_DIMENSION", "384")``; ``migrations/env.py``
exports the configured value into the environment before the migration runs so
that both sides always agree.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base, UUIDPrimaryKeyMixin

__all__ = ["EMBEDDING_DIMENSION", "ChunkType", "DocumentChunk"]

#: Dimension of the embedding vectors stored in ``document_chunks.embedding``.
#: The Alembic migration MUST use the same value.
EMBEDDING_DIMENSION: int = get_settings().embedding_dimension

#: Allowed values of ``document_chunks.chunk_type``.
CHUNK_TYPES: tuple[str, ...] = ("text", "table")

#: ``VARCHAR(32)`` plus a CHECK constraint (no native PostgreSQL enum type).
ChunkType = SAEnum(
    *CHUNK_TYPES,
    name="ck_document_chunks_chunk_type",
    native_enum=False,
    length=32,
    create_constraint=True,
)


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    """A single retrievable chunk of a document."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
        Index("ix_document_chunks_document_id", "document_id"),
        Index(
            "ix_document_chunks_metadata_json",
            "metadata_json",
            postgresql_using="gin",
        ),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chunk_type: Mapped[str] = mapped_column(
        ChunkType,
        nullable=False,
        default="text",
        server_default="text",
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False,
    )
    embedding_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )