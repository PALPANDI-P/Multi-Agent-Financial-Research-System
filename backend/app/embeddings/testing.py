"""TEST-ONLY deterministic embedding provider.

.. warning::

    This module exists **only** so that unit tests can run without a model.
    It must never be used in production.

The vectors produced here are **deterministic and NON-SEMANTIC**: they are
derived from a SHA-256 digest of the text, not from a language model.  Two
identical texts always produce the identical vector and two different texts
always produce different vectors, which is what the tests need - but the
*direction* of a vector carries no meaning at all, so distances and
similarities computed from these vectors are meaningless as well.

The provider is flagged with the ``__test_only__`` class attribute and it is
deliberately **not** re-exported by :mod:`app.embeddings`, so production code
cannot pick it up by accident.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from app.embeddings.base import EmbeddingProviderHealth

__all__ = ["TEST_PROVIDER_NAME", "DeterministicHashEmbeddingProvider"]

#: Name under which the test provider is selected in the settings.
TEST_PROVIDER_NAME = "test-hash"


class DeterministicHashEmbeddingProvider:
    """Deterministic, non semantic embedding provider used by the tests.

    Parameters
    ----------
    dimension:
        Length of the produced vectors.
    """

    #: Marks the class as test-only; the factory refuses it in production.
    __test_only__ = True

    def __init__(self, dimension: int = 384) -> None:
        if dimension < 1:
            raise ValueError("dimension must be a positive integer")
        self._dimension = int(dimension)

    @property
    def model_id(self) -> str:
        """Return the identifier of the (fake) model."""
        return "test-hash-provider"

    @property
    def dimension(self) -> int:
        """Return the length of every produced vector."""
        return self._dimension

    def _vector(self, text: str) -> list[float]:
        """Return the deterministic vector of *text*."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()

        # Expand the digest to as many bytes as the vector needs.
        blocks: list[bytes] = []
        counter = 0
        while sum(len(block) for block in blocks) < self._dimension:
            blocks.append(
                hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
            )
            counter += 1
        raw = b"".join(blocks)[: self._dimension]

        values = [byte / 255.0 for byte in raw]
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 0.0:
            # Practically unreachable (a SHA-256 digest is never all zero),
            # but the contract demands a vector that is never all zeros.
            values = [1.0, *([0.0] * (self._dimension - 1))]
            norm = 1.0
        return [value / norm for value in values]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one deterministic vector per text, in the input order."""
        return [self._vector(text) for text in texts]

    def health(self) -> EmbeddingProviderHealth:
        """Return the (always positive) health of the test provider."""
        return EmbeddingProviderHealth(True, "test-only deterministic provider")

    def probe(self) -> EmbeddingProviderHealth:
        """Return the (always positive) result of an end-to-end probe."""
        return EmbeddingProviderHealth(True, "test-only deterministic provider")
