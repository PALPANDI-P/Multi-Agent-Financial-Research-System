"""Persistence operations for the ``users`` table.

The repository never returns the password hash unless it is asked to: the
methods that return a user return the whole row, therefore a caller that
wants to log a user must redact the hash itself.  The service layer never
logs a user row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.user import User

__all__ = ["UserRepository"]


class UserRepository:
    """CRUD operations for :class:`~app.db.models.user.User`.

    Every mutating method commits the session it was given and refreshes
    the affected row, therefore the returned object carries the server side
    defaults (``created_at`` and ``updated_at``).
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
        email: str,
        full_name: str,
        password_hash: str,
        role: str = "analyst",
        scenario_key: str | None = None,
        is_active: bool = True,
    ) -> User:
        """Insert a user and return it."""
        user = User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            scenario_key=scenario_key,
            is_active=is_active,
        )
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def update_last_login(self, user_id: UUID, *, when: datetime | None = None) -> None:
        """Write the moment of the last login of the user *user_id*."""
        user = self.get(user_id)
        if user is None:
            return
        user.last_login_at = when or utcnow()
        self._session.commit()

    def set_password_hash(self, user_id: UUID, password_hash: str) -> None:
        """Replace the stored hash of the user *user_id*.

        The method is used to upgrade a password that was hashed with
        weaker parameters.
        """
        user = self.get(user_id)
        if user is None:
            return
        user.password_hash = password_hash
        self._session.commit()

    def set_role(self, user_id: UUID, role: str) -> None:
        """Replace the role of the user *user_id*."""
        user = self.get(user_id)
        if user is None:
            return
        user.role = role
        self._session.commit()

    def set_scenario_key(self, user_id: UUID, scenario_key: str | None) -> None:
        """Replace the demo scenario of the user *user_id*."""
        user = self.get(user_id)
        if user is None:
            return
        user.scenario_key = scenario_key
        self._session.commit()

    def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        """Activate or deactivate the user *user_id*."""
        user = self.get(user_id)
        if user is None:
            return
        user.is_active = is_active
        self._session.commit()

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get(self, user_id: UUID) -> User | None:
        """Return the user *user_id* or ``None``."""
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return the user with *email* or ``None``.

        The lookup is case insensitive: the address is lowercased before it
        is compared, exactly like it is stored.
        """
        normalised = (email or "").strip().lower()
        if not normalised:
            return None
        statement = select(User).where(User.email == normalised).limit(1)
        return self._session.execute(statement).scalars().first()

    def list_by_scenario(self, scenario_key: str) -> list[User]:
        """Return every user of the scenario *scenario_key*."""
        statement = (
            select(User)
            .where(User.scenario_key == scenario_key)
            .order_by(User.created_at.asc(), User.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())