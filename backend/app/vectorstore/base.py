"""Immutable contracts shared by every vector store implementation.

The dataclasses in this module are the *only* objects that cross the boundary
between the embedding pipeline and a vector store.  They are deliberately
frozen: once a chunk has been handed to a store it cannot be modified in
flight, which keeps the pipeline reproducible and makes the data flow easy to
reason about.

Every mapping field is exposed as a read-only :class:`~types.MappingProxyType`
so that a frozen dataclass cannot be used to smuggle a mutable dictionary into
the store.

Workspace isolation
-------------------
:attr:`VectorRecord.workspace_id` and :attr:`SearchHit.workspace_id` are
mandatory.  ``workspace_id`` is a **required** search filter: an implementation
must enforce it in the query itself (in SQL for the pgvector store) and must
never rely on the caller to filter afterwards.  A store that cannot guarantee
workspace isolation is unusable for multi-tenant data.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.core.enums import ChunkType
from app.core.exceptions import VectorStoreError

__all__ = [
    "MAX_SEARCH_LIMIT",
    "METADATA_KEY_CONTENT_HASH",
    "METADATA_KEY_EMBEDDING_CONFIG_HASH",
    "METADATA_KEY_TOKEN_COUNT",
    "SearchHit",
    "VectorRecord",
    "VectorStore",
    "clamp_limit",
    "record_content_hash",
    "record_embedding_config_hash",
    "record_token_count",
    "resolve_chunk_indexes",
]

#: Upper bound for the number of hits a single search may return.
MAX_SEARCH_LIMIT: int = 100


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return an immutable, shallow copy of *value*."""
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A chunk that is ready to be written to a vector store.

    ``chunk_index`` is optional.  When it is ``None`` (or absent from
    ``metadata``) the store assigns the position of the record inside the
    ``upsert_chunks`` call, counted per document.  Callers that re-index
    documents (for example a re-chunking run) should always set it
    explicitly, because the positional fallback cannot express a gap.
    """

    chunk_id: UUID
    document_id: UUID
    workspace_id: UUID
    content: str
    embedding: Sequence[float]
    page_start: int | None = None
    page_end: int | None = None
    section_heading: str | None = None
    chunk_type: str = ChunkType.TEXT.value
    metadata: Mapping[str, object] = field(default_factory=dict)
    chunk_index: int | None = None

    def __post_init__(self) -> None:
        """Replace the mutable mapping by an immutable view of it."""
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One chunk returned by a similarity search.

    The ``score`` is a cosine similarity in ``[-1, 1]``: ``1.0`` is a perfect
    match, ``0.0`` is orthogonal and ``-1.0`` is the opposite direction.
    """

    chunk_id: UUID
    document_id: UUID
    workspace_id: UUID
    content: str
    score: float
    page_start: int | None = None
    page_end: int | None = None
    section_heading: str | None = None
    chunk_type: str = ChunkType.TEXT.value
    metadata: Mapping[str, object] = field(default_factory=dict)
    document_title: str | None = None
    company_name: str | None = None
    document_type: str | None = None
    fiscal_period: str | None = None

    def __post_init__(self) -> None:
        """Replace the mutable mapping by an immutable view of it."""
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@runtime_checkable
class VectorStore(Protocol):
    """The storage contract used by the retrieval layer."""

    def upsert_chunks(self, records: Sequence[VectorRecord]) -> int:
        """Insert or update *records* and return the number of rows written.

        The operation must be idempotent: writing the same records twice must
        leave exactly one row per ``(document_id, chunk_index)``.
        """
        ...

    def search(
        self,
        embedding: Sequence[float],
        workspace_id: UUID,
        *,
        limit: int = 10,
        document_ids: Sequence[UUID] | None = None,
        chunk_types: Sequence[str] | None = None,
    ) -> list[SearchHit]:
        """Return the *limit* closest chunks of *workspace_id*.

        ``workspace_id`` is mandatory and must be enforced by the store
        itself, never by the caller.
        """
        ...

    def delete_document_chunks(self, document_id: UUID) -> int:
        """Delete every chunk of *document_id* and return the row count."""
        ...

    def count_chunks(self, document_id: UUID | None = None) -> int:
        """Return the number of stored chunks, optionally of one document."""
        ...

    def get_existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``."""
        ...


#: Key under which the SHA-256 hash of the content of a chunk is carried.
METADATA_KEY_CONTENT_HASH = "content_hash"

#: Key under which the hash of the embedding configuration is carried.
#:
#: The hash identifies the model (and the vector dimension) that produced a
#: vector.  A stored vector may only be reused when its hash still matches
#: the hash of the *current* embedding configuration, therefore the value is
#: stored next to every vector instead of being derived by the store: the
#: producer of a vector knows which model produced it.
METADATA_KEY_EMBEDDING_CONFIG_HASH = "embedding_config_hash"

#: Key under which the number of tokens of a chunk is carried.
METADATA_KEY_TOKEN_COUNT = "token_count"


def record_content_hash(record: VectorRecord) -> str:
    """Return the content hash of *record*.

    The hash is taken from the metadata of the record (key ``"content_hash"``).
    When it is missing, the SHA-256 hex digest of the content of the record
    is computed instead.
    """
    explicit = record.metadata.get(METADATA_KEY_CONTENT_HASH)
    if isinstance(explicit, str) and explicit:
        return explicit
    return hashlib.sha256(record.content.encode("utf-8")).hexdigest()


def record_embedding_config_hash(record: VectorRecord, default: str) -> str:
    """Return the embedding configuration hash of *record*.

    The hash is taken from the metadata of the record (key
    ``"embedding_config_hash"``).  When it is missing, *default* is returned.
    A store therefore never overrides the hash that the producer of the
    record computed.
    """
    explicit = record.metadata.get(METADATA_KEY_EMBEDDING_CONFIG_HASH)
    if isinstance(explicit, str) and explicit:
        return explicit
    return default


def record_token_count(record: VectorRecord) -> int | None:
    """Return the token count of *record*, or ``None`` when it is unknown."""
    explicit = record.metadata.get(METADATA_KEY_TOKEN_COUNT)
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        return explicit
    return None


def clamp_limit(limit: int) -> int:
    """Return a usable search limit.

    ``limit`` is clamped to ``1..MAX_SEARCH_LIMIT``: a limit above the
    maximum is reduced to the maximum, a limit below ``1`` is rejected with
    :class:`~app.core.exceptions.VectorStoreError` (code ``invalid_limit``)
    because "return nothing" is never what a caller means.
    """
    if limit < 1:
        raise VectorStoreError(
            "search limit must be at least 1",
            code="invalid_limit",
            details={"limit": limit},
        )
    return min(limit, MAX_SEARCH_LIMIT)


def resolve_chunk_indexes(records: Sequence[VectorRecord]) -> list[int]:
    """Return the chunk index that every record of *records* must use.

    The explicit ``record.chunk_index`` wins, then ``metadata["chunk_index"]``.
    When neither is present the position inside the call is used, counted per
    document, so that a batch of records for one document receives
    ``0, 1, 2, ...`` and a second document starts at ``0`` again.
    """
    resolved: list[int] = []
    next_index: dict[UUID, int] = {}
    for record in records:
        explicit = record.chunk_index
        if explicit is None:
            candidate = record.metadata.get("chunk_index")
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                explicit = candidate
        if explicit is None:
            explicit = next_index.get(record.document_id, 0)
        if explicit < 0:
            raise VectorStoreError(
                "chunk index must not be negative",
                code="invalid_chunk_index",
                details={"chunk_index": explicit},
            )
        next_index[record.document_id] = explicit + 1
        resolved.append(explicit)
    return resolved
