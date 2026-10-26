"""add authentication

Creates the three tables of the authentication of the Multi-Agent Financial
Research System:

* ``users``            - the accounts a person signs in with.
* ``auth_sessions``    - one row per signed-in session (the SHA-256 hash of
                         the token, never the token itself).
* ``workspace_members`` - the membership of a user in a workspace.

In addition the column ``workspaces.owner_id`` becomes a foreign key to
``users.id`` with ``ON DELETE SET NULL``: the column already existed and is
``NULL`` for every existing row, therefore **no row is touched** by this
revision.  The column stays nullable, because a workspace may exist
without an owner (the shared seed corpus for example).

Revision ID: 0003_add_authentication
Revises: 0002_expand_processing_status
Create Date: 2026-10-21

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_add_authentication"
down_revision: str | None = "0002_expand_processing_status"
branch_labels: str | None = None
depends_on: str | None = None

#: Name of the foreign key that links a workspace to its owner.
WORKSPACE_OWNER_FK = "fk_workspaces_owner_id_users"

#: Comment stored on ``workspaces.owner_id`` (identical to the ORM model).
OWNER_ID_COMMENT = (
    "The user that owns the workspace. The column stays NULL for a workspace "
    "without an owner (the shared seed corpus for example)."
)

#: The comment the column carried before this revision.
LEGACY_OWNER_ID_COMMENT = (
    "Reserved for a future multi-tenant owner. M1 implements no "
    "authentication and therefore no multi-user isolation: this column "
    "is always NULL."
)

#: The roles a user may have.
USER_ROLES: tuple[str, ...] = ("analyst", "researcher", "administrator")

#: The roles a member of a workspace may have.
WORKSPACE_MEMBER_ROLES: tuple[str, ...] = ("owner", "member", "viewer")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default=sa.text("'analyst'"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("scenario_key", sa.String(length=64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "role IN ('analyst', 'researcher', 'administrator')",
            name="ck_users_role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_scenario_key", "users", ["scenario_key"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_auth_sessions_user_id_expires_at",
        "auth_sessions",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default=sa.text("'member'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'member', 'viewer')",
            name="ck_workspace_members_role",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_workspace_members_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_members_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        # The composite primary key **is** the unique constraint of the
        # pair (workspace_id, user_id).  PostgreSQL does not create a
        # second, redundant unique index for a pair that is already
        # unique, therefore the pair is declared once - as the primary
        # key of the table.
        sa.PrimaryKeyConstraint(
            "workspace_id",
            "user_id",
            name="pk_workspace_members",
        ),
    )
    op.create_index(
        "ix_workspace_members_user_id", "workspace_members", ["user_id"], unique=False
    )

    # The column comments are part of the schema: Alembic compares them.
    op.execute(
        "COMMENT ON COLUMN users.email IS "
        "'Lowercased and stripped e-mail address.';"
    )
    op.execute(
        "COMMENT ON COLUMN users.password_hash IS "
        "'Argon2id hash of the password. The password itself is never stored.';"
    )
    op.execute(
        "COMMENT ON COLUMN users.scenario_key IS "
        "'Key of the demo scenario the account was created for.';"
    )
    op.execute(
        "COMMENT ON COLUMN auth_sessions.token_hash IS "
        "'SHA-256 hex digest of the session token. The token itself is never stored.';"
    )

    # The column already exists and is NULL for every row, therefore the
    # foreign key can be added without touching a single row.
    op.create_foreign_key(
        WORKSPACE_OWNER_FK,
        "workspaces",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "COMMENT ON COLUMN workspaces.owner_id IS "
        "'The user that owns the workspace. The column stays NULL for a "
        "workspace without an owner (the shared seed corpus for example).';"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The owners of the workspaces disappear with the table of the users.
    # The column is nullable, therefore the references are cleared before
    # the users are dropped - otherwise the foreign key could not be
    # created again by a later upgrade.
    op.execute("UPDATE workspaces SET owner_id = NULL WHERE owner_id IS NOT NULL")
    op.execute(
        "COMMENT ON COLUMN workspaces.owner_id IS "
        "'Reserved for a future multi-tenant owner. M1 implements no "
        "authentication and therefore no multi-user isolation: this column "
        "is always NULL.';"
    )
    op.drop_constraint(WORKSPACE_OWNER_FK, "workspaces", type_="foreignkey")

    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_table("workspace_members")

    op.drop_index("ix_auth_sessions_user_id_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_users_scenario_key", table_name="users")
    op.drop_table("users")