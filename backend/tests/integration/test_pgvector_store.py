"""Integration tests for the pgvector backed vector store.

The tests run against a **real** PostgreSQL server with the pgvector
extension.  The database is taken from the ``TEST_DATABASE_URL`` environment
variable and falls back to the local development test database.

Every test cleans up after itself: the workspace it creates is deleted at the
end of the test, and the ``ON DELETE CASCADE`` of the schema removes the
documents and the chunks that belong to it.  A session scoped fixture
additionally asserts that the test leaves no chunk behind.
"""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from collections.abc import Iterator
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import ChunkType
from app.core.exceptions import VectorStoreError
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.workspace import Workspace
from app.vectorstore import PgVectorStore, VectorRecord

pytestmark = pytest.mark.integration

#: The database used by the integration tests.
TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL") or (
    "postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test"
)

#: Width of the test vectors.
DIMENSION: int = 384


def _unit_vector(position: int) -> list[float]:
    """Return a unit vector that points at *position*."""
    vector = [0.0] * DIMENSION
    vector[position] = 1.0
    return vector


def _mixed_vector(position: int, weight: float) -> list[float]:
    """Return the unit vector ``e[position] + weight * e[position + 1]``."""
    vector = [0.0] * DIMENSION
    vector[position] = 1.0
    vector[position + 1] = weight
    norm = math.sqrt(1.0 + weight**2)
    return [value / norm for value in vector]


