"""Document ingestion pipeline.

This package owns the transformation of an uploaded document into the
structured artefacts that the rest of the system consumes: text, tables and
metadata.  It hosts

* the extraction layer (see :mod:`app.ingestion.extractors`),
* the upload validation (see :mod:`app.ingestion.validators`),
* the metadata detection (see :mod:`app.ingestion.metadata`), and
* the immutable hand-off contracts that the extraction, chunking, embedding
  and vector-store layers share (see :mod:`app.ingestion.contracts`).

Public API
----------
The names re-exported here are the stable entry points of the package.  They
are resolved **lazily** (PEP 562): importing a submodule of this package -
for example ``app.ingestion.chunking`` - does not drag the extraction
stack (PyMuPDF, pdfplumber) into the process.  ``from app.ingestion import
DocumentExtractor`` keeps working exactly as before, the name is simply
imported on first access.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cycle free type hints
    from app.ingestion.contracts import (
        EXTRACTION_METHOD_EMPTY,
        EXTRACTION_METHOD_OCR,
        EXTRACTION_METHOD_TABLE,
        EXTRACTION_METHOD_TEXT,
        Chunk,
        DocumentExtractionMetadata,
        ExtractedDocument,
        ExtractedPage,
        ExtractedTable,
    )
    from app.ingestion.extractors import (
        DocumentExtractor,
        OcrAvailability,
        OcrExtractor,
        PdfPlumberTableExtractor,
        PyMuPdfTextExtractor,
        ocr_pages_for_document,
    )
    from app.ingestion.metadata import (
        build_document_metadata,
        detect_company_name,
        detect_document_title,
        detect_fiscal_period,
        infer_document_type,
    )
    from app.ingestion.validators import (
        FileValidator,
        ValidationIssue,
        ValidationResult,
        validate_upload,
    )

__all__ = [
    "EXTRACTION_METHOD_EMPTY",
    "EXTRACTION_METHOD_OCR",
    "EXTRACTION_METHOD_TABLE",
    "EXTRACTION_METHOD_TEXT",
    "Chunk",
    "DocumentExtractionMetadata",
    "DocumentExtractor",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedTable",
    "FileValidator",
    "OcrAvailability",
    "OcrExtractor",
    "PdfPlumberTableExtractor",
    "PyMuPdfTextExtractor",
    "ValidationIssue",
    "ValidationResult",
    "build_document_metadata",
    "detect_company_name",
    "detect_document_title",
    "detect_fiscal_period",
    "infer_document_type",
    "ocr_pages_for_document",
    "validate_upload",
]

#: Maps every public name of the package to the module that defines it.
_EXPORT_MODULES: dict[str, str] = {
    "EXTRACTION_METHOD_EMPTY": "app.ingestion.contracts",
    "EXTRACTION_METHOD_OCR": "app.ingestion.contracts",
    "EXTRACTION_METHOD_TABLE": "app.ingestion.contracts",
    "EXTRACTION_METHOD_TEXT": "app.ingestion.contracts",
    "Chunk": "app.ingestion.contracts",
    "DocumentExtractionMetadata": "app.ingestion.contracts",
    "ExtractedDocument": "app.ingestion.contracts",
    "ExtractedPage": "app.ingestion.contracts",
    "ExtractedTable": "app.ingestion.contracts",
    "DocumentExtractor": "app.ingestion.extractors",
    "OcrAvailability": "app.ingestion.extractors",
    "OcrExtractor": "app.ingestion.extractors",
    "PdfPlumberTableExtractor": "app.ingestion.extractors",
    "PyMuPdfTextExtractor": "app.ingestion.extractors",
    "ocr_pages_for_document": "app.ingestion.extractors",
    "build_document_metadata": "app.ingestion.metadata",
    "detect_company_name": "app.ingestion.metadata",
    "detect_document_title": "app.ingestion.metadata",
    "detect_fiscal_period": "app.ingestion.metadata",
    "infer_document_type": "app.ingestion.metadata",
    "FileValidator": "app.ingestion.validators",
    "ValidationIssue": "app.ingestion.validators",
    "ValidationResult": "app.ingestion.validators",
    "validate_upload": "app.ingestion.validators",
}


def __getattr__(name: str) -> Any:
    """Return the public name *name* of the package (PEP 562).

    The name is imported from the module that defines it on first access
    and cached in the module namespace afterwards.
    """
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return the public names of the package."""
    return sorted(__all__)