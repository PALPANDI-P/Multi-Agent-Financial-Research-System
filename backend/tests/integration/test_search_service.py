"""Integration tests for the search service.

The tests run against a **real** PostgreSQL server with the pgvector
extension.  The vectors are produced by the deterministic test provider: this
module verifies the *store and service* integration - the ordering, the
metadata and the workspace isolation - and makes no claim about the quality
of the embeddings themselves.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from uuid import UUID

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.models.document import Document
from app.db.models.workspace import Workspace
from app.embeddings.service import EmbeddingService
from app.embeddings.testing import DeterministicHashEmbeddingProvider
from app.services.search_service import SearchService
from app.vectorstore.base import SearchHit
from app.vectorstore.pgvector_store import PgVectorStore

pytestmark = pytest.mark.integration

#: Width of the test vectors.
DIMENSION: int = 384

#: The query of the tests; it is also the content of the closest chunk.
QUERY = "the revenue of the reporting period grew by eight percent"


class _RecordingStore:
    """A thin wrapper that records the limit of every search."""

    def __init__(self, store: PgVectorStore) -> None:
        self._store = store
        self.limits: list[int] = []
        self.workspace_ids: list[UUID] = []

    def search(
        self,
        embedding: Sequence[float],
        workspace_id: UUID,
        *,
        limit: int = 10,
        document_ids: Sequence[UUID] | None = None,
        chunk_types: Sequence[str] | None = None,
    ) -> list[SearchHit]:
        """Record the call and delegate it to the wrapped store."""
        self.limits.append(limit)
        self.workspace_ids.append(workspace_id)
        return self._store.search(
            embedding,
            workspace_id,
            limit=limit,
            document_ids=document_ids,
            chunk_types=chunk_types,
        )


def _orthogonal_vector(vector: list[float]) -> list[float]:
    """Return a unit vector that is orthogonal to *vector*."""
    for position in range(len(vector)):
        candidate = [0.0] * len(vector)
        candidate[position] = 1.0
        projection = sum(a * b for a, b in zip(vector, candidate, strict=True))
        candidate = [
            c - projection * v for c, v in zip(candidate, vector, strict=True)
        ]
        norm = math.sqrt(sum(c * c for c in candidate))
        if norm > 1e-6:
            return [c / norm for c in candidate]
    raise AssertionError("could not build an orthogonal vector")


def _add_workspace(session: Session, name: str) -> UUID:
    """Insert a workspace and return its id."""
    workspace = Workspace(name=name, description="search integration test")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace.id


def _add_document(
    session: Session,
    workspace_id: UUID,
    *,
    document_title: str,
    company_name: str,
) -> UUID:
    """Insert a document and return its id."""
    document = Document(
        workspace_id=workspace_id,
        original_filename=f"{document_title}.pdf",
        storage_key=f"2025/01/{uuid.uuid4().hex}.pdf",
        content_hash=uuid.uuid4().hex,
        file_size_bytes=2048,
        mime_type="application/pdf",
        document_title=document_title,
        company_name=company_name,
        document_type="annual_report",
        fiscal_period="FY2025",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document.id


@pytest.fixture
def provider() -> DeterministicHashEmbeddingProvider:
    """Return the deterministic (non semantic) test provider."""
    return DeterministicHashEmbeddingProvider(dimension=DIMENSION)


@pytest.fixture
def embedding_service(provider: DeterministicHashEmbeddingProvider) -> EmbeddingService:
    """Return the embedding service under test."""
    return EmbeddingService(provider, expected_dimension=DIMENSION)


@pytest.fixture
def store(session_factory: sessionmaker[Session]) -> PgVectorStore:
    """Return the pgvector store bound to the test database."""
    return PgVectorStore(session_factory=session_factory, dimension=DIMENSION)


@pytest.fixture
def service(
    store: PgVectorStore,
    embedding_service: EmbeddingService,
    settings: Settings,
) -> SearchService:
    """Return the service under test."""
    return SearchService(
        vector_store=store,
        embedding_service=embedding_service,
        settings=settings,
    )


@pytest.fixture
def corpus(
    db_session: Session,
    store: PgVectorStore,
    provider: DeterministicHashEmbeddingProvider,
) -> tuple[UUID, UUID, UUID]:
    """Insert two workspaces, three documents and four chunks.

    Returns
    -------
    tuple[UUID, UUID, UUID]
        The id of the first workspace, the id of the second workspace and
        the id of the document that holds the closest chunk.
    """
    query_vector = provider.embed([QUERY])[0]
    orthogonal = _orthogonal_vector(query_vector)

    workspace_id = _add_workspace(db_session, "workspace-a")
    other_workspace_id = _add_workspace(db_session, "workspace-b")

    first_document = _add_document(
        db_session,
        workspace_id,
        document_title="Acme Annual Report 2025",
        company_name="Acme Corporation",
    )
    second_document = _add_document(
        db_session,
        workspace_id,
        document_title="Acme Form 10-Q",
        company_name="Acme Corporation",
    )
    foreign_document = _add_document(
        db_session,
        other_workspace_id,
        document_title="Globex Annual Report 2025",
        company_name="Globex Corporation",
    )

    store.upsert_chunks(
        [
            _record(
                document_id=first_document,
                workspace_id=workspace_id,
                content=QUERY,
                embedding=query_vector,
                chunk_index=0,
                page_start=12,
                page_end=13,
                section_heading="Revenue",
                chunk_type="text",
            ),
            _record(
                document_id=first_document,
                workspace_id=workspace_id,
                content="the inventory of the company grew",
                embedding=orthogonal,
                chunk_index=1,
                page_start=40,
                page_end=40,
                section_heading="Inventory",
                chunk_type="table",
            ),
            _record(
                document_id=second_document,
                workspace_id=workspace_id,
                content="the balance sheet of the quarter",
                embedding=orthogonal,
                chunk_index=0,
                page_start=1,
                page_end=2,
                section_heading="Balance sheet",
                chunk_type="text",
            ),
            _record(
                document_id=foreign_document,
                workspace_id=other_workspace_id,
                content=QUERY,
                embedding=query_vector,
                chunk_index=0,
                page_start=1,
                page_end=1,
                section_heading="Secret",
                chunk_type="text",
            ),
        ]
    )

    return workspace_id, other_workspace_id, first_document


def _record(
    *,
    document_id: UUID,
    workspace_id: UUID,
    content: str,
    embedding: list[float],
    chunk_index: int,
    page_start: int,
    page_end: int,
    section_heading: str,
    chunk_type: str,
):
    """Return a vector record for the corpus."""
    from app.vectorstore.base import VectorRecord

    return VectorRecord(
        chunk_id=uuid.uuid4(),
        document_id=document_id,
        workspace_id=workspace_id,
        content=content,
        embedding=embedding,
        page_start=page_start,
        page_end=page_end,
        section_heading=section_heading,
        chunk_type=chunk_type,
        chunk_index=chunk_index,
        metadata={"section": section_heading},
    )


# ----------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------
def test_search_returns_the_hits_in_descending_score_order(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """The closest chunk comes first."""
    workspace_id, _other, first_document = corpus

    results = service.search(workspace_id=workspace_id, query=QUERY)

    assert results.total == len(results.results)
    assert results.total == 3
    assert results.workspace_id == workspace_id
    assert results.query == QUERY
    assert results.took_ms >= 0.0

    scores = [item.score for item in results.results]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(1.0, abs=1e-5)
    assert results.results[0].document_id == first_document
    assert results.results[0].content == QUERY


def test_search_hits_carry_the_document_and_chunk_metadata(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """The hits carry the metadata of the document and of the chunk."""
    workspace_id, _other, first_document = corpus

    results = service.search(workspace_id=workspace_id, query=QUERY)

    top = results.results[0]
    assert top.document_id == first_document
    assert top.document_title == "Acme Annual Report 2025"
    assert top.company_name == "Acme Corporation"
    assert top.document_type == "annual_report"
    assert top.fiscal_period == "FY2025"
    assert top.page_start == 12
    assert top.page_end == 13
    assert top.section_heading == "Revenue"
    assert top.chunk_type == "text"
    assert isinstance(top.metadata, dict)
    assert top.metadata["section"] == "Revenue"

    table_hit = next(item for item in results.results if item.chunk_type == "table")
    assert table_hit.page_start == 40
    assert table_hit.section_heading == "Inventory"


def test_search_never_leaks_another_workspace(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """A chunk of another workspace never shows up in the results."""
    workspace_id, other_workspace_id, _first = corpus

    results = service.search(workspace_id=workspace_id, query=QUERY)
    assert all("Secret" not in item.section_heading for item in results.results)

    other_results = service.search(workspace_id=other_workspace_id, query=QUERY)
    assert other_results.total == 1
    assert other_results.results[0].section_heading == "Secret"
    assert other_results.results[0].company_name == "Globex Corporation"


def test_search_rejects_a_blank_query(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """An empty query is a validation error."""
    workspace_id, _other, _first = corpus

    with pytest.raises(ValidationError):
        service.search(workspace_id=workspace_id, query="   ")

    with pytest.raises(ValidationError):
        service.search(workspace_id=workspace_id, query="")


def test_search_rejects_a_too_long_query(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """A query of more than 1000 characters is a validation error."""
    workspace_id, _other, _first = corpus

    with pytest.raises(ValidationError):
        service.search(workspace_id=workspace_id, query="x" * 1001)


def test_search_rejects_a_limit_below_one(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """A limit of zero or less is a validation error."""
    workspace_id, _other, _first = corpus

    with pytest.raises(ValidationError):
        service.search(workspace_id=workspace_id, query=QUERY, limit=0)

    with pytest.raises(ValidationError):
        service.search(workspace_id=workspace_id, query=QUERY, limit=-5)


def test_search_clamps_the_limit_to_the_configured_maximum(
    store: PgVectorStore,
    embedding_service: EmbeddingService,
    settings: Settings,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """A limit above ``retrieval_max_top_k`` is clamped."""
    workspace_id, _other, _first = corpus
    recording = _RecordingStore(store)
    service = SearchService(
        vector_store=recording,
        embedding_service=embedding_service,
        settings=settings,
    )

    service.search(workspace_id=workspace_id, query=QUERY, limit=500)

    assert recording.limits == [settings.retrieval_max_top_k]
    assert recording.workspace_ids == [workspace_id]


def test_search_uses_the_configured_default_limit(
    store: PgVectorStore,
    embedding_service: EmbeddingService,
    settings: Settings,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """Without a limit the configured ``retrieval_top_k`` is used."""
    workspace_id, _other, _first = corpus
    recording = _RecordingStore(store)
    service = SearchService(
        vector_store=recording,
        embedding_service=embedding_service,
        settings=settings,
    )

    service.search(workspace_id=workspace_id, query=QUERY)

    assert recording.limits == [settings.retrieval_top_k]


def test_search_without_any_match_returns_an_empty_result(
    service: SearchService,
    db_session: Session,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """A workspace without chunks returns an empty list, not an error."""
    _workspace_id, _other, _first = corpus
    empty_workspace = _add_workspace(db_session, "workspace-empty")

    results = service.search(workspace_id=empty_workspace, query=QUERY)

    assert results.total == 0
    assert results.results == []
    assert results.took_ms >= 0.0


def test_search_can_be_narrowed_down_by_document_ids(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """The ``document_ids`` filter narrows the result set."""
    workspace_id, _other, first_document = corpus

    results = service.search(
        workspace_id=workspace_id,
        query=QUERY,
        document_ids=[first_document],
    )

    assert results.total == 2
    assert all(item.document_id == first_document for item in results.results)


def test_search_can_be_narrowed_down_by_chunk_types(
    service: SearchService,
    corpus: tuple[UUID, UUID, UUID],
) -> None:
    """The ``chunk_types`` filter narrows the result set."""
    workspace_id, _other, _first = corpus

    results = service.search(
        workspace_id=workspace_id,
        query=QUERY,
        chunk_types=["table"],
    )

    assert results.total == 1
    assert results.results[0].chunk_type == "table"