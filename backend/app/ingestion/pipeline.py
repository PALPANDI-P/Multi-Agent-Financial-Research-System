"""Orchestration of the document ingestion pipeline.

The pipeline turns a stored document into indexed, searchable chunks.  It
runs eight stages and reports the state of the document after every one of
them, so that the API layer (and a human) always sees where the processing
stands:

=============  =====================  ==================================
``stage``      ``ProcessingStatus``    work
=============  =====================  ==================================
``validating``  ``VALIDATING``         re-validate the stored bytes
``pdf_text``    ``EXTRACTING``         read the text layer of the PDF
``pdf_tables``  ``EXTRACTING``         read the tables of the PDF
``ocr``         ``EXTRACTING``         OCR the pages without a text layer
``chunking``    ``CHUNKING``           split the document into chunks
``embedding``   ``EMBEDDING``          embed the chunks (with reuse)
``indexing``    ``INDEXING``           write the chunks into the vector store
``completed``   ``COMPLETED``          everything is done
=============  =====================  ==================================

Design rules
------------
* **No transaction is open during the extraction or the embedding.**  The
  pipeline owns *no* session at all: the reporter and the vector store each
  manage their own short transactions and the pipeline only calls them.  A
  long running extraction therefore never blocks the database.
* **The pipeline is a pure orchestration component.**  It does **not** import
  ``app.services`` or ``app.repositories``; it only depends on the two
  protocols defined below and on the components that are injected into it.
  This is what allows a future dedicated worker (Celery/RQ/Arq) to run the
  pipeline unchanged.
* **A failure never leaves a document in a non-terminal state.**  Every
  exception is reported as ``FAILED`` (with an error code and a concise,
  non secret message) before it is re-raised.
* **The run is idempotent.**  Running the pipeline twice for the same
  document leaves exactly one chunk per ``(document_id, chunk_index)``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.enums import ProcessingStatus
from app.core.exceptions import ProcessingError, ValidationError
from app.core.logging import get_logger
from app.core.storage import StorageBackend
from app.embeddings.service import EmbeddingService
from app.ingestion.chunking import Chunker
from app.ingestion.contracts import (
    EXTRACTION_METHOD_OCR,
    Chunk,
    DocumentExtractionMetadata,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
)
from app.ingestion.metadata import build_document_metadata
from app.ingestion.validators import FileValidator
from app.vectorstore.base import VectorRecord, VectorStore

__all__ = [
    "ExistingEmbeddingSource",
    "IngestionPipeline",
    "IngestionResult",
    "OcrAvailabilityLike",
    "OcrTextExtractor",
    "ProcessingStatusReporter",
    "TableExtractor",
    "TextExtractor",
    "error_code_of",
    "error_message_of",
]

logger = get_logger(__name__)

#: Maximum length of the error message that is stored on the document.
MAX_ERROR_MESSAGE_LENGTH: int = 500

#: Stage names of the pipeline (the value of ``documents.processing_stage``).
STAGE_VALIDATING = "validating"
STAGE_PDF_TEXT = "pdf_text"
STAGE_PDF_TABLES = "pdf_tables"
STAGE_OCR = "ocr"
STAGE_CHUNKING = "chunking"
STAGE_EMBEDDING = "embedding"
STAGE_INDEXING = "indexing"
STAGE_COMPLETED = "completed"


# ---------------------------------------------------------------------------
# protocols
# ---------------------------------------------------------------------------
@runtime_checkable
class ProcessingStatusReporter(Protocol):
    """The sink the pipeline reports the state of a document to."""

    def report_status(
        self,
        document_id: UUID,
        status: ProcessingStatus | str,
        *,
        stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record the new *status* of the document *document_id*."""
        ...


