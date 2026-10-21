"""Repository layer: the only place that talks SQL.

A repository owns exactly one aggregate (a table plus the rows that belong to
it) and exposes plain CRUD operations on the ORM objects.  It contains **no
business rules**: validation, orchestration and the translation of a missing
row into a domain error happen in :mod:`app.services`.

Rules that every repository of this package obeys:

* **No HTTP types, no Pydantic schemas, no embeddings and no vector
  calls.**  A repository returns ORM objects; the service layer turns them
  into frozen dataclasses.
* **A method that cannot find a row returns ``None``** instead of raising.
  The services translate ``None`` into
  :class:`~app.core.exceptions.NotFoundError`.
* **No N+1 queries.**  Aggregations over a collection are expressed as a
  single grouped statement (see
  :meth:`WorkspaceRepository.count_documents` and
  :meth:`ChunkRepository.count_by_documents`).
* **This package never imports :mod:`app.services`.**  The dependency arrow
  points in one direction only: services -> repositories -> models.
"""

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import ProcessingJobRepository
from app.repositories.workspace_repository import WorkspaceRepository

__all__ = [
    "ChunkRepository",
    "DocumentRepository",
    "ProcessingJobRepository",
    "WorkspaceRepository",
]