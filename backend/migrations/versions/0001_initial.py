"""initial schema

Creates the four core tables of the Multi-Agent Financial Research System:

* ``workspaces``      - top level container for documents.
* ``documents``       - uploaded files and their processing state.
* ``document_chunks`` - retrievable chunks plus their pgvector embeddings.
* ``processing_jobs`` - one row per ingestion attempt.

The embedding dimension is *not* hard coded in the schema: it is read from
the ``EMBEDDING_DIMENSION`` environment variable (default ``384``) which
``migrations/env.py`` populates from the application settings.  The value
must match ``app.db.models.chunk.EMBEDDING_DIMENSION``.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-21

"""

from __future__ import annotations

import os
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

#: Dimension of the pgvector column.  Must match the application settings.
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))

#: Comment stored on ``workspaces.owner_id`` (identical to the ORM model).
OWNER_ID_COMMENT = (
    "Reserved for a future multi-tenant owner. M1 implements no "
    "authentication and therefore no multi-user isolation: this column is "
    "always NULL."
)


class VectorType(sa.types.UserDefinedType):
    """Render the pgvector column type, for example ``vector(384)``.

    ``sa.text(f"vector({dim})")`` cannot be used directly as a column type
    because SQLAlchemy requires a ``TypeEngine`` instance; the raw type text
    is therefore produced from a text clause.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:
        """Return the DDL type specification for this column."""
        return str(sa.text(f"vector({self.dim})"))


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector is required for the `vector` column type.  The extension is
    # shared with other databases and is therefore never dropped in
    # `downgrade()`.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment=OWNER_ID_COMMENT,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_index("ix_workspaces_name", "workspaces", ["name"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("document_title", sa.String(length=512), nullable=True),
        sa.Column("document_type", sa.String(length=64), nullable=True),
        sa.Column("fiscal_period", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum(
                "queued",
                "processing",
                "completed",
                "failed",
                name="ck_documents_processing_status",
                native_enum=False,
                length=32,
                create_constraint=True,
            ),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("processing_stage", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_documents_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "workspace_id",
            "content_hash",
            name="uq_documents_workspace_content_hash",
        ),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )
    op.create_index(
        "ix_documents_workspace_id", "documents", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_documents_workspace_id_processing_status",
        "documents",
        ["workspace_id", "processing_status"],
        unique=False,
    )
    op.create_index(
        "ix_documents_content_hash", "documents", ["content_hash"], unique=False
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.String(length=512), nullable=True),
        sa.Column(
            "chunk_type",
            sa.Enum(
                "text",
                "table",
                name="ck_document_chunks_chunk_type",
                native_enum=False,
                length=32,
                create_constraint=True,
            ),
            server_default=sa.text("'text'"),
            nullable=False,
        ),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", VectorType(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("embedding_config_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_metadata_json",
        "document_chunks",
        ["metadata_json"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "completed",
                "failed",
                name="ck_processing_jobs_status",
                native_enum=False,
                length=32,
                create_constraint=True,
            ),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_processing_jobs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_jobs"),
    )
    op.create_index(
        "ix_processing_jobs_document_id",
        "processing_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_processing_jobs_document_id_attempt_count",
        "processing_jobs",
        ["document_id", "attempt_count"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_document_chunks_embedding_hnsw", table_name="document_chunks"
    )
    op.drop_table("processing_jobs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("workspaces")
    # The `vector` extension is shared with other databases and is therefore
    # intentionally NOT dropped here.