@runtime_checkable
class ExistingEmbeddingSource(Protocol):
    """Source of the embeddings that were already computed for a document."""

    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``."""
        ...


@runtime_checkable
class TextExtractor(Protocol):
    """Extracts the text layer of a document."""

    def extract(self, file_path: Path) -> ExtractedDocument:
        """Return the extracted document of *file_path*."""
        ...


@runtime_checkable
class TableExtractor(Protocol):
    """Extracts the tables of a document."""

    def extract_tables(
        self,
        file_path: Path,
    ) -> dict[int, list[ExtractedTable]]:
        """Return the tables of *file_path*, grouped by page number."""
        ...


@runtime_checkable
class OcrAvailabilityLike(Protocol):
    """Structural protocol of the OCR availability report."""

    @property
    def available(self) -> bool:
        """Return ``True`` when OCR can actually be executed."""
        ...


@runtime_checkable
class OcrTextExtractor(Protocol):
    """Reads the text of a scanned page with optical character recognition."""

    def is_available(self) -> OcrAvailabilityLike:
        """Return whether OCR can be executed on this machine."""
        ...

    def extract_page(self, pdf_path: Path, page_number: int) -> ExtractedPage:
        """Return the OCR text of the 1-based *page_number* of *pdf_path*."""
        ...


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class IngestionResult:
    """The outcome of a single run of the ingestion pipeline."""

    document_id: UUID
    page_count: int
    chunk_count: int
    embedded_count: int
    reused_embedding_count: int
    metadata: DocumentExtractionMetadata
    warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def error_code_of(exc: BaseException) -> str:
    """Return the stable error code of *exc*.

    The ``error_code`` attribute wins (it is the fine grained diagnosis of
    the domain exceptions), then the ``code`` attribute (the stable envelope
    code) and finally the class name of the exception.
    """
    for attribute in ("error_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, str) and value:
            return value
    return type(exc).__name__


def error_message_of(exc: BaseException) -> str:
    """Return a concise, non secret message for *exc*.

    The message is collapsed into a single line and truncated, because it is
    written to the database and shown to a user.  It never contains a stack
    trace and never contains a secret.
    """
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(exc)
    message = " ".join(message.split())
    if len(message) > MAX_ERROR_MESSAGE_LENGTH:
        message = message[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."
    return message or type(exc).__name__


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------
class IngestionPipeline:
    """Turns a stored document into indexed chunks.

    The pipeline is a pure orchestrator: every component it needs is
    injected, therefore it can be executed by the document agent, by a
    background thread or by a future dedicated worker without a change.
    """

    def __init__(
        self,
        *,
        storage: StorageBackend,
        text_extractor: TextExtractor,
        table_extractor: TableExtractor,
        ocr_extractor: OcrTextExtractor,
        chunker: Chunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        reporter: ProcessingStatusReporter,
        embedding_source: ExistingEmbeddingSource,
        settings: Settings,
    ) -> None:
        """Create the pipeline.

        Parameters
        ----------
        storage:
            Backend the stored document is read from.
        text_extractor:
            Extractor of the text layer of the document.
        table_extractor:
            Extractor of the tables of the document.
        ocr_extractor:
            Extractor of scanned pages.
        chunker:
            Splitter that turns the extracted document into chunks.
        embedding_service:
            Service that embeds the chunks (and reuses the vectors that were
            already computed).
        vector_store:
            Store the chunks are written to.
        reporter:
            Sink the state of the document is reported to.
        embedding_source:
            Source of the embeddings that are already stored for a document.
        settings:
            Application settings (the thresholds of the pipeline).
        """
        self._storage = storage
        self._text_extractor = text_extractor
        self._table_extractor = table_extractor
        self._ocr_extractor = ocr_extractor
        self._chunker = chunker
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._reporter = reporter
        self._embedding_source = embedding_source
        self._settings = settings
        self._validator = FileValidator(settings)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def run(
        self,
        *,
        document_id: UUID,
        storage_key: str,
        content_hash: str,
        workspace_id: UUID | None = None,
    ) -> IngestionResult:
        """Process the document that is stored under *storage_key*.

        Parameters
        ----------
        document_id:
            Id of the document the run belongs to.
        storage_key:
            Key of the document in the storage backend.
        content_hash:
            SHA-256 hash of the document as it was registered.  It is only
            used to report an integrity warning.
        workspace_id:
            Id of the workspace the document belongs to.  It is **required**:
            every chunk is written with the id of its workspace because the
            vector store enforces the workspace isolation with it.  When it
            is omitted the pipeline asks the injected components for a
            ``workspace_id_for(document_id)`` method and raises a
            :class:`~app.core.exceptions.ProcessingError` when the workspace
            cannot be determined.

        Returns
        -------
        IngestionResult
            The outcome of the run.

        Raises
        ------
        Exception
            Every failure of a stage is reported as ``FAILED`` and then
            re-raised.
        """
        try:
            return self._run(
                document_id=document_id,
                storage_key=storage_key,
                content_hash=content_hash,
                workspace_id=workspace_id,
            )
        except Exception as exc:
            self._report_failure(document_id, exc)
            raise

    # ------------------------------------------------------------------
    # the stages
    # ------------------------------------------------------------------
    def _run(
        self,
        *,
        document_id: UUID,
        storage_key: str,
        content_hash: str,
        workspace_id: UUID | None,
    ) -> IngestionResult:
        """Execute the stages of the pipeline."""
        warnings: list[str] = []
        resolved_workspace = self._resolve_workspace_id(document_id, workspace_id)

        # 1. validating -----------------------------------------------------
        self._report(document_id, ProcessingStatus.VALIDATING, STAGE_VALIDATING)
        payload = self._storage.read(storage_key)
        self._validate_stored_payload(storage_key, payload)
        if content_hash:
            digest = hashlib.sha256(payload).hexdigest()
            if digest != content_hash:
                warnings.append(
                    "the stored bytes do not match the recorded content hash"
                )

        path = self._storage.path_for(storage_key)

        # 2. extracting: the text layer -------------------------------------
        self._report(document_id, ProcessingStatus.EXTRACTING, STAGE_PDF_TEXT)
        extracted = self._text_extractor.extract(path)
        pages = list(extracted.pages)
        for page in pages:
            warnings.extend(page.warnings)

        # 3. extracting: the tables -----------------------------------------
        self._report(document_id, ProcessingStatus.EXTRACTING, STAGE_PDF_TABLES)
        tables_by_page = self._table_extractor.extract_tables(path)
        if tables_by_page:
            pages = [
                self._attach_tables(page, tables_by_page.get(page.page_number, ()))
                for page in pages
            ]

        # 4. extracting: the scanned pages ----------------------------------
        self._report(document_id, ProcessingStatus.EXTRACTING, STAGE_OCR)
        pages, ocr_warnings = self._apply_ocr(path, pages)
        warnings.extend(ocr_warnings)

        # 5. chunking --------------------------------------------------------
        self._report(document_id, ProcessingStatus.CHUNKING, STAGE_CHUNKING)
        metadata = build_document_metadata(
            [page.text for page in pages],
            Path(storage_key).name,
        )
        document = ExtractedDocument(
            pages=tuple(pages),
            metadata=metadata,
            page_count=len(pages),
            warnings=tuple(warnings),
        )
        chunks = self._chunker.chunk(document)

        # 6. embedding -------------------------------------------------------
        self._report(document_id, ProcessingStatus.EMBEDDING, STAGE_EMBEDDING)
        texts = [chunk.content for chunk in chunks]
        content_hashes = [
            hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
            for chunk in chunks
        ]
        existing = self._embedding_source.existing_embeddings(document_id)
        embeddings = self._embedding_service.embed_texts_reusing(
            texts, content_hashes, existing
        )
        reused_count = self._count_reused(content_hashes, existing)

        # 7. indexing --------------------------------------------------------
        self._report(document_id, ProcessingStatus.INDEXING, STAGE_INDEXING)
        self._vector_store.delete_document_chunks(document_id)
        records = [
            self._build_record(
                chunk=chunk,
                embedding=embeddings[index],
                content_hash=content_hashes[index],
                document_id=document_id,
                workspace_id=resolved_workspace,
            )
            for index, chunk in enumerate(chunks)
        ]
        self._vector_store.upsert_chunks(records)

        # 8. completed -------------------------------------------------------
        self._report(document_id, ProcessingStatus.COMPLETED, STAGE_COMPLETED)

        return IngestionResult(
            document_id=document_id,
            page_count=len(pages),
            chunk_count=len(chunks),
            embedded_count=len(chunks) - reused_count,
            reused_embedding_count=reused_count,
            metadata=metadata,
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _report(
        self,
        document_id: UUID,
        status: ProcessingStatus,
        stage: str | None = None,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Report the *status* of the document to the reporter."""
        self._reporter.report_status(
            document_id,
            status,
            stage=stage,
            error_code=error_code,
            error_message=error_message,
        )

    def _report_failure(self, document_id: UUID, exc: Exception) -> None:
        """Report *exc* as a failure of the document and log it."""
        error_code = error_code_of(exc)
        error_message = error_message_of(exc)
        logger.error(
            "the processing of the document %s failed: %s",
            document_id,
            error_message,
            extra={"document_id": str(document_id), "error_code": error_code},
        )
        try:
            self._report(
                document_id,
                ProcessingStatus.FAILED,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:  # the status must never mask the original error
            logger.exception(
                "the failure of the document %s could not be reported",
                document_id,
            )

    def _resolve_workspace_id(
        self,
        document_id: UUID,
        workspace_id: UUID | None,
    ) -> UUID:
        """Return the workspace the document belongs to."""
        if workspace_id is not None:
            return workspace_id

        for component in (self._embedding_source, self._reporter):
            resolver = getattr(component, "workspace_id_for", None)
            if not callable(resolver):
                continue
            resolved = resolver(document_id)
            if resolved is not None:
                return UUID(str(resolved))

        raise ProcessingError(
            "the workspace of the document is unknown; the pipeline needs the "
            "workspace id to write the chunks",
            code="missing_workspace_id",
            details={"document_id": str(document_id)},
        )

    def _validate_stored_payload(self, storage_key: str, payload: bytes) -> None:
        """Re-validate the bytes that are stored under *storage_key*.

        The upload was validated when it was registered, but the stored file
        is checked again: the file system is outside the trust boundary of
        the application.
        """
        result = self._validator.validate(
            filename=Path(storage_key).name,
            declared_mime_type=None,
            data=payload,
        )
        if result.ok:
            return
        raise ValidationError(
            "the stored document does not pass the validation any more",
            code="invalid_stored_document",
            details={
                "issues": list(result.error_codes()),
                "storage_key": storage_key,
            },
        )

    @staticmethod
    def _attach_tables(
        page: ExtractedPage,
        tables: list[ExtractedTable] | tuple[ExtractedTable, ...],
    ) -> ExtractedPage:
        """Return *page* with the *tables* that belong to it."""
        if not tables:
            return page
        return replace(page, tables=tuple(tables))

    def _apply_ocr(
        self,
        path: Path,
        pages: list[ExtractedPage],
    ) -> tuple[list[ExtractedPage], list[str]]:
        """Read the pages that have no usable text layer with OCR.

        The text of a page is never fabricated: when OCR is not available the
        page is left untouched and a warning is recorded instead.
        """
        threshold = self._settings.min_text_chars_per_page
        available = self._ocr_extractor.is_available()
        warnings: list[str] = []
        updated: list[ExtractedPage] = []

        for page in pages:
            if len((page.text or "").strip()) >= threshold:
                updated.append(page)
                continue

            if not available.available:
                warnings.append(
                    f"page {page.page_number}: scanned content could not be "
                    "extracted (ocr unavailable)"
                )
                updated.append(page)
                continue

            try:
                ocr_page = self._ocr_extractor.extract_page(path, page.page_number)
            except Exception as exc:
                warnings.append(
                    f"page {page.page_number}: scanned content could not be "
                    f"extracted ({error_message_of(exc)})"
                )
                updated.append(page)
                continue

            updated.append(
                replace(
                    page,
                    text=ocr_page.text,
                    extraction_method=EXTRACTION_METHOD_OCR,
                )
            )

        return updated, warnings

    def _count_reused(
        self,
        content_hashes: list[str],
        existing: dict[str, tuple[str, list[float]]],
    ) -> int:
        """Return the number of embeddings that were reused."""
        config_hash = self._embedding_service.config_hash
        reused = 0
        for content_hash in content_hashes:
            stored = existing.get(content_hash)
            if stored is None:
                continue
            if stored[0] == config_hash:
                reused += 1
        return reused

    def _build_record(
        self,
        *,
        chunk: Chunk,
        embedding: list[float],
        content_hash: str,
        document_id: UUID,
        workspace_id: UUID,
    ) -> VectorRecord:
        """Return the vector record of *chunk*."""
        metadata: dict[str, object] = dict(chunk.metadata)
        metadata["content_hash"] = content_hash
        metadata["embedding_config_hash"] = self._embedding_service.config_hash
        metadata["token_count"] = chunk.token_count

        return VectorRecord(
            chunk_id=uuid4(),
            document_id=document_id,
            workspace_id=workspace_id,
            content=chunk.content,
            embedding=embedding,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_heading=chunk.section_heading,
            chunk_type=chunk.chunk_type,
            chunk_index=chunk.chunk_index,
            metadata=metadata,
        )