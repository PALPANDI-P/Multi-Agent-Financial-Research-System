"""Integration tests of the authentication service.

The tests run against a **real** PostgreSQL server.  Every test empties the
test tables before and after it runs, therefore the tests are independent of
each other and leave no residue behind.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import hash_session_token
from app.core.storage import LocalStorage
from app.db.base import utcnow
from app.db.models.auth_session import AuthSession
from app.db.models.document import Document
from app.db.models.user import User
from app.ingestion.validators import FileValidator
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.auth_service import DEMO_SCENARIOS, AuthService
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.services.workspace_service import WorkspaceService

pytestmark = pytest.mark.integration

#: A password that satisfies the configured minimum length.
PASSWORD = "a-correct-horse-battery-staple"

#: A second password, used to prove that it does not verify.
WRONG_PASSWORD = "a-different-horse-battery-staple"


def _register(
    service: AuthService,
    *,
    email: str = "ada@example.com",
    full_name: str = "Ada Analyst",
    scenario_key: str | None = None,
) -> UUID:
    """Register a user and return its id."""
    return service.register(
        email=email,
        full_name=full_name,
        password=PASSWORD,
        scenario_key=scenario_key,
    ).id


def _session_rows(session_factory: sessionmaker[Session]) -> list[AuthSession]:
    """Return every row of the ``auth_sessions`` table."""
    with session_factory() as session:
        statement = select(AuthSession).order_by(AuthSession.created_at.asc())
        return list(session.execute(statement).scalars().all())


def _user_row(session_factory: sessionmaker[Session], email: str) -> User | None:
    """Return the row of the user *email*."""
    with session_factory() as session:
        return UserRepository(session).get_by_email(email)


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------
def test_a_registered_user_is_stored_with_a_hashed_password(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """The password is hashed and the plaintext never reaches the database."""
    summary = auth_service.register(
        email="Ada@Example.COM",
        full_name="Ada Analyst",
        password=PASSWORD,
    )

    row = _user_row(session_factory, "ada@example.com")
    assert row is not None
    assert row.id == summary.id
    assert row.email == "ada@example.com"
    assert row.full_name == "Ada Analyst"
    assert row.role == "analyst"
    assert row.is_active is True
    assert row.password_hash != PASSWORD
    assert PASSWORD not in row.password_hash
    assert row.password_hash.startswith("$argon2id$")


def test_the_password_hash_is_never_returned(auth_service: AuthService) -> None:
    """The summary of a user does not carry the hash."""
    summary = auth_service.register(
        email="ada@example.com",
        full_name="Ada Analyst",
        password=PASSWORD,
    )

    assert not hasattr(summary, "password_hash")
    assert PASSWORD not in repr(summary)


def test_a_duplicate_email_is_a_conflict(auth_service: AuthService) -> None:
    """The same address cannot be registered twice."""
    auth_service.register(
        email="ada@example.com",
        full_name="Ada Analyst",
        password=PASSWORD,
    )

    with pytest.raises(ConflictError):
        auth_service.register(
            email="ADA@example.com",
            full_name="Ada Analyst",
            password=PASSWORD,
        )


def test_a_short_password_is_rejected(auth_service: AuthService) -> None:
    """A password that is too short is a validation error."""
    with pytest.raises(ValidationError):
        auth_service.register(
            email="ada@example.com",
            full_name="Ada Analyst",
            password="short",
        )


def test_a_malformed_email_is_rejected(auth_service: AuthService) -> None:
    """An address that is not an address is a validation error."""
    with pytest.raises(ValidationError):
        auth_service.register(
            email="not-an-email",
            full_name="Ada Analyst",
            password=PASSWORD,
        )


def test_an_empty_full_name_is_rejected(auth_service: AuthService) -> None:
    """A user without a name is a validation error."""
    with pytest.raises(ValidationError):
        auth_service.register(
            email="ada@example.com",
            full_name="   ",
            password=PASSWORD,
        )


# ----------------------------------------------------------------------
# authentication
# ----------------------------------------------------------------------
def test_a_correct_password_opens_a_session(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """The session row carries the hash of the token and never the token."""
    _register(auth_service)

    authenticated = auth_service.authenticate(
        email="ada@example.com",
        password=PASSWORD,
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    assert authenticated.user.email == "ada@example.com"
    assert authenticated.token
    assert authenticated.expires_at > utcnow()

    rows = _session_rows(session_factory)
    assert len(rows) == 1
    row = rows[0]
    assert row.token_hash == hash_session_token(authenticated.token)
    assert row.token_hash != authenticated.token
    assert authenticated.token not in row.token_hash
    assert row.user_id == authenticated.user.id
    assert row.user_agent == "pytest"
    assert row.ip_address == "127.0.0.1"


def test_a_wrong_password_is_rejected(auth_service: AuthService) -> None:
    """A wrong password never opens a session."""
    _register(auth_service)

    with pytest.raises(AuthenticationError):
        auth_service.authenticate(
            email="ada@example.com",
            password=WRONG_PASSWORD,
        )


def test_an_unknown_email_is_indistinguishable(
    auth_service: AuthService,
) -> None:
    """An unknown address produces the very same error and message."""
    _register(auth_service)

    with pytest.raises(AuthenticationError) as wrong_password:
        auth_service.authenticate(
            email="ada@example.com",
            password=WRONG_PASSWORD,
        )

    with pytest.raises(AuthenticationError) as unknown_email:
        auth_service.authenticate(
            email="nobody@example.com",
            password=PASSWORD,
        )

    assert str(wrong_password.value) == str(unknown_email.value)
    assert wrong_password.value.code == unknown_email.value.code
    assert wrong_password.value.http_status == 401
    assert "ada@example.com" not in str(unknown_email.value)


def test_the_last_login_is_written(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A successful login stamps the moment of the login."""
    _register(auth_service)

    auth_service.authenticate(email="ada@example.com", password=PASSWORD)

    row = _user_row(session_factory, "ada@example.com")
    assert row is not None
    assert row.last_login_at is not None


