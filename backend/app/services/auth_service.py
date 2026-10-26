"""Authentication business rules.

The service owns everything that happens between a credential and a
session:

* :meth:`AuthService.register` creates an account,
* :meth:`AuthService.authenticate` turns a password into a session,
* :meth:`AuthService.resolve_session` turns a session token back into the
  user it belongs to,
* :meth:`AuthService.logout` and :meth:`AuthService.revoke_all_sessions`
  end sessions,
* :meth:`AuthService.list_scenarios` returns the demo scenarios.

Security rules
--------------
* **The password hash is never returned and never logged.**  The service
  returns :class:`UserSummary` objects, which do not carry the hash at all.
* **A failed login never reveals whether the account exists.**  An unknown
  address, an inactive account and a wrong password all raise the very
  same :class:`~app.core.exceptions.AuthenticationError` with the very same
  message.  A dummy hash is verified when the account does not exist, so
  that the response time does not leak the existence of the account
  either.
* **The raw session token is never persisted.**  Only its SHA-256 hash is
  written to the database; the raw token is returned to the caller once
  and is then delivered to the client in an httpOnly cookie.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)
from app.db.base import utcnow
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "ANONYMOUS_USER",
    "ANONYMOUS_USER_ID",
    "DEMO_PASSWORD",
    "DEMO_SCENARIOS",
    "EMAIL_PATTERN",
    "INVALID_CREDENTIALS_MESSAGE",
    "SESSION_INVALID_MESSAGE",
    "AuthService",
    "AuthenticatedSession",
    "ScenarioSummary",
    "UserSummary",
]

logger = get_logger(__name__)

#: A deliberately simple e-mail pattern: a local part, an ``@`` and a
#: domain with at least one dot.  The pattern is *not* an attempt to
#: implement RFC 5322 - it rejects the obvious mistakes and accepts every
#: address that is used in practice.
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

#: The maximum length of an e-mail address (the column is ``VARCHAR(320)``).
MAX_EMAIL_LENGTH = 320

#: The maximum length of a display name (the column is ``VARCHAR(255)``).
MAX_FULL_NAME_LENGTH = 255

#: The message of a failed login.  It is the **same** for an unknown
#: address, an inactive account and a wrong password.
INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."

#: The message of a session that could not be resolved.
SESSION_INVALID_MESSAGE = "The session is missing, expired or invalid."

#: The id of the synthetic user that is used when the authentication is
#: switched off.  It is the nil UUID and therefore owns nothing.
ANONYMOUS_USER_ID = UUID("00000000-0000-0000-0000-000000000000")

#: The password of the three demo accounts.
DEMO_PASSWORD = "DemoAnalyst2024!"


@dataclass(frozen=True, slots=True)
class UserSummary:
    """A user as the rest of the application sees it.

    The field names match :class:`app.schemas.auth.UserRead`, therefore the
    API layer can map the summary with a single ``model_validate`` call.
    The password hash is **not** part of the summary.
    """

    id: UUID
    email: str
    full_name: str
    role: str
    scenario_key: str | None
    created_at: datetime
    last_login_at: datetime | None
    #: ``True`` for the synthetic user that is used when the
    #: authentication is switched off.
    is_anonymous: bool = False


@dataclass(frozen=True, slots=True)
class ScenarioSummary:
    """One demo scenario of the system."""

    key: str
    title: str
    tagline: str
    description: str
    focus_areas: list[str]
    suggested_queries: list[str]
    demo_email: str | None = None
    demo_password: str | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """The outcome of a successful login.

    ``token`` is the **raw** session token.  It is the only moment the
    raw token exists outside of the client, therefore it must not be
    stored and must not be logged.
    """

    user: UserSummary
    token: str
    expires_at: datetime


#: The synthetic user that is returned when the authentication is off.
ANONYMOUS_USER = UserSummary(
    id=ANONYMOUS_USER_ID,
    email="anonymous@local.invalid",
    full_name="Anonymous",
    role="analyst",
    scenario_key=None,
    created_at=datetime(1970, 1, 1, tzinfo=UTC),
    last_login_at=None,
    is_anonymous=True,
)

#: The three demo scenarios of the system.  The frontend fetches them from
#: ``GET /api/v1/auth/scenarios`` and never hard codes them.
DEMO_SCENARIOS: tuple[ScenarioSummary, ...] = (
    ScenarioSummary(
        key="equity-analyst",
        title="Equity Analyst",
        tagline="Follow the earnings power of a company.",
        description=(
            "The workspace of an equity analyst follows a listed company: the "
            "statements of income, the development of the revenue and of the "
            "margin and the contribution of every segment.  The suggested "
            "queries lead to the consolidated statements of income, to the "
            "segment revenue and operating income and to the effective tax "
            "rate of the reporting period."
        ),
        focus_areas=[
            "company filings",
            "revenue & margin trends",
            "segment performance",
        ],
        suggested_queries=[
            "consolidated statements of income",
            "segment revenue and operating income",
            "effective income tax rate",
        ],
        demo_email="analyst@demo.local",
        demo_password=DEMO_PASSWORD,
    ),
    ScenarioSummary(
        key="credit-analyst",
        title="Credit Analyst",
        tagline="Judge the balance sheet and the funding of a bank.",
        description=(
            "The workspace of a credit analyst follows the financial "
            "structure of a company: the size of the balance sheet, the "
            "liquidity and the funding and the risks that come with them.  "
            "The suggested queries lead to the total assets and the total "
            "liabilities, to the net interest income and to the deposits and "
            "the long-term debt."
        ),
        focus_areas=[
            "balance sheet strength",
            "liquidity and funding",
            "credit risk",
        ],
        suggested_queries=[
            "total assets and total liabilities",
            "net interest income and noninterest revenue",
            "deposits and long-term debt",
        ],
        demo_email="credit@demo.local",
        demo_password=DEMO_PASSWORD,
    ),
    ScenarioSummary(
        key="corporate-development",
        title="Corporate Development",
        tagline="Understand how the capital is put to work.",
        description=(
            "The workspace of a corporate development analyst follows the "
            "capital allocation of a company: the acquisitions, the "
            "investments, the research and development and the money that "
            "goes back to the shareholders.  The suggested queries lead to "
            "the share repurchases and the dividends, to the acquisitions "
            "and the investments and to the research and development "
            "expense."
        ),
        focus_areas=[
            "capital allocation",
            "M&A and investments",
            "shareholder returns",
        ],
        suggested_queries=[
            "share repurchases and dividends",
            "acquisitions and investments",
            "research and development expense",
        ],
        demo_email="corpdev@demo.local",
        demo_password=DEMO_PASSWORD,
    ),
)

#: A hash of a random password.  It is verified when a login is attempted
#: for an address that does not exist, so that the response time of a
#: login does not leak whether the account exists.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(24))


class AuthService:
    """Business rules of the authentication."""

    def __init__(self, session_factory: Callable[[], Session], *, settings: Settings) -> None:
        """Create the service.

        Parameters
        ----------
        session_factory:
            Callable that returns a fresh :class:`~sqlalchemy.orm.Session`.
            The service opens and closes the sessions itself, therefore the
            factory must return a session the service may dispose of.
        settings:
            The effective configuration.  The session lifetime and the
            minimum length of a password are read from it.
        """
        self._session_factory = session_factory
        self._settings = settings

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
    def _to_summary(user) -> UserSummary:
        """Return the summary of the user row *user*."""
        return UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            scenario_key=user.scenario_key,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_email(email: str | None) -> str:
        """Return the normalised form of *email*.

        The address is trimmed and lowercased, therefore
        ``Alice@Example.COM`` and ``alice@example.com`` are the same
        account.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the address is empty, too long or malformed.
        """
        if not isinstance(email, str) or not email.strip():
            raise ValidationError(
                "the e-mail address must not be empty",
                code="invalid_email",
                details={"field": "email"},
            )
        normalised = email.strip().lower()
        if len(normalised) > MAX_EMAIL_LENGTH:
            raise ValidationError(
                f"the e-mail address must not be longer than {MAX_EMAIL_LENGTH} "
                "characters",
                code="invalid_email",
                details={"field": "email", "max_length": MAX_EMAIL_LENGTH},
            )
        if EMAIL_PATTERN.match(normalised) is None:
            raise ValidationError(
                "the e-mail address is not a valid address",
                code="invalid_email",
                details={"field": "email"},
            )
        return normalised

    @staticmethod
    def _validate_full_name(full_name: str | None) -> str:
        """Return the cleaned display name.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the name is empty or too long.
        """
        if not isinstance(full_name, str) or not full_name.strip():
            raise ValidationError(
                "the full name must not be empty",
                code="invalid_full_name",
                details={"field": "full_name"},
            )
        cleaned = full_name.strip()
        if len(cleaned) > MAX_FULL_NAME_LENGTH:
            raise ValidationError(
                f"the full name must not be longer than {MAX_FULL_NAME_LENGTH} "
                "characters",
                code="invalid_full_name",
                details={"field": "full_name", "max_length": MAX_FULL_NAME_LENGTH},
            )
        return cleaned

    def _validate_password(self, password: str | None) -> str:
        """Return the password if it satisfies the configured rules.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the password is empty or shorter than
            ``settings.auth_password_min_length``.
        """
        minimum = int(self._settings.auth_password_min_length)
        if not isinstance(password, str) or not password:
            raise ValidationError(
                "the password must not be empty",
                code="invalid_password",
                details={"field": "password"},
            )
        if len(password) < minimum:
            raise ValidationError(
                f"the password must not be shorter than {minimum} characters",
                code="invalid_password",
                details={"field": "password", "min_length": minimum},
            )
        return password

    @staticmethod
    def _validate_scenario_key(scenario_key: str | None) -> str | None:
        """Return the scenario key if it is one of the known scenarios.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the key is not known.
        """
        if scenario_key is None:
            return None
        cleaned = str(scenario_key).strip()
        if not cleaned:
            return None
        known = {scenario.key for scenario in DEMO_SCENARIOS}
        if cleaned not in known:
            raise ValidationError(
                "the scenario key is not known",
                code="invalid_scenario_key",
                details={"field": "scenario_key", "scenario_key": cleaned},
            )
        return cleaned

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def register(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        scenario_key: str | None = None,
    ) -> UserSummary:
        """Create an account and return its summary.

        The e-mail address is normalised (trimmed and lowercased) before it
        is stored, therefore the same address can never be registered twice.

        Raises
        ------
        app.core.exceptions.ValidationError
            If the address, the name or the password does not satisfy the
            rules of the service.
        app.core.exceptions.ConflictError
            If an account with the address already exists.
        """
        normalised_email = self._normalise_email(email)
        cleaned_name = self._validate_full_name(full_name)
        self._validate_password(password)
        cleaned_scenario = self._validate_scenario_key(scenario_key)

        with self._session_scope() as session:
            repository = UserRepository(session)
            if repository.get_by_email(normalised_email) is not None:
                raise ConflictError(
                    "an account with this e-mail address already exists",
                    code="email_already_registered",
                    details={"email": normalised_email},
                )
            user = repository.create(
                email=normalised_email,
                full_name=cleaned_name,
                password_hash=hash_password(password),
                role="analyst",
                scenario_key=cleaned_scenario,
            )
            return self._to_summary(user)

    def authenticate(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthenticatedSession:
        """Verify a credential and open a session.

        The session token is returned **raw**: it is the only moment the
        raw token exists outside of the client.

        Raises
        ------
        app.core.exceptions.AuthenticationError
            If the address is unknown, the account is inactive or the
            password is wrong.  The message is the same in all three cases.
        """
        normalised_email = (email or "").strip().lower()
        candidate = password if isinstance(password, str) else ""

        with self._session_scope() as session:
            user_repository = UserRepository(session)
            user = (
                user_repository.get_by_email(normalised_email)
                if normalised_email
                else None
            )

            if user is None:
                # The account does not exist: a dummy hash is verified so
                # that the response time does not leak the existence of the
                # account.
                verify_password(candidate, _DUMMY_PASSWORD_HASH)
                raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

            if not verify_password(candidate, user.password_hash):
                raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

            if not user.is_active:
                # The credential was correct, but the account is switched
                # off.  The answer is the same as for a wrong password.
                raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

            if needs_rehash(user.password_hash):
                # The stored hash was produced with weaker parameters: it is
                # replaced with a current one.
                user_repository.set_password_hash(user.id, hash_password(candidate))

            now = utcnow()
            user_repository.update_last_login(user.id, when=now)

            token = generate_session_token()
            expires_at = now + timedelta(hours=int(self._settings.auth_session_ttl_hours))
            AuthSessionRepository(session).create(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            return AuthenticatedSession(
                user=self._to_summary(user),
                token=token,
                expires_at=expires_at,
            )

    def resolve_session(self, raw_token: str) -> UserSummary:
        """Return the user of the session *raw_token*.

        The token is hashed before it is looked up, therefore the database
        never sees it.

        Raises
        ------
        app.core.exceptions.AuthenticationError
            If the token is unknown, revoked, expired, or belongs to an
            account that is not active any more.
        """
        if not isinstance(raw_token, str) or not raw_token:
            raise AuthenticationError(SESSION_INVALID_MESSAGE)

        token_hash = hash_session_token(raw_token)
        with self._session_scope() as session:
            session_repository = AuthSessionRepository(session)
            row = session_repository.get_by_token_hash(token_hash)
            if row is None:
                raise AuthenticationError(SESSION_INVALID_MESSAGE)
            if row.revoked_at is not None:
                raise AuthenticationError(SESSION_INVALID_MESSAGE)
            if row.expires_at <= utcnow():
                raise AuthenticationError(SESSION_INVALID_MESSAGE)

            user = UserRepository(session).get(row.user_id)
            if user is None or not user.is_active:
                raise AuthenticationError(SESSION_INVALID_MESSAGE)
            return self._to_summary(user)

    def logout(self, raw_token: str | None) -> None:
        """Revoke the session of *raw_token*.

        The method is idempotent: an unknown or an already revoked token is
        not an error.
        """
        if not isinstance(raw_token, str) or not raw_token:
            return
        with self._session_scope() as session:
            AuthSessionRepository(session).revoke_by_token_hash(
                hash_session_token(raw_token)
            )

    def revoke_all_sessions(self, user_id: UUID) -> int:
        """Revoke every session of the user *user_id*; return the count."""
        with self._session_scope() as session:
            return AuthSessionRepository(session).revoke_all_for_user(user_id)

    def list_scenarios(self) -> list[ScenarioSummary]:
        """Return the demo scenarios of the system.

        The demo credentials are only part of the answer when
        ``settings.auth_demo_scenarios_enabled`` is true; otherwise they
        are ``None``.
        """
        enabled = bool(self._settings.auth_demo_scenarios_enabled)
        return [
            ScenarioSummary(
                key=scenario.key,
                title=scenario.title,
                tagline=scenario.tagline,
                description=scenario.description,
                focus_areas=list(scenario.focus_areas),
                suggested_queries=list(scenario.suggested_queries),
                demo_email=scenario.demo_email if enabled else None,
                demo_password=scenario.demo_password if enabled else None,
            )
            for scenario in DEMO_SCENARIOS
        ]