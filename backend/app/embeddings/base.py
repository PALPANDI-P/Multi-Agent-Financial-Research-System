"""Contract of an embedding provider.

An *embedding provider* is a replaceable adapter that turns text into dense
vectors.  It is the only place in the system that is allowed to know which
model runs, which library performs the inference and which vector dimension
comes out of it.

The business layer (ingestion pipeline, vector store, retrieval) never sees
the concrete implementation: it only ever sees the
:class:`EmbeddingProvider` protocol defined in this module.  Swapping
``BAAI/bge-small-en-v1.5`` for another model therefore means writing one
more adapter, never touching a caller.

Two flavours of health information are exposed:

``health()``
    A cheap, side effect free check.  It answers "is the provider ready to
    be used?" and must never raise.
``probe()``
    The real end-to-end check: it embeds a single short text and reports
    the observed dimension.  It may fail - that is the point of it.

This module also owns :func:`build_embedding_error`, the single factory for
:class:`app.core.exceptions.EmbeddingError` instances.  The application
exception hierarchy has no ``error_code`` attribute of its own, so the
helper attaches the stable, fine grained diagnosis (for example
``embedding_degenerate_vector``) both as an attribute and inside the
serialisable ``details`` mapping.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.core.exceptions import EmbeddingError

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderHealth",
    "build_embedding_error",
]


@dataclass(frozen=True, slots=True)
class EmbeddingProviderHealth:
    """Outcome of a provider health check or of an end-to-end probe.

    Attributes
    ----------
    ok:
        ``True`` when the provider is usable, ``False`` otherwise.
    detail:
        Human readable explanation.  It never contains secrets: only the
        model identifier, the observed dimension and the sanitised error
        message are reported.
    """

    ok: bool
    detail: str


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol every embedding adapter has to satisfy."""

    @property
    def model_id(self) -> str:
        """Return the identifier of the model that produces the vectors."""

    @property
    def dimension(self) -> int:
        """Return the length of every vector the provider returns."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""

    def health(self) -> EmbeddingProviderHealth:
        """Return a cheap readiness check.  This method never raises."""

    def probe(self) -> EmbeddingProviderHealth:
        """Return the result of a real end-to-end embedding attempt."""


def build_embedding_error(
    message: str,
    *,
    error_code: str,
    details: Mapping[str, Any] | None = None,
) -> EmbeddingError:
    """Return an :class:`EmbeddingError` carrying a stable ``error_code``.

    Parameters
    ----------
    message:
        Human readable description of the failure.
    error_code:
        Fine grained, stable diagnosis such as ``embedding_provider_error``
        or ``embedding_degenerate_vector``.
    details:
        Optional JSON-serialisable diagnostic context.
    """
    payload: dict[str, Any] = dict(details or {})
    payload.setdefault("error_code", error_code)
    error = EmbeddingError(message, code="embedding_error", details=payload)
    # ``EmbeddingError`` (unlike ``ProcessingError``) has no dedicated
    # ``error_code`` parameter, so the attribute is attached explicitly.
    error.error_code = error_code  # type: ignore[attr-defined]
    return error
