"""Optical character recognition for pages without a usable text layer.

Honesty contract
----------------
When OCR is not available the scanned content is reported as **unavailable**.
It is never silently treated as successfully extracted: :meth:`OcrExtractor.extract_page`
raises :class:`app.core.exceptions.ExtractionError` with the stable code
``ocr_unavailable`` instead of returning an empty page, a placeholder or a
fabricated text.  A caller therefore always knows whether the content of a
page was really read or not.

Availability
------------
OCR needs two things: the Python binding ``pytesseract`` and the
``tesseract`` executable itself.  Both are optional: neither is installed
by default, therefore the availability check is explicit and reports *why*
OCR cannot be used.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ingestion.contracts import (
    EXTRACTION_METHOD_OCR,
    ExtractedDocument,
    ExtractedPage,
)
from app.ingestion.extractors.base import extraction_error

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz  # type: ignore[no-redef]

__all__ = ["OcrAvailability", "OcrExtractor", "ocr_pages_for_document"]

logger = get_logger(__name__)

#: Resolution the page is rendered with before it is handed to tesseract.
OCR_RENDER_DPI = 300


@dataclass(frozen=True, slots=True)
class OcrAvailability:
    """The result of the OCR availability check.

    Attributes
    ----------
    available:
        ``True`` only when OCR can actually be executed.
    reason:
        A human readable explanation.  When ``available`` is ``False`` the
        reason names the missing dependency.
    """

    available: bool
    reason: str


def _module_available(name: str) -> bool:
    """Return ``True`` when the module *name* can be imported."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def ocr_pages_for_document(
    document: ExtractedDocument,
    settings: Settings | None = None,
) -> tuple[int, ...]:
    """Return the page numbers of *document* that need optical character recognition.

    A page needs OCR when its text layer holds fewer characters than
    ``settings.min_text_chars_per_page`` - such a page is either empty or
    a scan.
    """
    config = settings if settings is not None else get_settings()
    threshold = config.min_text_chars_per_page
    return tuple(
        page.page_number
        for page in document.pages
        if len((page.text or "").strip()) < threshold
    )


class OcrExtractor:
    """Extract the text of a scanned page with tesseract."""

    name = "ocr"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    # -- availability -----------------------------------------------------

    def is_available(self) -> OcrAvailability:
        """Return whether OCR can be executed on this machine.

        The check looks for the ``pytesseract`` binding *and* for the
        ``tesseract`` executable.  When one of them is missing the reason
        names the missing dependency.
        """
        missing: list[str] = []
        if not _module_available("pytesseract"):
            missing.append("the Python package 'pytesseract' is not installed")
        if shutil.which("tesseract") is None:
            missing.append("the 'tesseract' executable was not found on PATH")

        if missing:
            return OcrAvailability(
                available=False,
                reason="OCR is not available: " + "; ".join(missing) + ".",
            )
        return OcrAvailability(
            available=True,
            reason="OCR is available (pytesseract and the tesseract executable).",
        )

    def ocr_pages_for_document(self, document: ExtractedDocument) -> tuple[int, ...]:
        """Return the pages of *document* that need OCR."""
        return ocr_pages_for_document(document, self._settings)

    # -- extraction -------------------------------------------------------

    def extract_page(self, pdf_path: Path, page_number: int) -> ExtractedPage:
        """Return the OCR text of a single page of the PDF at *pdf_path*.

        Parameters
        ----------
        pdf_path:
            The PDF the page belongs to.
        page_number:
            The **1-based** number of the page.

        Raises
        ------
        app.core.exceptions.ExtractionError
            With ``error_code == "ocr_unavailable"`` when OCR is not
            configured on this machine.
        """
        availability = self.is_available()
        if not availability.available:
            raise extraction_error(
                f"OCR is not configured: {availability.reason}",
                code="ocr_unavailable",
                page_number=page_number,
            )
        if not self._settings.ocr_enabled:
            raise extraction_error(
                "OCR is not configured: OCR is disabled by the OCR_ENABLED setting.",
                code="ocr_unavailable",
                page_number=page_number,
            )

        path = Path(pdf_path)
        image_path = self._render_page(path, page_number)
        try:
            text = self._run_tesseract(image_path)
        finally:
            image_path.unlink(missing_ok=True)

        return ExtractedPage(
            page_number=page_number,
            text=text,
            headings=(),
            tables=(),
            extraction_method=EXTRACTION_METHOD_OCR,
        )

    def extract(self, file_path: Path) -> ExtractedDocument:
        """Return the OCR text of every page of the PDF at *file_path*."""
        path = Path(file_path)
        availability = self.is_available()
        if not availability.available:
            raise extraction_error(
                f"OCR is not configured: {availability.reason}",
                code="ocr_unavailable",
                path=str(path),
            )

        pages: list[ExtractedPage] = []
        for page_number in range(1, self._page_count(path) + 1):
            pages.append(self.extract_page(path, page_number))
        return ExtractedDocument(pages=tuple(pages), page_count=len(pages))

    # -- internals --------------------------------------------------------

    def _page_count(self, path: Path) -> int:
        """Return the number of pages of the PDF at *path*."""
        document = self._open(path)
        try:
            return document.page_count
        finally:
            document.close()

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

    def _render_page(self, path: Path, page_number: int) -> Path:
        """Render a page into a PNG file and return the path of the file."""
        document = self._open(path)
        try:
            if page_number < 1 or page_number > document.page_count:
                raise extraction_error(
                    f"Page {page_number} does not exist in {path.name}",
                    code="page_out_of_range",
                    page_number=page_number,
                    page_count=document.page_count,
                )
            page = document[page_number - 1]
            pixmap = page.get_pixmap(dpi=OCR_RENDER_DPI)
            payload = pixmap.tobytes("png")
        finally:
            document.close()

        descriptor, name = tempfile.mkstemp(prefix="frs-ocr-", suffix=".png")
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        return Path(name)

    def _run_tesseract(self, image_path: Path) -> str:
        """Return the text tesseract reads from *image_path*."""
        import pytesseract

        try:
            text = pytesseract.image_to_string(
                str(image_path),
                lang=self._settings.ocr_language,
            )
        except Exception as exc:  # tesseract failures are opaque
            raise extraction_error(
                f"tesseract failed to read {image_path.name}: {exc}",
                code="ocr_failed",
            ) from exc
        return text