"""Integration tests for the document service.

The tests run against a **real** PostgreSQL server and a real local storage
backend.  Every test empties the test tables before and after it runs and
the temporary storage directory is unique per test, therefore the tests are
independent of each other and leave no residue behind.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.enums import ProcessingJobStatus, ProcessingStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.storage import LocalStorage
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.job import ProcessingJob
from app.db.models.workspace import Workspace
from app.ingestion.validators import FileValidator
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import ProcessingJobRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.document_service import DocumentService

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz as pymupdf  # type: ignore[no-redef]

pytestmark = pytest.mark.integration

#: A text long enough to pass the "is this a scan?" heuristic.
PDF_TEXT = (
    "Acme Corporation Annual Report for the fiscal year 2025. "
    "Total revenue was 1.2 billion US dollars, an increase of 8 percent "
    "compared with the previous year. The board of directors approved the "
    "dividend of 0.42 US dollars per share for the reporting period."
)

#: Width of the test vectors.
DIMENSION: int = 384


def _pdf_bytes(text: str = PDF_TEXT) -> bytes:
    """Return the bytes of a small but *valid* PDF with *text* on one page."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 100), text, fontsize=11)
        return document.tobytes()
    finally:
        document.close()


def _stored_files(storage: LocalStorage) -> list[Path]:
    """Return every file that *storage* holds."""
    root = storage.root.resolve()
    if not root.is_dir():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


