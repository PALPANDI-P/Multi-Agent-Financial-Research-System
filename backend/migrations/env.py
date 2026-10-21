"""Alembic environment for the Multi-Agent Financial Research System.

The database URL is taken from the application settings so that migrations
always run against the same database the application uses.  The full ORM
metadata is imported so that ``alembic revision --autogenerate`` and
``alembic check`` see every table.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the `app` package importable regardless of the current directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.db import models  # noqa: F401  (registers every ORM model)
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# `%` is the ConfigParser interpolation character, escape it.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# The initial migration reads the embedding dimension from the environment so
# that the vector column always matches the configured model.
os.environ.setdefault("EMBEDDING_DIMENSION", str(settings.embedding_dimension))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI connection (emit SQL to stdout)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table="alembic_version",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table="alembic_version",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()