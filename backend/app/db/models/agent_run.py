"""Agent run ORM model.

Tracks a single execution of an agent (for example the Red Flag, the
Comparison or the Research agent).  It stores the inputs, the outputs, the
timing and the outcome of the run so that agent activity can be audited
and retried.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

__all__ = ["AgentRun"]


class AgentRun(TimestampMixin, Base):
    """A single execution of an agent."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_workspace_id", "workspace_id"),
        Index("ix_agent_runs_document_id", "document_id"),
        Index("ix_agent_runs_agent_name", "agent_name"),
        Index("ix_agent_runs_status", "status"),
        Index("ix_agent_runs_parent_run_id", "parent_run_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    workspace_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )

    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    parent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    agent_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    agent_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
    )

    task_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    input_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    output_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