class _FailingCommitSession:
    """A session proxy whose ``commit`` always fails.

    It simulates a database that rejects the transaction, so that the
    compensating action of the registration can be observed.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name: str):  # pragma: no cover - trivial delegation
        return getattr(self._session, name)

    def commit(self) -> None:
        """Fail like a database that refuses the transaction."""
        raise RuntimeError("the database refused the transaction")


@pytest.fixture
def service(
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    settings: Settings,
) -> DocumentService:
    """Return the service under test."""
    return DocumentService(
        session_factory,
        storage=tmp_storage,
        validator=FileValidator(settings),
    )


@pytest.fixture
def workspace_id(db_session: Session) -> UUID:
    """Create a workspace and return its id."""
    workspace = Workspace(name="documents", description="integration test")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace.id


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------
def test_register_upload_creates_the_document_and_its_job(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    workspace_id: UUID,
) -> None:
    """A valid upload produces a committed document row and a queued job."""
    payload = _pdf_bytes()

    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme-annual-report.pdf",
        data=payload,
        declared_mime_type="application/pdf",
    )

    assert registration.duplicate is False
    assert registration.processing_status == ProcessingStatus.QUEUED.value
    assert registration.processing_stage is None
    assert registration.content_hash == hashlib.sha256(payload).hexdigest()

    # The rows are read from a *separate* session: they are committed.
    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.workspace_id == workspace_id
        assert document.content_hash == registration.content_hash
        assert document.file_size_bytes == len(payload)
        assert document.mime_type == "application/pdf"
        assert document.processing_status == ProcessingStatus.QUEUED

        jobs = session.execute(
            select(ProcessingJob).where(
                ProcessingJob.document_id == registration.document_id
            )
        ).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].status == ProcessingJobStatus.QUEUED
        assert jobs[0].attempt_count == 0

        storage_key = document.storage_key

    assert tmp_storage.exists(storage_key) is True
    assert tmp_storage.read(storage_key) == payload


def test_register_upload_stores_the_supplied_metadata(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
) -> None:
    """The metadata of the upload is written to the document row."""
    from app.schemas.document import DocumentMetadata

    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
        metadata=DocumentMetadata(
            company_name="Acme Corporation",
            document_title="Annual Report 2025",
            document_type="annual_report",
            fiscal_period="FY2025",
            source_url="https://example.invalid/acme",
        ),
    )

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.company_name == "Acme Corporation"
        assert document.document_title == "Annual Report 2025"
        assert document.document_type == "annual_report"
        assert document.fiscal_period == "FY2025"
        assert document.source_url == "https://example.invalid/acme"


def test_a_duplicate_upload_returns_the_same_document(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    workspace_id: UUID,
) -> None:
    """The same bytes in the same workspace are reported as a duplicate."""
    payload = _pdf_bytes()

    first = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=payload,
        declared_mime_type="application/pdf",
    )
    second = service.register_upload(
        workspace_id=workspace_id,
        filename="acme-copy.pdf",
        data=payload,
        declared_mime_type="application/pdf",
    )

    assert second.duplicate is True
    assert second.document_id == first.document_id

    with session_factory() as session:
        documents = session.execute(
            select(Document).where(Document.workspace_id == workspace_id)
        ).scalars().all()
        assert len(documents) == 1

    # No second file was written to the storage backend.
    assert len(_stored_files(tmp_storage)) == 1


def test_the_same_bytes_in_another_workspace_are_not_a_duplicate(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    db_session: Session,
    workspace_id: UUID,
) -> None:
    """The duplicate check is scoped to a single workspace."""
    other = Workspace(name="other", description=None)
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    payload = _pdf_bytes()

    first = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=payload,
        declared_mime_type="application/pdf",
    )
    second = service.register_upload(
        workspace_id=other.id,
        filename="acme.pdf",
        data=payload,
        declared_mime_type="application/pdf",
    )

    assert second.duplicate is False
    assert second.document_id != first.document_id

    with session_factory() as session:
        assert len(session.execute(select(Document)).scalars().all()) == 2


def test_an_invalid_upload_is_rejected(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    workspace_id: UUID,
) -> None:
    """A payload that is not a PDF is refused and nothing is written."""
    with pytest.raises(ValidationError) as excinfo:
        service.register_upload(
            workspace_id=workspace_id,
            filename="notes.txt",
            data=b"this is definitely not a pdf",
            declared_mime_type="text/plain",
        )

    issues = excinfo.value.details["issues"]
    assert "not_a_pdf" in issues
    assert "extension_not_allowed" in issues

    with session_factory() as session:
        assert session.execute(select(Document)).scalars().all() == []
        assert session.execute(select(ProcessingJob)).scalars().all() == []

    assert _stored_files(tmp_storage) == []


def test_a_failing_database_write_removes_the_stored_file(
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    settings: Settings,
    workspace_id: UUID,
) -> None:
    """The file is removed again when the database write fails."""
    payload = _pdf_bytes()

    def failing_factory() -> Session:
        return _FailingCommitSession(session_factory())

    failing_service = DocumentService(
        failing_factory,
        storage=tmp_storage,
        validator=FileValidator(settings),
    )

    with pytest.raises(RuntimeError):
        failing_service.register_upload(
            workspace_id=workspace_id,
            filename="acme.pdf",
            data=payload,
            declared_mime_type="application/pdf",
        )

    # The compensating action removed the file ...
    assert _stored_files(tmp_storage) == []
    # ... and the rolled back transaction left no row behind.
    with session_factory() as session:
        assert session.execute(select(Document)).scalars().all() == []
        assert session.execute(select(ProcessingJob)).scalars().all() == []


def test_register_upload_of_an_unknown_workspace_raises_not_found(
    service: DocumentService,
    tmp_storage: LocalStorage,
) -> None:
    """A upload into a workspace that does not exist is refused."""
    with pytest.raises(NotFoundError):
        service.register_upload(
            workspace_id=uuid.uuid4(),
            filename="acme.pdf",
            data=_pdf_bytes(),
            declared_mime_type="application/pdf",
        )

    assert _stored_files(tmp_storage) == []


# ----------------------------------------------------------------------
# status bookkeeping
# ----------------------------------------------------------------------
def test_report_status_updates_the_document(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
) -> None:
    """Every status change is written to the document row."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    service.report_status(
        registration.document_id,
        ProcessingStatus.EXTRACTING,
        stage="pdf_text",
    )

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.EXTRACTING
        assert document.processing_stage == "pdf_text"
        assert document.error_code is None
        assert document.error_message is None


