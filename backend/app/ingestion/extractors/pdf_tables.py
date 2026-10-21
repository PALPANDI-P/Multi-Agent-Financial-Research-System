"""Table extraction from a PDF (pdfplumber).

Table extraction is a *best effort* stage of the pipeline: a document that
has no ruled tables, a document that uses a layout pdfplumber cannot
understand and a document that trips pdfplumber up must never abort the
ingestion.  Every failure is therefore logged and swallowed; the pipeline
continues with the text layer of the document.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ingestion.contracts import (
    EXTRACTION_METHOD_TABLE,
    DocumentExtractionMetadata,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
)

__all__ = ["PdfPlumberTableExtractor"]

logger = get_logger(__name__)

#: The magic bytes every PDF file starts with.
PDF_MAGIC = b"%PDF-"


def _normalize_cell(cell: Any) -> str:
    """Return the whitespace normalised text of a table cell."""
    if cell is None:
        return ""
    return " ".join(str(cell).split())


class PdfPlumberTableExtractor:
    """Extract the tables of a PDF with pdfplumber."""

    name = "pdf_tables"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    # -- protocol ---------------------------------------------------------

    def supports(self, file_path: Path) -> bool:
        """Return ``True`` when *file_path* is an existing PDF file."""
        try:
            path = Path(file_path)
            if not path.is_file():
                return False
            with path.open("rb") as handle:
                head = handle.read(1024)
        except OSError:
            return False
        return PDF_MAGIC in head

    def extract(self, file_path: Path) -> ExtractedDocument:
        """Return a document that carries the tables of the PDF."""
        path = Path(file_path)
        pages: list[ExtractedPage] = []
        page_count = 0

        for page_number, page in self._iter_pages(path):
            page_count = max(page_count, page_number)
            try:
                tables = self._tables_of_page(page, page_number)
            except Exception as exc:  # one broken page must not abort
                logger.warning(
                    "Table extraction failed on page %s of %s: %s",
                    page_number,
                    path.name,
                    exc,
                )
                continue
            if tables:
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        text="",
                        headings=(),
                        tables=tuple(tables),
                        extraction_method=EXTRACTION_METHOD_TABLE,
                    )
                )

        return ExtractedDocument(
            pages=tuple(pages),
            metadata=DocumentExtractionMetadata(page_count=page_count),
            page_count=page_count,
        )

    # -- public API -------------------------------------------------------

    def extract_tables(self, file_path: Path) -> dict[int, list[ExtractedTable]]:
        """Return the tables of the PDF, grouped by page number.

        The keys of the returned mapping are **1-based** page numbers, the
        values are the tables of that page in the order pdfplumber found
        them.  An empty mapping is returned when the document could not be
        read at all - a table extraction failure never aborts the pipeline.
        """
        path = Path(file_path)
        tables_by_page: dict[int, list[ExtractedTable]] = {}

        for page_number, page in self._iter_pages(path):
            try:
                tables = self._tables_of_page(page, page_number)
            except Exception as exc:  # one broken page must not abort
                logger.warning(
                    "Table extraction failed on page %s of %s: %s",
                    page_number,
                    path.name,
                    exc,
                )
                continue
            if tables:
                tables_by_page[page_number] = tables

        return tables_by_page

    # -- internals --------------------------------------------------------

    def _iter_pages(self, path: Path) -> Iterator[tuple[int, Any]]:
        """Yield ``(page_number, page)`` for every page of the PDF."""
        try:
            import pdfplumber
        except ImportError:  # pragma: no cover - pdfplumber is a hard dependency
            logger.warning("pdfplumber is not installed - table extraction is skipped")
            return

        try:
            pdf = pdfplumber.open(path)
        except Exception as exc:  # any parser failure is the same
            logger.warning("pdfplumber could not open %s: %s", path.name, exc)
            return

        try:
            with pdf:
                yield from enumerate(pdf.pages, start=1)
        except Exception as exc:  # keep whatever was found already
            logger.warning("pdfplumber failed while reading %s: %s", path.name, exc)

    def _tables_of_page(self, page: Any, page_number: int) -> list[ExtractedTable]:
        """Return the tables of a single pdfplumber page."""
        tables: list[ExtractedTable] = []

        for table_index, table in enumerate(page.find_tables() or ()):
            rows: list[tuple[str, ...]] = []
            for raw_row in table.extract() or ():
                cells = tuple(_normalize_cell(cell) for cell in raw_row)
                if not any(cells):
                    continue
                rows.append(cells)

            if not rows:
                continue

            tables.append(
                ExtractedTable(
                    page_number=page_number,
                    table_index=table_index,
                    header=rows[0],
                    rows=tuple(rows[1:]),
                )
            )
        return tables