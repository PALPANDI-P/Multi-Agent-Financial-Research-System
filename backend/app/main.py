"""The FastAPI application of the Multi-Agent Financial Research System.

The application is built by the factory :func:`create_app`, therefore a
test can build an application with its own settings (a test database, a
temporary storage root) without touching the environment of the process.

Middlewares
-----------
The stack of the application is (from the outside to the inside):

``RequestIdMiddleware``
    Reads the ``X-Request-ID`` header of the request (or generates one),
    binds it to the logging context and writes it into the response.  The
    id of a request is therefore the same in the log and in the error
    envelope of the response.
``CORSMiddleware``
    Serves the browser clients of the frontend.
``MaxRequestSizeMiddleware``
    Rejects a request whose ``Content-Length`` exceeds the configured
    maximum with ``413`` - before the body is read at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.agents.job_runner import BackgroundThreadJobRunner
from app.api.deps import get_job_runner
from app.api.errors import error_response, register_exception_handlers
from app.api.router import api_router
from app.api.v1.auth import authentication_error_handler
from app.core.config import Settings, get_settings, validate_runtime_settings
from app.core.exceptions import AuthenticationError, ConfigurationError
from app.core.logging import bind_context, clear_context, configure_logging, get_logger

__all__ = ["app", "create_app"]

logger = get_logger(__name__)

#: The title of the OpenAPI document.
API_TITLE = "Multi-Agent Financial Research System API"

#: The description of the OpenAPI document.
API_DESCRIPTION = """
The HTTP API of the Multi-Agent Financial Research System.

The API manages **workspaces** (the container of a research project) and
the **documents** that are uploaded into them, and it answers **semantic
search** queries over the indexed chunks of a workspace.

Processing
----------
An upload is registered, validated and then handed to the job runner.  The
status that the upload endpoint reports is the real status of the document:
with the inline runner the document was processed completely when the
answer was written, with the background runner it is still being processed.

Errors
------
Every non 2xx response carries the same envelope::

    {"error": {"code": "...", "message": "...", "details": {}, "request_id": "..."}}

The `code` is stable and machine readable, the `request_id` is the id of
the request in the log of the server.
""".strip()


class RequestIdMiddleware:
    """Bind a request id to the logging context of every request.

    The id is taken from the ``X-Request-ID`` header of the request or
    generated.  It is written into the response header of the same name and
    into the log records of the request.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap *app*."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the request id to the scope, the log and the response."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or uuid4().hex
        bind_context(request_id=request_id)
        # The scope is shared by every layer of the stack, therefore the id
        # is also visible to the error handler of the framework, which runs
        # *outside* of this middleware.
        scope["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except BaseException:
            # The context stays bound: the error handler of the framework
            # runs outside of this middleware and still needs the id of the
            # request for its log record.  The handler clears the context.
            raise
        else:
            clear_context()


class MaxRequestSizeMiddleware:
    """Reject a request whose body is larger than the configured maximum.

    The check uses the ``Content-Length`` header, therefore the body of an
    oversized request is never read.  The upload endpoint enforces the very
    same limit again while it streams the file, because a client may lie
    about the length of the body.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        """Wrap *app*; *max_bytes* is the maximum length of a body."""
        self.app = app
        self.max_bytes = int(max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer with ``413`` when the body is too large."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        raw_length = headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                length = None
            if length is not None and length > self.max_bytes:
                response = error_response(
                    "payload_too_large",
                    "the request body exceeds the maximum allowed size",
                    status_code=413,
                    details={"max_upload_size_bytes": self.max_bytes},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _index(settings: Settings) -> dict[str, Any]:
    """Return the tiny index of the API."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": "/api/v1",
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Parameters
    ----------
    settings:
        The configuration of the application.  When it is omitted the
        cached settings of the process are used.

    Raises
    ------
    app.core.exceptions.ConfigurationError
        If the configuration is invalid or unsafe.  The application refuses
        to start with a broken configuration instead of failing at the first
        request.
    """
    config = settings if settings is not None else get_settings()

    configure_logging(config)
    try:
        validate_runtime_settings(config)
    except ConfigurationError as exc:
        raise ConfigurationError(
            f"the application cannot start: {exc.message}",
            code=exc.code,
            details=exc.details,
        ) from exc

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Prepare the storage and the background worker of the process."""
        try:
            config.storage_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("the storage root could not be created")

        runner = get_job_runner(config)
        if isinstance(runner, BackgroundThreadJobRunner):
            runner.start()
            recovered = runner.run_pending()
            if recovered:
                logger.info("%s queued document(s) were recovered", recovered)
        try:
            yield
        finally:
            if isinstance(runner, BackgroundThreadJobRunner) and runner.is_running:
                runner.stop()

    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=config.app_version,
        lifespan=lifespan,
    )
    app.state.settings = config

    # The order of the calls matters: the last middleware that is added is
    # the outermost one.  The request id therefore surrounds everything,
    # the CORS middleware surrounds the size limit (so that a 413 also
    # carries the CORS headers).
    app.add_middleware(
        MaxRequestSizeMiddleware,
        max_bytes=config.max_upload_size_bytes,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    # The authentication error carries a ``WWW-Authenticate`` header; it is
    # registered separately because the generic handler of the domain errors
    # does not know about it.
    app.add_exception_handler(AuthenticationError, authentication_error_handler)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["index"], summary="A tiny index of the API")
    def index() -> dict[str, Any]:
        """Return the name, the version and the entry points of the API."""
        return _index(config)

    return app


#: The application the process serves (``uvicorn app.main:app``).
app = create_app()