"""Integration tests of the Document Agent.

The tests run against a **real** PostgreSQL server with pgvector, a real
local storage backend, the real extractors, the real chunker and the real
embedding model.  Only the failure scenario replaces the embedding service
by a stub that always raises.

Every test cleans up after itself: the ``clean_database`` fixture of
``conftest.py`` truncates the tables before and after each test, therefore
the test database stays empty.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.document_agent import DocumentAgent
from app.agents.job_runner import BackgroundThreadJobRunner, InlineJobRunner
from app.core.config import Settings
from app.core.enums import ProcessingJobStatus, ProcessingStatus
from app.core.exceptions import EmbeddingError
from app.core.storage import LocalStorage
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.job import ProcessingJob
from app.db.models.workspace import Workspace
from app.embeddings.service import EmbeddingService, create_embedding_service
from app.ingestion.chunking import TokenAwareChunker
from app.ingestion.extractors.ocr import OcrExtractor
from app.ingestion.extractors.pdf_tables import PdfPlumberTableExtractor
from app.ingestion.extractors.pdf_text import PyMuPdfTextExtractor
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.validators import FileValidator
from app.schemas.document import DocumentMetadata
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.vectorstore.pgvector_store import PgVectorStore

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz as pymupdf  # type: ignore[no-redef]

pytestmark = pytest.mark.integration

#: The width of the vectors of the embedding model.
DIMENSION: int = 384

#: The heading of the first page.
HEADING_ONE = "Acme Corporation Annual Report"

#: The body of the first page.
BODY_ONE = (
    "Acme Corporation Annual Report for the fiscal year 2025. Total revenue was "
    "1.2 billion US dollars, an increase of 8 percent compared with the previous "
    "year. The board of directors approved a dividend of 0.42 US dollars per "
    "share for the reporting period."
)

#: The heading of the second page.
HEADING_TWO = "Management Discussion and Analysis"

#: The body of the second page.
BODY_TWO = (
    "Management discussion and analysis of the financial year 2025. Operating "
    "expenses grew by 3 percent while the operating margin improved to 18 "
    "percent. The industrial segment reported a revenue of 640 million US "
    "dollars and a profit of 95 million US dollars."
)

#: The name of the uploaded document.
FILENAME = "acme-annual-report-2025.pdf"

#: The metadata that a user supplies when the document is registered.  The
#: values are deliberately different from everything the heuristics of the
#: extraction can derive from the fixture, therefore a regression that
#: overwrites them is visible.
REGISTERED_COMPANY = "Walmart Inc."
REGISTERED_TITLE = (
    "Walmart Inc. Form 10-K for the fiscal year ended January 31, 2026"
)
REGISTERED_DOCUMENT_TYPE = "form_10k"
REGISTERED_FISCAL_PERIOD = "FY2026"
REGISTERED_SOURCE_URL = (
    "https://www.sec.gov/Archives/edgar/data/104169/wmtfy26annualreport.pdf"
)

#: The metadata of the registered document.
REGISTERED_METADATA = DocumentMetadata(
    company_name=REGISTERED_COMPANY,
    document_title=REGISTERED_TITLE,
    document_type=REGISTERED_DOCUMENT_TYPE,
    fiscal_period=REGISTERED_FISCAL_PERIOD,
    source_url=REGISTERED_SOURCE_URL,
)

#: The fiscal period that the heuristics detect in the fixture.
DETECTED_FISCAL_PERIOD = "FY2025"

#: The document type that the heuristics detect in the fixture.
DETECTED_DOCUMENT_TYPE = "annual_report"

#: The title that the heuristics detect in the fixture.
DETECTED_TITLE = "Acme Corporation Annual Report"


def _pdf_bytes() -> bytes:
    """Return the bytes of a two page PDF with a heading and a body per page."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 80), HEADING_ONE, fontsize=16)
        page.insert_text((72, 120), BODY_ONE, fontsize=11)
        page = document.new_page()
        page.insert_text((72, 80), HEADING_TWO, fontsize=16)
        page.insert_text((72, 120), BODY_TWO, fontsize=11)
        return document.tobytes()
    finally:
        document.close()


class _FailingEmbeddingService:
    """An embedding service that always fails."""

    config_hash = "failing-config-hash"

    def embed_texts_reusing(
        self,
        texts: Sequence[str],
        content_hashes: Sequence[str],
        existing: dict[str, tuple[str, list[float]]],
    ) -> list[list[float]]:
        """Always raise."""
        raise EmbeddingError(
            "the embedding provider is unreachable",
            error_code="embedding_provider_unreachable",
        )


