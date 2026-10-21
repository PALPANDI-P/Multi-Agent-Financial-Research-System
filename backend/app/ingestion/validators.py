"""Validation of an uploaded document.

Trust model
-----------
Neither the file name nor the MIME type announced by the client is
trusted.  Both are attacker controlled and both are trivially wrong.

* The **content** of the file is the authoritative signal: the ``%PDF-``
  marker decides whether the payload is a PDF at all, and only a PDF that
  PyMuPDF can actually open is accepted.
* A **client supplied MIME type** is only ever a *corroborating* signal.  It
  can confirm what the sniffed content says, but it can never overrule it.
  A mismatch is reported as an issue, it is not silently corrected.
* The **file name** only contributes the file extension, and the extension
  is checked against the allow list - it is never used to decide that a
  file is a PDF.

Every applicable problem is collected, the validation therefore reports
*all* reasons an upload was rejected instead of only the first one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

__all__ = [
    "EXTENSION_NOT_ALLOWED",
    "FILE_EMPTY",
    "FILE_NOT_FOUND",
    "FILE_TOO_LARGE",
    "FILE_UNREADABLE",
    "MIME_TYPE_MISMATCH",
    "MIME_TYPE_NOT_ALLOWED",
    "NOT_A_PDF",
    "NO_PAGES",
    "PDF_ENCRYPTED",
    "PDF_UNREADABLE",
    "SCANNED_DOCUMENT_OCR_UNAVAILABLE",
    "TOO_MANY_PAGES",
    "FileValidator",
    "ValidationIssue",
    "ValidationResult",
    "validate_upload",
]

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz  # type: ignore[no-redef]

#: The payload is larger than the configured maximum.
FILE_TOO_LARGE = "file_too_large"
#: The payload is empty.
FILE_EMPTY = "file_empty"
#: The referenced file does not exist.
FILE_NOT_FOUND = "file_not_found"
#: The referenced file could not be read.
FILE_UNREADABLE = "file_unreadable"
#: The file extension is not on the allow list.
EXTENSION_NOT_ALLOWED = "extension_not_allowed"
#: The content of the file is not a PDF.
NOT_A_PDF = "not_a_pdf"
#: The declared MIME type is not on the allow list.
MIME_TYPE_NOT_ALLOWED = "mime_type_not_allowed"
#: The declared MIME type contradicts the sniffed content.
MIME_TYPE_MISMATCH = "mime_type_mismatch"
#: The PDF cannot be opened.
PDF_UNREADABLE = "pdf_unreadable"
#: The PDF is password protected.
PDF_ENCRYPTED = "pdf_encrypted"
#: The PDF has no pages.
NO_PAGES = "no_pages"
#: The PDF has more pages than allowed.
TOO_MANY_PAGES = "too_many_pages"
#: The document is a scan and OCR is not available.
SCANNED_DOCUMENT_OCR_UNAVAILABLE = "scanned_document_ocr_unavailable"

#: The magic bytes of a PDF file.
PDF_MAGIC = b"%PDF-"

#: Number of bytes that are inspected when the content type is sniffed.
SNIFF_LENGTH = 1024

#: The MIME type of a PDF file.
PDF_MIME_TYPE = "application/pdf"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single reason why an upload was rejected."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The outcome of an upload validation.

    Attributes
    ----------
    ok:
        ``True`` when no issue was found.
    issues:
        Every issue that was found, in the order they were detected.
    detected_mime_type:
        The MIME type that was sniffed from the content of the file.
    page_count:
        The number of pages of the PDF, when it could be determined.
    """

    ok: bool
    issues: tuple[ValidationIssue, ...]
    detected_mime_type: str | None = None
    page_count: int | None = None

    def error_codes(self) -> tuple[str, ...]:
        """Return the codes of every issue, in detection order."""
        return tuple(issue.code for issue in self.issues)


def _normalize_mime_type(mime_type: str | None) -> str | None:
    """Return the normalised MIME type or ``None`` when none was declared."""
    if mime_type is None:
        return None
    normalized = str(mime_type).split(";", 1)[0].strip().casefold()
    return normalized or None


def _sniff_mime_type(head: bytes) -> str:
    """Return the MIME type that *head* suggests."""
    if PDF_MAGIC in head:
        return PDF_MIME_TYPE
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/plain"


