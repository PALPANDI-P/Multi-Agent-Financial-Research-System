"""The search endpoint of the API.

Workspace isolation
-------------------
The workspace of the path is the **only** scope of a search: it is handed
to the vector store, which enforces it in SQL (``documents.workspace_id =
:workspace_id`` is part of the ``WHERE`` clause).  A document of another
workspace can therefore never be returned - not even when its id is
supplied by the client.

The document ids of a request are verified against the workspace before the
query runs: an id that belongs to another workspace is **dropped** (it is
not an error, the client simply asked for something that is not in the
scope of the request).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from app.api.deps import get_document_service, get_search_service, get_workspace_service
from app.core.exceptions import NotFoundError
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.services.workspace_service import WorkspaceService

__all__ = ["SearchRequestBody", "router"]

router = APIRouter(tags=["search"])


class SearchRequestBody(SearchRequest):
    """The body of a search request.

    It only relaxes the **upper** bound of ``limit``: a limit above the
    maximum the server can serve is clamped instead of rejected, so that a
    client that asks for more hits than the server is willing to return
    still gets an answer.  Every other rule of
    :class:`~app.schemas.search.SearchRequest` (the length of the query,
    the lower bound of the limit, the rejection of unknown fields) is
    unchanged.
    """

    limit: int = Field(default=10, ge=1)


def _documents_of_workspace(
    document_ids: list[UUID],
    workspace_id: UUID,
    service: DocumentService,
) -> list[UUID]:
    """Return the ids of *document_ids* that belong to *workspace_id*.

    An id that does not exist and an id that belongs to another workspace
    are dropped: a search must never leave the scope of its workspace.
    """
    allowed: list[UUID] = []
    for document_id in document_ids:
        try:
            document = service.get_document(document_id)
        except NotFoundError:
            continue
        if document.workspace_id == workspace_id:
            allowed.append(document_id)
    return allowed


@router.post(
    "/workspaces/{workspace_id}/search",
    response_model=SearchResponse,
    summary="Search the documents of a workspace",
)
def search(
    workspace_id: UUID,
    payload: SearchRequestBody,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    search_service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    """Search the chunks of the workspace *workspace_id*.

    An unknown workspace is answered with ``404``; a workspace without
    indexed documents is answered with an empty result list - it is not an
    error.
    """
    workspace_service.get_workspace(workspace_id)

    document_ids: list[UUID] | None = None
    if payload.document_ids is not None:
        document_ids = _documents_of_workspace(
            payload.document_ids,
            workspace_id,
            document_service,
        )

    results = search_service.search(
        workspace_id=workspace_id,
        query=payload.query,
        limit=payload.limit,
        document_ids=document_ids,
        chunk_types=payload.chunk_types,
    )

    return SearchResponse(
        query=results.query,
        workspace_id=results.workspace_id,
        total=results.total,
        results=[
            SearchResultItem.model_validate(item, from_attributes=True)
            for item in results.results
        ],
        took_ms=results.took_ms,
    )