def _row_counts(session_factory: sessionmaker[Session]) -> dict[str, int]:
    """Return the number of rows of every table of the test database."""
    counts: dict[str, int] = {}
    with session_factory() as session:
        counts["workspaces"] = session.execute(
            select(func.count()).select_from(Workspace)
        ).scalar_one()
        counts["documents"] = session.execute(
            select(func.count()).select_from(Document)
        ).scalar_one()
        counts["document_chunks"] = session.execute(
            select(func.count()).select_from(DocumentChunk)
        ).scalar_one()
        counts["processing_jobs"] = session.execute(
            select(func.count()).select_from(ProcessingJob)
        ).scalar_one()
    return counts


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def document_service(
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    settings: Settings,
) -> DocumentService:
    """Return the real document service."""
    return DocumentService(
        session_factory,
        storage=tmp_storage,
        validator=FileValidator(settings),
    )


@pytest.fixture
def workspace_id(db_session: Session) -> UUID:
    """Create a workspace and return its id."""
    workspace = Workspace(name="documents", description="agent integration test")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace.id


@pytest.fixture
def embedding_service(settings: Settings) -> EmbeddingService:
    """Return the real embedding service (the model is cached locally)."""
    return create_embedding_service(settings)


@pytest.fixture
def vector_store(session_factory: sessionmaker[Session]) -> PgVectorStore:
    """Return the real pgvector backed store."""
    return PgVectorStore(session_factory=session_factory)


@pytest.fixture
def pipeline(
    settings: Settings,
    tmp_storage: LocalStorage,
    document_service: DocumentService,
    embedding_service: EmbeddingService,
    vector_store: PgVectorStore,
) -> IngestionPipeline:
    """Return the real pipeline, wired with the real components."""
    return IngestionPipeline(
        storage=tmp_storage,
        text_extractor=PyMuPdfTextExtractor(settings),
        table_extractor=PdfPlumberTableExtractor(settings),
        ocr_extractor=OcrExtractor(settings),
        chunker=TokenAwareChunker(),
        embedding_service=embedding_service,
        vector_store=vector_store,
        reporter=document_service,
        embedding_source=vector_store,
        settings=settings,
    )


@pytest.fixture
def failing_pipeline(
    settings: Settings,
    tmp_storage: LocalStorage,
    document_service: DocumentService,
    vector_store: PgVectorStore,
) -> IngestionPipeline:
    """Return a real pipeline whose embedding service always fails."""
    return IngestionPipeline(
        storage=tmp_storage,
        text_extractor=PyMuPdfTextExtractor(settings),
        table_extractor=PdfPlumberTableExtractor(settings),
        ocr_extractor=OcrExtractor(settings),
        chunker=TokenAwareChunker(),
        embedding_service=_FailingEmbeddingService(),
        vector_store=vector_store,
        reporter=document_service,
        embedding_source=vector_store,
        settings=settings,
    )


@pytest.fixture
def agent(
    pipeline: IngestionPipeline,
    document_service: DocumentService,
    session_factory: sessionmaker[Session],
) -> DocumentAgent:
    """Return the real document agent."""
    return DocumentAgent(
        pipeline=pipeline,
        document_service=document_service,
        session_factory=session_factory,
    )


@pytest.fixture
def document_id(
    document_service: DocumentService,
    workspace_id: UUID,
) -> UUID:
    """Register the two page PDF and return the id of the document."""
    registration = document_service.register_upload(
        workspace_id=workspace_id,
        filename=FILENAME,
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )
    assert registration.duplicate is False
    return registration.document_id


