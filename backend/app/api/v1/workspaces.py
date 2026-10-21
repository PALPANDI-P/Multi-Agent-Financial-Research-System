"""The workspace endpoints of the API.

A workspace is the container of the documents of a research project.  The
endpoints are thin: they translate the request into a call of the workspace
service and the summary the service returns into the response schema.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_workspace_service
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

__all__ = ["router"]

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

#: The maximum number of workspaces a single page may contain.
MAX_PAGE_SIZE = 100


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
def create_workspace(
    payload: WorkspaceCreate,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceRead:
    """Create a workspace and return it."""
    summary = service.create_workspace(
        name=payload.name,
        description=payload.description,
    )
    return WorkspaceRead.model_validate(summary)


@router.get(
    "",
    response_model=WorkspaceListResponse,
    summary="List the workspaces",
)
def list_workspaces(
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    name: str | None = Query(default=None, max_length=255),
) -> WorkspaceListResponse:
    """Return a page of workspaces and the total number of workspaces."""
    summaries, total = service.list_workspaces(
        limit=limit,
        offset=offset,
        name_contains=name,
    )
    return WorkspaceListResponse(
        items=[WorkspaceRead.model_validate(summary) for summary in summaries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceRead,
    summary="Return a single workspace",
)
def get_workspace(
    workspace_id: UUID,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceRead:
    """Return the workspace *workspace_id*."""
    summary = service.get_workspace(workspace_id)
    return WorkspaceRead.model_validate(summary)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceRead,
    summary="Update a workspace",
)
def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceRead:
    """Update the workspace *workspace_id*.

    Only the fields that the client actually sent are written: an omitted
    field keeps its value, an explicit ``null`` clears the description.
    """
    changes = payload.model_dump(exclude_unset=True)
    summary = service.update_workspace(
        workspace_id,
        **changes,
    )
    return WorkspaceRead.model_validate(summary)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a workspace",
)
def delete_workspace(
    workspace_id: UUID,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> Response:
    """Delete the workspace *workspace_id* and every document it owns."""
    service.delete_workspace(workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)