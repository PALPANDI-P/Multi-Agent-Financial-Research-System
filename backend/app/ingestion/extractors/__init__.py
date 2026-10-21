"""Document extractors.

This package contains the concrete extraction strategies that turn a binary
document (currently PDF) into the page/table structures described by
:mod:`app.ingestion.contracts`.  Every extractor reports the method it used
(``pdf_text``, ``pdf_tables``, ``ocr`` or ``empty``) so that the pipeline
can decide whether OCR or table extraction has to run.

Public API
----------
``DocumentExtractor``
    The protocol every strategy implements.
``PyMuPdfTextExtractor``
    Reads the text layer of a PDF and detects its headings.
``PdfPlumberTableExtractor``
    Reads the tables of a PDF; failures degrade gracefully and never abort
    the pipeline.
``OcrExtractor`` / ``OcrAvailability``
    Optical character recognition for scanned pages.  When OCR is not
    configured the scanned content is reported as **unavailable** instead
    of being silently treated as successfully extracted.
"""

from app.ingestion.extractors.base import DocumentExtractor, extraction_error
from app.ingestion.extractors.ocr import (
    OcrAvailability,
    OcrExtractor,
    ocr_pages_for_document,
)
from app.ingestion.extractors.pdf_tables import PdfPlumberTableExtractor
from app.ingestion.extractors.pdf_text import PyMuPdfTextExtractor

__all__ = [
    "DocumentExtractor",
    "OcrAvailability",
    "OcrExtractor",
    "PdfPlumberTableExtractor",
    "PyMuPdfTextExtractor",
    "extraction_error",
    "ocr_pages_for_document",
]