class FileValidator:
    """Validate an uploaded document against the configured limits."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(
        self,
        *,
        filename: str,
        declared_mime_type: str | None,
        data: bytes | Path,
    ) -> ValidationResult:
        """Validate the upload and return every issue that was found.

        Parameters
        ----------
        filename:
            The original file name of the upload.
        declared_mime_type:
            The MIME type the client announced (may be ``None``).  It is
            only a corroborating signal.
        data:
            The content of the upload, either as raw bytes or as the path
            of a file.
        """
        issues: list[ValidationIssue] = []
        detected_mime_type: str | None = None
        page_count: int | None = None

        payload = self._read_payload(data, issues)
        if payload is None:
            return ValidationResult(ok=False, issues=tuple(issues))

        size = len(payload)
        if size > self._settings.max_upload_size_bytes:
            issues.append(
                ValidationIssue(
                    code=FILE_TOO_LARGE,
                    message=(
                        f"the file is {size} bytes which exceeds the maximum of "
                        f"{self._settings.max_upload_size_bytes} bytes"
                    ),
                )
            )
        if size == 0:
            issues.append(
                ValidationIssue(
                    code=FILE_EMPTY,
                    message="the file is empty",
                )
            )

        extension = Path(filename or "").suffix.casefold()
        allowed_extensions = {
            allowed.casefold() for allowed in self._settings.allowed_document_extensions
        }
        if extension not in allowed_extensions:
            issues.append(
                ValidationIssue(
                    code=EXTENSION_NOT_ALLOWED,
                    message=(
                        f"the file extension {extension or '<none>'} is not allowed "
                        f"(allowed: {', '.join(sorted(allowed_extensions))})"
                    ),
                )
            )

        head = payload[:SNIFF_LENGTH]
        is_pdf = PDF_MAGIC in head
        detected_mime_type = _sniff_mime_type(head)
        if not is_pdf:
            issues.append(
                ValidationIssue(
                    code=NOT_A_PDF,
                    message="the content of the file is not a PDF (the '%PDF-' marker is missing)",
                )
            )

        declared = _normalize_mime_type(declared_mime_type)
        allowed_mime_types = {
            allowed.casefold() for allowed in self._settings.allowed_mime_types
        }
        if declared is not None and declared not in allowed_mime_types:
            issues.append(
                ValidationIssue(
                    code=MIME_TYPE_NOT_ALLOWED,
                    message=(
                        f"the declared MIME type {declared} is not allowed "
                        f"(allowed: {', '.join(sorted(allowed_mime_types))})"
                    ),
                )
            )
        if (
            declared is not None
            and detected_mime_type is not None
            and declared != detected_mime_type
        ):
            issues.append(
                ValidationIssue(
                    code=MIME_TYPE_MISMATCH,
                    message=(
                        f"the declared MIME type {declared} does not match the "
                        f"detected type {detected_mime_type}"
                    ),
                )
            )

        if is_pdf:
            page_count = self._validate_pdf(payload, issues)

        return ValidationResult(
            ok=not issues,
            issues=tuple(issues),
            detected_mime_type=detected_mime_type,
            page_count=page_count,
        )

    # -- internals --------------------------------------------------------

    def _read_payload(
        self,
        data: bytes | Path,
        issues: list[ValidationIssue],
    ) -> bytes | None:
        """Return the content of the upload or ``None`` when it is unreadable."""
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)

        path = Path(data)
        if not path.is_file():
            issues.append(
                ValidationIssue(
                    code=FILE_NOT_FOUND,
                    message=f"the file {path} does not exist",
                )
            )
            return None
        try:
            return path.read_bytes()
        except OSError as exc:
            issues.append(
                ValidationIssue(
                    code=FILE_UNREADABLE,
                    message=f"the file {path} could not be read: {exc}",
                )
            )
            return None

    def _validate_pdf(self, payload: bytes, issues: list[ValidationIssue]) -> int | None:
        """Validate the PDF and return its page count when it is known."""
        try:
            document = fitz.open(stream=payload, filetype="pdf")
        except Exception as exc:  # any parser failure is the same
            issues.append(
                ValidationIssue(
                    code=PDF_UNREADABLE,
                    message=f"the PDF could not be opened: {exc}",
                )
            )
            return None

        with document:
            if document.needs_pass and not document.authenticate(""):
                issues.append(
                    ValidationIssue(
                        code=PDF_ENCRYPTED,
                        message="the PDF is password protected",
                    )
                )
                return None

            page_count = document.page_count
            if page_count == 0:
                issues.append(
                    ValidationIssue(
                        code=NO_PAGES,
                        message="the PDF does not contain a single page",
                    )
                )
                return page_count

            if page_count > self._settings.max_pdf_pages:
                issues.append(
                    ValidationIssue(
                        code=TOO_MANY_PAGES,
                        message=(
                            f"the PDF has {page_count} pages which exceeds the maximum "
                            f"of {self._settings.max_pdf_pages} pages"
                        ),
                    )
                )
                return page_count

            self._validate_scanned(document, page_count, issues)
            return page_count

    def _validate_scanned(
        self,
        document: Any,
        page_count: int,
        issues: list[ValidationIssue],
    ) -> None:
        """Flag a document whose pages are all scans while OCR is missing."""
        try:
            texts = [document[index].get_text("text") for index in range(page_count)]
        except Exception as exc:  # the page structure is optional
            issues.append(
                ValidationIssue(
                    code=PDF_UNREADABLE,
                    message=f"the pages of the PDF could not be read: {exc}",
                )
            )
            return

        threshold = self._settings.min_text_chars_per_page
        if not all(len((text or "").strip()) < threshold for text in texts):
            return

        if self._ocr_available():
            return

        issues.append(
            ValidationIssue(
                code=SCANNED_DOCUMENT_OCR_UNAVAILABLE,
                message=(
                    "every page of the document has less than "
                    f"{threshold} characters of text (the document is a scan) "
                    "and OCR is not available, therefore its content cannot be read"
                ),
            )
        )

    def _ocr_available(self) -> bool:
        """Return ``True`` when OCR can be executed on this machine."""
        from app.ingestion.extractors.ocr import OcrExtractor

        return OcrExtractor(self._settings).is_available().available


def validate_upload(
    filename: str,
    declared_mime_type: str | None,
    data: bytes | Path,
) -> ValidationResult:
    """Validate an upload with the cached application settings."""
    return FileValidator(get_settings()).validate(
        filename=filename,
        declared_mime_type=declared_mime_type,
        data=data,
    )