"""Unit tests of the ingestion pipeline.

The tests use small in-file fakes: no database, no network and no real
model.  They protect the contract of the pipeline - the reported stage
sequence, the failure handling, the OCR fallback, the reuse of embeddings,
the shape of the vector records and the idempotency of a run - and they
protect the architectural rule that the pipeline never imports the service
or the repository layer.
"""

from __future__ import annotations

import ast
import hashlib
import uuid
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.enums import ProcessingStatus
from app.core.exceptions import EmbeddingError, ValidationError
from app.ingestion.contracts import (
    EXTRACTION_METHOD_OCR,
    Chunk,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
)
from app.ingestion.pipeline import IngestionPipeline, IngestionResult
from app.vectorstore.base import VectorRecord

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz as pymupdf  # type: ignore[no-redef]

pytestmark = pytest.mark.unit

#: The stage sequence the pipeline has to report.
EXPECTED_SEQUENCE: list[tuple[str, str]] = [
    (ProcessingStatus.VALIDATING.value, "validating"),
    (ProcessingStatus.EXTRACTING.value, "pdf_text"),
    (ProcessingStatus.EXTRACTING.value, "pdf_tables"),
    (ProcessingStatus.EXTRACTING.value, "ocr"),
    (ProcessingStatus.CHUNKING.value, "chunking"),
    (ProcessingStatus.EMBEDDING.value, "embedding"),
    (ProcessingStatus.INDEXING.value, "indexing"),
    (ProcessingStatus.COMPLETED.value, "completed"),
]

#: The key of the stored document.
STORAGE_KEY = "2025/01/0a1b2c3d.pdf"

#: The text of the pages of the fake document.
PAGE_TEXT = (
    "Acme Corporation Annual Report for the fiscal year 2025. The revenue of "
    "the group grew by eight percent compared with the previous year."
)


def _pdf_bytes(text: str = PAGE_TEXT) -> bytes:
    """Return the bytes of a small but *valid* PDF with *text* on one page.

    The pipeline re-validates the stored bytes, therefore the fake storage
    has to hand out a document that really is a PDF with a text layer.
    """
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 100), text, fontsize=11)
        return document.tobytes()
    finally:
        document.close()


