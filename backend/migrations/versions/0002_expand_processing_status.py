"""expand document processing states

Replaces the coarse ``processing`` value of ``documents.processing_status``
with the explicit per-stage states required by the specification::

    queued -> validating -> extracting -> chunking -> embedding -> indexing
    -> completed

plus ``failed``.

The column keeps its ``VARCHAR(32)`` type; only the set of allowed values
changes.  Existing rows that carry the old ``processing`` value are mapped
back to ``queued`` so that no row is lost and the new CHECK constraint can
be added without a validation error.

The allowed values are imported from :mod:`app.core.enums` so that the
migration and the ORM model can never drift apart.

Revision ID: 0002_expand_processing_status
Revises: 0001_initial
Create Date: 2026-10-21

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.enums import ProcessingStatus

# revision identifiers, used by Alembic.
revision: str = "0002_expand_processing_status"
down_revision: str | None = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None

#: Name of the CHECK constraint on ``documents.processing_status``.
CONSTRAINT_NAME = "ck_documents_processing_status"

#: Allowed values after this revision, taken from the authoritative enum.
PROCESSING_STATUS_VALUES: tuple[str, ...] = tuple(
    status.value for status in ProcessingStatus
)

#: The four values that were allowed before this revision.  They cannot be
#: derived from :class:`ProcessingStatus` because the old ``processing``
#: value was removed from the enum on purpose.
LEGACY_PROCESSING_STATUSES: tuple[str, ...] = (
    "queued",
    "processing",
    "completed",
    "failed",
)

#: Per-stage values that collapse back into the coarse ``processing`` value
#: when this revision is downgraded.
COLLAPSED_TO_PROCESSING: tuple[str, ...] = (
    ProcessingStatus.VALIDATING.value,
    ProcessingStatus.EXTRACTING.value,
    ProcessingStatus.CHUNKING.value,
    ProcessingStatus.EMBEDDING.value,
    ProcessingStatus.INDEXING.value,
)

#: Comment stored on ``documents.processing_stage`` (identical to the ORM
#: model).  The column is supplementary detail, not a second state machine.
PROCESSING_STAGE_COMMENT = (
    "Supplementary sub-stage detail (for example 'pdf_text', 'pdf_tables' "
    "or 'ocr'). NOT an independent status: the authoritative state is "
    "'processing_status'."
)


def _sql_literal(value: str) -> str:
    """Return *value* rendered as a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _sql_values(values: tuple[str, ...]) -> str:
    """Return *values* rendered as a SQL string literal list."""
    return ", ".join(_sql_literal(value) for value in values)


def _create_check_constraint(values: tuple[str, ...]) -> None:
    """Replace the CHECK constraint on ``documents.processing_status``."""
    op.execute(f"ALTER TABLE documents DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME};")
    op.execute(
        f"ALTER TABLE documents ADD CONSTRAINT {CONSTRAINT_NAME} "
        f"CHECK (processing_status IN ({_sql_values(values)}));"
    )


def _alter_column_type() -> None:
    """Guarantee that ``documents.processing_status`` stays ``VARCHAR(32)``."""
    op.alter_column(
        "documents",
        "processing_status",
        type_=sa.String(length=32),
        existing_type=sa.String(length=32),
        existing_nullable=False,
        existing_server_default=sa.text("'queued'"),
    )


def upgrade() -> None:
    """Upgrade schema."""
    # Legacy rows that used the coarse 'processing' value are moved back to
    # the start of the pipeline before the new constraint is applied.
    op.execute(
        "UPDATE documents SET processing_status = 'queued' "
        "WHERE processing_status = 'processing';"
    )

    _alter_column_type()
    _create_check_constraint(PROCESSING_STATUS_VALUES)

    op.execute(
        "COMMENT ON COLUMN documents.processing_stage IS "
        f"{_sql_literal(PROCESSING_STAGE_COMMENT)};"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Every per-stage value collapses back into the coarse 'processing'
    # value, because the old constraint does not know them.
    collapsed = _sql_values(COLLAPSED_TO_PROCESSING)
    op.execute(
        "UPDATE documents SET processing_status = 'processing' "
        f"WHERE processing_status IN ({collapsed});"
    )

    _alter_column_type()
    _create_check_constraint(LEGACY_PROCESSING_STATUSES)

    # The comment did not exist before this revision.
    op.execute("COMMENT ON COLUMN documents.processing_stage IS NULL;")
