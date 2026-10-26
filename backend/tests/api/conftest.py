"""Fixtures of the HTTP API tests.

The tests run against the **real** application: the real services, the real
extraction pipeline, the real embedding model and a real PostgreSQL
database.  Only the configuration is different from a production run:

* the database is the test database (the ``clean_database`` fixture of the
  parent conftest empties it before and after every test),
* the storage root is a temporary directory,
* ``processing_inline`` is enabled, therefore an upload is processed
  completely before the request returns and the tests are deterministic.

The API is **protected**: every route except the health check, the login,
the registration and the list of the demo scenarios requires a session.
The ``client`` fixture therefore signs a test account in through the real
``POST /api/v1/auth/login`` endpoint and keeps the session cookie in the
cookie jar of the test client, exactly like a browser would do.  The
``anonymous_client`` fixture is the counterpart: a client **without** a
session, used by the tests that check the ``401`` answers.

The dependency cache of :mod:`app.api.deps` is cleared before and after
every test, so that no component (and no database connection) of a
previous test survives.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import clear_dependency_cache, get_settings_dep
from app.core.config import Settings
from app.db.session import create_engine_from_settings
from app.main import create_app
from app.services.auth_service import AuthService

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz as pymupdf  # type: ignore[no-redef]

__all__ = [
    "TEST_DATABASE_URL",
    "anonymous_client",
    "api_settings",
    "app",
    "client",
    "pdf_bytes",
    "test_user",
]

#: The database the API tests run against.
TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL") or (
    "postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test"
)

#: The heading of the first page of the test document.
HEADING_ONE = "Acme Corporation Annual Report"

#: The body of the first page of the test document.
BODY_ONE = (
    "Acme Corporation Annual Report for the fiscal year 2025. Total revenue was "
    "1.2 billion US dollars, an increase of 8 percent compared with the previous "
    "year. The board of directors approved a dividend of 0.42 US dollars per "
    "share for the reporting period."
)

#: The heading of the second page of the test document.
HEADING_TWO = "Management Discussion and Analysis"

#: The body of the second page of the test document.
BODY_TWO = (
    "Management discussion and analysis of the financial year 2025. Operating "
    "expenses grew by 3 percent while the operating margin improved to 18 "
    "percent. The industrial segment reported a revenue of 640 million US "
    "dollars and a profit of 95 million US dollars."
)

#: The e-mail address of the account the API tests sign in with.
TEST_USER_EMAIL = "api-test@frs.local"

#: The password of the account the API tests sign in with.
TEST_USER_PASSWORD = "ApiTestPassword123!"

#: The display name of the account the API tests sign in with.
TEST_USER_FULL_NAME = "API Test User"


@pytest.fixture
def api_settings(tmp_path: Path) -> Settings:
    """Return the settings of the API test run."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        app_env="test",
        storage_root=tmp_path / "storage",
        processing_inline=True,
    )


@pytest.fixture
def app(api_settings: Settings):
    """Return the application under test."""
    application = create_app(api_settings)
    application.dependency_overrides[get_settings_dep] = lambda: api_settings
    return application


@pytest.fixture
def api_session_factory(api_settings: Settings) -> sessionmaker[Session]:
    """Return a session factory bound to the test database."""
    engine = create_engine_from_settings(api_settings)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def pdf_bytes() -> bytes:
    """Return the bytes of a valid two page PDF with a text layer."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 80), HEADING_ONE, fontsize=16)
        page.insert_text((72, 120), BODY_ONE, fontsize=11)
        page = document.new_page()
        page.insert_text((72, 80), HEADING_TWO, fontsize=16)
        page.insert_text((72, 120), BODY_TWO, fontsize=11)
        return document.tobytes()
    finally:
        document.close()


def _sign_in(
    client: TestClient,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> UUID:
    """Create the test account, sign it in and return its id."""
    service = AuthService(session_factory, settings=settings)
    summary = service.register(
        email=TEST_USER_EMAIL,
        full_name=TEST_USER_FULL_NAME,
        password=TEST_USER_PASSWORD,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == str(summary.id)
    return summary.id


@pytest.fixture
def test_user(
    api_session_factory: sessionmaker[Session],
    api_settings: Settings,
) -> UUID:
    """Return the id of the account the API tests sign in with."""
    service = AuthService(api_session_factory, settings=api_settings)
    return service.register(
        email=TEST_USER_EMAIL,
        full_name=TEST_USER_FULL_NAME,
        password=TEST_USER_PASSWORD,
    ).id


@pytest.fixture
def client(
    app,
    api_session_factory: sessionmaker[Session],
    api_settings: Settings,
) -> Iterator[TestClient]:
    """Return a test client of the application under test that is **signed in**."""
    clear_dependency_cache()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        _sign_in(test_client, api_session_factory, api_settings)
        yield test_client
    clear_dependency_cache()


@pytest.fixture
def anonymous_client(app) -> Iterator[TestClient]:
    """Return a test client of the application under test **without** a session."""
    clear_dependency_cache()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    clear_dependency_cache()