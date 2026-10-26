"""Document business rules.

The service owns the rules of the ingestion pipeline that is *not* the
pipeline itself: the validation of an upload, the registration of a
document, the status bookkeeping and the retry logic.

Transaction rules
-----------------
* The service opens its own short lived session through the injected
  ``session_factory``; no session is kept open between two calls.
* **The document row is committed before any processing starts.**  The
  registration writes the document *and* its job in one transaction and
  commits it; only then may the pipeline pick the document up.
* No transaction is held open across a slow external call: the upload is
  written to the storage backend **before** the database is touched, and
  the file is removed again when the database write fails.
* A missing row is translated into
  :class:`~app.core.exceptions.NotFoundError`; a retry of a document that is
  not failed into :class:`~app.core.exceptions.ConflictError`.

The service returns **frozen dataclasses** - never ORM objects and never
Pydantic schemas.  The field names of :class:`DocumentSummary` match
:class:`app.schemas.document.DocumentRead`, the field names of
:class:`DocumentRegistration` match
:class:`app.schemas.document.DocumentUploadResponse` and the field names of
:class:`JobSummary` match :class:`app.schemas.document.RetryResponse`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import ProcessingJobStatus, ProcessingStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.storage import StorageBackend
from app.db.models.document import Document
from app.ingestion.contracts import DocumentExtractionMetadata
from app.ingestion.validators import FileValidator
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import ProcessingJobRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.document import DocumentMetadata

__all__ = [
    "DocumentProcessor",
    "DocumentRegistration",
    "DocumentService",
    "DocumentSummary",
    "JobSummary",
]

logger = get_logger(__name__)

#: MIME type of a PDF - the only document type the system accepts today.
DEFAULT_MIME_TYPE = "application/pdf"

#: Extension used when the file name carries none.
DEFAULT_EXTENSION = ".pdf"


def _status_value(status: ProcessingStatus | str | None) -> str:
    """Return the persisted string value of *status*."""
    if status is None:
        return ""
    if isinstance(status, ProcessingStatus):
        return status.value
    try:
        return ProcessingStatus(status).value
    except ValueError:
        return str(status)


def _is_empty(value: str | None) -> bool:
    """Return whether *value* carries no information.

    A value is empty when it is ``None`` or when it consists of white space
    only: a blank string is as good as no value at all and must therefore be
    filled by a detected one.
    """
    return value is None or not value.strip()


def _job_status_value(status: ProcessingJobStatus | str | None) -> str:
    """Return the persisted string value of a job *status*."""
    if status is None:
        return ""
    if isinstance(status, ProcessingJobStatus):
        return status.value
    try:
        return ProcessingJobStatus(status).value
    except ValueError:
        return str(status)


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """A document as the rest of the application sees it."""

    id: UUID
    workspace_id: UUID
    original_filename: str
    content_hash: str
    file_size_bytes: int
    mime_type: str
    company_name: str | None
    document_title: str | None
    document_type: str | None
    fiscal_period: str | None
    source_url: str | None
    page_count: int | None
    processing_status: str
    processing_stage: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    chunk_count: int


@dataclass(frozen=True, slots=True)
class DocumentRegistration:
    """The outcome of the registration of an upload."""

    document_id: UUID
    processing_status: str
    processing_stage: str | None
    content_hash: str
    duplicate: bool


@dataclass(frozen=True, slots=True)
class JobSummary:
    """A processing job as the rest of the application sees it."""

    job_id: UUID
    document_id: UUID
    status: str
    attempt_count: int
    error_code: str | None
    error_message: str | None
    #: Status of the *document* the job belongs to.  It mirrors
    #: ``app.schemas.document.RetryResponse.processing_status`` so that the
    #: API layer can map the summary with a single ``model_validate`` call.
    processing_status: str = ""


@runtime_checkable
class DocumentProcessor(Protocol):
    """Implemented by the Document Agent (app.agents.document_agent)."""

    def process(self, document_id: UUID) -> None:
        """Process the document *document_id*."""
        ...


class DocumentService:
    """Business rules for documents and their processing jobs."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        storage: StorageBackend,
        validator: FileValidator,
    ) -> None:
        """Create the service.

        Parameters
        ----------
        session_factory:
            Callable that returns a fresh :class:`~sqlalchemy.orm.Session`.
            The service opens and closes the sessions itself, therefore the
            factory must return a session the service may dispose of.
        storage:
            Backend the uploaded bytes are written to and read from.
        validator:
            Validator that decides whether an upload is acceptable.
        """
        self._session_factory = session_factory
        self._storage = storage
        self._validator = validator

    # ------------------------------------------------------------------
    # infrastructure
    # ------------------------------------------------------------------
    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Open a session, roll back on error and always close it."""
        session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _require_workspace(
        repository: WorkspaceRepository,
        workspace_id: UUID,
        owner_id: UUID | None,
    ) -> None:
        """Make sure the workspace *workspace_id* exists and may be reached.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the workspace does not exist or the user may not reach it.
        """
        if repository.get(workspace_id) is None:
            raise NotFoundError(
                f"the workspace {workspace_id} does not exist",
                details={"workspace_id": str(workspace_id)},
            )
        if owner_id is not None and not repository.can_access_workspace(
            workspace_id, owner_id
        ):
            raise NotFoundError(
                f"the workspace {workspace_id} does not exist",
                details={"workspace_id": str(workspace_id)},
            )

    @staticmethod
    def _not_found(document_id: UUID) -> NotFoundError:
        """Return the error that reports a missing document."""
        return NotFoundError(
            f"the document {document_id} does not exist",
            details={"document_id": str(document_id)},
        )

    def _remove_file(self, storage_key: str) -> None:
        """Remove *storage_key* from the storage backend.

        A failure is logged and never raised: the database is the source of
        truth and a dangling file is harmless, while a raised error would
        report a delete that did in fact happen.
        """
        try:
            self._storage.delete(storage_key)
        except Exception as exc:  # a dangling file must not break the flow
            logger.warning(
                "could not remove the stored document",
                extra={"storage_key": storage_key, "error": str(exc)},
            )

    @staticmethod
    def _to_summary(document: Document, *, chunk_count: int) -> DocumentSummary:
        """Return the summary of *document*."""
        return DocumentSummary(
            id=document.id,
            workspace_id=document.workspace_id,
            original_filename=document.original_filename,
            content_hash=document.content_hash,
            file_size_bytes=int(document.file_size_bytes),
            mime_type=document.mime_type,
            company_name=document.company_name,
            document_title=document.document_title,
            document_type=document.document_type,
            fiscal_period=document.fiscal_period,
            source_url=document.source_url,
            page_count=document.page_count,
            processing_status=_status_value(document.processing_status),
            processing_stage=document.processing_stage,
            error_code=document.error_code,
            error_message=document.error_message,
            created_at=document.created_at,
            updated_at=document.updated_at,
            processed_at=document.processed_at,
            chunk_count=chunk_count,
        )

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------
    def register_upload(
        self,
        *,
        workspace_id: UUID,
        filename: str,
        data: bytes,
        declared_mime_type: str | None = None,
        metadata: DocumentMetadata | None = None,
        owner_id: UUID | None = None,
    ) -> DocumentRegistration:
        """Register an upload and return the outcome.

        The steps are executed in this order:

        1. the payload is validated - a rejected upload raises
           :class:`~app.core.exceptions.ValidationError` and carries the
           collected issue codes in ``details["issues"]``,
        2. the SHA-256 content hash is computed,
        3. a document with the same ``(workspace_id, content_hash)`` is
           looked up - an existing document is reported with
           ``duplicate=True`` and **no second file is written**,
        4. the workspace is verified,
        5. the bytes are written to the storage backend,
        6. the document row and the processing job row are inserted in
           **one transaction** and committed - the document row is
           committed before any processing may start,
        7. when the database write fails, the stored file is removed again
           (compensating action) and the error is re-raised.

        ``owner_id`` restricts the upload to the workspaces the user owns
        or is a member of.  A workspace the user may not reach is reported
        as :class:`~app.core.exceptions.NotFoundError` - the existence of a
        workspace of somebody else is never disclosed.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the upload does not pass the validation.
        app.core.exceptions.NotFoundError
            If the workspace does not exist or the user may not reach it.
        """
        validation = self._validator.validate(
            filename=filename,
            declared_mime_type=declared_mime_type,
            data=data,
        )
        if not validation.ok:
            raise ValidationError(
                "the uploaded document was rejected by the validation",
                code="invalid_upload",
                details={
                    "issues": list(validation.error_codes()),
                    "filename": filename,
                },
            )

        content_hash = hashlib.sha256(bytes(data)).hexdigest()

        with self._session_scope() as session:
            workspace_repository = WorkspaceRepository(session)
            self._require_workspace(workspace_repository, workspace_id, owner_id)

            document_repository = DocumentRepository(session)
            duplicate = document_repository.get_by_content_hash(
                workspace_id, content_hash
            )
            if duplicate is not None:
                return DocumentRegistration(
                    document_id=duplicate.id,
                    processing_status=_status_value(duplicate.processing_status),
                    processing_stage=duplicate.processing_stage,
                    content_hash=duplicate.content_hash,
                    duplicate=True,
                )

        extension = Path(filename or "").suffix.lower() or DEFAULT_EXTENSION
        mime_type = validation.detected_mime_type or DEFAULT_MIME_TYPE
        storage_key = self._storage.save(bytes(data), extension=extension)

        try:
            with self._session_scope() as session:
                document_repository = DocumentRepository(session)
                job_repository = ProcessingJobRepository(session)
                document = document_repository.create(
                    workspace_id=workspace_id,
                    original_filename=filename,
                    storage_key=storage_key,
                    content_hash=content_hash,
                    file_size_bytes=len(data),
                    mime_type=mime_type,
                    company_name=metadata.company_name if metadata else None,
                    document_title=metadata.document_title if metadata else None,
                    document_type=metadata.document_type if metadata else None,
                    fiscal_period=metadata.fiscal_period if metadata else None,
                    source_url=metadata.source_url if metadata else None,
                    processing_status=ProcessingStatus.QUEUED,
                    commit=False,
                )
                job_repository.create(
                    document_id=document.id,
                    status=ProcessingJobStatus.QUEUED,
                    commit=False,
                )
                session.commit()
        except Exception:
            self._remove_file(storage_key)
            raise

        return DocumentRegistration(
            document_id=document.id,
            processing_status=ProcessingStatus.QUEUED.value,
            processing_stage=None,
            content_hash=content_hash,
            duplicate=False,
        )

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def list_documents(
        self,
        workspace_id: UUID,
        *,
        limit: int,
        offset: int,
        status: ProcessingStatus | str | None = None,
        document_type: str | None = None,
        company_name: str | None = None,
        owner_id: UUID | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        """Return a page of documents of a workspace and the **total** count.

        ``owner_id`` restricts the answer to the workspaces the user owns
        or is a member of.  A workspace the user may not reach is reported
        as :class:`~app.core.exceptions.NotFoundError`.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the workspace does not exist or the user may not reach it.
        """
        with self._session_scope() as session:
            workspace_repository = WorkspaceRepository(session)
            self._require_workspace(workspace_repository, workspace_id, owner_id)
            document_repository = DocumentRepository(session)
            chunk_repository = ChunkRepository(session)
            page, total = document_repository.list_by_workspace(
                workspace_id,
                limit=limit,
                offset=offset,
                status=status,
                document_type=document_type,
                company_name=company_name,
                owner_id=owner_id,
            )
            counts = chunk_repository.count_by_documents(
                [document.id for document in page]
            )
            summaries = [
                self._to_summary(document, chunk_count=counts.get(document.id, 0))
                for document in page
            ]
            return summaries, total

    def get_document(
        self,
        document_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> DocumentSummary:
        """Return the document *document_id*.

        ``owner_id`` restricts the answer to the documents of the
        workspaces the user owns or is a member of.  A document of a
        workspace the user may not reach is reported as
        :class:`~app.core.exceptions.NotFoundError`.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist or the user may not reach it.
        """
        with self._session_scope() as session:
            document_repository = DocumentRepository(session)
            chunk_repository = ChunkRepository(session)
            document = document_repository.get(document_id, owner_id=owner_id)
            if document is None:
                raise self._not_found(document_id)
            chunk_count = chunk_repository.count_by_document(document_id)
            return self._to_summary(document, chunk_count=chunk_count)

    def get_job_summary(self, document_id: UUID) -> JobSummary | None:
        """Return the newest job of the document *document_id* or ``None``."""
        with self._session_scope() as session:
            job_repository = ProcessingJobRepository(session)
            document_repository = DocumentRepository(session)
            job = job_repository.get_latest(document_id)
            if job is None:
                return None
            document = document_repository.get(document_id)
            return JobSummary(
                job_id=job.id,
                document_id=job.document_id,
                status=_job_status_value(job.status),
                attempt_count=int(job.attempt_count or 0),
                error_code=job.error_code,
                error_message=job.error_message,
                processing_status=(
                    _status_value(document.processing_status)
                    if document is not None
                    else ""
                ),
            )

    # ------------------------------------------------------------------
    # mutations
    # ------------------------------------------------------------------
    def delete_document(
        self,
        document_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        """Delete the document *document_id* and the file that belongs to it.

        The database row is deleted and committed first - the cascade of the
        schema removes the chunks and the jobs with it - and the stored file
        is removed afterwards.  A failure to remove the file is logged and
        never raised.

        ``owner_id`` restricts the deletion to the documents of the
        workspaces the user owns or is a member of.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist or the user may not reach it.
        """
        with self._session_scope() as session:
            document_repository = DocumentRepository(session)
            document = document_repository.get(document_id, owner_id=owner_id)
            if document is None:
                raise self._not_found(document_id)
            storage_key = document.storage_key
            document_repository.delete(document_id)
        self._remove_file(storage_key)

    def retry_document(
        self,
        document_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> JobSummary:
        """Queue a new processing attempt for the document *document_id*.

        A **new** job row is created (the attempt counter of the new job
        starts at zero) and the document goes back to ``queued``.  The
        document is **not** processed here: running the pipeline is the job
        of the job runner.

        ``owner_id`` restricts the retry to the documents of the workspaces
        the user owns or is a member of.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist or the user may not reach it.
        app.core.exceptions.ConflictError
            If the document is not in the ``failed`` state.
        """
        with self._session_scope() as session:
            document_repository = DocumentRepository(session)
            job_repository = ProcessingJobRepository(session)

            document = document_repository.get(document_id, owner_id=owner_id)
            if document is None:
                raise self._not_found(document_id)
            current_status = _status_value(document.processing_status)
            if current_status != ProcessingStatus.FAILED.value:
                raise ConflictError(
                    "only a failed document can be retried",
                    code="document_not_failed",
                    details={
                        "document_id": str(document_id),
                        "processing_status": current_status,
                    },
                )

            job = job_repository.create(
                document_id=document_id,
                status=ProcessingJobStatus.QUEUED,
                commit=False,
            )
            document_repository.set_status(
                document_id,
                ProcessingStatus.QUEUED,
                commit=False,
            )
            summary = JobSummary(
                job_id=job.id,
                document_id=job.document_id,
                status=_job_status_value(job.status),
                attempt_count=int(job.attempt_count or 0),
                error_code=job.error_code,
                error_message=job.error_message,
                processing_status=ProcessingStatus.QUEUED.value,
            )
            session.commit()
            return summary

    def report_status(
        self,
        document_id: UUID,
        status: ProcessingStatus | str,
        *,
        stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record the new *status* of the document *document_id*.

        This is the status sink of the pipeline.  Every call opens its own
        session and commits immediately, therefore the status of a document
        is durable as soon as the pipeline reports it.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist.
        """
        with self._session_scope() as session:
            repository = DocumentRepository(session)
            document = repository.set_status(
                document_id,
                status,
                stage=stage,
                error_code=error_code,
                error_message=error_message,
            )
            if document is None:
                raise self._not_found(document_id)

    def apply_extraction_metadata(
        self,
        document_id: UUID,
        metadata: DocumentExtractionMetadata,
    ) -> None:
        """Persist the metadata that the extraction stage detected.

        The rule
        --------
        **The detected metadata may only fill empty fields.**  It never
        overwrites a value that was explicitly supplied when the document
        was registered (by a user or by the seed manifest).

        * ``page_count`` is a **fact** that the extraction produced, not a
          heuristic: it is written when the document does not carry one yet.
        * ``company_name``, ``document_title``, ``document_type`` and
          ``fiscal_period`` are **heuristics**: every one of them is
          written only when the stored value is still empty (``NULL`` or
          blank).  A heuristic therefore never replaces a value that a
          human (or a pinned manifest) provided.

        A detected value that is ``None`` is never written at all, and a
        document that already carries a value keeps it - therefore a
        partial detection never wipes an existing value.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist.
        """
        with self._session_scope() as session:
            repository = DocumentRepository(session)
            document = repository.get(document_id)
            if document is None:
                raise self._not_found(document_id)

            repository.set_metadata(
                document_id,
                company_name=(
                    metadata.company_name
                    if _is_empty(document.company_name)
                    else None
                ),
                document_title=(
                    metadata.document_title
                    if _is_empty(document.document_title)
                    else None
                ),
                document_type=(
                    metadata.document_type
                    if _is_empty(document.document_type)
                    else None
                ),
                fiscal_period=(
                    metadata.fiscal_period
                    if _is_empty(document.fiscal_period)
                    else None
                ),
                page_count=(
                    metadata.page_count if document.page_count is None else None
                ),
            )