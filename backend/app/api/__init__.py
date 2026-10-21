"""The HTTP API layer of the Multi-Agent Financial Research System.

The package is split into four parts:

``app.api.deps``
    The dependency providers.  Every service of the application is built
    here, from the settings alone, and is cached so that the expensive
    components (the engine, the embedding model, the vector store) are
    created once.
``app.api.errors``
    The exception handlers that translate a domain error into the standard
    error envelope.
``app.api.v1``
    The routers of the first API version.
``app.api.router``
    The router that collects the v1 routers.
"""

from __future__ import annotations

__all__ = ["router"]