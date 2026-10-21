"""Shared fixtures of the test suite.

The integration tests run against a **real** PostgreSQL server with the
pgvector extension.  The database is taken from the ``TEST_DATABASE_URL``
environment variable and falls back to the local development test database.

Isolation
---------
The ``clean_database`` fixture empties the test tables before and after
every integration test, therefore the tests neither see the residue of a
previous test nor leave anything behind.  The fixture is only active for
tests that carry the ``integration`` marker; the unit tests never touch a
database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.storage import LocalStorage

__all__ = [
    "TEST_DATABASE_URL",
    "TRUNCATE_TABLES",
    "clean_database",
    "db_session",
    "engine",
    "session_factory",
    "settings",
    "tmp_storage",
]

#: The database used by the integration tests.
TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL") or (
    "postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test"
)

#: Tables that are emptied before and after every integration test.
TRUNCATE_TABLES: tuple[str, ...] = (
    "document_chunks",
    "processing_jobs",
    "documents",
    "workspaces",
)


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers of the project."""
    config.addinivalue_line(
        "markers",
        "integration: requires a live TEST_DATABASE_URL database",
    )


def _truncate(engine: Engine) -> None:
    """Remove every row of the test tables."""
    statement = text(
        "TRUNCATE TABLE " + ", ".join(TRUNCATE_TABLES) + " RESTART IDENTITY CASCADE"
    )
    with engine.begin() as connection:
        connection.execute(statement)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Return an engine bound to the test database."""
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Return a session bound to the test engine."""
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to the test engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return the settings of the test run."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        app_env="test",
        storage_root=tmp_path / "storage",
    )


@pytest.fixture
def tmp_storage(tmp_path: Path) -> LocalStorage:
    """Return a local storage backend below *tmp_path*."""
    return LocalStorage(tmp_path / "storage")


@pytest.fixture(autouse=True)
def clean_database(request: pytest.FixtureRequest) -> Iterator[None]:
    """Empty the test database around every integration test.

    The fixture is inert for the tests that are not marked with
    ``integration``; those never reach the database.
    """
    if request.node.get_closest_marker("integration") is None:
        yield
        return

    test_engine: Engine = request.getfixturevalue("engine")
    _truncate(test_engine)
    try:
        yield
    finally:
        _truncate(test_engine)