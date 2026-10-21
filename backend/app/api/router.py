"""The router that collects the routers of the first API version."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import documents, health, search, workspaces

__all__ = ["api_router"]

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)