"""The Document Agent: the owner of a single ingestion attempt.

The agent is the component that connects the *business* side of the
ingestion (the document row, the processing job) with the *mechanical* side
(the :class:`~app.ingestion.pipeline.IngestionPipeline`).  It is the only
place that knows both.

Responsibilities
----------------
1. load the document and make sure that it exists,
2. find (or create) the processing job of the document,
3. mark the job as running - this counts the attempt,
4. run the pipeline,
5. close the job (completed or failed) and persist the extracted metadata.

Failure contract
----------------
A failure of the pipeline is **recorded, not raised**: the document and the
job carry the error, the agent returns a :class:`ProcessingOutcome` with the
status ``FAILED`` and the caller decides what to do next.  Only a *missing*
document raises (:class:`~app.core.exceptions.NotFoundError`), because that
is a programming error of the caller and not a processing failure.

The agent never leaves the job or the document in a non-terminal state: both
are closed before the outcome is returned.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import ProcessingJobStatus, ProcessingStatus
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.ingestion.contracts import DocumentExtractionMetadata
from app.ingestion.pipeline import (
    IngestionPipeline,
    error_code_of,
    error_message_of,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import ProcessingJobRepository
from app.services.document_service import DocumentService

__all__ = ["DocumentAgent", "ProcessingOutcome"]

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    """The outcome of a single processing attempt."""

    document_id: UUID
    status: ProcessingStatus
    job_id: UUID | None
    attempt_count: int
    chunk_count: int
    page_count: int
    error_code: str | None
    error_message: str | None


class DocumentAgent:
    """Runs the ingestion pipeline for a single document."""

    def __init__(
        self,
        *,
        pipeline: IngestionPipeline,
        document_service: DocumentService,
        session_factory: Callable[[], Session],
    ) -> None:
        """Create the agent.

        Parameters
        ----------
        pipeline:
            The pipeline that does the actual work.
        document_service:
            Service that owns the document row (and the status bookkeeping).
        session_factory:
            Callable that returns a fresh :class:`~sqlalchemy.orm.Session`.
            The agent opens and closes its sessions itself, therefore the
            factory must return a session the agent may dispose of.
        """
        self._pipeline = pipeline
        self._document_service = document_service
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def session_factory(self) -> Callable[[], Session]:
        """Return the session factory the agent works with."""
        return self._session_factory

    def process(self, document_id: UUID) -> ProcessingOutcome:
        """Process the document *document_id* and return the outcome.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the document does not exist.
        """
        document = self._document_service.get_document(document_id)
        storage_key = self._storage_key(document_id)
        job_id = self._ensure_job(document_id)
        self._mark_running(job_id)

        try:
            result = self._pipeline.run(
                document_id=document_id,
                storage_key=storage_key,
                content_hash=document.content_hash,
                workspace_id=document.workspace_id,
            )
        except Exception as exc:
            return self._fail(document_id, job_id, exc)

        self._mark_completed(job_id)
        self._apply_metadata(document_id, result.metadata)

        return ProcessingOutcome(
            document_id=document_id,
            status=ProcessingStatus.COMPLETED,
            job_id=job_id,
            attempt_count=self._attempt_count(job_id),
            chunk_count=result.chunk_count,
            page_count=result.page_count,
            error_code=None,
            error_message=None,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _storage_key(self, document_id: UUID) -> str:
        """Return the storage key of the document.

        The public summary of the document service does not carry the storage
        key - it is an implementation detail of the storage backend - so the
        row is read directly.
        """
        with self._session_factory() as session:
            record = DocumentRepository(session).get(document_id)
            if record is None:
                raise NotFoundError(
                    f"the document {document_id} does not exist",
                    details={"document_id": str(document_id)},
                )
            return record.storage_key

    def _ensure_job(self, document_id: UUID) -> UUID:
        """Return the id of the job of the document and create it when needed."""
        with self._session_factory() as session:
            repository = ProcessingJobRepository(session)
            job = repository.get_latest(document_id)
            if job is None:
                job = repository.create(
                    document_id=document_id,
                    status=ProcessingJobStatus.QUEUED,
                )
            return job.id

    def _mark_running(self, job_id: UUID) -> None:
        """Mark the job as running; this counts the attempt."""
        with self._session_factory() as session:
            ProcessingJobRepository(session).mark_running(job_id)

    def _mark_completed(self, job_id: UUID) -> None:
        """Mark the job as completed."""
        with self._session_factory() as session:
            ProcessingJobRepository(session).mark_completed(job_id)

    def _mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        """Mark the job as failed and record the error on it."""
        with self._session_factory() as session:
            ProcessingJobRepository(session).mark_failed(
                job_id,
                error_code=error_code,
                error_message=error_message,
            )

    def _attempt_count(self, job_id: UUID) -> int:
        """Return the number of attempts of the job *job_id*."""
        with self._session_factory() as session:
            job = ProcessingJobRepository(session).get(job_id)
            if job is None:
                return 0
            return int(job.attempt_count or 0)

    def _apply_metadata(
        self,
        document_id: UUID,
        metadata: DocumentExtractionMetadata,
    ) -> None:
        """Persist the metadata that the extraction stage detected.

        The detected metadata may only **fill empty fields**: a value that
        was supplied when the document was registered is never overwritten
        by a heuristic of the extraction.  The rule itself is implemented
        by :meth:`DocumentService.apply_extraction_metadata`.

        The document is already ``completed`` at this point, therefore a
        failure of the (secondary) metadata write is logged and never
        changes the outcome of the attempt.
        """
        try:
            self._document_service.apply_extraction_metadata(document_id, metadata)
        except Exception:
            logger.exception(
                "the extracted metadata of the document %s could not be written",
                document_id,
            )

    def _fail(
        self,
        document_id: UUID,
        job_id: UUID,
        exc: Exception,
    ) -> ProcessingOutcome:
        """Record the failure of the attempt and return the outcome."""
        error_code = error_code_of(exc)
        error_message = error_message_of(exc)

        logger.error(
            "the processing of the document %s failed: %s",
            document_id,
            error_message,
            extra={
                "document_id": str(document_id),
                "job_id": str(job_id),
                "error_code": error_code,
            },
        )

        try:
            self._mark_failed(
                job_id,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:  # the original failure must not be masked
            logger.exception(
                "the failure of the document %s could not be recorded on its job",
                document_id,
            )

        return ProcessingOutcome(
            document_id=document_id,
            status=ProcessingStatus.FAILED,
            job_id=job_id,
            attempt_count=self._attempt_count(job_id),
            chunk_count=0,
            page_count=0,
            error_code=error_code,
            error_message=error_message,
        )