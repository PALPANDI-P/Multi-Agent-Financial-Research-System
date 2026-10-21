"""Unit tests for the embedding package.

The bulk of the tests runs against in-memory stub providers and never
touches a model file.  Exactly one test (:func:`test_fastembed_provider_
produces_real_embeddings`) uses the real ``fastembed`` model; it is marked
``slow`` but it must pass, because it is the proof that the production
provider really works.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

import pytest

from app.core.config import Settings
from app.core.exceptions import ConfigurationError, EmbeddingError
from app.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderHealth,
    EmbeddingService,
    FastEmbedProvider,
    create_embedding_service,
)
from app.embeddings import service as service_module
from app.embeddings.base import build_embedding_error
from app.embeddings.testing import TEST_PROVIDER_NAME, DeterministicHashEmbeddingProvider

#: Dimension used by the stub providers.
DIMENSION = 4

#: A valid, normalised vector of length :data:`DIMENSION`.
VALID_VECTOR = [0.5, 0.5, 0.5, 0.5]


def _settings(**overrides: object) -> Settings:
    """Return settings that do not depend on the local ``.env`` file."""
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


class StubProvider:
    """Provider that returns canned vectors and counts its calls."""

    def __init__(
        self,
        vectors: Sequence[Sequence[float]],
        *,
        model_id: str = "stub-provider",
        dimension: int = DIMENSION,
    ) -> None:
        self.vectors = [list(vector) for vector in vectors]
        self.model = model_id
        self.dimension_value = dimension
        self.calls = 0

    @property
    def model_id(self) -> str:
        return self.model

    @property
    def dimension(self) -> int:
        return self.dimension_value

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return [list(vector) for vector in self.vectors]

    def health(self) -> EmbeddingProviderHealth:
        return EmbeddingProviderHealth(True, "stub provider")

    def probe(self) -> EmbeddingProviderHealth:
        return EmbeddingProviderHealth(True, "stub provider")


class FlakyProvider(StubProvider):
    """Provider that fails *failures* times before it succeeds."""

    def __init__(self, *, failures: int, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.remaining_failures = failures

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise build_embedding_error(
                "transient provider failure",
                error_code="embedding_provider_error",
            )
        return [list(vector) for vector in self.vectors]


# ----------------------------------------------------------------------
# provider protocol
# ----------------------------------------------------------------------
def test_stub_provider_satisfies_the_protocol() -> None:
    assert isinstance(StubProvider([VALID_VECTOR]), EmbeddingProvider)
    assert isinstance(DeterministicHashEmbeddingProvider(), EmbeddingProvider)


# ----------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------
def test_embed_texts_rejects_a_wrong_dimension() -> None:
    provider = StubProvider([[0.1, 0.2]], dimension=DIMENSION)
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["hello"])

    assert excinfo.value.error_code == "embedding_dimension_mismatch"


def test_embed_texts_rejects_a_non_finite_component() -> None:
    provider = StubProvider([[float("nan"), 0.2, 0.3, 0.4]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["hello"])

    assert excinfo.value.error_code == "embedding_non_finite_value"


def test_embed_texts_rejects_an_infinite_component() -> None:
    provider = StubProvider([[float("inf"), 0.2, 0.3, 0.4]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError):
        service.embed_texts(["hello"])


def test_embed_texts_rejects_a_degenerate_zero_vector() -> None:
    provider = StubProvider([[0.0, 0.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["hello"])

    assert excinfo.value.error_code == "embedding_degenerate_vector"


def test_embed_texts_rejects_too_few_vectors() -> None:
    provider = StubProvider([VALID_VECTOR])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["first", "second"])

    assert excinfo.value.error_code == "embedding_count_mismatch"


def test_embed_texts_rejects_too_many_vectors() -> None:
    provider = StubProvider([VALID_VECTOR, VALID_VECTOR])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError):
        service.embed_texts(["only one"])


def test_embed_texts_returns_the_vectors_in_input_order() -> None:
    provider = StubProvider([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    vectors = service.embed_texts(["a", "b"])

    assert vectors == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]


def test_embed_texts_with_no_input_does_not_call_the_provider() -> None:
    provider = StubProvider([])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    assert service.embed_texts([]) == []
    assert provider.calls == 0


def test_embed_query_returns_a_single_validated_vector() -> None:
    provider = StubProvider([VALID_VECTOR])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    vector = service.embed_query("quarterly revenue")

    assert len(vector) == DIMENSION
    assert provider.calls == 1


# ----------------------------------------------------------------------
# configuration hash
# ----------------------------------------------------------------------
def test_config_hash_is_a_sha256_hex_digest() -> None:
    service = EmbeddingService(
        StubProvider([VALID_VECTOR], model_id="some-model"),
        expected_dimension=DIMENSION,
    )

    assert re.fullmatch(r"[0-9a-f]{64}", service.config_hash)


def test_config_hash_changes_when_the_model_id_changes() -> None:
    first = EmbeddingService(
        StubProvider([VALID_VECTOR], model_id="model-a"),
        expected_dimension=DIMENSION,
    )
    second = EmbeddingService(
        StubProvider([VALID_VECTOR], model_id="model-b"),
        expected_dimension=DIMENSION,
    )

    assert first.config_hash != second.config_hash


def test_config_hash_changes_when_the_dimension_changes() -> None:
    first = EmbeddingService(
        StubProvider([VALID_VECTOR], model_id="model-a"),
        expected_dimension=DIMENSION,
    )
    second = EmbeddingService(
        StubProvider([VALID_VECTOR], model_id="model-a"),
        expected_dimension=DIMENSION + 1,
    )

    assert first.config_hash != second.config_hash


# ----------------------------------------------------------------------
# embedding reuse
# ----------------------------------------------------------------------
def test_embed_texts_reusing_reuses_a_matching_vector() -> None:
    provider = StubProvider([[9.0, 9.0, 9.0, 9.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)
    stored = [1.0, 0.0, 0.0, 0.0]

    vectors = service.embed_texts_reusing(
        ["unchanged text"],
        ["hash-1"],
        {"hash-1": (service.config_hash, stored)},
    )

    assert provider.calls == 0
    assert vectors == [stored]


def test_embed_texts_reusing_reembeds_when_the_config_hash_differs() -> None:
    provider = StubProvider([[1.0, 0.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    vectors = service.embed_texts_reusing(
        ["changed text"],
        ["hash-1"],
        {"hash-1": ("a-stale-config-hash", [1.0, 0.0, 0.0, 0.0])},
    )

    assert provider.calls == 1
    assert vectors == [[1.0, 0.0, 0.0, 0.0]]


def test_embed_texts_reusing_embeds_only_the_missing_texts_in_one_call() -> None:
    provider = StubProvider([[0.0, 1.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)
    stored = [1.0, 0.0, 0.0, 0.0]

    vectors = service.embed_texts_reusing(
        ["cached text", "new text"],
        ["hash-cached", "hash-new"],
        {"hash-cached": (service.config_hash, stored)},
    )

    assert provider.calls == 1
    assert vectors == [stored, [0.0, 1.0, 0.0, 0.0]]


def test_embed_texts_reusing_preserves_the_input_order() -> None:
    provider = StubProvider([[0.0, 1.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)
    first = [1.0, 0.0, 0.0, 0.0]
    third = [0.0, 0.0, 0.0, 1.0]

    vectors = service.embed_texts_reusing(
        ["text a", "text b", "text c"],
        ["hash-a", "hash-b", "hash-c"],
        {
            "hash-a": (service.config_hash, first),
            "hash-c": (service.config_hash, third),
        },
    )

    assert vectors == [first, [0.0, 1.0, 0.0, 0.0], third]


def test_embed_texts_reusing_validates_a_reused_vector() -> None:
    provider = StubProvider([])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts_reusing(
            ["cached text"],
            ["hash-1"],
            {"hash-1": (service.config_hash, [1.0, 0.0])},
        )

    assert excinfo.value.error_code == "embedding_dimension_mismatch"


def test_embed_texts_reusing_requires_one_hash_per_text() -> None:
    provider = StubProvider([VALID_VECTOR])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(ValueError):
        service.embed_texts_reusing(["a", "b"], ["hash-a"], {})


# ----------------------------------------------------------------------
# deterministic test provider
# ----------------------------------------------------------------------
def test_deterministic_provider_is_deterministic() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=DIMENSION)

    first = provider.embed(["the same text"])[0]
    second = provider.embed(["the same text"])[0]

    assert first == second


def test_deterministic_provider_has_the_requested_dimension() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=17)

    vector = provider.embed(["a text"])[0]

    assert len(vector) == 17


def test_deterministic_provider_never_returns_a_zero_vector() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=DIMENSION)

    vector = provider.embed(["a text", "", "another text"])[0]

    assert any(component != 0.0 for component in vector)
    assert math.sqrt(sum(component**2 for component in vector)) == pytest.approx(1.0)


def test_deterministic_provider_differs_for_different_texts() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=DIMENSION)

    first, second = provider.embed(["first text", "second text"])

    assert first != second


def test_deterministic_provider_reports_its_health() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=DIMENSION)

    assert provider.health().ok
    assert provider.probe().ok
    assert provider.model_id == "test-hash-provider"
    assert provider.__test_only__ is True


def test_deterministic_provider_is_not_exported_by_the_package() -> None:
    import app.embeddings as embeddings_package

    assert not hasattr(embeddings_package, "DeterministicHashEmbeddingProvider")


# ----------------------------------------------------------------------
# retry policy
# ----------------------------------------------------------------------
def test_transient_failures_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "_sleep", lambda _seconds: None)
    provider = FlakyProvider(failures=2, vectors=[VALID_VECTOR])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    vectors = service.embed_texts(["hello"])

    assert provider.calls == 3
    assert vectors == [VALID_VECTOR]


def test_the_retry_budget_is_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "_sleep", lambda _seconds: None)
    provider = FlakyProvider(failures=99, vectors=[VALID_VECTOR])
    service = EmbeddingService(
        provider,
        expected_dimension=DIMENSION,
        max_retries=3,
    )

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["hello"])

    # One initial attempt plus ``max_retries`` retries.
    assert provider.calls == 4
    assert excinfo.value.error_code == "embedding_provider_error"


def test_the_backoff_is_exponential(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(service_module, "_sleep", delays.append)
    provider = FlakyProvider(failures=99, vectors=[VALID_VECTOR])
    service = EmbeddingService(
        provider,
        expected_dimension=DIMENSION,
        max_retries=3,
    )

    with pytest.raises(EmbeddingError):
        service.embed_texts(["hello"])

    assert delays == [0.5, 1.0, 2.0]


def test_validation_failures_are_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "_sleep", lambda _seconds: None)
    provider = StubProvider([[0.0, 0.0, 0.0, 0.0]])
    service = EmbeddingService(provider, expected_dimension=DIMENSION)

    with pytest.raises(EmbeddingError):
        service.embed_texts(["hello"])

    assert provider.calls == 1


def test_a_provider_contract_violation_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "_sleep", lambda _seconds: None)

    class BrokenProvider(StubProvider):
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            self.calls += 1
            raise RuntimeError("the model exploded")

    provider = BrokenProvider([])
    service = EmbeddingService(
        provider,
        expected_dimension=DIMENSION,
        max_retries=1,
    )

    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_texts(["hello"])

    assert excinfo.value.error_code == "embedding_provider_error"
    assert provider.calls == 2


# ----------------------------------------------------------------------
# dependency injection factory
# ----------------------------------------------------------------------
def test_create_embedding_service_builds_the_fastembed_service() -> None:
    service = create_embedding_service(_settings())

    assert isinstance(service, EmbeddingService)
    assert isinstance(service.provider, FastEmbedProvider)
    assert service.dimension == 384
    assert service.config_hash == service.config_hash


def test_create_embedding_service_rejects_an_unknown_provider() -> None:
    settings = _settings()
    # ``embedding_provider`` is a literal in the settings, so the unsupported
    # name is injected by assignment.
    settings.embedding_provider = "unsupported-provider"  # type: ignore[assignment]

    with pytest.raises(ConfigurationError) as excinfo:
        create_embedding_service(settings)

    assert "fastembed" in excinfo.value.message


def test_create_embedding_service_rejects_a_dimension_mismatch() -> None:
    with pytest.raises(ConfigurationError):
        create_embedding_service(_settings(embedding_dimension=999))


def test_create_embedding_service_rejects_the_test_provider_in_production() -> None:
    settings = _settings(app_env="production")
    settings.embedding_provider = TEST_PROVIDER_NAME  # type: ignore[assignment]

    with pytest.raises(ConfigurationError):
        create_embedding_service(settings)


def test_create_embedding_service_allows_the_test_provider_outside_production() -> None:
    settings = _settings(app_env="test")
    settings.embedding_provider = TEST_PROVIDER_NAME  # type: ignore[assignment]

    service = create_embedding_service(settings)

    assert isinstance(service.provider, DeterministicHashEmbeddingProvider)
    assert service.dimension == 384


# ----------------------------------------------------------------------
# real provider (uses the locally cached fastembed model)
# ----------------------------------------------------------------------
def test_fastembed_provider_health_before_the_model_is_loaded() -> None:
    provider = FastEmbedProvider("BAAI/bge-small-en-v1.5", dimension=384)

    health = provider.health()

    assert health.ok
    assert "not loaded" in health.detail


@pytest.mark.slow
def test_fastembed_provider_produces_real_embeddings() -> None:
    provider = FastEmbedProvider("BAAI/bge-small-en-v1.5", dimension=384)
    text = "Revenue grew by twelve percent in the fiscal year ended January 31, 2026."

    vectors = provider.embed([text])
    vector = vectors[0]

    assert len(vectors) == 1
    assert len(vector) == 384
    assert all(math.isfinite(component) for component in vector)
    norm = math.sqrt(sum(component**2 for component in vector))
    assert norm == pytest.approx(1.0, rel=1e-3)

    repeated = provider.embed([text])[0]
    assert repeated == pytest.approx(vector, rel=1e-6)

    different = provider.embed(["The weather in Zurich is cold today."])[0]
    assert different != pytest.approx(vector, rel=1e-6)

    assert provider.health().ok
    assert "model loaded" in provider.health().detail

    probe = provider.probe()
    assert probe.ok
    assert "384" in probe.detail
