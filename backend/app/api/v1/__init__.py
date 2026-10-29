"""The routers of the first API version."""

from __future__ import annotations

from app.api.v1 import auth, documents, financial, health, search, workspaces

__all__ = ["auth", "documents", "financial", "health", "search", "workspaces"]

