"""Processing job ORM model.

A processing job tracks one attempt of the ingestion pipeline for a
document.  ``attempt_count`` together with the unique constraint on
``(document_id, chunk_index)``-style bookkeeping lets later waves implement
retry policies without changing the schema.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["JobStatus", "ProcessingJob"]

#: Allowed values of ``processing_jobs.status``.
JOB_STATUSES: tuple[str, ...] = ("queued", "running", "completed", "failed")

#: ``VARCHAR(32)`` plus a CHECK constraint (no native PostgreSQL enum type).
JobStatus = SAEnum(
    *JOB_STATUSES,
    name="ck_processing_jobs_status",
    native_enum=False,
    length=32,
    create_constraint=True,
)


class ProcessingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One attempt of the document processing pipeline."""

    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_processing_jobs_document_id", "document_id"),
        Index(
            "ix_processing_jobs_document_id_attempt_count",
            "document_id",
            "attempt_count",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        JobStatus,
        nullable=False,
        default="queued",
        server_default="queued",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)