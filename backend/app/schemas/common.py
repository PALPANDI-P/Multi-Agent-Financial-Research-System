"""Shared Pydantic v2 response and error contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "PageMeta",
]


class PageMeta(BaseModel):
    """Pagination metadata attached to list responses."""

    total: int = 0
    limit: int = 50
    offset: int = 0


class ErrorDetail(BaseModel):
    """The payload of the ``error`` member of an error envelope."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error envelope returned for every non 2xx response."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Service health payload used by the health endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: str
    app: str
    version: str
    environment: str
    timestamp: datetime
    checks: dict[str, str] = Field(default_factory=dict)