def test_report_status_records_the_error_and_clears_it_again(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
) -> None:
    """A failure keeps its error, a success clears the error fields."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    service.report_status(
        registration.document_id,
        ProcessingStatus.FAILED,
        stage="extracting",
        error_code="ocr_unavailable",
        error_message="OCR is not available on this host",
    )

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.FAILED
        assert document.error_code == "ocr_unavailable"
        assert document.error_message == "OCR is not available on this host"

    service.report_status(registration.document_id, ProcessingStatus.COMPLETED)

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.COMPLETED
        assert document.error_code is None
        assert document.error_message is None
        assert document.processed_at is not None


def test_report_status_of_an_unknown_document_raises_not_found(
    service: DocumentService,
) -> None:
    """A missing document is reported as :class:`NotFoundError`."""
    with pytest.raises(NotFoundError):
        service.report_status(uuid.uuid4(), ProcessingStatus.COMPLETED)


def test_apply_extraction_metadata_writes_only_the_known_values(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
) -> None:
    """The metadata of the extraction stage is persisted."""
    from app.ingestion.contracts import DocumentExtractionMetadata

    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    service.apply_extraction_metadata(
        registration.document_id,
        DocumentExtractionMetadata(
            company_name="Acme Corporation",
            document_title="Annual Report 2025",
            document_type="annual_report",
            fiscal_period="FY2025",
            page_count=12,
        ),
    )

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.company_name == "Acme Corporation"
        assert document.document_title == "Annual Report 2025"
        assert document.document_type == "annual_report"
        assert document.fiscal_period == "FY2025"
        assert document.page_count == 12


# ----------------------------------------------------------------------
# retry
# ----------------------------------------------------------------------
def test_retry_document_creates_a_new_queued_job(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    workspace_id: UUID,
) -> None:
    """A failed document goes back to ``queued`` with a fresh job."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )
    service.report_status(
        registration.document_id,
        ProcessingStatus.FAILED,
        error_code="ocr_unavailable",
        error_message="boom",
    )

    summary = service.retry_document(registration.document_id)

    assert summary.status == ProcessingJobStatus.QUEUED.value
    assert summary.attempt_count == 0
    assert summary.document_id == registration.document_id
    assert summary.error_code is None

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        assert document.processing_status == ProcessingStatus.QUEUED
        assert document.error_code is None
        assert document.error_message is None

        jobs = session.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == registration.document_id)
            .order_by(ProcessingJob.created_at.asc())
        ).scalars().all()
        assert len(jobs) == 2
        assert summary.job_id in {job.id for job in jobs}


def test_retry_document_rejects_a_document_that_is_not_failed(
    service: DocumentService,
    workspace_id: UUID,
) -> None:
    """A completed document cannot be retried."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )
    service.report_status(registration.document_id, ProcessingStatus.COMPLETED)

    with pytest.raises(ConflictError):
        service.retry_document(registration.document_id)


def test_retry_document_rejects_an_unknown_document(
    service: DocumentService,
) -> None:
    """A missing document is reported as :class:`NotFoundError`."""
    with pytest.raises(NotFoundError):
        service.retry_document(uuid.uuid4())


def test_the_job_summary_maps_onto_the_retry_response_of_the_api(
    service: DocumentService,
    workspace_id: UUID,
) -> None:
    """The summary carries the fields the API schema expects."""
    from app.schemas.document import RetryResponse

    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )
    service.report_status(
        registration.document_id,
        ProcessingStatus.FAILED,
        error_code="ocr_unavailable",
        error_message="boom",
    )

    summary = service.retry_document(registration.document_id)
    response = RetryResponse.model_validate(summary, from_attributes=True)

    assert response.document_id == registration.document_id
    assert response.job_id == summary.job_id
    assert response.attempt_count == 0
    assert response.processing_status == ProcessingStatus.QUEUED.value


def test_get_job_summary_returns_the_latest_job(
    service: DocumentService,
    workspace_id: UUID,
) -> None:
    """The summary of the newest job is reported."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    summary = service.get_job_summary(registration.document_id)

    assert summary is not None
    assert summary.status == ProcessingJobStatus.QUEUED.value
    assert summary.attempt_count == 0
    assert service.get_job_summary(uuid.uuid4()) is None


# ----------------------------------------------------------------------
# reads
# ----------------------------------------------------------------------
def test_list_documents_supports_pagination_and_filters(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    db_session: Session,
    workspace_id: UUID,
) -> None:
    """The list is paginated and can be narrowed down by the filters."""
    repository = DocumentRepository(db_session)
    for index in range(3):
        repository.create(
            workspace_id=workspace_id,
            original_filename=f"document-{index}.pdf",
            storage_key=f"2025/01/document-{index}.pdf",
            content_hash=uuid.uuid4().hex,
            file_size_bytes=2048,
            mime_type="application/pdf",
            company_name="Acme" if index < 2 else "Globex",
            document_type="annual_report" if index < 2 else "form_10q",
            processing_status=(
                ProcessingStatus.FAILED if index == 0 else ProcessingStatus.QUEUED
            ),
        )

    page, total = service.list_documents(workspace_id, limit=2, offset=0)
    assert len(page) == 2
    assert total == 3

    second_page, total = service.list_documents(workspace_id, limit=2, offset=2)
    assert len(second_page) == 1
    assert total == 3

    identifiers = {summary.id for summary in page + second_page}
    assert len(identifiers) == 3

    failed, total = service.list_documents(
        workspace_id, limit=10, offset=0, status=ProcessingStatus.FAILED
    )
    assert total == 1
    assert failed[0].processing_status == ProcessingStatus.FAILED.value

    reports, total = service.list_documents(
        workspace_id, limit=10, offset=0, document_type="annual_report"
    )
    assert total == 2
    assert all(summary.document_type == "annual_report" for summary in reports)

    acme, total = service.list_documents(
        workspace_id, limit=10, offset=0, company_name="Acme"
    )
    assert total == 2
    assert all(summary.company_name == "Acme" for summary in acme)


