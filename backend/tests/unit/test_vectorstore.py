"""Unit tests for the vector store contracts and the in-memory store."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from uuid import UUID

import pytest

from app.core.enums import ChunkType
from app.core.exceptions import VectorStoreError
from app.vectorstore import (
    InMemoryVectorStore,
    SearchHit,
    VectorRecord,
    VectorStore,
)

pytestmark = pytest.mark.unit


def _record(
    *,
    workspace_id: UUID,
    document_id: UUID,
    content: str,
    embedding: Sequence[float],
    chunk_index: int = 0,
    chunk_type: str = ChunkType.TEXT.value,
) -> VectorRecord:
    """Build a vector record for a test."""
    return VectorRecord(
        chunk_id=uuid.uuid4(),
        document_id=document_id,
        workspace_id=workspace_id,
        content=content,
        embedding=list(embedding),
        chunk_type=chunk_type,
        chunk_index=chunk_index,
    )


@pytest.fixture
def workspace_id() -> UUID:
    """Return a workspace id."""
    return uuid.uuid4()


@pytest.fixture
def other_workspace_id() -> UUID:
    """Return a second, unrelated workspace id."""
    return uuid.uuid4()


@pytest.fixture
def document_id() -> UUID:
    """Return a document id."""
    return uuid.uuid4()


@pytest.fixture
def other_document_id() -> UUID:
    """Return a second, unrelated document id."""
    return uuid.uuid4()


def test_in_memory_store_satisfies_the_protocol() -> None:
    """The in-memory store implements the whole VectorStore protocol."""
    assert isinstance(InMemoryVectorStore(), VectorStore)


def test_upsert_is_idempotent(workspace_id: UUID, document_id: UUID) -> None:
    """Writing the same records twice leaves exactly one chunk per record."""
    store = InMemoryVectorStore()
    records = [
        _record(
            workspace_id=workspace_id,
            document_id=document_id,
            content="alpha",
            embedding=[1.0, 0.0, 0.0],
            chunk_index=0,
        ),
        _record(
            workspace_id=workspace_id,
            document_id=document_id,
            content="beta",
            embedding=[0.0, 1.0, 0.0],
            chunk_index=1,
        ),
    ]

    assert store.upsert_chunks(records) == 2
    assert store.upsert_chunks(records) == 2
    assert store.count_chunks() == 2
    assert store.count_chunks(document_id) == 2


def test_count_chunks_can_filter_by_document(
    workspace_id: UUID,
    document_id: UUID,
    other_document_id: UUID,
) -> None:
    """``count_chunks`` reports the chunks of a single document."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="alpha",
                embedding=[1.0, 0.0, 0.0],
            ),
            _record(
                workspace_id=workspace_id,
                document_id=other_document_id,
                content="beta",
                embedding=[0.0, 1.0, 0.0],
            ),
        ]
    )

    assert store.count_chunks() == 2
    assert store.count_chunks(document_id) == 1
    assert store.count_chunks(other_document_id) == 1
    assert store.count_chunks(uuid.uuid4()) == 0


def test_search_returns_the_closest_vector_first(
    workspace_id: UUID,
    document_id: UUID,
) -> None:
    """The hit with the highest cosine similarity comes first."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="orthogonal",
                embedding=[0.0, 1.0, 0.0],
                chunk_index=0,
            ),
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="close",
                embedding=[0.9, 0.1, 0.0],
                chunk_index=1,
            ),
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="exact",
                embedding=[1.0, 0.0, 0.0],
                chunk_index=2,
            ),
        ]
    )

    hits = store.search([1.0, 0.0, 0.0], workspace_id)

    assert [hit.content for hit in hits] == ["exact", "close", "orthogonal"]
    expected_close = 0.9 / math.sqrt(0.9**2 + 0.1**2)
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(expected_close, abs=1e-6)
    assert hits[1].score < hits[0].score
    assert -1.0 <= hits[2].score <= 1.0
    assert all(isinstance(hit, SearchHit) for hit in hits)


def test_search_never_leaks_another_workspace(
    workspace_id: UUID,
    other_workspace_id: UUID,
    document_id: UUID,
    other_document_id: UUID,
) -> None:
    """Chunks of workspace A are invisible to a workspace B query."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="secret-a",
                embedding=[1.0, 0.0, 0.0],
            ),
            _record(
                workspace_id=other_workspace_id,
                document_id=other_document_id,
                content="visible-b",
                embedding=[1.0, 0.0, 0.0],
            ),
        ]
    )

    hits = store.search([1.0, 0.0, 0.0], workspace_id)

    assert [hit.content for hit in hits] == ["secret-a"]
    assert all(hit.workspace_id == workspace_id for hit in hits)


