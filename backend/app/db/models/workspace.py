"""Workspace ORM model.

A workspace is the top level container for documents, chunks and retrieval
scope.  M1 has no authentication, therefore :attr:`Workspace.owner_id` is
reserved but always ``NULL`` and no multi-user isolation is provided.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["Workspace"]


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
        nullable=True,
        comment=(
            "Reserved for a future multi-tenant owner. M1 implements no "
            "authentication and therefore no multi-user isolation: this "
            "column is always NULL."
        ),
    )