"""Document request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DocumentListResponse",
    "DocumentMetadata",
    "DocumentRead",
    "DocumentUploadResponse",
    "RetryResponse",
]


class DocumentMetadata(BaseModel):
    """Optional metadata supplied alongside an upload."""

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, max_length=255)
    document_title: str | None = Field(default=None, max_length=512)
    document_type: str | None = Field(default=None, max_length=64)
    fiscal_period: str | None = Field(default=None, max_length=64)
    source_url: str | None = None


class DocumentRead(BaseModel):
    """A document as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    original_filename: str
    content_hash: str
    file_size_bytes: int
    mime_type: str
    company_name: str | None = None
    document_title: str | None = None
    document_type: str | None = None
    fiscal_period: str | None = None
    source_url: str | None = None
    page_count: int | None = None
    processing_status: str
    processing_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
    chunk_count: int = 0


class DocumentListResponse(BaseModel):
    """A page of documents."""

    model_config = ConfigDict(extra="forbid")

    items: list[DocumentRead] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class DocumentUploadResponse(BaseModel):
    """Result of an upload request."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    processing_status: str
    processing_stage: str | None = None
    content_hash: str
    duplicate: bool = False


class RetryResponse(BaseModel):
    """Result of a retry request for a failed document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    job_id: UUID
    attempt_count: int
    processing_status: str