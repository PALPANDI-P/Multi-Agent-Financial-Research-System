"""Embedding generation.

This package turns the chunks produced by the ingestion pipeline into dense
vectors.  It is the only place that may know which embedding model and
which embedding dimension are in use; the resulting vector length must match
``document_chunks.embedding`` and the configuration hash recorded next to
it.
"""
