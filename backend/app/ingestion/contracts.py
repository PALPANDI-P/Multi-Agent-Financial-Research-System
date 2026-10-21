"""Immutable hand-off contracts of the document ingestion pipeline.

The dataclasses in this module are the *only* objects that are passed
between the extraction, chunking, embedding and vector-store layers.  They
are deliberately frozen: once a value has been handed over, no later stage
may modify it, which keeps the pipeline reproducible and makes the data
flow easy to reason about.

Every mapping field is exposed as a read-only :class:`~types.MappingProxyType`
so that a frozen dataclass cannot be used to smuggle a mutable dictionary
into the next stage.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from app.core.enums import ChunkType

__all__ = [
    "EXTRACTION_METHOD_EMPTY",
    "EXTRACTION_METHOD_OCR",
    "EXTRACTION_METHOD_TABLE",
    "EXTRACTION_METHOD_TEXT",
    "Chunk",
    "DocumentExtractionMetadata",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedTable",
]

#: Text was taken from the embedded text layer of the PDF.
EXTRACTION_METHOD_TEXT = "pdf_text"
#: Tables were taken from the table layer of the PDF.
EXTRACTION_METHOD_TABLE = "pdf_tables"
#: The page had to be processed with optical character recognition.
EXTRACTION_METHOD_OCR = "ocr"
#: Nothing could be extracted from the page.
EXTRACTION_METHOD_EMPTY = "empty"


def _freeze_mapping[ValueT](value: Mapping[str, ValueT]) -> Mapping[str, ValueT]:
    """Return an immutable, shallow copy of *value*."""
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class DocumentExtractionMetadata:
    """Metadata that describes a document as a whole."""

    company_name: str | None = None
    document_title: str | None = None
    document_type: str | None = None
    fiscal_period: str | None = None
    page_count: int = 0
    detected_language: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Replace the mutable mapping by an immutable view of it."""
        object.__setattr__(self, "extra", _freeze_mapping(self.extra))


@dataclass(frozen=True, slots=True)
class ExtractedTable:
    """A single table that was found on one page."""

    page_number: int
    table_index: int
    header: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    caption: str | None = None
    units: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """A single page of a document."""

    page_number: int
    text: str = ""
    headings: tuple[str, ...] = ()
    tables: tuple[ExtractedTable, ...] = ()
    extraction_method: str = EXTRACTION_METHOD_TEXT
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """The full result of the extraction stage."""

    pages: tuple[ExtractedPage, ...] = ()
    metadata: DocumentExtractionMetadata = field(default_factory=DocumentExtractionMetadata)
    page_count: int = 0
    warnings: tuple[str, ...] = ()

    def iter_tables(self) -> Iterator[tuple[ExtractedPage, ExtractedTable]]:
        """Yield ``(page, table)`` pairs for every table of the document.

        The owning page comes first so that the caller keeps the page
        context (page number, headings, extraction method) of each table.
        The pairs are produced in document order: pages in the order they
        appear in :attr:`pages`, tables in the order they appear on a page.
        """
        for page in self.pages:
            for table in page.tables:
                yield page, table

    def page_by_number(self, page_number: int) -> ExtractedPage | None:
        """Return the page with *page_number*, or ``None`` if there is none."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None

    def full_text(self) -> str:
        """Return the text of every page, joined by a blank line."""
        return "\n\n".join(page.text for page in self.pages)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable slice of a document, ready to be embedded."""

    chunk_index: int
    content: str
    chunk_type: str = ChunkType.TEXT.value
    page_start: int | None = None
    page_end: int | None = None
    section_heading: str | None = None
    token_count: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Replace the mutable mapping by an immutable view of it."""
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
