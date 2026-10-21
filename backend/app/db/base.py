"""SQLAlchemy declarative base, naming conventions and shared column mixins.

All ORM models inherit from :class:`Base`, which carries a deterministic
naming convention.  Explicit constraint names are used wherever the default
convention would not produce the name required by the public contract (for
example ``uq_documents_workspace_content_hash``).

All timestamp columns are stored as ``TIMESTAMP WITH TIME ZONE`` and are
therefore timezone aware in both directions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "utcnow",
]

#: Deterministic constraint naming used by every table in the project.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Return the current time as a timezone aware UTC ``datetime``."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for every ORM model in the project."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds timezone aware ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UUIDPrimaryKeyMixin:
    """Adds a client side generated UUIDv4 primary key column."""

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )