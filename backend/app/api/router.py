"""The router that collects the routers of the first API version.

Authentication
--------------
Every router that is **not** public carries the dependency
:func:`app.api.deps.require_session` on the router itself.  The dependency
is therefore applied to *every* route of the router, and a new route can
never be forgotten: it is protected as well.

The public routers are the health check and the authentication (the login,
the registration and the list of the demo scenarios).  The two endpoints of
the authentication that need a session (``/auth/me`` and ``/auth/logout``)
carry the dependency on the route itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_session
from app.api.v1 import auth, documents, health, search, workspaces

__all__ = ["api_router"]

api_router = APIRouter()

# ---- the public routers ----------------------------------------------------
api_router.include_router(health.router)
api_router.include_router(auth.router)

# ---- the protected routers -------------------------------------------------
# The dependency is applied on the router: every route of these routers
# requires a session and a new route inherits the protection.
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