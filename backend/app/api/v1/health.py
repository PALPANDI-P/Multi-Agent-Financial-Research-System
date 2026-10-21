"""The health endpoint of the API.

The endpoint answers the question "is the service able to serve requests?"
and never leaks a secret: the checks report the *state* of a dependency,
never its configuration.  The connection string, the password and the
internal paths of the server are therefore never part of the response.

Degraded state
--------------
A failing dependency does **not** fail the request: the process is alive
and answers with ``200`` and ``status="degraded"``.  A load balancer must
not take a healthy process out of rotation because a single dependency is
down, and the client of the health endpoint wants to know *what* is broken,
not that something is broken.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import SettingsDep, get_embedding_service, get_session_factory
from app.embeddings.service import EmbeddingService
from app.schemas.common import HealthResponse

__all__ = ["router"]

router = APIRouter(tags=["health"])

#: The message that is reported when the database cannot be reached.
DATABASE_UNAVAILABLE = "unavailable: the database is not reachable"

#: The message that is reported when the pgvector extension is missing.
PGVECTOR_UNAVAILABLE = "unavailable: the pgvector extension is not installed"

#: The message that is reported when the storage root is missing.
STORAGE_MISSING = "unavailable: the storage root does not exist"

#: The message that is reported when the storage root is not writable.
STORAGE_NOT_WRITABLE = "unavailable: the storage root is not writable"

#: The prefix of the state of a dependency that is not available.
UNAVAILABLE_PREFIX = "unavailable"


def _check_database(
    session_factory: Callable[[], Session],
) -> tuple[str, str]:
    """Return the state of the database and of the pgvector extension."""
    try:
        started = time.perf_counter()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            try:
                version = session.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                ).scalar()
            except Exception:
                version = None
    except Exception:
        return DATABASE_UNAVAILABLE, PGVECTOR_UNAVAILABLE

    database_state = f"ok ({elapsed_ms:.0f} ms)"
    if version is None:
        return database_state, PGVECTOR_UNAVAILABLE
    return database_state, str(version)


def _check_embeddings(embedding_service: EmbeddingService) -> str:
    """Return the state of the embedding provider.

    The *cheap* health check of the provider is used: it never loads the
    model, therefore the endpoint stays fast even when the model was never
    used before.
    """
    provider = embedding_service.provider
    label = f"{provider.model_id} (dimension {provider.dimension})"
    try:
        health = provider.health()
    except Exception:  # a health check never raises
        return f"{UNAVAILABLE_PREFIX}: {label}"
    if not health.ok:
        return f"{UNAVAILABLE_PREFIX}: {label}"
    return label


def _check_storage(root) -> str:
    """Return the state of the storage backend."""
    try:
        if not root.exists() or not root.is_dir():
            return STORAGE_MISSING
        if not os.access(root, os.W_OK):
            return STORAGE_NOT_WRITABLE
    except OSError:
        return STORAGE_NOT_WRITABLE
    return "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Report the health of the service and of its dependencies",
)
def health(
    settings: SettingsDep,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> HealthResponse:
    """Return the health of the service.

    The response is always ``200``: a failing dependency is reported as
    ``status="degraded"`` instead of as an error, because the process is
    alive and can still answer (and because the client wants to know
    *which* dependency is broken).
    """
    database_state, pgvector_state = _check_database(session_factory)

    checks: dict[str, str] = {
        "database": database_state,
        "pgvector": pgvector_state,
        "embeddings": _check_embeddings(embedding_service),
        "storage": _check_storage(settings.storage_root),
    }

    degraded = any(state.startswith(UNAVAILABLE_PREFIX) for state in checks.values())

    return HealthResponse(
        status="degraded" if degraded else "ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
        checks=checks,
    )