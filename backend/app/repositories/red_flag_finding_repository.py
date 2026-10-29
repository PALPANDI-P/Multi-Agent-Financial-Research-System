"""Persistence operations for the ``red_flag_findings`` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.red_flag_finding import RedFlagFinding

__all__ = ["RedFlagFindingRepository"]


class RedFlagFindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        workspace_id,
        flag_type,
        severity="medium",
        title=None,
        description=None,
        evidence=None,
        source_excerpt=None,
        confidence_score=None,
        status="open",
        detected_by=None,
        detected_at=None,
        document_id=None,
        financial_metric_id=None,
        financial_calculation_id=None,
        agent_run_id=None,
        resolution_notes=None,
        finding_metadata=None,
        commit=True,
    ) -> RedFlagFinding:
        row = RedFlagFinding(
            id=uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            financial_metric_id=financial_metric_id,
            financial_calculation_id=financial_calculation_id,
            agent_run_id=agent_run_id,
            flag_type=flag_type,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence,
            source_excerpt=source_excerpt,
            confidence_score=confidence_score,
            status=status,
            detected_by=detected_by,
            detected_at=detected_at or datetime.utcnow(),
            resolution_notes=resolution_notes,
            finding_metadata=finding_metadata,
        )
        self._session.add(row)
        if commit:
            self._session.commit()
            self._session.refresh(row)
        else:
            self._session.flush()
        return row

    def get(self, finding_id: UUID) -> RedFlagFinding | None:
        return self._session.get(RedFlagFinding, finding_id)

    def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        severity=None,
        status=None,
        limit=100,
        offset=0,
    ) -> list[RedFlagFinding]:
        stmt = select(RedFlagFinding).where(RedFlagFinding.workspace_id == workspace_id)
        if severity is not None:
            stmt = stmt.where(RedFlagFinding.severity == severity)
        if status is not None:
            stmt = stmt.where(RedFlagFinding.status == status)
        stmt = stmt.offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def list_by_document(
        self,
        document_id: UUID,
        *,
        severity=None,
        status=None,
        limit=100,
        offset=0,
    ) -> list[RedFlagFinding]:
        stmt = select(RedFlagFinding).where(RedFlagFinding.document_id == document_id)
        if severity is not None:
            stmt = stmt.where(RedFlagFinding.severity == severity)
        if status is not None:
            stmt = stmt.where(RedFlagFinding.status == status)
        stmt = stmt.offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def delete(self, row: RedFlagFinding, *, commit=True) -> None:
        self._session.delete(row)
        if commit:
            self._session.commit()

    def update(self, row: RedFlagFinding, **fields) -> RedFlagFinding:
        for key, value in fields.items():
            setattr(row, key, value)
        self._session.commit()
        self._session.refresh(row)
        return row