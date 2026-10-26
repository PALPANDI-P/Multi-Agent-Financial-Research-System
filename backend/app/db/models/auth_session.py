"""Authentication session ORM model.

A row of this table is one signed-in session.  The table stores the
**SHA-256 hash** of the session token and never the token itself: the raw
token exists only in the httpOnly cookie of the client, therefore a dump
of the table cannot be replayed against the API.

A session is valid when it is not revoked, when it has not expired and
when the user it belongs to is still active.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

__all__ = ["AuthSession"]


class AuthSession(UUIDPrimaryKeyMixin, Base):
    """One signed-in session of a user."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_user_id_expires_at", "user_id", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the session token. The token itself is never stored.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)