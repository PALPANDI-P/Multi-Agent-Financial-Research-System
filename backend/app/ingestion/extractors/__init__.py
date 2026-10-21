"""Document extractors.

This package contains the concrete extraction strategies that turn a binary
document (currently PDF) into the page/table structures described by
:mod:`app.ingestion.contracts`.  Every extractor must report the method it
used (``pdf_text``, ``pdf_tables``, ``ocr`` or ``empty``) so that the
pipeline can decide whether OCR or table extraction has to run.
"""