def _wait_for_status(
    session_factory: sessionmaker[Session],
    document_id: UUID,
    expected: ProcessingStatus,
    timeout_seconds: float = 30.0,
) -> str:
    """Wait until the document reaches *expected* and return its status."""
    deadline = time.monotonic() + timeout_seconds
    status = ""
    while time.monotonic() < deadline:
        with session_factory() as session:
            document = session.get(Document, document_id)
            status = "" if document is None else str(document.processing_status)
        if status == expected.value:
            return status
        time.sleep(0.2)
    raise AssertionError(
        f"the document {document_id} did not reach {expected.value!r} within "
        f"{timeout_seconds} seconds (last status: {status!r})"
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_the_agent_processes_a_document_end_to_end(
    agent: DocumentAgent,
    document_id: UUID,
    session_factory: sessionmaker[Session],
    embedding_service: EmbeddingService,
) -> None:
    """The document is completed, indexed and the job is closed."""
    outcome = agent.process(document_id)

    assert outcome.document_id == document_id
    assert outcome.status == ProcessingStatus.COMPLETED
    assert outcome.job_id is not None
    assert outcome.attempt_count == 1
    assert outcome.page_count == 2
    assert outcome.chunk_count >= 1
    assert outcome.error_code is None
    assert outcome.error_message is None

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.processed_at is not None
        assert document.page_count == 2
        assert document.error_code is None
        assert document.error_message is None

        jobs = session.execute(
            select(ProcessingJob).where(ProcessingJob.document_id == document_id)
        ).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].status == ProcessingJobStatus.COMPLETED.value
        assert jobs[0].attempt_count == 1

        chunks = session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).scalars().all()
        assert len(chunks) == outcome.chunk_count
        assert {chunk.page_start for chunk in chunks} == {1, 2}
        for chunk in chunks:
            assert chunk.page_start == chunk.page_end
            assert chunk.page_start in (1, 2)
            assert len(chunk.embedding) == DIMENSION
            assert chunk.content_hash
            assert chunk.embedding_config_hash == embedding_service.config_hash


def test_the_search_finds_the_document(
    agent: DocumentAgent,
    document_id: UUID,
    workspace_id: UUID,
    settings: Settings,
    embedding_service: EmbeddingService,
    vector_store: PgVectorStore,
) -> None:
    """The indexed chunks are found by a semantic search."""
    agent.process(document_id)

    search_service = SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        settings=settings,
    )
    results = search_service.search(
        workspace_id=workspace_id,
        query="how much did the revenue grow",
        limit=5,
    )

    assert results.total >= 1
    assert results.results
    hit = results.results[0]
    assert hit.document_id == document_id
    assert hit.page_start is not None
    assert hit.content


def test_processing_the_document_twice_does_not_duplicate_the_chunks(
    agent: DocumentAgent,
    document_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """A second run leaves exactly one chunk per chunk index."""
    first = agent.process(document_id)
    second = agent.process(document_id)

    assert first.status == ProcessingStatus.COMPLETED
    assert second.status == ProcessingStatus.COMPLETED
    assert second.chunk_count == first.chunk_count

    with session_factory() as session:
        chunks = session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).scalars().all()
        assert len(chunks) == first.chunk_count
        indexes = sorted(chunk.chunk_index for chunk in chunks)
        assert indexes == list(range(len(chunks)))

        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED


def test_a_failing_pipeline_marks_the_document_as_failed(
    failing_pipeline: IngestionPipeline,
    document_service: DocumentService,
    document_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """A failure is recorded on the document and on the job."""
    agent = DocumentAgent(
        pipeline=failing_pipeline,
        document_service=document_service,
        session_factory=session_factory,
    )

    outcome = agent.process(document_id)

    assert outcome.status == ProcessingStatus.FAILED
    assert outcome.error_code == "embedding_provider_unreachable"
    assert outcome.error_message == "the embedding provider is unreachable"
    assert outcome.chunk_count == 0
    assert outcome.page_count == 0
    assert outcome.attempt_count == 1

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.FAILED
        assert document.error_code == "embedding_provider_unreachable"

        jobs = session.execute(
            select(ProcessingJob).where(ProcessingJob.document_id == document_id)
        ).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].status == ProcessingJobStatus.FAILED.value
        assert jobs[0].attempt_count == 1
        assert jobs[0].error_code == "embedding_provider_unreachable"


def test_a_failed_document_can_be_retried_and_completes(
    failing_pipeline: IngestionPipeline,
    pipeline: IngestionPipeline,
    document_service: DocumentService,
    document_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """A failed document goes back to ``queued`` and completes on the retry."""
    failing_agent = DocumentAgent(
        pipeline=failing_pipeline,
        document_service=document_service,
        session_factory=session_factory,
    )
    assert failing_agent.process(document_id).status == ProcessingStatus.FAILED

    summary = document_service.retry_document(document_id)
    assert summary.status == ProcessingJobStatus.QUEUED.value
    assert summary.attempt_count == 0

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.QUEUED
        assert document.error_code is None

        jobs = session.execute(
            select(ProcessingJob).where(ProcessingJob.document_id == document_id)
        ).scalars().all()
        assert len(jobs) == 2
        assert summary.job_id in {job.id for job in jobs}

    agent = DocumentAgent(
        pipeline=pipeline,
        document_service=document_service,
        session_factory=session_factory,
    )
    outcome = agent.process(document_id)

    assert outcome.status == ProcessingStatus.COMPLETED
    assert outcome.job_id == summary.job_id

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.processed_at is not None

        jobs = session.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.asc())
        ).scalars().all()
        assert len(jobs) == 2

        new_job = next(job for job in jobs if job.id == summary.job_id)
        assert new_job.status == ProcessingJobStatus.COMPLETED.value

        # The new job was started once; the document needed two attempts in
        # total (the first one failed, the second one succeeded).
        assert new_job.attempt_count == 1
        assert sum(int(job.attempt_count or 0) for job in jobs) == 2


