"""Embedding service: validation, embedding reuse and retry policy.

The service is the façade the rest of the backend talks to.  It owns three
responsibilities that must never be delegated to a provider implementation:

**Validation**
    Every vector that leaves the service has been checked: the number of
    vectors matches the number of texts, every vector has the expected
    dimension, every component is finite and no vector is degenerate (an L2
    norm of zero).  A broken provider therefore fails loudly instead of
    silently poisoning the vector store.

**Reuse**
    :meth:`EmbeddingService.embed_texts_reusing` reuses previously computed
    vectors as long as the embedding configuration did not change.  The
    configuration is identified by :attr:`EmbeddingService.config_hash`,
    which changes whenever the model or the vector dimension changes.

**Retry**
    Only *transient* provider failures are retried, at most ``max_retries``
    times, with an exponential backoff (0.5 s, 1 s, 2 s) that has to fit
    into the total ``timeout_seconds`` budget.  Validation failures are never
    retried - a wrong dimension will not fix itself.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Mapping, Sequence

from app.core.config import Settings
from app.core.exceptions import ConfigurationError, EmbeddingError
from app.embeddings.base import EmbeddingProvider, build_embedding_error
from app.embeddings.provider import FastEmbedProvider

__all__ = ["KNOWN_MODEL_DIMENSIONS", "EmbeddingService", "create_embedding_service"]

#: First delay of the exponential backoff between two provider attempts.
_RETRY_BACKOFF_BASE_SECONDS = 0.5

#: Intrinsic dimensions of the embedding models the system knows about.
#:
#: The dimension of a model is a property of the model, not of the
#: deployment: configuring a different one is a contradiction that has to be
#: rejected before a single vector is produced.
KNOWN_MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
}

#: Error codes that describe a *transient* provider failure and may be retried.
_TRANSIENT_ERROR_CODES: frozenset[str | None] = frozenset(
    {None, "embedding_error", "embedding_provider_error"}
)


def _sleep(seconds: float) -> None:
    """Sleep between two provider attempts.

    The indirection exists so that the retry loop can be tested without
    spending real seconds on the backoff delays.
    """
    time.sleep(seconds)


class EmbeddingService:
    """Validate, retry and reuse embeddings produced by a provider."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        expected_dimension: int,
        batch_size: int = 32,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
    ) -> None:
        if expected_dimension < 1:
            raise ValueError("expected_dimension must be a positive integer")
        self._provider = provider
        self._expected_dimension = int(expected_dimension)
        self._batch_size = max(1, int(batch_size))
        self._max_retries = max(0, int(max_retries))
        self._timeout_seconds = float(timeout_seconds)
        self._config_hash = hashlib.sha256(
            f"{provider.model_id}|{self._expected_dimension}".encode()
        ).hexdigest()

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    @property
    def provider(self) -> EmbeddingProvider:
        """Return the provider the service delegates to."""
        return self._provider

    @property
    def config_hash(self) -> str:
        """Return the hash of the embedding configuration.

        The hash is the SHA-256 hex digest (64 characters) of
        ``"{model_id}|{expected_dimension}"``.  It changes whenever the model
        or the vector dimension changes, which is exactly when previously
        stored vectors become unusable.
        """
        return self._config_hash

    @property
    def dimension(self) -> int:
        """Return the expected length of every vector."""
        return self._expected_dimension

    @property
    def batch_size(self) -> int:
        """Return the configured batch size."""
        return self._batch_size

    @property
    def max_retries(self) -> int:
        """Return the number of retries allowed after the first attempt."""
        return self._max_retries

    @property
    def timeout_seconds(self) -> float:
        """Return the total budget (in seconds) of the retry loop."""
        return self._timeout_seconds

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    def _validate(
        self,
        vectors: Sequence[Sequence[float]],
        expected_count: int,
    ) -> list[list[float]]:
        """Return the validated vectors or raise :class:`EmbeddingError`."""
        if len(vectors) != expected_count:
            raise build_embedding_error(
                f"embedding provider returned {len(vectors)} vectors for "
                f"{expected_count} texts",
                error_code="embedding_count_mismatch",
                details={"expected_count": expected_count, "actual_count": len(vectors)},
            )

        validated: list[list[float]] = []
        for index, vector in enumerate(vectors):
            try:
                values = [float(component) for component in vector]
            except (TypeError, ValueError) as exc:
                raise build_embedding_error(
                    f"embedding vector {index} contains a non numeric component",
                    error_code="embedding_invalid_vector",
                    details={"index": index},
                ) from exc

            if len(values) != self._expected_dimension:
                raise build_embedding_error(
                    f"embedding vector {index} has dimension {len(values)}, "
                    f"expected {self._expected_dimension}",
                    error_code="embedding_dimension_mismatch",
                    details={
                        "index": index,
                        "actual_dimension": len(values),
                        "expected_dimension": self._expected_dimension,
                    },
                )

            if not all(math.isfinite(component) for component in values):
                raise build_embedding_error(
                    f"embedding vector {index} contains a non finite component",
                    error_code="embedding_non_finite_value",
                    details={"index": index},
                )

            norm = math.sqrt(sum(component * component for component in values))
            if not norm > 0.0:
                raise build_embedding_error(
                    f"embedding vector {index} is degenerate (its L2 norm is zero)",
                    error_code="embedding_degenerate_vector",
                    details={"index": index},
                )

            validated.append(values)
        return validated

    # ------------------------------------------------------------------
    # provider access
    # ------------------------------------------------------------------
    @staticmethod
    def _is_transient(error: EmbeddingError) -> bool:
        """Return ``True`` when *error* describes a retryable failure."""
        return getattr(error, "error_code", None) in _TRANSIENT_ERROR_CODES

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Return the delay (in seconds) before the retry numbered *attempt*."""
        return _RETRY_BACKOFF_BASE_SECONDS * (2**attempt)

    def _call_provider(self, items: list[str]) -> list[list[float]]:
        """Call the provider, retrying transient failures within the budget."""
        deadline = time.monotonic() + self._timeout_seconds
        attempt = 0
        while True:
            try:
                return list(self._provider.embed(items))
            except EmbeddingError as exc:
                if not self._is_transient(exc):
                    raise
                failure = exc
            except Exception as exc:  # a provider that violates its contract
                failure = build_embedding_error(
                    f"embedding provider {self._provider.model_id!r} failed: {exc}",
                    error_code="embedding_provider_error",
                    details={"provider": self._provider.model_id},
                )
                failure.__cause__ = exc

            if attempt >= self._max_retries:
                raise failure

            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise build_embedding_error(
                    "embedding provider did not succeed within the timeout budget",
                    error_code="embedding_timeout",
                    details={
                        "timeout_seconds": self._timeout_seconds,
                        "attempts": attempt + 1,
                    },
                ) from failure

            _sleep(min(self._backoff_delay(attempt), remaining))
            attempt += 1

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one validated vector per text, in the input order."""
        items = list(texts)
        if not items:
            return []
        raw = self._call_provider(items)
        return self._validate(raw, len(items))

    def embed_texts_reusing(
        self,
        texts: Sequence[str],
        content_hashes: Sequence[str],
        existing: Mapping[str, tuple[str, list[float]]],
    ) -> list[list[float]]:
        """Embed *texts*, reusing stored vectors whenever possible.

        Parameters
        ----------
        texts:
            The texts to embed.
        content_hashes:
            One content hash per text.  Must have the same length as
            *texts*.
        existing:
            Maps a content hash onto a ``(embedding_config_hash, embedding)``
            pair.  A stored vector is only reused when its stored
            ``embedding_config_hash`` equals :attr:`config_hash`.

        Returns
        -------
        list[list[float]]
            One validated vector per text, in the order of *texts*.
        """
        items = list(texts)
        hashes = list(content_hashes)
        if len(hashes) != len(items):
            raise ValueError(
                "content_hashes must have the same length as texts "
                f"({len(hashes)} != {len(items)})"
            )

        vectors: list[list[float] | None] = [None] * len(items)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        for index, content_hash in enumerate(hashes):
            stored = existing.get(content_hash)
            if stored is None:
                missing_indices.append(index)
                missing_texts.append(items[index])
                continue
            stored_config_hash, stored_vector = stored
            if stored_config_hash != self._config_hash:
                missing_indices.append(index)
                missing_texts.append(items[index])
                continue
            vectors[index] = list(stored_vector)

        if missing_texts:
            fresh = self.embed_texts(missing_texts)
            for index, vector in zip(missing_indices, fresh, strict=True):
                vectors[index] = vector

        assembled = [vector for vector in vectors if vector is not None]
        return self._validate(assembled, len(items))

    def embed_query(self, query: str) -> list[float]:
        """Return a single validated vector for *query*."""
        vectors = self.embed_texts([query])
        return vectors[0]