def test_list_documents_of_an_unknown_workspace_raises_not_found(
    service: DocumentService,
) -> None:
    """A missing workspace is reported as :class:`NotFoundError`."""
    with pytest.raises(NotFoundError):
        service.list_documents(uuid.uuid4(), limit=10, offset=0)


def test_get_document_returns_the_summary(
    service: DocumentService,
    workspace_id: UUID,
) -> None:
    """The summary of a document carries its chunk count."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    summary = service.get_document(registration.document_id)

    assert summary.id == registration.document_id
    assert summary.workspace_id == workspace_id
    assert summary.chunk_count == 0
    assert summary.processing_status == ProcessingStatus.QUEUED.value


def test_get_document_of_an_unknown_id_raises_not_found(service: DocumentService) -> None:
    """A missing document is reported as :class:`NotFoundError`."""
    with pytest.raises(NotFoundError):
        service.get_document(uuid.uuid4())


# ----------------------------------------------------------------------
# deletion
# ----------------------------------------------------------------------
def test_delete_document_removes_the_rows_and_the_file(
    service: DocumentService,
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
    workspace_id: UUID,
) -> None:
    """The document, its chunks, its jobs and its file are gone."""
    registration = service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    with session_factory() as session:
        document = session.get(Document, registration.document_id)
        assert document is not None
        storage_key = document.storage_key
        session.add(
            DocumentChunk(
                document_id=registration.document_id,
                chunk_index=0,
                content="a chunk",
                content_hash=uuid.uuid4().hex,
                chunk_type="text",
                metadata_json={},
                embedding=[0.0] * (DIMENSION - 1) + [1.0],
                embedding_config_hash="test",
            )
        )
        session.commit()

    service.delete_document(registration.document_id)

    with session_factory() as session:
        assert session.get(Document, registration.document_id) is None
        assert session.execute(select(DocumentChunk)).scalars().all() == []
        assert session.execute(select(ProcessingJob)).scalars().all() == []

    assert tmp_storage.exists(storage_key) is False


def test_delete_document_of_an_unknown_id_raises_not_found(
    service: DocumentService,
) -> None:
    """A missing document is reported as :class:`NotFoundError`."""
    with pytest.raises(NotFoundError):
        service.delete_document(uuid.uuid4())


def test_the_workspace_repository_still_sees_the_workspace(
    service: DocumentService,
    db_session: Session,
    workspace_id: UUID,
) -> None:
    """The registration does not touch the workspace row."""
    service.register_upload(
        workspace_id=workspace_id,
        filename="acme.pdf",
        data=_pdf_bytes(),
        declared_mime_type="application/pdf",
    )

    repository = WorkspaceRepository(db_session)
    workspace = repository.get(workspace_id)
    assert workspace is not None
    assert workspace.name == "documents"


def test_the_job_repository_reports_the_attempts(
    db_session: Session,
    workspace_id: UUID,
) -> None:
    """``mark_running`` counts the attempts of a job."""
    repository = DocumentRepository(db_session)
    document = repository.create(
        workspace_id=workspace_id,
        original_filename="acme.pdf",
        storage_key="2025/01/acme.pdf",
        content_hash=uuid.uuid4().hex,
        file_size_bytes=2048,
        mime_type="application/pdf",
    )
    job_repository = ProcessingJobRepository(db_session)
    job = job_repository.create(document_id=document.id)

    running = job_repository.mark_running(job.id)
    assert running is not None
    assert running.status == ProcessingJobStatus.RUNNING.value
    assert running.attempt_count == 1
    assert running.started_at is not None

    failed = job_repository.mark_failed(
        job.id, error_code="boom", error_message="it broke"
    )
    assert failed is not None
    assert failed.status == ProcessingJobStatus.FAILED.value
    assert failed.error_code == "boom"
    assert failed.completed_at is not None
