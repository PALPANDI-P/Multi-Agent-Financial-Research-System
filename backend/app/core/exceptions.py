"""Domain exception hierarchy for the Multi-Agent Financial Research System.

Every error raised by the application inherits from :class:`AppError` and
carries three stable pieces of metadata:

``code``
    A machine readable, stable string (for example ``"not_found"``).  The
    codes are part of the public API contract: they are returned verbatim in
    the ``error.code`` field of the API error envelope.
``message``
    A human readable description.  Messages may change between releases.
``details``
    A JSON-serialisable mapping with additional diagnostic context.
``error_code``
    An optional, finer grained diagnosis (for example ``"ocr_unavailable"``)
    that is distinct from the stable envelope ``code``.  It is used by the
    job records and is mirrored into :attr:`details` so that it can never be
    lost when the error is serialised.

Each exception also exposes an ``http_status`` so the API layer (Wave 5) can
translate a domain error into an HTTP response without a lookup table.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AppError",
    "ChunkingError",
    "ConfigurationError",
    "ConflictError",
    "EmbeddingError",
    "ExtractionError",
    "NotFoundError",
    "ProcessingError",
    "StorageError",
    "ValidationError",
    "VectorStoreError",
]


class AppError(Exception):
    """Base class for every error raised by the application.

    Parameters
    ----------
    message:
        Human readable description of the failure.
    code:
        Overrides the class level default code.  Used when a more specific
        machine readable code is required for a single occurrence.
    details:
        Optional JSON-serialisable mapping with extra diagnostic context.
    http_status:
        Overrides the class level default HTTP status code.
    """

    default_code: str = "app_error"
    default_http_status: int = 500
    default_error_code: str | None = None

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details: dict[str, Any] = dict(details) if details else {}
        self.http_status = (
            http_status if http_status is not None else self.default_http_status
        )
        self.error_code: str | None = (
            error_code if error_code is not None else self.default_error_code
        )
        if self.error_code is not None:
            self.details.setdefault("error_code", self.error_code)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable representation used by API envelopes."""
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        return payload

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ConfigurationError(AppError):
    """Raised when the application is configured with invalid or unsafe values."""

    default_code = "configuration_error"
    default_http_status = 500


class ValidationError(AppError):
    """Raised when user supplied data fails a domain level validation rule."""

    default_code = "validation_error"
    default_http_status = 422


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    default_code = "not_found"
    default_http_status = 404


class ConflictError(AppError):
    """Raised when a request conflicts with the current state of a resource."""

    default_code = "conflict"
    default_http_status = 409


class StorageError(AppError):
    """Raised when reading from or writing to the document storage backend fails."""

    default_code = "storage_error"
    default_http_status = 500


class ExtractionError(AppError):
    """Raised when text/table extraction from a document fails."""

    default_code = "extraction_error"
    default_http_status = 422


class ChunkingError(AppError):
    """Raised when a document cannot be split into chunks."""

    default_code = "chunking_error"
    default_http_status = 422


class EmbeddingError(AppError):
    """Raised when the embedding provider fails to produce a vector."""

    default_code = "embedding_error"
    default_http_status = 502


class VectorStoreError(AppError):
    """Raised when the vector store cannot serve or persist a query."""

    default_code = "vector_store_error"
    default_http_status = 500


class ProcessingError(AppError):
    """Raised when the ingestion pipeline fails while processing a document.

    ``error_code`` carries a finer grained diagnosis for the job record (for
    example ``OCR_UNAVAILABLE`` or ``EMBEDDING_TIMEOUT``).  It is distinct
    from the stable API envelope code (``processing_error``) and is surfaced
    through :attr:`details` so that it is never lost when the error is
    serialised.

    ``error_code`` is a first class attribute of :class:`AppError`.  This
    subclass only supplies the default ``"processing_error"`` so that a job
    failure always records an actionable code, while an explicit
    ``error_code=...`` still overrides it.
    """

    default_code = "processing_error"
    default_http_status = 500
    default_error_code = "processing_error"