def test_search_filters_by_document_ids(
    workspace_id: UUID,
    document_id: UUID,
    other_document_id: UUID,
) -> None:
    """The ``document_ids`` filter narrows the result set."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="wanted",
                embedding=[1.0, 0.0, 0.0],
            ),
            _record(
                workspace_id=workspace_id,
                document_id=other_document_id,
                content="unwanted",
                embedding=[1.0, 0.0, 0.0],
            ),
        ]
    )

    hits = store.search([1.0, 0.0, 0.0], workspace_id, document_ids=[document_id])

    assert [hit.content for hit in hits] == ["wanted"]


def test_search_filters_by_chunk_types(
    workspace_id: UUID,
    document_id: UUID,
) -> None:
    """The ``chunk_types`` filter narrows the result set."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="a-table",
                embedding=[1.0, 0.0, 0.0],
                chunk_index=0,
                chunk_type=ChunkType.TABLE.value,
            ),
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="a-text",
                embedding=[1.0, 0.0, 0.0],
                chunk_index=1,
                chunk_type=ChunkType.TEXT.value,
            ),
        ]
    )

    hits = store.search(
        [1.0, 0.0, 0.0],
        workspace_id,
        chunk_types=[ChunkType.TABLE.value],
    )

    assert [hit.content for hit in hits] == ["a-table"]
    assert hits[0].chunk_type == ChunkType.TABLE.value


def test_search_respects_the_limit(workspace_id: UUID, document_id: UUID) -> None:
    """At most ``limit`` hits are returned."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content=f"chunk-{index}",
                embedding=[1.0, 0.0, 0.0],
                chunk_index=index,
            )
            for index in range(5)
        ]
    )

    assert len(store.search([1.0, 0.0, 0.0], workspace_id, limit=2)) == 2


def test_search_rejects_a_limit_below_one(workspace_id: UUID) -> None:
    """A limit of zero is a programming error, not an empty result."""
    store = InMemoryVectorStore()

    with pytest.raises(VectorStoreError) as excinfo:
        store.search([1.0, 0.0, 0.0], workspace_id, limit=0)

    assert excinfo.value.code == "invalid_limit"


def test_delete_document_chunks_removes_them(
    workspace_id: UUID,
    document_id: UUID,
    other_document_id: UUID,
) -> None:
    """Deleting a document removes exactly its own chunks."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="alpha",
                embedding=[1.0, 0.0, 0.0],
            ),
            _record(
                workspace_id=workspace_id,
                document_id=other_document_id,
                content="beta",
                embedding=[0.0, 1.0, 0.0],
            ),
        ]
    )

    assert store.delete_document_chunks(document_id) == 1
    assert store.count_chunks(document_id) == 0
    assert store.count_chunks(other_document_id) == 1
    assert store.delete_document_chunks(document_id) == 0


def test_get_existing_embeddings_is_empty(
    workspace_id: UUID,
    document_id: UUID,
) -> None:
    """The test store keeps no embedding state."""
    store = InMemoryVectorStore()
    store.upsert_chunks(
        [
            _record(
                workspace_id=workspace_id,
                document_id=document_id,
                content="alpha",
                embedding=[1.0, 0.0, 0.0],
            )
        ]
    )

    assert store.get_existing_embeddings(document_id) == {}


def test_records_and_hits_freeze_their_metadata(workspace_id: UUID) -> None:
    """The mapping fields cannot be used to smuggle a mutable dict around."""
    record = VectorRecord(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=workspace_id,
        content="alpha",
        embedding=[1.0, 0.0, 0.0],
        metadata={"source": "pdf"},
    )

    assert dict(record.metadata) == {"source": "pdf"}
    with pytest.raises(TypeError):
        record.metadata["source"] = "tampered"  # type: ignore[index]

    hit = SearchHit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=workspace_id,
        content="alpha",
        score=1.0,
        metadata={"source": "pdf"},
    )
    with pytest.raises(TypeError):
        hit.metadata["source"] = "tampered"  # type: ignore[index]
