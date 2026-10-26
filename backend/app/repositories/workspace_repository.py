"""Persistence operations for the ``workspaces`` table."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.workspace import Workspace, WorkspaceMember

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

    Ownership
    ---------
    A user reaches a workspace when it **owns** it (``workspaces.owner_id``)
    or when it is a **member** of it (a row of ``workspace_members``).  The
    ``owner_id`` filter of :meth:`list` and the two helpers
    :meth:`list_accessible_workspace_ids` and :meth:`can_access_workspace`
    implement that rule.  ``owner_id=None`` means *no filtering at all*: it
    is the mode the system itself uses (the seed loader for example).
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def create(
        self,
        *,
        name: str,
        description: str | None,
        owner_id: UUID | None = None,
    ) -> Workspace:
        """Insert a workspace and return it."""
        workspace = Workspace(name=name, description=description, owner_id=owner_id)
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

    def set_owner(self, workspace_id: UUID, owner_id: UUID | None) -> bool:
        """Set the owner of the workspace *workspace_id*.

        The method returns whether the workspace existed.  It is used to
        adopt a workspace that has no owner yet.
        """
        workspace = self.get(workspace_id)
        if workspace is None:
            return False
        workspace.owner_id = owner_id
        self._session.commit()
        return True

    def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        role: str = "member",
    ) -> bool:
        """Add the user *user_id* to the workspace *workspace_id*.

        The method is idempotent: a membership that already exists is not
        created a second time and ``False`` is returned.
        """
        existing = self.get_member(workspace_id, user_id)
        if existing is not None:
            return False
        self._session.add(
            WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        )
        self._session.commit()
        return True

    def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        """Remove the user *user_id* from the workspace *workspace_id*."""
        member = self.get_member(workspace_id, user_id)
        if member is None:
            return False
        self._session.delete(member)
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
        owner_id: UUID | None = None,
    ) -> tuple[list[Workspace], int]:
        """Return a page of workspaces and the **total** number of rows.

        The second element of the tuple is the number of workspaces that
        match the filter - not the size of the returned page.

        ``owner_id`` restricts the page to the workspaces the user owns or
        is a member of.  ``None`` means *no filtering*.
        """
        filters = []
        if name_contains is not None:
            filters.append(Workspace.name.ilike(f"%{name_contains.strip()}%"))
        if owner_id is not None:
            filters.append(self._ownership_filter(owner_id))

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

    # ------------------------------------------------------------------
    # ownership
    # ------------------------------------------------------------------
    @staticmethod
    def _ownership_filter(owner_id: UUID):
        """Return the SQL condition of the workspaces *owner_id* may reach.

        The condition is a single expression with a subquery, therefore the
        filter never costs an extra round trip.
        """
        return or_(
            Workspace.owner_id == owner_id,
            Workspace.id.in_(
                select(WorkspaceMember.workspace_id).where(
                    WorkspaceMember.user_id == owner_id
                )
            ),
        )

    def list_accessible_workspace_ids(self, user_id: UUID) -> list[UUID]:
        """Return the ids of the workspaces *user_id* may reach.

        A workspace is reachable when the user owns it or when it is a
        member of it.
        """
        statement = select(Workspace.id).where(self._ownership_filter(user_id))
        return [row[0] for row in self._session.execute(statement).all()]

    def can_access_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        """Return whether *user_id* may reach the workspace *workspace_id*."""
        statement = (
            select(Workspace.id)
            .where(Workspace.id == workspace_id, self._ownership_filter(user_id))
            .limit(1)
        )
        return self._session.execute(statement).first() is not None

    def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        """Return the membership of *user_id* in *workspace_id* or ``None``."""
        statement = (
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .limit(1)
        )
        return self._session.execute(statement).scalars().first()

    def list_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        """Return every membership of the workspace *workspace_id*."""
        statement = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at.asc(), WorkspaceMember.user_id.asc())
        )
        return list(self._session.execute(statement).scalars().all())

    def list_member_ids(self, workspace_id: UUID) -> list[UUID]:
        """Return the ids of the members of the workspace *workspace_id*."""
        statement = (
            select(WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.user_id.asc())
        )
        return [row[0] for row in self._session.execute(statement).all()]