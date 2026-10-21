"""Persistence operations for the ``processing_jobs`` table."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ProcessingJobStatus
from app.db.base import utcnow
from app.db.models.job import ProcessingJob

__all__ = ["ProcessingJobRepository"]


class ProcessingJobRepository:
    """CRUD operations for :class:`~app.db.models.job.ProcessingJob`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def create(
        self,
        *,
        document_id: UUID,
        status: ProcessingJobStatus | str = ProcessingJobStatus.QUEUED,
        commit: bool = True,
    ) -> ProcessingJob:
        """Insert a processing job and return it."""
        job = ProcessingJob(
            document_id=document_id,
            status=ProcessingJobStatus(status).value,
            attempt_count=0,
        )
        self._session.add(job)
        if commit:
            self._session.commit()
            self._session.refresh(job)
        else:
            self._session.flush()
        return job

    def mark_running(self, job_id: UUID, *, commit: bool = True) -> ProcessingJob | None:
        """Mark the job *job_id* as running and count the attempt.

        ``attempt_count`` is incremented every time a job starts, therefore
        it is the number of attempts the document needed.  ``None`` is
        returned when the job does not exist.
        """
        job = self.get(job_id)
        if job is None:
            return None
        job.status = ProcessingJobStatus.RUNNING.value
        job.started_at = utcnow()
        job.attempt_count = int(job.attempt_count or 0) + 1
        if commit:
            self._session.commit()
            self._session.refresh(job)
        else:
            self._session.flush()
        return job

    def mark_completed(self, job_id: UUID, *, commit: bool = True) -> ProcessingJob | None:
        """Mark the job *job_id* as completed."""
        job = self.get(job_id)
        if job is None:
            return None
        job.status = ProcessingJobStatus.COMPLETED.value
        job.completed_at = utcnow()
        if commit:
            self._session.commit()
            self._session.refresh(job)
        else:
            self._session.flush()
        return job

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str | None,
        error_message: str | None,
        commit: bool = True,
    ) -> ProcessingJob | None:
        """Mark the job *job_id* as failed and record the error."""
        job = self.get(job_id)
        if job is None:
            return None
        job.status = ProcessingJobStatus.FAILED.value
        job.completed_at = utcnow()
        job.error_code = error_code
        job.error_message = error_message
        if commit:
            self._session.commit()
            self._session.refresh(job)
        else:
            self._session.flush()
        return job

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get(self, job_id: UUID) -> ProcessingJob | None:
        """Return the job *job_id* or ``None``."""
        return self._session.get(ProcessingJob, job_id)

    def get_latest(self, document_id: UUID) -> ProcessingJob | None:
        """Return the newest job of *document_id* or ``None``."""
        statement = (
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalars().first()

    def list_by_document(self, document_id: UUID) -> list[ProcessingJob]:
        """Return every job of *document_id*, newest first."""
        statement = (
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
        )
        return list(self._session.execute(statement).scalars().all())