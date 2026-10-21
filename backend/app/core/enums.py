"""Domain enumerations shared by every layer of the backend.

The enumerations in this module are the single source of truth for the
*values* that are persisted in PostgreSQL, so that the ORM models, the
Alembic migrations and the service layer can never drift apart.

State model
-----------
:class:`ProcessingStatus` is the **authoritative** document processing state.
The pipeline moves through the explicit per-stage states

``queued -> validating -> extracting -> chunking -> embedding -> indexing ->
completed``

and may end in ``failed``.

``documents.processing_stage`` is *not* a second state machine: it only
carries supplementary sub-stage detail (for example ``pdf_text``,
``pdf_tables`` or ``ocr``) that refines the current
:class:`ProcessingStatus`.  Code must therefore branch on
:class:`ProcessingStatus` alone and treat ``processing_stage`` as free-form
diagnostic information.

This module has no side effects and imports nothing but the standard
library, so it can be imported from models, migrations, services and the
API layer alike.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ACTIVE_PROCESSING_STATUSES",
    "TERMINAL_PROCESSING_STATUSES",
    "ChunkType",
    "DocumentType",
    "ProcessingJobStatus",
    "ProcessingStatus",
    "is_terminal",
]


class ProcessingStatus(StrEnum):
    """Authoritative state of a document inside the ingestion pipeline."""

    QUEUED = "queued"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJobStatus(StrEnum):
    """State of a single processing job (one ingestion attempt)."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkType(StrEnum):
    """Kind of content a chunk carries."""

    TEXT = "text"
    TABLE = "table"


class DocumentType(StrEnum):
    """Kind of financial document that was uploaded."""

    ANNUAL_REPORT = "annual_report"
    FORM_10K = "form_10k"
    FORM_10Q = "form_10q"
    EARNINGS_RELEASE = "earnings_release"
    ANNUAL_LETTER = "annual_letter"
    FINANCIAL_STATEMENTS = "financial_statements"
    OTHER = "other"


#: States from which the pipeline never continues.
TERMINAL_PROCESSING_STATUSES: frozenset[ProcessingStatus] = frozenset(
    {
        ProcessingStatus.COMPLETED,
        ProcessingStatus.FAILED,
    }
)

#: States from which the pipeline still has work to do.
ACTIVE_PROCESSING_STATUSES: frozenset[ProcessingStatus] = frozenset(
    {
        ProcessingStatus.QUEUED,
        ProcessingStatus.VALIDATING,
        ProcessingStatus.EXTRACTING,
        ProcessingStatus.CHUNKING,
        ProcessingStatus.EMBEDDING,
        ProcessingStatus.INDEXING,
    }
)


def is_terminal(status: ProcessingStatus | str) -> bool:
    """Return ``True`` when *status* is a terminal processing state.

    Unknown values are *not* terminal: an unrecognised state means the
    pipeline is still in flight as far as the caller is concerned.
    """
    try:
        resolved = ProcessingStatus(status)
    except ValueError:
        return False
    return resolved in TERMINAL_PROCESSING_STATUSES
