"""Persistence operations for the ``financial_metrics`` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.financial_metric import FinancialMetric

__all__ = ["FinancialMetricRepository"]


class FinancialMetricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, workspace_id, document_id, metric_type, metric_name, metric_value,
               currency=None, unit=None, red_flag_level=None, calculation_id=None,
               context=None, source_document_chunk=None, extracted_at=None,
               is_estimated=False, is_projected=False, notes=None, commit=True) -> FinancialMetric:
        row = FinancialMetric(
            id=uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            metric_type=metric_type,
            metric_name=metric_name,
            metric_value=metric_value,
            currency=currency,
            unit=unit,
            red_flag_level=red_flag_level,
            calculation_id=calculation_id,
            context=context,
            source_document_chunk=source_document_chunk,
            extracted_at=extracted_at or datetime.utcnow(),
            is_estimated=is_estimated,
            is_projected=is_projected,
            notes=notes,
        )
        self._session.add(row)
        if commit:
            self._session.commit()
            self._session.refresh(row)
        else:
            self._session.flush()
        return row

    def get(self, metric_id: UUID) -> FinancialMetric | None:
        return self._session.get(FinancialMetric, metric_id)

    def list_by_workspace(self, workspace_id: UUID, *, limit=100, offset=0) -> list[FinancialMetric]:
        stmt = select(FinancialMetric).where(FinancialMetric.workspace_id == workspace_id).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def list_by_document(self, document_id: UUID, *, limit=100, offset=0) -> list[FinancialMetric]:
        stmt = select(FinancialMetric).where(FinancialMetric.document_id == document_id).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def delete_by_document(self, document_id: UUID, *, commit=True) -> None:
        rows = self.list_by_document(document_id, limit=100000, offset=0)
        for r in rows:
            self._session.delete(r)
        if commit:
            self._session.commit()

    def update(self, row: FinancialMetric, **fields) -> FinancialMetric:
        for k, v in fields.items():
            setattr(row, k, v)
        self._session.commit()
        self._session.refresh(row)
        return row
