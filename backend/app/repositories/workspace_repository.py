"""Persistence operations for the ``workspaces`` table."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.workspace import Workspace

__all__ = ["UNSET", "WorkspaceRepository"]


class _Unset:
    """Sentinel that marks an argument as *not provided*.

    ``None`` is a perfectly valid value for a nullable column, therefore it
    cannot be used to mean "leave this field alone".  The sentinel makes the
    difference between "the caller did not mention the field" and "the
    caller wants the field to be cleared" visible.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable representation of the sentinel."""
        return "UNSET"

    def __bool__(self) -> bool:
        """Return ``False``: the sentinel carries no value at all."""
        return False


#: Singleton instance of :class:`_Unset`.
UNSET = _Unset()


class WorkspaceRepository:
    """CRUD operations for :class:`~app.db.models.workspace.Workspace`.

    The repository never opens a transaction on its own behalf: the session
    it was built with is owned by the caller.  Every mutating method commits
    the session it was given and refreshes the affected row so that the
    returned object carries the server side defaults (``created_at`` and
    ``updated_at``).
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def create(self, *, name: str, description: str | None) -> Workspace:
        """Insert a workspace and return it."""
        workspace = Workspace(name=name, description=description)
        self._session.add(workspace)
        self._session.commit()
        self._session.refresh(workspace)
        return workspace

    def update(
        self,
        workspace: Workspace,
        *,
        name: str | _Unset | None = UNSET,
        description: str | _Unset | None = UNSET,
    ) -> Workspace:
        """Update *workspace* and return it.

        Only the fields that are **not** :data:`UNSET` are assigned, therefore
        a partial update never wipes an existing value.  An explicit ``None``
        *clears* a nullable field (the description), which is what a PATCH
        that removes a value has to express.
        """
        if name is not UNSET:
            workspace.name = name
        if description is not UNSET:
            workspace.description = description
        self._session.commit()
        self._session.refresh(workspace)
        return workspace

    def delete(self, workspace_id: UUID) -> bool:
        """Delete the workspace *workspace_id*; return whether it existed.

        The foreign keys of the schema cascade, therefore the documents, the
        chunks and the jobs of the workspace disappear with it.
        """
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            return False
        self._session.delete(workspace)
        self._session.commit()
        return True

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get(self, workspace_id: UUID) -> Workspace | None:
        """Return the workspace *workspace_id* or ``None``."""
        return self._session.get(Workspace, workspace_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        name_contains: str | None = None,
    ) -> tuple[list[Workspace], int]:
        """Return a page of workspaces and the **total** number of rows.

        The second element of the tuple is the number of workspaces that
        match the filter - not the size of the returned page.
        """
        filters = []
        if name_contains is not None:
            filters.append(Workspace.name.ilike(f"%{name_contains.strip()}%"))

        count_statement = select(func.count()).select_from(Workspace)
        page_statement = select(Workspace)
        if filters:
            count_statement = count_statement.where(*filters)
            page_statement = page_statement.where(*filters)

        total = int(self._session.execute(count_statement).scalar_one())
        page = list(
            self._session.execute(
                page_statement.order_by(Workspace.created_at.asc(), Workspace.id.asc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return page, total

    def count_documents(self, workspace_ids: Sequence[UUID]) -> dict[UUID, int]:
        """Return ``{workspace_id: document_count}`` for the given workspaces.

        The counts are collected with **one** grouped statement - a
        per-workspace query would be an N+1 access pattern.
        """
        identifiers = list(workspace_ids)
        if not identifiers:
            return {}

        statement = (
            select(Document.workspace_id, func.count())
            .where(Document.workspace_id.in_(identifiers))
            .group_by(Document.workspace_id)
        )
        rows = self._session.execute(statement).all()
        return {row[0]: int(row[1]) for row in rows}