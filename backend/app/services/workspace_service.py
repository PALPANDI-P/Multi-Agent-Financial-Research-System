"""Workspace business rules.

The service owns the rules that the repository is not allowed to know:
validation of the user supplied values, the translation of a missing row
into a domain error and the coordination of the database with the file
system.

Every method opens its own short lived session through the injected
``session_factory`` and returns a **frozen dataclass** - never an ORM
object and never a Pydantic schema.  The field names of
:class:`WorkspaceSummary` match :class:`app.schemas.workspace.WorkspaceRead`
so that the API layer can map the result with
``WorkspaceRead.model_validate(summary)``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.storage import StorageBackend
from app.db.models.workspace import Workspace
from app.repositories.document_repository import DocumentRepository
from app.repositories.workspace_repository import UNSET, WorkspaceRepository, _Unset

__all__ = [
    "MAX_WORKSPACE_NAME_LENGTH",
    "UNSET",
    "WorkspaceService",
    "WorkspaceSummary",
]

logger = get_logger(__name__)

#: Maximum length of a workspace name (the column is ``VARCHAR(255)``).
MAX_WORKSPACE_NAME_LENGTH: int = 255


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    """A workspace as the rest of the application sees it."""

    id: UUID
    name: str
    description: str | None
    owner_id: UUID | None
    document_count: int
    created_at: datetime
    updated_at: datetime


class WorkspaceService:
    """Business rules for workspaces."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        storage: StorageBackend | None = None,
    ) -> None:
        """Create the service.

        Parameters
        ----------
        session_factory:
            Callable that returns a fresh :class:`~sqlalchemy.orm.Session`.
            The service opens and closes the sessions itself, therefore the
            factory must return a session the service may dispose of.
        storage:
            Optional storage backend.  It is used to remove the files of the
            documents of a deleted workspace.
        """
        self._session_factory = session_factory
        self._storage = storage

    # ------------------------------------------------------------------
    # infrastructure
    # ------------------------------------------------------------------
    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Open a session, roll back on error and always close it."""
        session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _validate_name(name: str | None) -> str:
        """Return the cleaned *name* or raise :class:`ValidationError`."""
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(
                "the workspace name must not be empty",
                code="invalid_workspace_name",
                details={"field": "name"},
            )
        cleaned = name.strip()
        if len(cleaned) > MAX_WORKSPACE_NAME_LENGTH:
            raise ValidationError(
                f"the workspace name must not be longer than "
                f"{MAX_WORKSPACE_NAME_LENGTH} characters",
                code="invalid_workspace_name",
                details={
                    "field": "name",
                    "length": len(cleaned),
                    "max_length": MAX_WORKSPACE_NAME_LENGTH,
                },
            )
        return cleaned

    @staticmethod
    def _to_summary(workspace: Workspace, *, document_count: int) -> WorkspaceSummary:
        """Return the summary of *workspace*."""
        return WorkspaceSummary(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            owner_id=workspace.owner_id,
            document_count=document_count,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    def _remove_files(self, storage_keys: list[str]) -> None:
        """Remove *storage_keys* from the storage backend.

        A failure is logged and never raised: the database is the source of
        truth and a dangling file is harmless, while a raised error would
        report a delete that did in fact happen.
        """
        if self._storage is None:
            return
        for storage_key in storage_keys:
            try:
                self._storage.delete(storage_key)
            except Exception as exc:  # a dangling file must not break the flow
                logger.warning(
                    "could not remove the stored document of a deleted workspace",
                    extra={"storage_key": storage_key, "error": str(exc)},
                )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def create_workspace(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> WorkspaceSummary:
        """Create a workspace and return its summary.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the name is empty or longer than
            :data:`MAX_WORKSPACE_NAME_LENGTH` characters.
        """
        cleaned = self._validate_name(name)
        with self._session_scope() as session:
            repository = WorkspaceRepository(session)
            workspace = repository.create(name=cleaned, description=description)
            return self._to_summary(workspace, document_count=0)

    def list_workspaces(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        name_contains: str | None = None,
    ) -> tuple[list[WorkspaceSummary], int]:
        """Return a page of workspaces and the **total** number of workspaces.

        The document counts of the page are collected with a single grouped
        query, therefore the number of executed statements does not grow
        with the size of the page.
        """
        with self._session_scope() as session:
            repository = WorkspaceRepository(session)
            page, total = repository.list(
                limit=limit,
                offset=offset,
                name_contains=name_contains,
            )
            counts = repository.count_documents([workspace.id for workspace in page])
            summaries = [
                self._to_summary(workspace, document_count=counts.get(workspace.id, 0))
                for workspace in page
            ]
            return summaries, total

    def get_workspace(self, workspace_id: UUID) -> WorkspaceSummary:
        """Return the workspace *workspace_id*.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the workspace does not exist.
        """
        with self._session_scope() as session:
            repository = WorkspaceRepository(session)
            workspace = repository.get(workspace_id)
            if workspace is None:
                raise self._not_found(workspace_id)
            counts = repository.count_documents([workspace_id])
            return self._to_summary(
                workspace, document_count=counts.get(workspace_id, 0)
            )

    def update_workspace(
        self,
        workspace_id: UUID,
        *,
        name: str | _Unset | None = UNSET,
        description: str | _Unset | None = UNSET,
    ) -> WorkspaceSummary:
        """Update the workspace *workspace_id* and return its summary.

        Only the fields that are not :data:`UNSET` are written, therefore a
        partial update never wipes an existing value.  An explicit ``None``
        clears the description; the name of a workspace may never be cleared
        and is therefore rejected by the validation.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the workspace does not exist.
        app.core.exceptions.ValidationError
            If a new name is empty or too long.
        """
        cleaned = self._validate_name(name) if name is not UNSET else UNSET
        with self._session_scope() as session:
            repository = WorkspaceRepository(session)
            workspace = repository.get(workspace_id)
            if workspace is None:
                raise self._not_found(workspace_id)
            if cleaned is not UNSET or description is not UNSET:
                workspace = repository.update(
                    workspace, name=cleaned, description=description
                )
            counts = repository.count_documents([workspace_id])
            return self._to_summary(
                workspace, document_count=counts.get(workspace_id, 0)
            )

    def delete_workspace(self, workspace_id: UUID) -> None:
        """Delete the workspace *workspace_id* and every file it owns.

        Ordering
        --------
        1. the storage keys of the documents of the workspace are collected,
        2. the workspace row is deleted and **committed** - the foreign key
           cascade of the schema removes the documents, the chunks and the
           jobs with it,
        3. only then the files are removed from the storage backend.

        The files are removed **after** the commit on purpose: the database
        is the source of truth, therefore a dangling file is harmless, while
        a file that was removed while the row still exists would be a
        document without content.  A failure to remove a file is logged and
        never raised, because the database is already consistent.

        Raises
        ------
        app.core.exceptions.NotFoundError
            If the workspace does not exist.
        """
        storage_keys: list[str] = []
        with self._session_scope() as session:
            workspace_repository = WorkspaceRepository(session)
            document_repository = DocumentRepository(session)
            if workspace_repository.get(workspace_id) is None:
                raise self._not_found(workspace_id)
            storage_keys = document_repository.list_storage_keys(workspace_id)
            if not workspace_repository.delete(workspace_id):
                raise self._not_found(workspace_id)
        self._remove_files(storage_keys)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _not_found(workspace_id: UUID) -> NotFoundError:
        """Return the error that reports a missing workspace."""
        return NotFoundError(
            f"the workspace {workspace_id} does not exist",
            details={"workspace_id": str(workspace_id)},
        )