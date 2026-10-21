"""Unit tests for the upload validation.

The tests build their PDFs in memory with PyMuPDF, therefore they need
neither a fixture directory nor a network connection.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from app.core.config import Settings
from app.ingestion.validators import (
    EXTENSION_NOT_ALLOWED,
    FILE_EMPTY,
    FILE_NOT_FOUND,
    FILE_TOO_LARGE,
    MIME_TYPE_MISMATCH,
    MIME_TYPE_NOT_ALLOWED,
    NO_PAGES,
    NOT_A_PDF,
    PDF_ENCRYPTED,
    SCANNED_DOCUMENT_OCR_UNAVAILABLE,
    TOO_MANY_PAGES,
    FileValidator,
    ValidationResult,
)

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz  # type: ignore[no-redef]

#: A PDF that carries a single page but no page at all.
EMPTY_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Size 3 /Root 1 0 R >>\n%%EOF\n"
)

#: A sentence that is long enough to be considered real text.
BODY_TEXT = (
    "Example Holdings Inc. reports record results for the fiscal year ended "
    "January 31, 2026 with revenue growth across every business segment."
)


def _settings(**overrides: object) -> Settings:
    """Return settings that do not depend on the local ``.env`` file."""
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def _pdf_bytes(texts: Sequence[str | None] = ()) -> bytes:
    """Return the bytes of a PDF with one page per entry of *texts*."""
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 100), text, fontname="helv", fontsize=11)
    payload = document.tobytes()
    document.close()
    return payload


@pytest.fixture
def validator() -> FileValidator:
    """Return a validator that uses the default limits."""
    return FileValidator(_settings())


def test_valid_pdf_passes(validator: FileValidator) -> None:
    result = validator.validate(
        filename="annual-report.pdf",
        declared_mime_type="application/pdf",
        data=_pdf_bytes([BODY_TEXT]),
    )

    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.error_codes() == ()
    assert result.detected_mime_type == "application/pdf"
    assert result.page_count == 1


def test_valid_pdf_passes_when_no_mime_type_is_declared(validator: FileValidator) -> None:
    result = validator.validate(
        filename="annual-report.pdf",
        declared_mime_type=None,
        data=_pdf_bytes([BODY_TEXT]),
    )

    assert result.ok is True
    assert result.error_codes() == ()


def test_text_extension_is_rejected(validator: FileValidator) -> None:
    result = validator.validate(
        filename="notes.txt",
        declared_mime_type="text/plain",
        data=b"just some plain text",
    )

    assert result.ok is False
    assert EXTENSION_NOT_ALLOWED in result.error_codes()
    assert NOT_A_PDF in result.error_codes()


def test_content_that_is_not_a_pdf_is_rejected(validator: FileValidator) -> None:
    result = validator.validate(
        filename="report.pdf",
        declared_mime_type="application/pdf",
        data=b"this is definitely not a PDF document",
    )

    assert result.ok is False
    assert NOT_A_PDF in result.error_codes()


def test_oversized_file_is_rejected() -> None:
    settings = _settings(max_upload_size_bytes=64)
    result = FileValidator(settings).validate(
        filename="report.pdf",
        declared_mime_type="application/pdf",
        data=_pdf_bytes([BODY_TEXT]),
    )

    assert result.ok is False
    assert FILE_TOO_LARGE in result.error_codes()


def test_empty_file_is_rejected(validator: FileValidator) -> None:
    result = validator.validate(
        filename="report.pdf",
        declared_mime_type="application/pdf",
        data=b"",
    )

    assert result.ok is False
    assert FILE_EMPTY in result.error_codes()


def test_absent_file_is_reported(validator: FileValidator, tmp_path: Path) -> None:
    result = validator.validate(
        filename="report.pdf",
        declared_mime_type="application/pdf",
        data=tmp_path / "does-not-exist.pdf",
    )

    assert result.ok is False
    assert FILE_NOT_FOUND in result.error_codes()


def test_encrypted_pdf_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "encrypted.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 100), "Secret content", fontname="helv", fontsize=11)
    document.save(
        target,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()

    result = FileValidator(_settings()).validate(
        filename="encrypted.pdf",
        declared_mime_type="application/pdf",
        data=target,
    )

    assert result.ok is False
    assert PDF_ENCRYPTED in result.error_codes()


def test_mismatched_declared_mime_type_is_flagged(validator: FileValidator) -> None:
    result = validator.validate(
        filename="report.pdf",
        declared_mime_type="text/plain",
        data=_pdf_bytes([BODY_TEXT]),
    )

    assert result.ok is False
    assert MIME_TYPE_MISMATCH in result.error_codes()
    assert MIME_TYPE_NOT_ALLOWED in result.error_codes()


def test_scanned_document_without_ocr_is_flagged(validator: FileValidator) -> None:
    result = validator.validate(
        filename="scan.pdf",
        declared_mime_type="application/pdf",
        data=_pdf_bytes([None]),
    )

    assert result.ok is False
    assert SCANNED_DOCUMENT_OCR_UNAVAILABLE in result.error_codes()


def test_pdf_without_pages_is_flagged(validator: FileValidator) -> None:
    result = validator.validate(
        filename="empty.pdf",
        declared_mime_type="application/pdf",
        data=EMPTY_PDF,
    )

    assert result.ok is False
    assert NO_PAGES in result.error_codes()
    assert result.page_count == 0


def test_document_with_too_many_pages_is_flagged() -> None:
    settings = _settings(max_pdf_pages=1)
    result = FileValidator(settings).validate(
        filename="report.pdf",
        declared_mime_type="application/pdf",
        data=_pdf_bytes([BODY_TEXT, BODY_TEXT]),
    )

    assert result.ok is False
    assert TOO_MANY_PAGES in result.error_codes()
    assert result.page_count == 2


def test_a_broken_pdf_is_reported(validator: FileValidator) -> None:
    result = validator.validate(
        filename="broken.pdf",
        declared_mime_type="application/pdf",
        data=b"%PDF-1.4\nthis is not a parsable pdf body\n",
    )

    assert result.ok is False
    assert "pdf_unreadable" in result.error_codes()