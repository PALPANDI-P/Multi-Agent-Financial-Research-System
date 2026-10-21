"""Text extraction from the embedded text layer of a PDF (PyMuPDF).

The extractor reads the text layer of every page, detects the headings of
the page and reports pages that carry (almost) no text at all.  Pages with
almost no text are the pages that need optical character recognition; they
are flagged with a warning instead of being silently reported as empty,
because an empty page and a scanned page are very different things for the
downstream pipeline.
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ingestion.contracts import (
    EXTRACTION_METHOD_TEXT,
    ExtractedDocument,
    ExtractedPage,
)
from app.ingestion.extractors.base import extraction_error
from app.ingestion.metadata import build_document_metadata

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz  # type: ignore[no-redef]

__all__ = ["PyMuPdfTextExtractor"]

logger = get_logger(__name__)

#: The magic bytes every PDF file starts with.
PDF_MAGIC = b"%PDF-"

#: Maximum number of headings that are reported for a single page.
MAX_HEADINGS_PER_PAGE = 60

#: Maximum number of characters a heading may have.
MAX_HEADING_CHARS = 200

#: A span is a heading when its size exceeds the body size by this factor.
HEADING_SIZE_RATIO = 1.15

#: Font name fragments that mark a span as a heading.
BOLD_FONT_MARKERS: tuple[str, ...] = ("bold", "semibold", "black")

_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _normalize_text(text: str) -> str:
    """Return *text* with sensible whitespace."""
    lines = [line.rstrip() for line in (text or "").splitlines()]
    return _MULTI_NEWLINE_RE.sub("\n\n", "\n".join(lines)).strip()


def _is_pure_number(text: str) -> bool:
    """Return ``True`` when *text* is nothing but a number."""
    cleaned = (
        text.replace(",", "")
        .replace("$", "")
        .replace("%", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "")
        .replace(".", "")
    )
    if not cleaned:
        return False
    if cleaned.startswith("-"):
        cleaned = cleaned[1:]
    return cleaned.isdigit()


class PyMuPdfTextExtractor:
    """Extract the text layer of a PDF with PyMuPDF."""

    name = "pdf_text"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    # -- protocol ---------------------------------------------------------

    def supports(self, file_path: Path) -> bool:
        """Return ``True`` when *file_path* is an existing PDF file.

        The ``%PDF-`` marker must appear in the first 1024 bytes.  It is
        normally the very first thing in the file, but some producers emit
        a short preamble before it.
        """
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
        """Return the text of every page of the PDF at *file_path*."""
        path = Path(file_path)
        document = self._open(path)
        try:
            pages = self._extract_pages(document, path)
        finally:
            document.close()

        text_by_page = [page.text for page in pages]
        metadata = build_document_metadata(text_by_page, filename=path.name)
        return ExtractedDocument(
            pages=tuple(pages),
            metadata=metadata,
            page_count=len(pages),
            warnings=tuple(warning for page in pages for warning in page.warnings),
        )

    # -- internals --------------------------------------------------------

    def _open(self, path: Path) -> Any:
        """Open *path* and return the PyMuPDF document."""
        if not path.is_file():
            raise extraction_error(
                f"PDF file does not exist: {path}",
                code="pdf_unreadable",
                path=str(path),
            )
        try:
            document = fitz.open(path)
        except Exception as exc:  # any parser failure is the same
            raise extraction_error(
                f"Unable to open the PDF {path.name}: {exc}",
                code="pdf_unreadable",
                path=str(path),
            ) from exc

        if document.needs_pass and not document.authenticate(""):
            document.close()
            raise extraction_error(
                f"The PDF {path.name} is password protected",
                code="pdf_encrypted",
                path=str(path),
            )
        return document

    def _extract_pages(self, document: Any, path: Path) -> list[ExtractedPage]:
        """Return the extracted pages of *document*."""
        outline = self._outline_by_page(document)
        pages: list[ExtractedPage] = []

        for index in range(document.page_count):
            page_number = index + 1
            try:
                page = document[index]
                text = page.get_text("text")
            except Exception as exc:  # one broken page must not abort
                logger.warning(
                    "Could not read the text of page %s of %s: %s",
                    page_number,
                    path.name,
                    exc,
                )
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        text="",
                        headings=(),
                        tables=(),
                        extraction_method=EXTRACTION_METHOD_TEXT,
                        warnings=(f"page {page_number}: the text layer could not be read ({exc})",),
                    )
                )
                continue

            headings = self._detect_headings(page, page_number)
            for title in outline.get(page_number, ()):
                if title.casefold() not in {item.casefold() for item in headings}:
                    headings.append(title)
            headings = headings[:MAX_HEADINGS_PER_PAGE]

            normalized = _normalize_text(text)
            warnings: list[str] = []
            if len(normalized.strip()) < self._settings.min_text_chars_per_page:
                warnings.append(
                    f"page {page_number}: little or no extractable text "
                    "(possible scanned page)"
                )

            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=normalized,
                    headings=tuple(headings),
                    tables=(),
                    extraction_method=EXTRACTION_METHOD_TEXT,
                    warnings=tuple(warnings),
                )
            )
        return pages

    def _detect_headings(self, page: Any, page_number: int) -> list[str]:
        """Return the headings that were found on *page*."""
        try:
            page_dict = page.get_text("dict")
        except Exception as exc:  # the text layer is still usable
            logger.warning(
                "Could not read the span structure of page %s: %s", page_number, exc
            )
            return []

        spans = [
            span
            for block in page_dict.get("blocks", ())
            if block.get("type", 0) == 0
            for line in block.get("lines", ())
            for span in line.get("spans", ())
        ]
        if not spans:
            return []

        sizes = [float(span.get("size", 0.0) or 0.0) for span in spans]
        median_size = statistics.median(sizes)
        threshold = max(1.0, median_size * HEADING_SIZE_RATIO)

        headings: list[str] = []
        seen: set[str] = set()
        for span in spans:
            text = str(span.get("text", "")).strip()
            if not text or len(text) > MAX_HEADING_CHARS:
                continue
            if _is_pure_number(text):
                continue
            size = float(span.get("size", 0.0) or 0.0)
            font = str(span.get("font", ""))
            is_bold = any(marker in font.casefold() for marker in BOLD_FONT_MARKERS)
            if size <= threshold and not is_bold:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            headings.append(text)
            if len(headings) >= MAX_HEADINGS_PER_PAGE:
                break
        return headings

    def _outline_by_page(self, document: Any) -> dict[int, list[str]]:
        """Return the document outline, grouped by the page it starts on."""
        try:
            toc = document.get_toc(simple=True)
        except Exception as exc:  # the outline is optional
            logger.warning("Could not read the document outline: %s", exc)
            return {}

        outline: dict[int, list[str]] = {}
        for entry in toc or ():
            if len(entry) < 3:
                continue
            title = str(entry[1]).strip()
            try:
                page_number = int(entry[2])
            except (TypeError, ValueError):
                continue
            if not title or page_number <= 0:
                continue
            titles = outline.setdefault(page_number, [])
            if title.casefold() not in {item.casefold() for item in titles}:
                titles.append(title)
        return outline