# ----------------------------------------------------------------------
# sessions
# ----------------------------------------------------------------------
def test_a_session_is_resolved_to_its_user(auth_service: AuthService) -> None:
    """The raw token is resolved back into the user."""
    _register(auth_service)
    authenticated = auth_service.authenticate(
        email="ada@example.com",
        password=PASSWORD,
    )

    summary = auth_service.resolve_session(authenticated.token)

    assert summary.id == authenticated.user.id
    assert summary.email == "ada@example.com"


def test_a_revoked_session_is_rejected(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A revoked token no longer opens the user."""
    _register(auth_service)
    authenticated = auth_service.authenticate(
        email="ada@example.com",
        password=PASSWORD,
    )

    auth_service.logout(authenticated.token)

    with pytest.raises(AuthenticationError):
        auth_service.resolve_session(authenticated.token)
    assert _session_rows(session_factory)[0].revoked_at is not None


def test_an_expired_session_is_rejected(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A token whose session expired is refused."""
    user_id = _register(auth_service)
    with session_factory() as session:
        AuthSessionRepository(session).create(
            user_id=user_id,
            token_hash=hash_session_token("expired-token"),
            expires_at=utcnow() - timedelta(minutes=1),
        )

    with pytest.raises(AuthenticationError):
        auth_service.resolve_session("expired-token")


def test_an_inactive_user_has_no_session(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A session of an account that was switched off is refused."""
    user_id = _register(auth_service)
    authenticated = auth_service.authenticate(
        email="ada@example.com",
        password=PASSWORD,
    )
    with session_factory() as session:
        UserRepository(session).set_active(user_id, is_active=False)

    with pytest.raises(AuthenticationError):
        auth_service.resolve_session(authenticated.token)


def test_an_inactive_user_cannot_sign_in(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A switched off account never opens a session."""
    user_id = _register(auth_service)
    with session_factory() as session:
        UserRepository(session).set_active(user_id, is_active=False)

    with pytest.raises(AuthenticationError):
        auth_service.authenticate(email="ada@example.com", password=PASSWORD)


def test_an_unknown_token_is_rejected(auth_service: AuthService) -> None:
    """A token that was never issued is refused."""
    with pytest.raises(AuthenticationError):
        auth_service.resolve_session("a-token-that-was-never-issued")


def test_the_logout_is_idempotent(auth_service: AuthService) -> None:
    """Logging out twice is not an error."""
    _register(auth_service)
    authenticated = auth_service.authenticate(
        email="ada@example.com",
        password=PASSWORD,
    )

    auth_service.logout(authenticated.token)
    auth_service.logout(authenticated.token)
    auth_service.logout("a-token-that-was-never-issued")


def test_every_session_of_a_user_can_be_revoked(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """The revocation of all sessions of a user touches every row."""
    user_id = _register(auth_service)
    first = auth_service.authenticate(email="ada@example.com", password=PASSWORD)
    second = auth_service.authenticate(email="ada@example.com", password=PASSWORD)
    assert len(_session_rows(session_factory)) == 2

    revoked = auth_service.revoke_all_sessions(user_id)

    assert revoked == 2
    for row in _session_rows(session_factory):
        assert row.revoked_at is not None
    with pytest.raises(AuthenticationError):
        auth_service.resolve_session(first.token)
    with pytest.raises(AuthenticationError):
        auth_service.resolve_session(second.token)


# ----------------------------------------------------------------------
# scenarios
# ----------------------------------------------------------------------
def test_the_three_scenarios_are_listed(auth_service: AuthService) -> None:
    """The scenarios carry the documented keys."""
    scenarios = auth_service.list_scenarios()

    assert [scenario.key for scenario in scenarios] == [
        "equity-analyst",
        "credit-analyst",
        "corporate-development",
    ]
    for scenario in scenarios:
        assert scenario.title
        assert scenario.tagline
        assert scenario.description
        assert scenario.focus_areas
        assert scenario.suggested_queries
        assert scenario.demo_email
        assert scenario.demo_password


def test_the_demo_credentials_can_be_switched_off(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    """Without the demo scenarios the credentials are not published."""
    service = AuthService(
        session_factory,
        settings=settings.model_copy(update={"auth_demo_scenarios_enabled": False}),
    )

    scenarios = service.list_scenarios()

    assert len(scenarios) == len(DEMO_SCENARIOS)
    for scenario in scenarios:
        assert scenario.demo_email is None
        assert scenario.demo_password is None


# ----------------------------------------------------------------------
# ownership
# ----------------------------------------------------------------------
def test_a_workspace_of_another_user_is_not_found(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A user neither reads nor changes nor deletes a foreign workspace."""
    owner_id = _register(auth_service, email="owner@example.com")
    stranger_id = _register(auth_service, email="stranger@example.com")
    service = WorkspaceService(session_factory)

    workspace = service.create_workspace(
        name="Owner workspace",
        owner_id=owner_id,
    )

    with pytest.raises(NotFoundError):
        service.get_workspace(workspace.id, owner_id=stranger_id)
    with pytest.raises(NotFoundError):
        service.update_workspace(
            workspace.id,
            owner_id=stranger_id,
            name="stolen",
        )
    with pytest.raises(NotFoundError):
        service.delete_workspace(workspace.id, owner_id=stranger_id)

    # The workspace still exists and still belongs to its owner.
    assert service.get_workspace(workspace.id, owner_id=owner_id).id == workspace.id


def test_a_member_reaches_the_workspace_of_another_user(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """A member may read the workspace of somebody else."""
    owner_id = _register(auth_service, email="owner@example.com")
    member_id = _register(auth_service, email="member@example.com")
    service = WorkspaceService(session_factory)

    workspace = service.create_workspace(name="Shared workspace", owner_id=owner_id)
    service.add_member(workspace.id, member_id)

    assert service.get_workspace(workspace.id, owner_id=member_id).id == workspace.id
    assert workspace.id in service.list_accessible_workspace_ids(member_id)


def test_the_workspaces_of_a_user_are_listed(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
) -> None:
    """The list only carries the workspaces the user may reach."""
    first_id = _register(auth_service, email="first@example.com")
    second_id = _register(auth_service, email="second@example.com")
    service = WorkspaceService(session_factory)

    own = service.create_workspace(name="Own workspace", owner_id=first_id)
    foreign = service.create_workspace(name="Foreign workspace", owner_id=second_id)
    service.add_member(foreign.id, first_id)

    summaries, total = service.list_workspaces(owner_id=first_id)

    assert total == 2
    assert {summary.id for summary in summaries} == {own.id, foreign.id}

    foreign_summaries, foreign_total = service.list_workspaces(owner_id=second_id)
    assert foreign_total == 1
    assert {summary.id for summary in foreign_summaries} == {foreign.id}


def test_a_document_of_an_inaccessible_workspace_is_not_visible(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
    settings: Settings,
    tmp_storage: LocalStorage,
) -> None:
    """A document of a foreign workspace cannot be read."""
    owner_id = _register(auth_service, email="owner@example.com")
    stranger_id = _register(auth_service, email="stranger@example.com")
    workspace_service = WorkspaceService(session_factory)
    document_service = DocumentService(
        session_factory,
        storage=tmp_storage,
        validator=FileValidator(settings),
    )

    workspace = workspace_service.create_workspace(
        name="Owner workspace",
        owner_id=owner_id,
    )
    with session_factory() as session:
        document = Document(
            workspace_id=workspace.id,
            original_filename="secret.pdf",
            storage_key="2025/01/secret.pdf",
            content_hash=uuid.uuid4().hex,
            file_size_bytes=1024,
            mime_type="application/pdf",
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = document.id

    with pytest.raises(NotFoundError):
        document_service.get_document(document_id, owner_id=stranger_id)
    with pytest.raises(NotFoundError):
        document_service.list_documents(
            workspace.id,
            limit=10,
            offset=0,
            owner_id=stranger_id,
        )
    with pytest.raises(NotFoundError):
        document_service.delete_document(document_id, owner_id=stranger_id)

    # The owner still sees the document.
    assert document_service.get_document(document_id, owner_id=owner_id).id == document_id


class _UnusedVectorStore:
    """A vector store that must never be reached by a scoped search."""

    def search(self, *args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("the vector store must not be reached")


class _UnusedEmbeddingService:
    """An embedding service that must never be reached by a scoped search."""

    def embed_texts(self, *args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("the embedding service must not be reached")


def test_a_search_in_an_inaccessible_workspace_is_not_found(
    auth_service: AuthService,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    """A scoped search verifies the scope before it searches."""
    owner_id = _register(auth_service, email="owner@example.com")
    stranger_id = _register(auth_service, email="stranger@example.com")
    workspace_service = WorkspaceService(session_factory)

    workspace = workspace_service.create_workspace(
        name="Owner workspace",
        owner_id=owner_id,
    )
    def can_access(workspace_id: UUID, user_id: UUID) -> bool:
        """Return whether *user_id* may reach the workspace *workspace_id*."""
        with session_factory() as session:
            return WorkspaceRepository(session).can_access_workspace(
                workspace_id, user_id
            )

    service = SearchService(
        vector_store=_UnusedVectorStore(),
        embedding_service=_UnusedEmbeddingService(),
        settings=settings,
        workspace_access=can_access,
    )

    with pytest.raises(NotFoundError):
        service.search(
            workspace_id=workspace.id,
            query="revenue",
            owner_id=stranger_id,
        )