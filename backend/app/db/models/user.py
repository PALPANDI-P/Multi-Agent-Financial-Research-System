"""User ORM model.

A user is the account a person signs in with.  The password is **never**
stored: the table carries the Argon2id hash that
:func:`app.core.security.hash_password` produced.  The e-mail address is
unique and is stored lowercased and stripped, therefore the login of
``Alice@Example.COM`` and of ``alice@example.com`` is the same account.

The role is a coarse authorisation hint (``analyst``, ``researcher`` or
``administrator``); the *ownership* of a workspace is expressed by
``workspaces.owner_id`` and by the rows of ``workspace_members``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["USER_ROLES", "User"]

#: The roles a user may have.
USER_ROLES: tuple[str, ...] = ("analyst", "researcher", "administrator")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An account that may sign in."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('analyst', 'researcher', 'administrator')",
            name="ck_users_role",
        ),
        Index("ix_users_scenario_key", "scenario_key"),
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        comment="Lowercased and stripped e-mail address.",
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="analyst",
        server_default="analyst",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Argon2id hash of the password. The password itself is never stored.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    scenario_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Key of the demo scenario the account was created for.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )