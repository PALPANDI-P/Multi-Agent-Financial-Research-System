"""Workspace ORM model.

A workspace is the top level container for documents, chunks and retrieval
scope.  :attr:`Workspace.owner_id` points at the user that owns the
workspace; the column stays nullable, because a workspace may exist
without an owner (the shared seed corpus for example).

Beside the owner, a user may be a **member** of a workspace: the rows of
:attr:`WorkspaceMember` express that a user may read (and write) a
workspace that somebody else owns.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["WORKSPACE_MEMBER_ROLES", "Workspace", "WorkspaceMember"]

#: The roles a member of a workspace may have.
WORKSPACE_MEMBER_ROLES: tuple[str, ...] = ("owner", "member", "viewer")


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named container that groups documents and their chunks."""

    __tablename__ = "workspaces"
    __table_args__ = (
        Index("ix_workspaces_name", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment=(
            "The user that owns the workspace. The column stays NULL for a "
            "workspace without an owner (the shared seed corpus for example)."
        ),
    )


class WorkspaceMember(Base):
    """The membership of a user in a workspace."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        # The composite primary key **is** the unique constraint of the
        # pair (workspace_id, user_id).  PostgreSQL does not create a
        # second, redundant unique index for a pair that is already
        # unique, therefore the pair is declared once - as the primary
        # key of the table.
        PrimaryKeyConstraint("workspace_id", "user_id", name="pk_workspace_members"),
        CheckConstraint(
            "role IN ('owner', 'member', 'viewer')",
            name="ck_workspace_members_role",
        ),
        Index("ix_workspace_members_user_id", "user_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="member",
        server_default="member",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )