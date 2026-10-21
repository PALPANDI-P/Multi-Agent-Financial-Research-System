"""Pydantic v2 request/response contracts shared across the API."""

from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PageMeta,
)
from app.schemas.document import (
    DocumentListResponse,
    DocumentMetadata,
    DocumentRead,
    DocumentUploadResponse,
    RetryResponse,
)
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
    WorkspaceUpdate,
)

__all__ = [
    "DocumentListResponse",
    "DocumentMetadata",
    "DocumentRead",
    "DocumentUploadResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "PageMeta",
    "RetryResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "WorkspaceCreate",
    "WorkspaceListResponse",
    "WorkspaceRead",
    "WorkspaceUpdate",
]