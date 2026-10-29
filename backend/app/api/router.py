"""The router that collects the routers of the first API version."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_session
from app.api.v1 import auth, documents, financial, health, search, workspaces

__all__ = ["api_router"]

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)

api_router.include_router(
    workspaces.router,
    dependencies=[Depends(require_session)],
)
api_router.include_router(
    documents.router,
    dependencies=[Depends(require_session)],
)
api_router.include_router(
    search.router,
    dependencies=[Depends(require_session)],
)
api_router.include_router(
    financial.router,
    dependencies=[Depends(require_session)],
)