#: Three deterministic vectors with a known ranking.
VECTOR_EXACT: list[float] = _unit_vector(0)
VECTOR_CLOSE: list[float] = _mixed_vector(0, 2.0)
VECTOR_ORTHOGONAL: list[float] = _unit_vector(2)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Return an engine bound to the test database."""
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return the session factory used by the store under test."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _database_is_clean(engine: Engine) -> Iterator[None]:
    """Assert that the test session leaves no chunk behind."""
    with engine.connect() as connection:
        baseline = connection.execute(
            select(func.count()).select_from(DocumentChunk)
        ).scalar_one()
    yield
    with engine.connect() as connection:
        leftover = connection.execute(
            select(func.count()).select_from(DocumentChunk)
        ).scalar_one()
    assert leftover == baseline, (
        f"the integration test left {leftover - baseline} chunk(s) behind "
        f"(baseline was {baseline})"
    )


@pytest.fixture
def store(session_factory: sessionmaker[Session]) -> PgVectorStore:
    """Return a store bound to the test database."""
    return PgVectorStore(session_factory=session_factory, dimension=DIMENSION)


@pytest.fixture
def workspace(session_factory: sessionmaker[Session]) -> Iterator[UUID]:
    """Create a workspace and delete it (with its cascade) afterwards."""
    workspace_id = uuid.uuid4()
    session = session_factory()
    try:
        session.add(
            Workspace(
                id=workspace_id,
                name=f"integration-{workspace_id.hex}",
                description="pgvector integration test",
            )
        )
        session.commit()
    finally:
        session.close()

    yield workspace_id

    session = session_factory()
    try:
        session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        session.commit()
    finally:
        session.close()


def _add_document(
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
    *,
    suffix: str = "primary",
) -> UUID:
    """Create a document in *workspace_id* and return its id."""
    document_id = uuid.uuid4()
    session = session_factory()
    try:
        session.add(
            Document(
                id=document_id,
                workspace_id=workspace_id,
                original_filename=f"{suffix}-report.pdf",
                storage_key=f"integration/{suffix}/{document_id.hex}.pdf",
                content_hash=document_id.hex,
                file_size_bytes=2048,
                mime_type="application/pdf",
                document_title=f"{suffix} integration report",
                company_name="Integration Corp",
                document_type="annual_report",
                fiscal_period="2025",
            )
        )
        session.commit()
    finally:
        session.close()
    return document_id


@pytest.fixture
def document(
    session_factory: sessionmaker[Session],
    workspace: UUID,
) -> UUID:
    """Create a document in the workspace and return its id."""
    return _add_document(session_factory, workspace)


def _record(
    *,
    document_id: UUID,
    workspace_id: UUID,
    content: str,
    embedding: list[float],
    chunk_index: int,
    chunk_type: str = ChunkType.TEXT.value,
) -> VectorRecord:
    """Build a vector record for the test."""
    return VectorRecord(
        chunk_id=uuid.uuid4(),
        document_id=document_id,
        workspace_id=workspace_id,
        content=content,
        embedding=list(embedding),
        chunk_type=chunk_type,
        chunk_index=chunk_index,
    )


def test_upsert_writes_rows(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """``upsert_chunks`` writes one row per record."""
    records = [
        _record(
            document_id=document,
            workspace_id=workspace,
            content="alpha",
            embedding=VECTOR_EXACT,
            chunk_index=0,
        ),
        _record(
            document_id=document,
            workspace_id=workspace,
            content="beta",
            embedding=VECTOR_CLOSE,
            chunk_index=1,
        ),
    ]

    assert store.upsert_chunks(records) == 2
    assert store.count_chunks(document) == 2
    assert store.count_chunks() >= 2


def test_search_returns_the_nearer_vector_first(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """The identical vector comes first with a score close to one."""
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content="orthogonal",
                embedding=VECTOR_ORTHOGONAL,
                chunk_index=0,
            ),
            _record(
                document_id=document,
                workspace_id=workspace,
                content="close",
                embedding=VECTOR_CLOSE,
                chunk_index=1,
            ),
            _record(
                document_id=document,
                workspace_id=workspace,
                content="exact",
                embedding=VECTOR_EXACT,
                chunk_index=2,
            ),
        ]
    )

    hits = store.search(VECTOR_EXACT, workspace)

    assert [hit.content for hit in hits] == ["exact", "close", "orthogonal"]
    assert hits[0].score > 0.9
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].score > hits[1].score > hits[2].score
    assert hits[0].workspace_id == workspace
    assert hits[0].document_id == document


def test_search_returns_the_document_metadata(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """The hits carry the metadata of the document they belong to."""
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content="alpha",
                embedding=VECTOR_EXACT,
                chunk_index=0,
            )
        ]
    )

    hit = store.search(VECTOR_EXACT, workspace)[0]

    assert hit.document_title == "primary integration report"
    assert hit.company_name == "Integration Corp"
    assert hit.document_type == "annual_report"
    assert hit.fiscal_period == "2025"
    assert hit.chunk_type == ChunkType.TEXT.value


def test_search_never_leaks_another_workspace(
    store: PgVectorStore,
    session_factory: sessionmaker[Session],
    workspace: UUID,
    document: UUID,
) -> None:
    """A chunk of another workspace never shows up in the results."""
    other_workspace = uuid.uuid4()
    session = session_factory()
    try:
        session.add(
            Workspace(id=other_workspace, name=f"integration-{other_workspace.hex}")
        )
        session.commit()
    finally:
        session.close()
    other_document = _add_document(
        session_factory, other_workspace, suffix="isolated"
    )

    try:
        store.upsert_chunks(
            [
                _record(
                    document_id=document,
                    workspace_id=workspace,
                    content="visible",
                    embedding=VECTOR_EXACT,
                    chunk_index=0,
                ),
                _record(
                    document_id=other_document,
                    workspace_id=other_workspace,
                    content="secret",
                    embedding=VECTOR_EXACT,
                    chunk_index=0,
                ),
            ]
        )

        hits = store.search(VECTOR_EXACT, workspace)

        assert [hit.content for hit in hits] == ["visible"]
        assert all(hit.workspace_id == workspace for hit in hits)

        other_hits = store.search(VECTOR_EXACT, other_workspace)
        assert [hit.content for hit in other_hits] == ["secret"]
    finally:
        session = session_factory()
        try:
            session.execute(delete(Workspace).where(Workspace.id == other_workspace))
            session.commit()
        finally:
            session.close()


def test_search_filters_by_document_ids(
    store: PgVectorStore,
    session_factory: sessionmaker[Session],
    workspace: UUID,
    document: UUID,
) -> None:
    """The ``document_ids`` filter narrows the result set."""
    other_document = _add_document(session_factory, workspace, suffix="secondary")
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content="primary",
                embedding=VECTOR_EXACT,
                chunk_index=0,
            ),
            _record(
                document_id=other_document,
                workspace_id=workspace,
                content="secondary",
                embedding=VECTOR_EXACT,
                chunk_index=0,
            ),
        ]
    )

    hits = store.search(VECTOR_EXACT, workspace, document_ids=[document])

    assert [hit.content for hit in hits] == ["primary"]
    assert hits[0].document_id == document


def test_search_filters_by_chunk_types(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """The ``chunk_types`` filter narrows the result set."""
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content="a-table",
                embedding=VECTOR_EXACT,
                chunk_index=0,
                chunk_type=ChunkType.TABLE.value,
            ),
            _record(
                document_id=document,
                workspace_id=workspace,
                content="a-text",
                embedding=VECTOR_EXACT,
                chunk_index=1,
                chunk_type=ChunkType.TEXT.value,
            ),
        ]
    )

    hits = store.search(
        VECTOR_EXACT,
        workspace,
        chunk_types=[ChunkType.TABLE.value],
    )

    assert [hit.content for hit in hits] == ["a-table"]


def test_upsert_is_idempotent(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """Writing the same records twice does not create a second row."""
    records = [
        _record(
            document_id=document,
            workspace_id=workspace,
            content="alpha",
            embedding=VECTOR_EXACT,
            chunk_index=0,
        ),
        _record(
            document_id=document,
            workspace_id=workspace,
            content="beta",
            embedding=VECTOR_CLOSE,
            chunk_index=1,
        ),
    ]

    assert store.upsert_chunks(records) == 2
    assert store.upsert_chunks(records) == 2
    assert store.count_chunks(document) == 2


def test_delete_document_chunks_removes_every_chunk(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """Deleting a document removes its chunks and reports the row count."""
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content="alpha",
                embedding=VECTOR_EXACT,
                chunk_index=0,
            ),
            _record(
                document_id=document,
                workspace_id=workspace,
                content="beta",
                embedding=VECTOR_CLOSE,
                chunk_index=1,
            ),
        ]
    )
    assert store.count_chunks(document) == 2

    assert store.delete_document_chunks(document) == 2
    assert store.count_chunks(document) == 0
    assert store.delete_document_chunks(document) == 0


def test_get_existing_embeddings_returns_the_stored_mapping(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """The stored embeddings are reported per content hash."""
    content = "alpha"
    store.upsert_chunks(
        [
            _record(
                document_id=document,
                workspace_id=workspace,
                content=content,
                embedding=VECTOR_EXACT,
                chunk_index=0,
            )
        ]
    )

    existing = store.get_existing_embeddings(document)

    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert set(existing) == {expected_hash}
    config_hash, embedding = existing[expected_hash]
    assert isinstance(config_hash, str) and config_hash
    assert embedding == pytest.approx(VECTOR_EXACT, abs=1e-5)


def test_upsert_rejects_a_wrong_dimension(
    store: PgVectorStore,
    workspace: UUID,
    document: UUID,
) -> None:
    """An embedding of the wrong width is refused before it reaches the DB."""
    record = _record(
        document_id=document,
        workspace_id=workspace,
        content="alpha",
        embedding=[0.1, 0.2, 0.3],
        chunk_index=0,
    )

    with pytest.raises(VectorStoreError) as excinfo:
        store.upsert_chunks([record])

    assert excinfo.value.code == "embedding_dimension_mismatch"
    assert store.count_chunks(document) == 0


def test_search_rejects_a_wrong_dimension(
    store: PgVectorStore,
    workspace: UUID,
) -> None:
    """A query vector of the wrong width is refused."""
    with pytest.raises(VectorStoreError) as excinfo:
        store.search([0.1, 0.2, 0.3], workspace)

    assert excinfo.value.code == "embedding_dimension_mismatch"