def _pages(count: int) -> list[ExtractedPage]:
    """Return *count* fake pages with a text layer."""
    return [
        ExtractedPage(page_number=index + 1, text=f"{PAGE_TEXT} (page {index + 1})")
        for index in range(count)
    ]


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------
class FakeStorage:
    """A storage backend that always returns the same bytes."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.reads: list[str] = []

    def save(self, data: bytes, *, extension: str) -> str:
        """Pretend to store *data*."""
        return "saved"

    def read(self, storage_key: str) -> bytes:
        """Return the stored bytes."""
        self.reads.append(storage_key)
        return self._payload

    def delete(self, storage_key: str) -> None:
        """Pretend to delete the document."""
        return None

    def exists(self, storage_key: str) -> bool:
        """Return ``True``: the fake always has the document."""
        return True

    def path_for(self, storage_key: str) -> Path:
        """Return a virtual path for *storage_key*."""
        return Path("virtual") / storage_key


class FakeTextExtractor:
    """Returns a fixed document."""

    def __init__(self, pages: list[ExtractedPage]) -> None:
        self._pages = pages
        self.calls = 0

    def extract(self, file_path: Path) -> ExtractedDocument:
        """Return the fake document."""
        self.calls += 1
        return ExtractedDocument(
            pages=tuple(self._pages),
            page_count=len(self._pages),
        )


class FakeTableExtractor:
    """Returns a fixed mapping of tables."""

    def __init__(self, tables: dict[int, list[ExtractedTable]] | None = None) -> None:
        self._tables = tables or {}
        self.calls = 0

    def extract_tables(self, file_path: Path) -> dict[int, list[ExtractedTable]]:
        """Return the fake tables."""
        self.calls += 1
        return self._tables


class FakeOcrAvailability:
    """The availability report of the fake OCR extractor."""

    def __init__(self, available: bool) -> None:
        self.available = available


class FakeOcrExtractor:
    """An OCR extractor that is either available or not."""

    def __init__(self, available: bool = False, text: str = "ocr text") -> None:
        self._available = available
        self._text = text
        self.calls: list[int] = []

    def is_available(self) -> FakeOcrAvailability:
        """Return the availability of the fake OCR extractor."""
        return FakeOcrAvailability(self._available)

    def extract_page(self, pdf_path: Path, page_number: int) -> ExtractedPage:
        """Return the OCR text of the page."""
        self.calls.append(page_number)
        return ExtractedPage(
            page_number=page_number,
            text=self._text,
            extraction_method=EXTRACTION_METHOD_OCR,
        )


class FakeChunker:
    """Turns every page into exactly one chunk."""

    def __init__(self) -> None:
        self.documents: list[ExtractedDocument] = []

    def chunk(self, document: ExtractedDocument) -> list[Chunk]:
        """Return one chunk per page of *document*."""
        self.documents.append(document)
        return [
            Chunk(
                chunk_index=index,
                content=page.text,
                page_start=page.page_number,
                page_end=page.page_number,
                section_heading=None,
                token_count=len(page.text.split()),
                metadata={"source": "unit-test"},
            )
            for index, page in enumerate(document.pages)
        ]


class FakeEmbeddingService:
    """An embedding service that counts what it was asked to embed."""

    def __init__(self, config_hash: str = "config-hash") -> None:
        self._config_hash = config_hash
        self.embedded_texts: list[str] = []
        self.error: Exception | None = None

    @property
    def config_hash(self) -> str:
        """Return the hash of the (fake) embedding configuration."""
        return self._config_hash

    def embed_texts_reusing(
        self,
        texts: Sequence[str],
        content_hashes: Sequence[str],
        existing: dict[str, tuple[str, list[float]]],
    ) -> list[list[float]]:
        """Return one vector per text, reusing the vectors of *existing*."""
        if self.error is not None:
            raise self.error
        vectors: list[list[float]] = []
        for text, content_hash in zip(texts, content_hashes, strict=True):
            stored = existing.get(content_hash)
            if stored is not None:
                vectors.append(stored[1])
                continue
            self.embedded_texts.append(text)
            vectors.append([float(len(text)), 0.0, 0.0])
        return vectors


class FakeVectorStore:
    """A vector store that keeps the records in a list."""

    def __init__(self) -> None:
        self.records: list[VectorRecord] = []
        self.deleted: list[UUID] = []

    def upsert_chunks(self, records: Sequence[VectorRecord]) -> int:
        """Write *records*, replacing the ones with the same chunk index."""
        for record in records:
            self.records = [
                existing
                for existing in self.records
                if not (
                    existing.document_id == record.document_id
                    and existing.chunk_index == record.chunk_index
                )
            ]
            self.records.append(record)
        return len(records)

    def delete_document_chunks(self, document_id: UUID) -> int:
        """Remove every chunk of *document_id*."""
        before = len(self.records)
        self.records = [
            record for record in self.records if record.document_id != document_id
        ]
        self.deleted.append(document_id)
        return before - len(self.records)

    def count_chunks(self, document_id: UUID | None = None) -> int:
        """Return the number of stored chunks."""
        if document_id is None:
            return len(self.records)
        return len(
            [record for record in self.records if record.document_id == document_id]
        )

    def get_existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """The fake store keeps no embedding state."""
        return {}

    def search(self, *args: object, **kwargs: object) -> list[object]:
        """The fake store is never searched."""
        return []


class FakeReporter:
    """Records the reported ``(status, stage)`` pairs."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []
        self.failures: list[tuple[str | None, str | None]] = []

    def report_status(
        self,
        document_id: UUID,
        status: ProcessingStatus | str,
        *,
        stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record the status of the document."""
        value = status.value if isinstance(status, ProcessingStatus) else str(status)
        self.events.append((value, stage))
        if error_code is not None or error_message is not None:
            self.failures.append((error_code, error_message))

    @property
    def sequence(self) -> list[tuple[str, str | None]]:
        """Return the recorded sequence."""
        return list(self.events)


class FakeEmbeddingSource:
    """Returns a fixed mapping of existing embeddings."""

    def __init__(
        self,
        existing: dict[str, tuple[str, list[float]]] | None = None,
    ) -> None:
        self._existing = existing or {}

    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return the fake mapping."""
        return dict(self._existing)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return the settings of the unit test."""
    return Settings(
        database_url="postgresql+psycopg://frs:frs@127.0.0.1:5432/financial_research_test",
        app_env="test",
        storage_root=tmp_path / "storage",
    )


@pytest.fixture
def document_id() -> UUID:
    """Return the id of the processed document."""
    return uuid.uuid4()


@pytest.fixture
def workspace_id() -> UUID:
    """Return the id of the workspace of the document."""
    return uuid.uuid4()


@pytest.fixture
def reporter() -> FakeReporter:
    """Return the fake reporter."""
    return FakeReporter()


@pytest.fixture
def store() -> FakeVectorStore:
    """Return the fake vector store."""
    return FakeVectorStore()


@pytest.fixture
def embedding_service() -> FakeEmbeddingService:
    """Return the fake embedding service."""
    return FakeEmbeddingService()


def _pipeline(
    *,
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    pages: list[ExtractedPage] | None = None,
    ocr_extractor: FakeOcrExtractor | None = None,
    tables: dict[int, list[ExtractedTable]] | None = None,
    existing: dict[str, tuple[str, list[float]]] | None = None,
) -> IngestionPipeline:
    """Return a pipeline that is wired with the fakes."""
    return IngestionPipeline(
        storage=FakeStorage(_pdf_bytes()),
        text_extractor=FakeTextExtractor(pages if pages is not None else _pages(2)),
        table_extractor=FakeTableExtractor(tables),
        ocr_extractor=ocr_extractor or FakeOcrExtractor(available=False),
        chunker=FakeChunker(),
        embedding_service=embedding_service,
        vector_store=store,
        reporter=reporter,
        embedding_source=FakeEmbeddingSource(existing),
        settings=settings,
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_the_pipeline_reports_every_stage_in_order(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """The reported sequence is exactly the documented one."""
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
    )

    result = pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert reporter.sequence == EXPECTED_SEQUENCE
    assert isinstance(result, IngestionResult)
    assert result.document_id == document_id
    assert result.page_count == 2
    assert result.chunk_count == 2


def test_a_failure_in_the_embedding_stage_is_reported_and_re_raised(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """The failure is reported as ``FAILED`` and the error is re-raised."""
    embedding_service.error = EmbeddingError(
        "the embedding provider is unreachable",
        error_code="embedding_provider_unreachable",
    )
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
    )

    with pytest.raises(EmbeddingError):
        pipeline.run(
            document_id=document_id,
            storage_key=STORAGE_KEY,
            content_hash="",
            workspace_id=workspace_id,
        )

    assert reporter.sequence == [
        *EXPECTED_SEQUENCE[:6],
        (ProcessingStatus.FAILED.value, None),
    ]
    assert reporter.failures == [
        ("embedding_provider_unreachable", "the embedding provider is unreachable")
    ]
    assert store.count_chunks() == 0


def test_a_page_without_text_and_without_ocr_is_never_fabricated(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """An empty page produces a warning, never invented text."""
    pages = [
        ExtractedPage(page_number=1, text=PAGE_TEXT),
        ExtractedPage(page_number=2, text=""),
    ]
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
        pages=pages,
        ocr_extractor=FakeOcrExtractor(available=False),
    )

    result = pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert any("ocr" in warning for warning in result.warnings)
    assert any("page 2" in warning for warning in result.warnings)

    # The empty page was left exactly as it was: no text was invented for it.
    contents = [record.content for record in store.records]
    assert contents[1] == ""
    assert all("ocr text" not in content for content in contents)


def test_an_available_ocr_replaces_the_text_of_the_page(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """An available OCR extractor fills the page with the scanned text."""
    pages = [
        ExtractedPage(page_number=1, text=PAGE_TEXT),
        ExtractedPage(page_number=2, text=""),
    ]
    ocr = FakeOcrExtractor(available=True, text="scanned revenue of 1.2 billion")
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
        pages=pages,
        ocr_extractor=ocr,
    )

    result = pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert ocr.calls == [2]
    assert "scanned revenue of 1.2 billion" in [
        record.content for record in store.records
    ]
    assert not any("ocr" in warning for warning in result.warnings)


def test_the_embedding_stage_only_embeds_the_missing_texts(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """A stored vector with the same configuration hash is reused."""
    pages = _pages(3)
    contents = [page.text for page in pages]
    hashes = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in contents]
    existing = {hashes[0]: ("config-hash", [1.0, 0.0, 0.0])}

    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
        pages=pages,
        existing=existing,
    )

    result = pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert embedding_service.embedded_texts == contents[1:]
    assert result.chunk_count == 3
    assert result.reused_embedding_count == 1
    assert result.embedded_count == 2


def test_the_vector_store_receives_one_record_per_chunk(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """Every record carries the chunk index and the provenance metadata."""
    pages = _pages(2)
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
        pages=pages,
    )

    pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert len(store.records) == 2
    for index, record in enumerate(store.records):
        expected_hash = hashlib.sha256(
            pages[index].text.encode("utf-8")
        ).hexdigest()
        assert record.document_id == document_id
        assert record.workspace_id == workspace_id
        assert record.chunk_index == index
        assert record.content == pages[index].text
        assert record.page_start == index + 1
        assert record.page_end == index + 1
        assert record.metadata["content_hash"] == expected_hash
        assert record.metadata["embedding_config_hash"] == "config-hash"
        assert record.metadata["token_count"] == len(pages[index].text.split())
        assert record.metadata["source"] == "unit-test"


def test_running_the_pipeline_twice_leaves_one_chunk_per_chunk_index(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """The run is idempotent: no duplicate chunk is left behind."""
    pipeline = _pipeline(
        settings=settings,
        reporter=reporter,
        store=store,
        embedding_service=embedding_service,
        pages=_pages(2),
    )

    pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )
    pipeline.run(
        document_id=document_id,
        storage_key=STORAGE_KEY,
        content_hash="",
        workspace_id=workspace_id,
    )

    assert store.count_chunks(document_id) == 2
    indexes = sorted(record.chunk_index for record in store.records)
    assert indexes == [0, 1]
    assert store.deleted == [document_id, document_id]


def test_an_invalid_stored_document_is_rejected(
    settings: Settings,
    reporter: FakeReporter,
    store: FakeVectorStore,
    embedding_service: FakeEmbeddingService,
    document_id: UUID,
    workspace_id: UUID,
) -> None:
    """The stored bytes are validated again before they are processed."""
    pipeline = IngestionPipeline(
        storage=FakeStorage(b"this is not a pdf"),
        text_extractor=FakeTextExtractor(_pages(1)),
        table_extractor=FakeTableExtractor(),
        ocr_extractor=FakeOcrExtractor(),
        chunker=FakeChunker(),
        embedding_service=embedding_service,
        vector_store=store,
        reporter=reporter,
        embedding_source=FakeEmbeddingSource(),
        settings=settings,
    )

    with pytest.raises(ValidationError):
        pipeline.run(
            document_id=document_id,
            storage_key=STORAGE_KEY,
            content_hash="",
            workspace_id=workspace_id,
        )

    assert reporter.sequence == [
        (ProcessingStatus.VALIDATING.value, "validating"),
        (ProcessingStatus.FAILED.value, None),
    ]
    assert store.count_chunks() == 0


def test_the_pipeline_module_does_not_import_the_services_or_the_repositories() -> None:
    """The pipeline stays a pure orchestration component.

    The module is scanned with the abstract syntax tree: a dynamic import
    would not be found, but a dynamic import would also be a lie.
    """
    import app.ingestion.pipeline as pipeline_module

    path = Path(pipeline_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or not node.module:
                continue
            imported.add(node.module)
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")

    forbidden = sorted(
        name
        for name in imported
        if name.startswith("app.services") or name.startswith("app.repositories")
    )
    assert forbidden == [], (
        "the ingestion pipeline must not import the service or the repository "
        f"layer, but it imports {forbidden}"
    )
