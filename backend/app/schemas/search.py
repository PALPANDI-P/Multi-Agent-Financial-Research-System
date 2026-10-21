"""Semantic search request/response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["SearchRequest", "SearchResponse", "SearchResultItem"]


class SearchRequest(BaseModel):
    """A semantic search request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    document_ids: list[UUID] | None = None
    chunk_types: list[str] | None = None


class SearchResultItem(BaseModel):
    """A single search hit."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    document_title: str | None = None
    company_name: str | None = None
    document_type: str | None = None
    fiscal_period: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_heading: str | None = None
    chunk_type: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """The result of a semantic search request."""

    model_config = ConfigDict(extra="forbid")

    query: str
    workspace_id: UUID | None = None
    total: int = 0
    results: list[SearchResultItem] = Field(default_factory=list)
    took_ms: float = 0.0