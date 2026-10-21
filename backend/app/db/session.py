"""Database engine, session factory and transaction helpers.

Importing this module never opens a connection: the engine is created lazily
on first use by the cached :func:`get_engine` factory.
"""

from __future__ import annotations

import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, NamedTuple

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

__all__ = [
    "DatabaseHealth",
    "SessionLocal",
    "check_database_connection",
    "create_engine_from_settings",
    "get_db",
    "get_engine",
    "session_scope",
]


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine from ``settings``.

    The engine is created with a pre-ping pool so that connections killed by
    the server are transparently recycled.
    """
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        echo=settings.database_echo,
        connect_args={"connect_timeout": 10},
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the lazily created, cached engine.

    The engine (and therefore a connection pool) is created on the first call
    only, so importing this module never touches the database.
    """
    return create_engine_from_settings(get_settings())


class LazySessionMaker(sessionmaker):
    """A :class:`sqlalchemy.orm.sessionmaker` that binds its engine lazily.

    ``SessionLocal()`` therefore works without the engine existing at import
    time, while an explicit ``bind`` still wins.
    """

    def __call__(self, **local_kw: Any) -> Session:
        """Create a new :class:`~sqlalchemy.orm.Session`."""
        if local_kw.get("bind") is None and self.kw.get("bind") is None:
            local_kw["bind"] = get_engine()
        return super().__call__(**local_kw)


#: Session factory used by the FastAPI dependency and by background code.
SessionLocal = LazySessionMaker(
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI compatible database session dependency.

    The session is committed when the request handler returns normally,
    rolled back when it raises and always closed.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session scope for non request code."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class DatabaseHealth(NamedTuple):
    """Result of a database connectivity probe."""

    ok: bool
    latency_ms: float


def check_database_connection() -> DatabaseHealth:
    """Probe the database and report reachability plus round trip latency."""
    started = time.perf_counter()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return DatabaseHealth(False, (time.perf_counter() - started) * 1000.0)
    return DatabaseHealth(True, (time.perf_counter() - started) * 1000.0)