def test_the_background_runner_processes_a_document_in_a_thread(
    agent: DocumentAgent,
    document_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """The background runner processes the document and stops cleanly."""
    runner = BackgroundThreadJobRunner(agent, poll_interval_seconds=0.1)
    runner.start()
    assert runner.is_running is True

    try:
        runner.submit(document_id)
        status = _wait_for_status(
            session_factory,
            document_id,
            ProcessingStatus.COMPLETED,
            timeout_seconds=30.0,
        )
        assert status == ProcessingStatus.COMPLETED.value
    finally:
        runner.stop()

    assert runner.is_running is False

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.processed_at is not None


def test_the_inline_runner_processes_the_queued_documents(
    agent: DocumentAgent,
    document_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """``run_pending`` picks the queued document up and completes it."""
    runner = InlineJobRunner(agent)

    assert runner.run_pending() == 1

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.processed_at is not None


def test_the_registered_metadata_is_not_overwritten_by_the_ingestion(
    agent: DocumentAgent,
    document_service: DocumentService,
    workspace_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """The heuristics of the extraction never replace a registered value.

    The metadata that was supplied when the document was registered is
    authoritative: the detection of the extraction may only fill the
    fields that are still empty.  The page count is the exception: it is
    a fact of the extraction and it fills the empty field.
    """
    registration = document_service.register_upload(
        workspace_id=workspace_id,
        filename=FILENAME,
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
        metadata=REGISTERED_METADATA,
    )
    assert registration.duplicate is False

    outcome = agent.process(registration.document_id)

    assert outcome.status == ProcessingStatus.COMPLETED
    assert outcome.chunk_count >= 1
    assert outcome.page_count == 2

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None

        # The registered values survived the ingestion.
        assert document.company_name == REGISTERED_COMPANY
        assert document.document_title == REGISTERED_TITLE
        assert document.document_type == REGISTERED_DOCUMENT_TYPE
        assert document.fiscal_period == REGISTERED_FISCAL_PERIOD
        assert document.source_url == REGISTERED_SOURCE_URL

        # The page count is the fact of the extraction.
        assert document.page_count == 2

        # The status and the chunks are not affected by the rule.
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.error_code is None
        chunks = session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == registration.document_id
            )
        ).scalars().all()
        assert len(chunks) == outcome.chunk_count
        assert {chunk.page_start for chunk in chunks} == {1, 2}


def test_the_detected_metadata_fills_the_empty_fields(
    agent: DocumentAgent,
    document_service: DocumentService,
    workspace_id: UUID,
    session_factory: sessionmaker[Session],
) -> None:
    """A document without metadata receives the detected values.

    The fixture yields a fiscal period, a document type and a title; the
    company name is a false positive of the heuristic, but it is a value
    nevertheless.  The rule only ever fills empty fields, therefore all of
    them are written.
    """
    registration = document_service.register_upload(
        workspace_id=workspace_id,
        filename=FILENAME,
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )
    assert registration.duplicate is False

    outcome = agent.process(registration.document_id)

    assert outcome.status == ProcessingStatus.COMPLETED
    assert outcome.chunk_count >= 1

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None

        # The heuristics filled the empty fields.
        assert document.fiscal_period == DETECTED_FISCAL_PERIOD
        assert document.document_type == DETECTED_DOCUMENT_TYPE
        assert document.document_title == DETECTED_TITLE
        assert document.company_name is not None
        assert document.page_count == 2

        # The status and the chunks are not affected by the rule.
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.error_code is None
        chunks = session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == registration.document_id
            )
        ).scalars().all()
        assert len(chunks) == outcome.chunk_count
        assert {chunk.page_start for chunk in chunks} == {1, 2}


def test_the_test_database_is_left_empty(
    session_factory: sessionmaker[Session],
) -> None:
    """The integration tests leave no row behind in the test database."""
    counts = _row_counts(session_factory)
    assert counts == {
        "workspaces": 0,
        "documents": 0,
        "document_chunks": 0,
        "processing_jobs": 0,
    }