"""Semantic search business rules.

The service glues the two halves of a retrieval request together: the query
is turned into a vector by the :class:`~app.embeddings.service.EmbeddingService`
and the vector is handed to the :class:`~app.vectorstore.base.VectorStore`,
which enforces the workspace isolation in SQL.

The service never talks to the database itself: the vector store owns the
persistence of the chunks.  It returns **frozen dataclasses** whose field
names match :class:`app.schemas.search.SearchResponse` and
:class:`app.schemas.search.SearchResultItem`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.embeddings.service import EmbeddingService
from app.vectorstore.base import SearchHit, VectorStore

__all__ = ["MAX_QUERY_LENGTH", "SearchResultItem", "SearchResults", "SearchService"]

#: Maximum length of a search query (characters).
MAX_QUERY_LENGTH: int = 1000


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """A single search hit."""

    chunk_id: UUID
    document_id: UUID
    document_title: str | None
    company_name: str | None
    document_type: str | None
    fiscal_period: str | None
    page_start: int | None
    page_end: int | None
    section_heading: str | None
    chunk_type: str
    content: str
    score: float
    metadata: dict


@dataclass(frozen=True, slots=True)
class SearchResults:
    """The result of a search request."""

    query: str
    workspace_id: UUID
    total: int
    results: list[SearchResultItem]
    took_ms: float


class SearchService:
    """Business rules for semantic search."""

    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        settings: Settings,
    ) -> None:
        """Create the service.

        Parameters
        ----------
        vector_store:
            Store the query is executed against.  It enforces the workspace
            isolation itself.
        embedding_service:
            Service that turns the query into a vector.
        settings:
            Application settings; ``retrieval_top_k`` and
            ``retrieval_max_top_k`` define the default and the maximum
            number of hits.
        """
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._settings = settings

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _resolve_limit(self, limit: int | None) -> int:
        """Return the effective limit of a search.

        ``None`` selects the configured ``retrieval_top_k``.  A limit above
        ``retrieval_max_top_k`` is clamped, a limit below one is rejected.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the limit is smaller than one.
        """
        maximum = int(self._settings.retrieval_max_top_k)
        if limit is None:
            return min(int(self._settings.retrieval_top_k), maximum)
        if limit < 1:
            raise ValidationError(
                "the search limit must be at least 1",
                code="invalid_search_limit",
                details={"limit": limit, "min_limit": 1},
            )
        return min(int(limit), maximum)

    @staticmethod
    def _to_item(hit: SearchHit) -> SearchResultItem:
        """Return the result item of *hit*."""
        return SearchResultItem(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            document_title=hit.document_title,
            company_name=hit.company_name,
            document_type=hit.document_type,
            fiscal_period=hit.fiscal_period,
            page_start=hit.page_start,
            page_end=hit.page_end,
            section_heading=hit.section_heading,
            chunk_type=hit.chunk_type,
            content=hit.content,
            score=float(hit.score),
            metadata=dict(hit.metadata),
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def search(
        self,
        *,
        workspace_id: UUID,
        query: str,
        limit: int | None = None,
        document_ids: Sequence[UUID] | None = None,
        chunk_types: Sequence[str] | None = None,
    ) -> SearchResults:
        """Search the chunks of *workspace_id* for *query*.

        The workspace isolation is enforced by the vector store, never by
        the caller.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the query is empty or too long, or if the limit is smaller
            than one.
        """
        started = time.perf_counter()

        cleaned = (query or "").strip()
        if not cleaned:
            raise ValidationError(
                "the search query must not be empty",
                code="invalid_search_query",
                details={"field": "query"},
            )
        if len(query) > MAX_QUERY_LENGTH:
            raise ValidationError(
                f"the search query must not be longer than {MAX_QUERY_LENGTH} characters",
                code="invalid_search_query",
                details={"field": "query", "length": len(query)},
            )

        effective_limit = self._resolve_limit(limit)
        embedding = self._embedding_service.embed_query(cleaned)
        hits = self._vector_store.search(
            embedding,
            workspace_id,
            limit=effective_limit,
            document_ids=document_ids,
            chunk_types=chunk_types,
        )
        results = [self._to_item(hit) for hit in hits]
        took_ms = (time.perf_counter() - started) * 1000.0

        return SearchResults(
            query=cleaned,
            workspace_id=workspace_id,
            total=len(results),
            results=results,
            took_ms=took_ms,
        )