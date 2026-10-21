"""Structured logging for the Multi-Agent Financial Research System.

The implementation uses the standard library only - no third party logging
framework is added to the dependency set.

Security rules
--------------
* **Never log secrets.**  Database URLs, API keys, passwords and bearer
  tokens must not be written to the log stream.  Use
  :func:`app.core.config._redact_url` (or an equivalent redaction helper of
  your own) before logging a connection string.
* The JSON formatter serialises ``extra`` attributes verbatim, so any value
  attached to a log record is persisted.  Do not attach sensitive data to a
  record.

Request correlation
-------------------
A :mod:`contextvars` based context carries the current request id.  Use
:func:`bind_context` to attach it (and any additional fields) and
:func:`clear_context` to reset it.  Because the context is stored in a
``ContextVar`` it is safe for concurrent async tasks and green threads.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "JsonFormatter",
    "TextFormatter",
    "bind_context",
    "clear_context",
    "configure_logging",
    "current_request_id",
    "get_logger",
]

#: Attributes that belong to :class:`logging.LogRecord` itself and must never
#: be treated as ``extra`` payload.
_RESERVED_RECORD_ATTRIBUTES: frozenset[str] = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}

_request_id: ContextVar[str | None] = ContextVar("frs_request_id", default=None)
_bound_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "frs_log_context", default=None
)

_configured = False
_handler: logging.Handler | None = None


class JsonFormatter(logging.Formatter):
    """Render log records as single line JSON documents."""

    def format(self, record: logging.LogRecord) -> str:
        """Return ``record`` serialised as a JSON object."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = _request_id.get()
        if request_id:
            payload["request_id"] = request_id

        for key, value in (_bound_context.get() or {}).items():
            payload.setdefault(key, value)

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRIBUTES or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Render log records as human readable plain text (development mode)."""

    default_time_format = "%Y-%m-%dT%H:%M:%S%z"

    def format(self, record: logging.LogRecord) -> str:
        """Return ``record`` rendered as a single text line."""
        base = super().format(record)
        request_id = _request_id.get()
        if request_id:
            return f"{base} request_id={request_id}"
        return base


def configure_logging(settings: Any | None = None) -> None:
    """Configure the root logger.

    The function is idempotent: calling it repeatedly never installs
    duplicate handlers, it only refreshes the handler with the current
    settings.

    Parameters
    ----------
    settings:
        Optional :class:`app.core.config.Settings` instance.  When omitted the
        cached settings are used.
    """
    global _configured, _handler

    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
        _handler.close()

    handler = logging.StreamHandler(sys.stdout)
    log_format = getattr(settings, "log_format", "json")
    if log_format == "text":
        handler.setFormatter(
            TextFormatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())

    root.addHandler(handler)
    root.setLevel(str(getattr(settings, "log_level", "INFO")).upper())

    _handler = handler
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return the logger identified by ``name``."""
    return logging.getLogger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind ``kwargs`` to the current logging context.

    ``request_id`` is stored in its own context variable so that the JSON
    formatter can always surface it; every other keyword is merged into the
    generic context mapping.
    """
    request_id = kwargs.pop("request_id", None)
    if request_id is not None:
        _request_id.set(str(request_id))
    if kwargs:
        _bound_context.set({**(_bound_context.get() or {}), **kwargs})


def clear_context() -> None:
    """Reset the logging context (request id and bound fields)."""
    _request_id.set(None)
    _bound_context.set(None)


def current_request_id() -> str | None:
    """Return the request id bound to the current context, if any."""
    return _request_id.get()