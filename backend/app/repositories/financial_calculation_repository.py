"""Persistence operations for the ``financial_calculations`` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.financial_calculation import FinancialCalculation

__all__ = ["FinancialCalculationRepository"]


class FinancialCalculationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, workspace_id, calculation_type, calculation_name, result_value,
               currency=None, unit=None, parent_calculation_id=None, description=None,
               formula=None, calculation_metadata=None, input_metrics=None, execution_context=None,
               calculated_at=None, confidence_score=None, error_message=None, commit=True) -> FinancialCalculation:
        row = FinancialCalculation(
            id=uuid4(),
            workspace_id=workspace_id,
            calculation_type=calculation_type,
            calculation_name=calculation_name,
            formula=formula,
            result_value=result_value,
            currency=currency,
            unit=unit,
            parent_calculation_id=parent_calculation_id,
            description=description,
            calculation_metadata=calculation_metadata,
            input_metrics=input_metrics,
            execution_context=execution_context,
            calculated_at=calculated_at or datetime.utcnow(),
            confidence_score=confidence_score,
            error_message=error_message,
        )
        # formula passed via kwargs? support
        if "formula" in (calculation_metadata or {}):
            pass
        self._session.add(row)
        if commit:
            self._session.commit()
            self._session.refresh(row)
        else:
            self._session.flush()
        return row

    def get(self, calculation_id: UUID) -> FinancialCalculation | None:
        return self._session.get(FinancialCalculation, calculation_id)

    def list_by_workspace(self, workspace_id: UUID, *, calculation_type=None, limit=100, offset=0) -> list[FinancialCalculation]:
        stmt = select(FinancialCalculation).where(FinancialCalculation.workspace_id == workspace_id)
        if calculation_type is not None:
            stmt = stmt.where(FinancialCalculation.calculation_type == calculation_type)
        stmt = stmt.offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def list_by_type(self, calculation_type: str, *, limit=100, offset=0) -> list[FinancialCalculation]:
        stmt = select(FinancialCalculation).where(FinancialCalculation.calculation_type == calculation_type).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def update(self, row: FinancialCalculation, **fields) -> FinancialCalculation:
        for k, v in fields.items():
            setattr(row, k, v)
        self._session.commit()
        self._session.refresh(row)
        return row

    def delete(self, row: FinancialCalculation, *, commit=True) -> None:
        self._session.delete(row)
        if commit:
            self._session.commit()
