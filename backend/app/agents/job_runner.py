"""The job runners: how a processing job reaches the Document Agent.

Two strategies are implemented:

:class:`InlineJobRunner`
    The job runs synchronously in the calling thread.  It is the strategy of
    the development milestone: an upload is processed before the API answers.

:class:`BackgroundThreadJobRunner`
    The job runs in an in-process background thread that is fed by a
    :class:`queue.Queue`.

Durability
----------
**No durable queue exists in this milestone.**  A job that is queued in the
background runner is lost when the process exits, and the queue lives in the
memory of the process that created it.  A future dedicated worker (Celery,
RQ or Arq) can replace the runner without changing a single line of the
ingestion pipeline: the runner only has to call
:meth:`app.agents.document_agent.DocumentAgent.process`.

The setting ``settings.processing_inline`` selects the strategy: it is
``True`` by default, therefore the inline runner is used.  The flag has to be
flipped once a real worker exists.

Crash recovery
--------------
Both runners offer :meth:`run_pending`: it scans the database for the
documents that are still ``queued`` and processes them.  The background
runner uses it to pick up the jobs that were lost when the process died.
"""

from __future__ import annotations

import queue
import threading
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy import select

from app.agents.document_agent import DocumentAgent
from app.core.enums import ProcessingStatus
from app.core.logging import get_logger
from app.db.models.document import Document

__all__ = [
    "BackgroundThreadJobRunner",
    "InlineJobRunner",
    "JobRunner",
    "create_job_runner",
]

logger = get_logger(__name__)

#: Sentinel that wakes the worker thread up when the runner is stopped.
_STOP = None

#: Maximum time the worker waits for the thread to end.
JOIN_TIMEOUT_SECONDS: float = 30.0


@runtime_checkable
class JobRunner(Protocol):
    """The strategy that decides *where* a processing job runs."""

    def submit(self, document_id: UUID) -> None:
        """Queue the document *document_id* for processing."""
        ...

    def run_pending(self) -> int:
        """Process the documents that are still queued and return the count."""
        ...


def _pending_document_ids(session_factory) -> list[UUID]:
    """Return the ids of the documents that are still queued."""
    with session_factory() as session:
        statement = (
            select(Document.id)
            .where(Document.processing_status == ProcessingStatus.QUEUED.value)
            .order_by(Document.created_at.asc(), Document.id.asc())
        )
        return list(session.execute(statement).scalars().all())


class InlineJobRunner:
    """Development strategy: the job runs synchronously in the calling thread."""

    def __init__(self, agent: DocumentAgent) -> None:
        """Create the runner for *agent*."""
        self._agent = agent

    def submit(self, document_id: UUID) -> None:
        """Process the document *document_id* right away."""
        self._agent.process(document_id)

    def run_pending(self) -> int:
        """Process every queued document and return the number of documents."""
        document_ids = _pending_document_ids(self._agent.session_factory)
        for document_id in document_ids:
            self._agent.process(document_id)
        return len(document_ids)


class BackgroundThreadJobRunner:
    """In-process background worker backed by a thread and a queue.

    NOT a durable queue: the jobs are lost when the process exits.  A future
    dedicated worker (Celery/RQ/Arq) can replace this without changing the
    pipeline.
    """

    def __init__(
        self,
        agent: DocumentAgent,
        *,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        """Create the runner for *agent*.

        Parameters
        ----------
        agent:
            The agent that processes the documents.
        poll_interval_seconds:
            How long the worker waits for a new job before it looks at the
            queue again.
        """
        self._agent = agent
        self._poll_interval = max(0.01, float(poll_interval_seconds))
        self._queue: queue.Queue[UUID | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        """Return ``True`` while the worker thread is alive."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        """Start the worker thread.

        The method is idempotent: starting a runner that already runs does
        nothing.
        """
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._worker_loop,
                name="frs-document-worker",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        """Stop the worker thread and wait for it to end.

        The method is idempotent: stopping a runner that does not run does
        nothing.  After the call no thread of the runner is alive any more.
        """
        with self._lock:
            thread = self._thread
            self._thread = None

        self._stop_event.set()
        self._queue.put(_STOP)
        if thread is not None:
            thread.join(timeout=JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():  # pragma: no cover - the worker always ends
                logger.error(
                    "the document worker did not stop within %s seconds",
                    JOIN_TIMEOUT_SECONDS,
                )
        self._discard_pending_jobs()

    def submit(self, document_id: UUID) -> None:
        """Queue the document *document_id* for processing.

        The worker is started on demand, therefore a submit is never lost.
        """
        self.start()
        self._queue.put(document_id)

    def run_pending(self) -> int:
        """Queue every document that is still queued and return the count."""
        document_ids = _pending_document_ids(self._agent.session_factory)
        if document_ids:
            self.start()
            for document_id in document_ids:
                self._queue.put(document_id)
        return len(document_ids)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        """Process the queued documents until the runner is stopped."""
        while not self._stop_event.is_set():
            try:
                document_id = self._queue.get(timeout=self._poll_interval)
            except queue.Empty:
                continue
            if document_id is _STOP:
                break
            try:
                self._agent.process(document_id)
            except Exception:
                logger.exception(
                    "the document worker could not process the document %s",
                    document_id,
                )
        self._queue.task_done()

    def _discard_pending_jobs(self) -> None:
        """Remove the jobs that are still in the queue."""
        discarded = 0
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is not _STOP:
                discarded += 1
        if discarded:
            logger.warning(
                "%s queued document(s) were discarded when the runner stopped",
                discarded,
            )


def create_job_runner(agent: DocumentAgent, settings) -> JobRunner:
    """Return the job runner that *settings* selects.

    ``settings.processing_inline`` is ``True`` by default, therefore the
    inline runner (the job runs in the calling thread) is returned.  A
    dedicated worker does not exist in this milestone.
    """
    if getattr(settings, "processing_inline", True):
        return InlineJobRunner(agent)
    return BackgroundThreadJobRunner(agent)