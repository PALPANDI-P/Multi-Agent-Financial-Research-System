"""Workspace request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "WorkspaceCreate",
    "WorkspaceListResponse",
    "WorkspaceRead",
    "WorkspaceUpdate",
]


class WorkspaceCreate(BaseModel):
    """Payload used to create a workspace."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceUpdate(BaseModel):
    """Payload used to update a workspace.

    Every field is optional.  A field that is present is validated; ``name``
    set to ``None`` means "leave unchanged", ``description`` set to ``None``
    clears the description.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceRead(BaseModel):
    """A workspace as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkspaceListResponse(BaseModel):
    """A page of workspaces."""

    model_config = ConfigDict(extra="forbid")

    items: list[WorkspaceRead] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0