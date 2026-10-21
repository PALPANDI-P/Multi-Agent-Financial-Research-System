"""Fixtures of the HTTP API tests.

The tests run against the **real** application: the real services, the real
extraction pipeline, the real embedding model and a real PostgreSQL
database.  Only the configuration is different from a production run:

* the database is the test database (the ``clean_database`` fixture of the
  parent conftest empties it before and after every test),
* the storage root is a temporary directory,
* ``processing_inline`` is enabled, therefore an upload is processed
  completely before the request returns and the tests are deterministic.

The dependency cache of :mod:`app.api.deps` is cleared before and after
every test, so that no component (and no database connection) of a
previous test survives.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import clear_dependency_cache, get_settings_dep
from app.core.config import Settings
from app.main import create_app

try:  # PyMuPDF >= 1.24.3 exposes the canonical module name.
    import pymupdf
except ImportError:  # pragma: no cover - legacy alias of older PyMuPDF
    import fitz as pymupdf  # type: ignore[no-redef]

__all__ = [
    "TEST_DATABASE_URL",
    "api_settings",
    "app",
    "client",
    "pdf_bytes",
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
def client(app) -> Iterator[TestClient]:
    """Return a test client of the application under test."""
    clear_dependency_cache()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    clear_dependency_cache()


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