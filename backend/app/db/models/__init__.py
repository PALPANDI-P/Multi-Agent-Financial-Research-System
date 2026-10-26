"""ORM models.

Importing this package registers every model on
``app.db.base.Base.metadata`` so that Alembic autogenerate sees the complete
schema.
"""

from app.db.base import Base
from app.db.models.auth_session import AuthSession
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
from app.db.models.user import USER_ROLES, User
from app.db.models.workspace import (
    WORKSPACE_MEMBER_ROLES,
    Workspace,
    WorkspaceMember,
)

__all__ = [
    "CHUNK_TYPES",
    "DOCUMENT_PROCESSING_STATUSES",
    "EMBEDDING_DIMENSION",
    "JOB_STATUSES",
    "USER_ROLES",
    "WORKSPACE_MEMBER_ROLES",
    "AuthSession",
    "Base",
    "ChunkType",
    "Document",
    "DocumentChunk",
    "DocumentProcessingStatus",
    "JobStatus",
    "ProcessingJob",
    "User",
    "Workspace",
    "WorkspaceMember",
]