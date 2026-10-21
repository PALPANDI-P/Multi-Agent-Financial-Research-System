"""Production embedding provider backed by ``fastembed``.

The provider is a thin adapter around :class:`fastembed.TextEmbedding`.  Two
properties matter for the rest of the system:

* **Lazy initialisation.**  Loading an ONNX model takes seconds; the model is
  therefore created on the first :meth:`FastEmbedProvider.embed` call and
  cached on the instance afterwards.  Importing this module - and building a
  service - never touches the model files.
* **Serialised inference.**  The ONNX runtime session is not guaranteed to be
  thread safe, so the actual inference call is guarded by a lock.

The retry policy deliberately does *not* live here: it belongs to
:class:`app.embeddings.service.EmbeddingService`, which is the only component
that knows how many attempts a single embedding request may cost.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

from app.core.exceptions import EmbeddingError
from app.embeddings.base import EmbeddingProviderHealth, build_embedding_error

__all__ = ["FastEmbedProvider"]


class FastEmbedProvider:
    """Embed text with a local ``fastembed`` ONNX model.

    Parameters
    ----------
    model_id:
        Name of the model, e.g. ``"BAAI/bge-small-en-v1.5"``.
    dimension:
        Expected length of every produced vector.
    batch_size:
        Number of texts handed to the model in a single inference call.
    max_retries:
        Recorded for introspection; the retry itself is performed by
        :class:`app.embeddings.service.EmbeddingService`.
    timeout_seconds:
        Recorded for introspection; see ``max_retries``.
    cache_dir:
        Optional directory holding the downloaded model files.  ``None`` uses
        the default ``fastembed`` cache location.
    """

    def __init__(
        self,
        model_id: str,
        *,
        dimension: int = 384,
        batch_size: int = 32,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
        cache_dir: str | None = None,
    ) -> None:
        self._model_id = str(model_id)
        self._dimension = int(dimension)
        self._batch_size = max(1, int(batch_size))
        self._max_retries = max(0, int(max_retries))
        self._timeout_seconds = float(timeout_seconds)
        self._cache_dir = cache_dir
        self._model: Any | None = None
        self._model_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    # ------------------------------------------------------------------
    # read-only configuration
    # ------------------------------------------------------------------
    @property
    def model_id(self) -> str:
        """Return the identifier of the embedded model."""
        return self._model_id

    @property
    def dimension(self) -> int:
        """Return the expected vector length."""
        return self._dimension

    @property
    def batch_size(self) -> int:
        """Return the number of texts per inference call."""
        return self._batch_size

    @property
    def max_retries(self) -> int:
        """Return the configured retry budget (informational)."""
        return self._max_retries

    @property
    def timeout_seconds(self) -> float:
        """Return the configured timeout budget (informational)."""
        return self._timeout_seconds

    # ------------------------------------------------------------------
    # model handling
    # ------------------------------------------------------------------
    def _ensure_model(self) -> Any:
        """Return the underlying model, creating it on first use."""
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(self._model_id, cache_dir=self._cache_dir)
        return self._model

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Embed a single batch of texts."""
        try:
            model = self._ensure_model()
            with self._inference_lock:
                raw = list(model.embed(batch))
        except EmbeddingError:
            raise
        except Exception as exc:  # any provider failure is fatal here
            raise build_embedding_error(
                f"embedding provider {self._model_id!r} failed: {exc}",
                error_code="embedding_provider_error",
                details={"provider": self._model_id},
            ) from exc

        if len(raw) != len(batch):
            raise build_embedding_error(
                f"embedding provider {self._model_id!r} returned {len(raw)} vectors "
                f"for {len(batch)} texts",
                error_code="embedding_count_mismatch",
                details={"expected_count": len(batch), "actual_count": len(raw)},
            )

        vectors: list[list[float]] = []
        for index, vector in enumerate(raw):
            try:
                values = [float(component) for component in vector]
            except (TypeError, ValueError) as exc:
                raise build_embedding_error(
                    f"embedding provider {self._model_id!r} returned a non numeric vector "
                    f"at index {index}",
                    error_code="embedding_invalid_vector",
                    details={"index": index},
                ) from exc
            if len(values) != self._dimension:
                raise build_embedding_error(
                    f"embedding provider {self._model_id!r} returned a vector with "
                    f"{len(values)} components, expected {self._dimension}",
                    error_code="embedding_dimension_mismatch",
                    details={
                        "index": index,
                        "actual_dimension": len(values),
                        "expected_dimension": self._dimension,
                    },
                )
            vectors.append(values)
        return vectors

    # ------------------------------------------------------------------
    # provider protocol
    # ------------------------------------------------------------------
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given."""
        items = list(texts)
        if not items:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(items), self._batch_size):
            vectors.extend(self._embed_batch(items[start : start + self._batch_size]))
        return vectors

    def health(self) -> EmbeddingProviderHealth:
        """Return a cheap readiness check.  Never raises."""
        try:
            if self._model is None:
                return EmbeddingProviderHealth(
                    True,
                    f"model not loaded yet (lazily initialized): {self._model_id}",
                )
            return EmbeddingProviderHealth(True, "model loaded")
        except Exception as exc:  # a health check never raises
            return EmbeddingProviderHealth(False, f"health check failed: {exc}")

    def probe(self) -> EmbeddingProviderHealth:
        """Embed a single short text and report the observed dimension."""
        try:
            vectors = self.embed(["embedding provider probe"])
        except Exception as exc:  # a probe reports the failure instead of raising
            message = getattr(exc, "message", None) or str(exc)
            return EmbeddingProviderHealth(False, f"probe failed: {message}")
        observed = len(vectors[0]) if vectors else 0
        return EmbeddingProviderHealth(
            True,
            f"model {self._model_id} produced a {observed}-dimensional vector",
        )
