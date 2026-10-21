"""Document ORM model.

A document is an uploaded file that has been registered for processing.
``processing_status`` mirrors the state of the ingestion pipeline and uses
the explicit per-stage states of :class:`app.core.enums.ProcessingStatus`
(``queued`` -> ``validating`` -> ``extracting`` -> ``chunking`` ->
``embedding`` -> ``indexing`` -> ``completed``, plus ``failed``).

``processing_stage`` is supplementary detail only (for example ``pdf_text``,
``pdf_tables`` or ``ocr``).  It is **not** an independent status: the
authoritative state is ``processing_status``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ProcessingStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["Document", "DocumentProcessingStatus"]

#: Allowed values of ``documents.processing_status``.
DOCUMENT_PROCESSING_STATUSES: tuple[str, ...] = tuple(
    status.value for status in ProcessingStatus
)

#: ``VARCHAR(32)`` plus a CHECK constraint (no native PostgreSQL enum type).
#: For a non-native enum SQLAlchemy uses ``name`` as the name of the CHECK
#: constraint, therefore it must be the constraint name required by the
#: public contract: ``ck_documents_processing_status``.
DocumentProcessingStatus = SAEnum(
    ProcessingStatus,
    name="ck_documents_processing_status",
    native_enum=False,
    length=32,
    create_constraint=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered source document that is (or was) being processed."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "content_hash",
            name="uq_documents_workspace_content_hash",
        ),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        Index("ix_documents_workspace_id", "workspace_id"),
        Index(
            "ix_documents_workspace_id_processing_status",
            "workspace_id",
            "processing_status",
        ),
        Index("ix_documents_content_hash", "content_hash"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)

    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    processing_status: Mapped[str] = mapped_column(
        DocumentProcessingStatus,
        nullable=False,
        default=ProcessingStatus.QUEUED.value,
        server_default=ProcessingStatus.QUEUED.value,
    )
    processing_stage: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "Supplementary sub-stage detail (for example 'pdf_text', "
            "'pdf_tables' or 'ocr'). NOT an independent status: the "
            "authoritative state is 'processing_status'."
        ),
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
