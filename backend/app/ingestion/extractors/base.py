"""Base contract shared by every document extractor.

Design rules
------------
* **Pure.**  An extractor derives its output exclusively from the bytes of
  the file it is given.  It never writes to the database, never mutates
  global state and never mutates the document itself.
* **Stateless.**  The only state an extractor holds is the configuration
  that is injected at construction time, therefore the same instance can be
  reused for any number of documents.
* **Independently testable.**  Because extractors are pure functions of
  their input they can be unit tested without a database, a network
  connection or a fixture directory: build a PDF in memory, call
  :meth:`DocumentExtractor.extract` and assert on the returned
  :class:`~app.ingestion.contracts.ExtractedDocument`.
* **Explicit failures.**  Unrecoverable problems raise
  :class:`app.core.exceptions.ExtractionError` with a stable machine
  readable ``code``; recoverable problems (a single unreadable page, a
  missing optional dependency) are reported as a warning and never abort
  the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.exceptions import ExtractionError
from app.ingestion.contracts import ExtractedDocument

__all__ = ["DocumentExtractor", "extraction_error"]


@runtime_checkable
class DocumentExtractor(Protocol):
    """The protocol every extraction strategy implements.

    Attributes
    ----------
    name:
        Stable, machine readable identifier of the strategy, for example
        ``"pdf_text"``.  The value matches the ``EXTRACTION_METHOD_*``
        constants of :mod:`app.ingestion.contracts` and is stored in
        ``documents.processing_stage``.
    """

    name: str

    def supports(self, file_path: Path) -> bool:
        """Return ``True`` when the extractor can handle *file_path*."""
        ...

    def extract(self, file_path: Path) -> ExtractedDocument:
        """Return the extracted document for *file_path*."""
        ...


def extraction_error(
    message: str,
    *,
    code: str,
    **details: Any,
) -> ExtractionError:
    """Return an :class:`~app.core.exceptions.ExtractionError` for *code*.

    The machine readable code is exposed three times so that it can never
    be lost on the way to the API envelope or to the processing job record:

    * as :attr:`~app.core.exceptions.AppError.code` (the stable envelope
      code),
    * as ``error_code`` (the finer grained diagnosis used by the job
      records), and
    * as ``details["error_code"]`` (so that it survives serialisation).
    """
    error = ExtractionError(message, code=code, details={"error_code": code, **details})
    error.error_code = code  # type: ignore[attr-defined]
    return error