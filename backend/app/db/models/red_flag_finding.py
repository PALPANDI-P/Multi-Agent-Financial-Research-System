"""Red flag finding ORM model.

Represents a risk or anomaly detected by the Red Flag agent while
analysing a financial document or a set of financial metrics.  A finding
captures the kind of risk, its severity, the evidence that supports it and
its resolution state.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DECIMAL, JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

__all__ = ["RedFlagFinding"]


class RedFlagFinding(TimestampMixin, Base):
    """A risk or anomaly detected during financial analysis."""

    __tablename__ = "red_flag_findings"
    __table_args__ = (
        Index("ix_red_flag_findings_workspace_id", "workspace_id"),
        Index("ix_red_flag_findings_document_id", "document_id"),
        Index("ix_red_flag_findings_severity", "severity"),
        Index("ix_red_flag_findings_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )

    financial_metric_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_metrics.id", ondelete="SET NULL"),
        nullable=True,
    )

    financial_calculation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )

    agent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    flag_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="medium",
        server_default="medium",
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    source_excerpt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence_score: Mapped[Decimal | None] = mapped_column(
        DECIMAL(precision=5, scale=2),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        server_default="open",
    )

    detected_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    detected_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    finding_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
