"""Document ingestion pipeline.

This package owns the transformation of an uploaded document into the
structured artefacts that the rest of the system consumes: text, tables and
metadata.  It hosts the extraction layer (see
:mod:`app.ingestion.extractors`) and the immutable hand-off contracts that
the extraction, chunking, embedding and vector-store layers share (see
:mod:`app.ingestion.contracts`).
"""
