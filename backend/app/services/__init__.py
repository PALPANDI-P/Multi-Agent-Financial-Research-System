"""Service layer: the business rules of the Multi-Agent Financial Research
System.

A service owns the rules, opens its own short lived database sessions and
returns **frozen dataclasses** - never ORM objects and never Pydantic
schemas.  The repositories below :mod:`app.repositories` own the SQL and
never import this package, therefore the dependency arrow points in one
direction only: services -> repositories -> models.
"""

from app.services.document_service import (
    DocumentProcessor,
    DocumentRegistration,
    DocumentService,
    DocumentSummary,
    JobSummary,
)
from app.services.search_service import (
    SearchResultItem,
    SearchResults,
    SearchService,
)
from app.services.workspace_service import WorkspaceService, WorkspaceSummary

__all__ = [
    "DocumentProcessor",
    "DocumentRegistration",
    "DocumentService",
    "DocumentSummary",
    "JobSummary",
    "SearchResultItem",
    "SearchResults",
    "SearchService",
    "WorkspaceService",
    "WorkspaceSummary",
]