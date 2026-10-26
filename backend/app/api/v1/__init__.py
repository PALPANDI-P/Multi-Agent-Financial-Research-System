"""The routers of the first API version.

Every router of this package is mounted under the ``/api/v1`` prefix by
:mod:`app.api.router`.
"""

from __future__ import annotations

from app.api.v1 import auth, documents, health, search, workspaces

__all__ = ["auth", "documents", "health", "search", "workspaces"]