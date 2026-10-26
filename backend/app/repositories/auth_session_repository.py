"""Persistence operations for the ``auth_sessions`` table.

The table stores the **SHA-256 hash** of a session token.  The raw token
lives in the httpOnly cookie of the client and is never written to the
database, therefore a row of this table can never be replayed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.auth_session import AuthSession

__all__ = ["AuthSessionRepository"]


class AuthSessionRepository:
    """CRUD operations for :class:`~app.db.models.auth_session.AuthSession`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSession:
        """Insert a session and return it."""
        session_row = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self._session.add(session_row)
        self._session.commit()
        self._session.refresh(session_row)
        return session_row

    def revoke(self, session_id: UUID, *, when: datetime | None = None) -> bool:
        """Revoke the session *session_id*; return whether it existed.

        The revocation is idempotent: a session that is already revoked
        keeps its first ``revoked_at``.
        """
        session_row = self.get(session_id)
        if session_row is None:
            return False
        if session_row.revoked_at is None:
            session_row.revoked_at = when or utcnow()
            self._session.commit()
        return True

    def revoke_by_token_hash(self, token_hash: str, *, when: datetime | None = None) -> bool:
        """Revoke the session of *token_hash*; return whether it existed.

        An unknown token is not an error: the caller asked to end a session
        that does not exist, which is already the case.
        """
        session_row = self.get_by_token_hash(token_hash)
        if session_row is None:
            return False
        return self.revoke(session_row.id, when=when)

    def revoke_all_for_user(self, user_id: UUID, *, when: datetime | None = None) -> int:
        """Revoke every session of the user *user_id*; return the count.

        Only the sessions that are still active are counted and stamped.
        """
        statement = select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        rows = list(self._session.execute(statement).scalars().all())
        stamp = when or utcnow()
        for row in rows:
            row.revoked_at = stamp
        if rows:
            self._session.commit()
        return len(rows)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        """Delete every session that expired before *now*; return the count."""
        moment = now or utcnow()
        statement = delete(AuthSession).where(AuthSession.expires_at < moment)
        result = self._session.execute(statement)
        self._session.commit()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get(self, session_id: UUID) -> AuthSession | None:
        """Return the session *session_id* or ``None``."""
        return self._session.get(AuthSession, session_id)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Return the session of *token_hash* or ``None``."""
        if not token_hash:
            return None
        statement = select(AuthSession).where(AuthSession.token_hash == token_hash).limit(1)
        return self._session.execute(statement).scalars().first()

    def list_for_user(self, user_id: UUID) -> list[AuthSession]:
        """Return every session of the user *user_id*."""
        statement = (
            select(AuthSession)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.created_at.asc(), AuthSession.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())