def create_embedding_service(settings: Settings) -> EmbeddingService:
    """Build an :class:`EmbeddingService` from the application settings.

    Only the ``fastembed`` provider is supported in this milestone.  The
    deterministic test provider is accepted for non-production environments
    only; a production deployment that selects it is rejected.
    """
    from app.embeddings.testing import TEST_PROVIDER_NAME

    supported_providers = ("fastembed", TEST_PROVIDER_NAME)
    provider_name = str(settings.embedding_provider).strip().lower()

    provider: EmbeddingProvider
    if provider_name == "fastembed":
        model_dimension = KNOWN_MODEL_DIMENSIONS.get(
            settings.embedding_model, settings.embedding_dimension
        )
        provider = FastEmbedProvider(
            settings.embedding_model,
            dimension=model_dimension,
            batch_size=settings.embedding_batch_size,
            max_retries=settings.embedding_max_retries,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    elif provider_name == TEST_PROVIDER_NAME:
        if settings.app_env == "production":
            raise ConfigurationError(
                "the test-only embedding provider must never be used when "
                "APP_ENV=production",
                details={"embedding_provider": provider_name, "app_env": settings.app_env},
            )
        from app.embeddings.testing import DeterministicHashEmbeddingProvider

        provider = DeterministicHashEmbeddingProvider(
            dimension=settings.embedding_dimension
        )
    else:
        raise ConfigurationError(
            f"unsupported EMBEDDING_PROVIDER {provider_name!r}; supported providers: "
            f"{', '.join(supported_providers)}",
            details={
                "embedding_provider": provider_name,
                "supported_providers": list(supported_providers),
            },
        )

    if provider.dimension != settings.embedding_dimension:
        raise ConfigurationError(
            "the embedding provider dimension does not match EMBEDDING_DIMENSION: "
            f"the model {provider.model_id!r} produces {provider.dimension} dimensional "
            f"vectors but {settings.embedding_dimension} were configured",
            details={
                "provider": provider.model_id,
                "provider_dimension": provider.dimension,
                "embedding_dimension": settings.embedding_dimension,
            },
        )

    return EmbeddingService(
        provider,
        expected_dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        max_retries=settings.embedding_max_retries,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
