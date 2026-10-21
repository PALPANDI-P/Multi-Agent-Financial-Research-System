"""Vector store access.

This package owns everything that talks to the pgvector storage of
``document_chunks``: writing vectors, running similarity searches and the
maintenance operations that keep the index consistent with the stored
metadata.

The public API is small on purpose:

* :class:`VectorStore` - the protocol every store implements.
* :class:`VectorRecord` / :class:`SearchHit` - the immutable hand-off
  objects that cross the boundary between the pipeline and the store.
* :class:`PgVectorStore` - the production implementation (PostgreSQL +
  pgvector).
* :class:`InMemoryVectorStore` - a **test only** implementation that keeps
  everything in a dictionary.  It is not a production store.
"""

from app.vectorstore.base import SearchHit, VectorRecord, VectorStore
from app.vectorstore.in_memory_store import InMemoryVectorStore
from app.vectorstore.pgvector_store import PgVectorStore

__all__ = [
    "InMemoryVectorStore",
    "PgVectorStore",
    "SearchHit",
    "VectorRecord",
    "VectorStore",
]
