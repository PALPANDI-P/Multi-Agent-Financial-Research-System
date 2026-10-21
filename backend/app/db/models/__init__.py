"""ORM models.

Importing this package registers every model on
``app.db.base.Base.metadata`` so that Alembic autogenerate sees the complete
schema.
"""

from app.db.base import Base
from app.db.models.chunk import (
    CHUNK_TYPES,
    EMBEDDING_DIMENSION,
    ChunkType,
    DocumentChunk,
)
from app.db.models.document import (
    DOCUMENT_PROCESSING_STATUSES,
    Document,
    DocumentProcessingStatus,
)
from app.db.models.job import JOB_STATUSES, JobStatus, ProcessingJob
from app.db.models.workspace import Workspace

__all__ = [
    "CHUNK_TYPES",
    "DOCUMENT_PROCESSING_STATUSES",
    "EMBEDDING_DIMENSION",
    "JOB_STATUSES",
    "Base",
    "ChunkType",
    "Document",
    "DocumentChunk",
    "DocumentProcessingStatus",
    "JobStatus",
    "ProcessingJob",
    "Workspace",
]