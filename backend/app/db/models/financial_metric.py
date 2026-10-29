"""Financial metric ORM model.

Represents a single financial metric extracted from a document,
for example revenue, net income, earnings per share, etc.
It stores the metric value, its context within the document and
any additional information needed for calculations and analysis.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DECIMAL, JSON, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

__all__ = ["FinancialMetric"]


class FinancialMetric(TimestampMixin, Base):
    """A single financial metric extracted from a document."""

    __tablename__ = "financial_metrics"
    __table_args__ = (
        CheckConstraint("metric_value >= -999999999999.99 AND metric_value <= 999999999999.99", name="ck_financial_metrics_value_range"),
        Index("ix_financial_metrics_metric_type", "metric_type"),
        Index("ix_financial_metrics_document_id", "document_id"),
        Index("ix_financial_metrics_workspace_id", "workspace_id"),
        Index("ix_financial_metrics_red_flag", "workspace_id", "red_flag_level"),
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

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    metric_type: Mapped[str] = mapped_column(
        nullable=False,
    )

    metric_name: Mapped[str] = mapped_column(
        nullable=False,
    )

    metric_value: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=15, scale=2),
        nullable=False,
    )

    currency: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    unit: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    red_flag_level: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    calculation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )

    context: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    source_document_chunk: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    is_estimated: Mapped[bool] = mapped_column(
        server_default="false",
        nullable=False,
    )

    is_projected: Mapped[bool] = mapped_column(
        server_default="false",
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
