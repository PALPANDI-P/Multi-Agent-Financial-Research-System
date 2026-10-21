"""Unit tests for the extraction strategies.

Every PDF the tests need is generated in memory with PyMuPDF, therefore the
tests are fast, deterministic and need no network access.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import ExtractionError
from app.ingestion.contracts import EXTRACTION_METHOD_TABLE, EXTRACTION_METHOD_TEXT
from app.ingestion.extractors import (
    DocumentExtractor,
    OcrExtractor,
    PdfPlumberTableExtractor,
    PyMuPdfTextExtractor,
    ocr_pages_for_document,
)

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz  # type: ignore[no-redef]

HEADING = "Item 1. Business"
BODY_LINES = (
    "The company operates a network of offices across the whole country.",
    "Revenue grew steadily over the year and the outlook remains stable.",
    "The board of directors approved the dividend that was paid in March.",
)
SECOND_PAGE_TEXT = "This second page carries a short note about the appendix."


def _settings(**overrides: object) -> Settings:
    """Return settings that do not depend on the local ``.env`` file."""
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def _two_page_pdf(tmp_path: Path) -> Path:
    """Write a two page PDF: a heading plus body text, then a text page."""
    target = tmp_path / "report.pdf"
    document = fitz.open()

    first = document.new_page()
    first.insert_text((72, 100), HEADING, fontname="hebo", fontsize=20)
    for index, line in enumerate(BODY_LINES):
        first.insert_text((72, 130 + index * 20), line, fontname="helv", fontsize=11)

    second = document.new_page()
    second.insert_text((72, 100), SECOND_PAGE_TEXT, fontname="helv", fontsize=11)

    document.save(target)
    document.close()
    return target


def _scanned_pdf(tmp_path: Path) -> Path:
    """Write a PDF whose single page has no text layer at all."""
    target = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(target)
    document.close()
    return target


@pytest.fixture
def extractor() -> PyMuPdfTextExtractor:
    """Return a text extractor that uses the default settings."""
    return PyMuPdfTextExtractor(_settings())


def test_extractor_implements_the_protocol(extractor: PyMuPdfTextExtractor) -> None:
    assert isinstance(extractor, DocumentExtractor)
    assert extractor.name == "pdf_text"


def test_supports_accepts_a_pdf_and_rejects_everything_else(
    extractor: PyMuPdfTextExtractor,
    tmp_path: Path,
) -> None:
    pdf = _two_page_pdf(tmp_path)
    other = tmp_path / "notes.txt"
    other.write_text("not a pdf", encoding="utf-8")

    assert extractor.supports(pdf) is True
    assert extractor.supports(other) is False
    assert extractor.supports(tmp_path / "missing.pdf") is False


def test_extract_returns_every_page(extractor: PyMuPdfTextExtractor, tmp_path: Path) -> None:
    document = extractor.extract(_two_page_pdf(tmp_path))

    assert document.page_count == 2
    assert [page.page_number for page in document.pages] == [1, 2]
    assert document.page_by_number(2) is not None
    assert document.page_by_number(99) is None


def test_extract_returns_the_text_of_the_page(extractor: PyMuPdfTextExtractor, tmp_path: Path) -> None:
    document = extractor.extract(_two_page_pdf(tmp_path))
    first = document.pages[0]

    assert HEADING in first.text
    assert BODY_LINES[0] in first.text
    assert SECOND_PAGE_TEXT in document.pages[1].text
    assert first.extraction_method == EXTRACTION_METHOD_TEXT
    assert document.pages[1].extraction_method == EXTRACTION_METHOD_TEXT


def test_headings_are_detected(extractor: PyMuPdfTextExtractor, tmp_path: Path) -> None:
    document = extractor.extract(_two_page_pdf(tmp_path))
    headings = document.pages[0].headings

    assert HEADING in headings
    assert all(len(heading) <= 200 for heading in headings)
    assert BODY_LINES[0] not in headings


def test_a_page_without_text_is_flagged(extractor: PyMuPdfTextExtractor, tmp_path: Path) -> None:
    document = extractor.extract(_scanned_pdf(tmp_path))
    warnings = document.pages[0].warnings

    assert "page 1: little or no extractable text (possible scanned page)" in warnings
    assert warnings[0] in document.warnings


def test_metadata_is_built_from_the_text(extractor: PyMuPdfTextExtractor, tmp_path: Path) -> None:
    document = extractor.extract(_two_page_pdf(tmp_path))

    assert document.metadata.page_count == 2
    assert document.metadata.fiscal_period is None


def test_a_corrupt_pdf_raises_an_extraction_error(
    extractor: PyMuPdfTextExtractor,
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\nnot a real pdf body\n")

    with pytest.raises(ExtractionError) as excinfo:
        extractor.extract(broken)

    assert excinfo.value.code == "pdf_unreadable"


def test_an_encrypted_pdf_raises_an_extraction_error(tmp_path: Path) -> None:
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

    extractor = PyMuPdfTextExtractor(_settings())
    with pytest.raises(ExtractionError) as excinfo:
        extractor.extract(target)

    assert excinfo.value.code == "pdf_encrypted"


def _ruled_table_pdf(tmp_path: Path) -> Path:
    """Write a PDF that carries a ruled table."""
    target = tmp_path / "table.pdf"
    document = fitz.open()
    page = document.new_page()

    x_edges = [72, 172, 272, 372]
    y_edges = [100, 140, 180, 220]
    for y in y_edges:
        page.draw_line((x_edges[0], y), (x_edges[-1], y))
    for x in x_edges:
        page.draw_line((x, y_edges[0]), (x, y_edges[-1]))

    cells = [
        ["Revenue", "2025", "2024"],
        ["Net sales", "1000", "900"],
        ["Cost of sales", "600", "550"],
    ]
    for row_index, row in enumerate(cells):
        for column_index, value in enumerate(row):
            page.insert_text(
                (x_edges[column_index] + 5, y_edges[row_index] + 25),
                value,
                fontname="helv",
                fontsize=11,
            )

    document.save(target)
    document.close()
    return target


def test_tables_are_extracted(tmp_path: Path) -> None:
    extractor = PdfPlumberTableExtractor(_settings())
    tables = extractor.extract_tables(_ruled_table_pdf(tmp_path))

    assert set(tables) == {1}
    table = tables[1][0]
    assert table.page_number == 1
    assert table.table_index == 0
    assert table.header == ("Revenue", "2025", "2024")
    assert table.rows == (("Net sales", "1000", "900"), ("Cost of sales", "600", "550"))


def test_the_extracted_document_carries_the_tables(tmp_path: Path) -> None:
    extractor = PdfPlumberTableExtractor(_settings())
    document = extractor.extract(_ruled_table_pdf(tmp_path))

    assert document.page_count == 1
    assert len(document.pages) == 1
    assert document.pages[0].extraction_method == EXTRACTION_METHOD_TABLE
    assert len(document.pages[0].tables) == 1


def test_table_extraction_degrades_gracefully(tmp_path: Path) -> None:
    extractor = PdfPlumberTableExtractor(_settings())
    tables = extractor.extract_tables(_two_page_pdf(tmp_path))

    assert isinstance(tables, dict)
    assert all(isinstance(page, int) for page in tables)


def test_table_extraction_of_a_missing_file_returns_an_empty_mapping(tmp_path: Path) -> None:
    extractor = PdfPlumberTableExtractor(_settings())

    assert extractor.extract_tables(tmp_path / "missing.pdf") == {}


def test_ocr_is_not_available_on_this_machine() -> None:
    availability = OcrExtractor(_settings()).is_available()

    assert availability.available is False
    assert availability.reason
    assert "pytesseract" in availability.reason or "tesseract" in availability.reason


def test_the_pages_that_need_ocr_are_reported(tmp_path: Path) -> None:
    extractor = PyMuPdfTextExtractor(_settings())
    document = extractor.extract(_scanned_pdf(tmp_path))
    pages = ocr_pages_for_document(document, _settings())

    assert pages == (1,)


def test_a_page_with_text_does_not_need_ocr(tmp_path: Path) -> None:
    extractor = PyMuPdfTextExtractor(_settings())
    document = extractor.extract(_two_page_pdf(tmp_path))
    pages = ocr_pages_for_document(document, _settings())

    assert pages == ()


def test_ocr_raises_when_it_is_not_configured(tmp_path: Path) -> None:
    pdf = _two_page_pdf(tmp_path)
    extractor = OcrExtractor(_settings())

    with pytest.raises(ExtractionError) as excinfo:
        extractor.extract_page(pdf, 1)

    assert excinfo.value.error_code == "ocr_unavailable"
    assert excinfo.value.code == "ocr_unavailable"