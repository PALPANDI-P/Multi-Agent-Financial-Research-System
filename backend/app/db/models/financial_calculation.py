"""Financial calculation ORM model.

Represents a calculated financial metric based on one or more raw
financial metrics. For example, a "net profit margin" calculation
might use revenue and net income metrics. This model stores the
calculation logic, intermediate results and the final computed value.
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

__all__ = ["FinancialCalculation"]


class FinancialCalculation(TimestampMixin, Base):
    """A calculated financial metric based on raw metrics."""

    __tablename__ = "financial_calculations"
    __table_args__ = (
        CheckConstraint("result_value >= -999999999999.99 AND result_value <= 999999999999.99", name="ck_financial_calculations_value_range"),
        Index("ix_financial_calculations_calculation_type", "calculation_type"),
        Index("ix_financial_calculations_workspace_id", "workspace_id"),
        Index("ix_financial_calculations_parent_calculation", "parent_calculation_id"),
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

    calculation_type: Mapped[str] = mapped_column(
        nullable=False,
    )

    calculation_name: Mapped[str] = mapped_column(
        nullable=False,
    )

    formula: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    result_value: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=15, scale=2),
        nullable=False,
    )

    currency: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    unit: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    parent_calculation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_calculations.id", ondelete="CASCADE"),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    calculation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    input_metrics: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    execution_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    calculated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    confidence_score: Mapped[Decimal | None] = mapped_column(
        DECIMAL(precision=5, scale=2),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
