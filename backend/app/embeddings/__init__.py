"""Embedding generation.

This package turns the chunks produced by the ingestion pipeline into dense
vectors.  It is the only place that may know which embedding model and
which embedding dimension are in use; the resulting vector length must match
``document_chunks.embedding`` and the configuration hash recorded next to
it.

Public API
----------
:class:`EmbeddingProvider`
    The protocol every adapter implements; the business layer only ever
    sees this protocol.
:class:`EmbeddingProviderHealth`
    The result of a cheap health check or of an end-to-end probe.
:class:`FastEmbedProvider`
    The production adapter, backed by a local ``fastembed`` ONNX model.
:class:`EmbeddingService`
    The validating façade: dimension/finiteness checks, embedding reuse and
    the retry policy.
:func:`create_embedding_service`
    The dependency-injection factory that builds a service from the
    application settings.

The deterministic test provider lives in :mod:`app.embeddings.testing`.  It
is intentionally **not** re-exported here so that production code cannot
use it by accident.
"""

from app.embeddings.base import EmbeddingProvider, EmbeddingProviderHealth
from app.embeddings.provider import FastEmbedProvider
from app.embeddings.service import EmbeddingService, create_embedding_service

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderHealth",
    "EmbeddingService",
    "FastEmbedProvider",
    "create_embedding_service",
]
