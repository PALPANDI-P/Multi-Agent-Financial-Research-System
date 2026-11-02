
"""Financial data, research, comparison and report endpoints."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.comparison_agent import ComparisonAgent
from app.agents.red_flag_agent import RedFlagAgent
from app.agents.report_agent import ReportAgent
from app.agents.research_agent import ResearchAgent
from app.api.deps import (
    CurrentUserDep,
    SettingsDep,
    get_search_service,
    get_session_factory,
    get_workspace_service,
    owner_scope,
)
from app.core.exceptions import NotFoundError
from app.repositories.financial_calculation_repository import FinancialCalculationRepository
from app.repositories.financial_metric_repository import FinancialMetricRepository
from app.repositories.red_flag_finding_repository import RedFlagFindingRepository
from app.services.export_service import ExportService
from app.services.forecasting_service import ForecastingService
from app.services.workspace_service import WorkspaceService

__all__ = ["router"]

router = APIRouter(tags=["financial"])


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", from_attributes=True)


class FinancialMetricCreate(_Base):
    workspace_id: UUID | None = None
    document_id: UUID | None = None
    metric_type: str
    metric_name: str
    metric_value: Decimal | float | int | str
    currency: str | None = None
    unit: str | None = None
    red_flag_level: str | None = None
    calculation_id: UUID | None = None
    context: dict[str, Any] | None = None
    source_document_chunk: str | None = None
    extracted_at: datetime | None = None
    is_estimated: bool = False
    is_projected: bool = False
    notes: str | None = None


class FinancialMetricUpdate(_Base):
    metric_type: str | None = None
    metric_name: str | None = None
    metric_value: Decimal | float | int | str | None = None
    currency: str | None = None
    unit: str | None = None
    red_flag_level: str | None = None
    calculation_id: UUID | None = None
    context: dict[str, Any] | None = None
    source_document_chunk: str | None = None
    is_estimated: bool | None = None
    is_projected: bool | None = None
    notes: str | None = None


class FinancialMetricRead(_Base):
    id: UUID
    workspace_id: UUID
    document_id: UUID
    metric_type: str
    metric_name: str
    metric_value: Any
    currency: str | None = None
    unit: str | None = None
    red_flag_level: str | None = None
    calculation_id: UUID | None = None
    context: dict[str, Any] | None = None
    source_document_chunk: str | None = None
    extracted_at: Any = None
    is_estimated: bool = False
    is_projected: bool = False
    notes: str | None = None
    created_at: Any = None
    updated_at: Any = None


class ListEnvelope(_Base):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class FinancialCalculationCreate(_Base):
    workspace_id: UUID | None = None
    calculation_type: str
    calculation_name: str
    formula: str | None = None
    result_value: Decimal | float | int | str
    currency: str | None = None
    unit: str | None = None
    parent_calculation_id: UUID | None = None
    description: str | None = None
    calculation_metadata: dict[str, Any] | None = None
    input_metrics: list[dict[str, Any]] | None = None
    execution_context: dict[str, Any] | None = None
    calculated_at: datetime | None = None
    confidence_score: Decimal | float | int | str | None = None
    error_message: str | None = None


class FinancialCalculationUpdate(_Base):
    calculation_type: str | None = None
    calculation_name: str | None = None
    formula: str | None = None
    result_value: Decimal | float | int | str | None = None
    currency: str | None = None
    unit: str | None = None
    parent_calculation_id: UUID | None = None
    description: str | None = None
    calculation_metadata: dict[str, Any] | None = None
    input_metrics: list[dict[str, Any]] | None = None
    execution_context: dict[str, Any] | None = None
    confidence_score: Decimal | float | int | str | None = None
    error_message: str | None = None


class FinancialCalculationRead(_Base):
    id: UUID
    workspace_id: UUID
    calculation_type: str
    calculation_name: str
    formula: str | None = None
    result_value: Any
    currency: str | None = None
    unit: str | None = None
    parent_calculation_id: UUID | None = None
    description: str | None = None
    calculation_metadata: dict[str, Any] | None = None
    input_metrics: list[dict[str, Any]] | None = None
    execution_context: dict[str, Any] | None = None
    calculated_at: Any = None
    confidence_score: Any = None
    error_message: str | None = None
    created_at: Any = None
    updated_at: Any = None


class RedFlagFindingCreate(_Base):
    workspace_id: UUID | None = None
    document_id: UUID | None = None
    financial_metric_id: UUID | None = None
    financial_calculation_id: UUID | None = None
    agent_run_id: UUID | None = None
    flag_type: str
    severity: str = "medium"
    title: str | None = None
    description: str | None = None
    evidence: dict[str, Any] | None = None
    source_excerpt: str | None = None
    confidence_score: Decimal | float | int | str | None = None
    status: str = "open"
    detected_by: str | None = None
    resolution_notes: str | None = None
    finding_metadata: dict[str, Any] | None = None


class RedFlagFindingUpdate(_Base):
    severity: str | None = None
    title: str | None = None
    description: str | None = None
    evidence: dict[str, Any] | None = None
    source_excerpt: str | None = None
    confidence_score: Decimal | float | int | str | None = None
    status: str | None = None
    resolution_notes: str | None = None
    finding_metadata: dict[str, Any] | None = None


class RedFlagFindingRead(_Base):
    id: UUID
    workspace_id: UUID
    document_id: UUID | None = None
    financial_metric_id: UUID | None = None
    financial_calculation_id: UUID | None = None
    agent_run_id: UUID | None = None
    flag_type: str
    severity: str
    title: str | None = None
    description: str | None = None
    evidence: dict[str, Any] | None = None
    source_excerpt: str | None = None
    confidence_score: Any = None
    status: str
    detected_by: str | None = None
    detected_at: Any = None
    resolved_at: Any = None
    resolution_notes: str | None = None
    finding_metadata: dict[str, Any] | None = None
    created_at: Any = None
    updated_at: Any = None
def _metric_to_read(row):
    return FinancialMetricRead.model_validate(row)


def _calc_to_read(row):
    return FinancialCalculationRead.model_validate(row)


def _finding_to_read(row):
    return RedFlagFindingRead.model_validate(row)


def _verify_workspace(workspace_id, workspace_service, current_user):
    try:
        workspace_service.get_workspace(workspace_id, owner_id=owner_scope(current_user))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found") from None


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _result_dict(result):
    if hasattr(result, "as_dict") and callable(result.as_dict):
        try:
            return result.as_dict()
        except Exception:
            pass
    if hasattr(result, "to_dict") and callable(result.to_dict):
        try:
            return result.to_dict()
        except Exception:
            pass
    try:
        from dataclasses import asdict as _asdict

        return _asdict(result)
    except Exception:
        return {"result": result}


@router.get("/workspaces/{workspace_id}/financial-metrics", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/financial_metrics", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/metrics", response_model=ListEnvelope)
def list_financial_metrics(
    workspace_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    metric_type: str | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    red_flag_level: str | None = Query(default=None),
) -> ListEnvelope:
    _verify_workspace(workspace_id, workspace_service, current_user)
    with session_factory() as session:
        repo = FinancialMetricRepository(session)
        if document_id is not None:
            rows = repo.list_by_document(document_id, limit=limit, offset=offset)
        else:
            rows = repo.list_by_workspace(workspace_id, limit=limit, offset=offset)
    if metric_type is not None:
        rows = [r for r in rows if r.metric_type == metric_type]
    if red_flag_level is not None:
        rows = [r for r in rows if r.red_flag_level == red_flag_level]
    items = [_metric_to_read(r).model_dump() for r in rows]
    return ListEnvelope(items=items, total=len(items), limit=limit, offset=offset)


@router.post("/workspaces/{workspace_id}/financial-metrics", response_model=FinancialMetricRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/financial_metrics", response_model=FinancialMetricRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/metrics", response_model=FinancialMetricRead, status_code=status.HTTP_201_CREATED)
def create_financial_metric(
    workspace_id: UUID,
    payload: FinancialMetricCreate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
) -> FinancialMetricRead:
    _verify_workspace(workspace_id, workspace_service, current_user)
    document_id = payload.document_id
    if document_id is None:
        raise HTTPException(status_code=422, detail="document_id required")
    with session_factory() as session:
        repo = FinancialMetricRepository(session)
        row = repo.create(
            workspace_id=workspace_id,
            document_id=document_id,
            metric_type=payload.metric_type,
            metric_name=payload.metric_name,
            metric_value=_to_decimal(payload.metric_value),
            currency=payload.currency,
            unit=payload.unit,
            red_flag_level=payload.red_flag_level,
            calculation_id=payload.calculation_id,
            context=payload.context,
            source_document_chunk=payload.source_document_chunk,
            extracted_at=payload.extracted_at,
            is_estimated=payload.is_estimated,
            is_projected=payload.is_projected,
            notes=payload.notes,
        )
        return _metric_to_read(row)


@router.get("/financial-metrics/{metric_id}", response_model=FinancialMetricRead)
@router.get("/metrics/{metric_id}", response_model=FinancialMetricRead)
def get_financial_metric(
    metric_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> FinancialMetricRead:
    with session_factory() as session:
        row = FinancialMetricRepository(session).get(metric_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found") from None
    return _metric_to_read(row)


@router.patch("/financial-metrics/{metric_id}", response_model=FinancialMetricRead)
@router.patch("/metrics/{metric_id}", response_model=FinancialMetricRead)
def update_financial_metric(
    metric_id: UUID,
    payload: FinancialMetricUpdate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> FinancialMetricRead:
    with session_factory() as session:
        repo = FinancialMetricRepository(session)
        row = repo.get(metric_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        fields = payload.model_dump(exclude_unset=True)
        if "metric_value" in fields and fields["metric_value"] is not None:
            fields["metric_value"] = _to_decimal(fields["metric_value"])
        row = repo.update(row, **fields)
        return _metric_to_read(row)


@router.delete("/financial-metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_financial_metric(
    metric_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> Response:
    with session_factory() as session:
        repo = FinancialMetricRepository(session)
        row = repo.get(metric_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        session.delete(row)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
@router.get("/workspaces/{workspace_id}/financial-calculations", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/financial_calculations", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/calculations", response_model=ListEnvelope)
def list_financial_calculations(
    workspace_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    calculation_type: str | None = Query(default=None),
) -> ListEnvelope:
    _verify_workspace(workspace_id, workspace_service, current_user)
    with session_factory() as session:
        rows = FinancialCalculationRepository(session).list_by_workspace(
            workspace_id, calculation_type=calculation_type, limit=limit, offset=offset
        )
    items = [_calc_to_read(r).model_dump() for r in rows]
    return ListEnvelope(items=items, total=len(items), limit=limit, offset=offset)


@router.post("/workspaces/{workspace_id}/financial-calculations", response_model=FinancialCalculationRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/financial_calculations", response_model=FinancialCalculationRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/calculations", response_model=FinancialCalculationRead, status_code=status.HTTP_201_CREATED)
def create_financial_calculation(
    workspace_id: UUID,
    payload: FinancialCalculationCreate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
) -> FinancialCalculationRead:
    _verify_workspace(workspace_id, workspace_service, current_user)
    with session_factory() as session:
        row = FinancialCalculationRepository(session).create(
            workspace_id=workspace_id,
            calculation_type=payload.calculation_type,
            calculation_name=payload.calculation_name,
            formula=payload.formula,
            result_value=_to_decimal(payload.result_value),
            currency=payload.currency,
            unit=payload.unit,
            parent_calculation_id=payload.parent_calculation_id,
            description=payload.description,
            calculation_metadata=payload.calculation_metadata,
            input_metrics=payload.input_metrics,
            execution_context=payload.execution_context,
            calculated_at=payload.calculated_at,
            confidence_score=_to_decimal(payload.confidence_score) if payload.confidence_score is not None else None,
            error_message=payload.error_message,
        )
        return _calc_to_read(row)


@router.get("/financial-calculations/{calculation_id}", response_model=FinancialCalculationRead)
@router.get("/calculations/{calculation_id}", response_model=FinancialCalculationRead)
def get_financial_calculation(
    calculation_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> FinancialCalculationRead:
    with session_factory() as session:
        row = FinancialCalculationRepository(session).get(calculation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found") from None
    return _calc_to_read(row)


@router.patch("/financial-calculations/{calculation_id}", response_model=FinancialCalculationRead)
@router.patch("/calculations/{calculation_id}", response_model=FinancialCalculationRead)
def update_financial_calculation(
    calculation_id: UUID,
    payload: FinancialCalculationUpdate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> FinancialCalculationRead:
    with session_factory() as session:
        repo = FinancialCalculationRepository(session)
        row = repo.get(calculation_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        fields = payload.model_dump(exclude_unset=True)
        if "result_value" in fields and fields["result_value"] is not None:
            fields["result_value"] = _to_decimal(fields["result_value"])
        if "confidence_score" in fields and fields["confidence_score"] is not None:
            fields["confidence_score"] = _to_decimal(fields["confidence_score"])
        row = repo.update(row, **fields)
        return _calc_to_read(row)


@router.delete("/financial-calculations/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/calculations/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_financial_calculation(
    calculation_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> Response:
    with session_factory() as session:
        repo = FinancialCalculationRepository(session)
        row = repo.get(calculation_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        repo.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
@router.get("/workspaces/{workspace_id}/red-flags", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/red_flags", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/red-flag-findings", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/red_flag_findings", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/findings", response_model=ListEnvelope)
def list_red_flag_findings(
    workspace_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
) -> ListEnvelope:
    _verify_workspace(workspace_id, workspace_service, current_user)
    with session_factory() as session:
        repo = RedFlagFindingRepository(session)
        if document_id is not None:
            rows = repo.list_by_document(document_id, severity=severity, status=status, limit=limit, offset=offset)
        else:
            rows = repo.list_by_workspace(workspace_id, severity=severity, status=status, limit=limit, offset=offset)
    items = [_finding_to_read(r).model_dump() for r in rows]
    return ListEnvelope(items=items, total=len(items), limit=limit, offset=offset)


@router.post("/workspaces/{workspace_id}/red-flags", response_model=RedFlagFindingRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/red_flags", response_model=RedFlagFindingRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/red-flag-findings", response_model=RedFlagFindingRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/red_flag_findings", response_model=RedFlagFindingRead, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/findings", response_model=RedFlagFindingRead, status_code=status.HTTP_201_CREATED)
def create_red_flag_finding(
    workspace_id: UUID,
    payload: RedFlagFindingCreate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
) -> RedFlagFindingRead:
    _verify_workspace(workspace_id, workspace_service, current_user)
    with session_factory() as session:
        row = RedFlagFindingRepository(session).create(
            workspace_id=workspace_id,
            document_id=payload.document_id,
            financial_metric_id=payload.financial_metric_id,
            financial_calculation_id=payload.financial_calculation_id,
            agent_run_id=payload.agent_run_id,
            flag_type=payload.flag_type,
            severity=payload.severity,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            source_excerpt=payload.source_excerpt,
            confidence_score=_to_decimal(payload.confidence_score) if payload.confidence_score is not None else None,
            status=payload.status,
            detected_by=payload.detected_by,
            resolution_notes=payload.resolution_notes,
            finding_metadata=payload.finding_metadata,
        )
        return _finding_to_read(row)


@router.get("/red-flags/{finding_id}", response_model=RedFlagFindingRead)
@router.get("/red_flags/{finding_id}", response_model=RedFlagFindingRead)
@router.get("/red-flag-findings/{finding_id}", response_model=RedFlagFindingRead)
@router.get("/red_flag_findings/{finding_id}", response_model=RedFlagFindingRead)
@router.get("/findings/{finding_id}", response_model=RedFlagFindingRead)
def get_red_flag_finding(
    finding_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> RedFlagFindingRead:
    with session_factory() as session:
        row = RedFlagFindingRepository(session).get(finding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found") from None
    return _finding_to_read(row)


@router.patch("/red-flags/{finding_id}", response_model=RedFlagFindingRead)
@router.patch("/red_flags/{finding_id}", response_model=RedFlagFindingRead)
@router.patch("/red-flag-findings/{finding_id}", response_model=RedFlagFindingRead)
@router.patch("/red_flag_findings/{finding_id}", response_model=RedFlagFindingRead)
@router.patch("/findings/{finding_id}", response_model=RedFlagFindingRead)
def update_red_flag_finding(
    finding_id: UUID,
    payload: RedFlagFindingUpdate,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> RedFlagFindingRead:
    with session_factory() as session:
        repo = RedFlagFindingRepository(session)
        row = repo.get(finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        fields = payload.model_dump(exclude_unset=True)
        if "confidence_score" in fields and fields["confidence_score"] is not None:
            fields["confidence_score"] = _to_decimal(fields["confidence_score"])
        if "status" in fields and fields["status"] == "resolved":
            fields["resolved_at"] = datetime.utcnow()
        row = repo.update(row, **fields)
        return _finding_to_read(row)


@router.delete("/red-flags/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/red_flags/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/red-flag-findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/red_flag_findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.delete("/findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_red_flag_finding(
    finding_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    current_user: CurrentUserDep,
) -> Response:
    with session_factory() as session:
        repo = RedFlagFindingRepository(session)
        row = repo.get(finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found") from None
        repo.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/workspaces/{workspace_id}/red-flags/analyze", response_model=dict)
@router.post("/workspaces/{workspace_id}/red_flags/analyze", response_model=dict)
@router.post("/workspaces/{workspace_id}/red-flag-analysis", response_model=dict)
@router.post("/workspaces/{workspace_id}/analyze-red-flags", response_model=dict)
def analyze_red_flags_endpoint(
    workspace_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    settings: SettingsDep,
    current_user: CurrentUserDep,
    document_id: UUID | None = Query(default=None),
) -> dict:
    _verify_workspace(workspace_id, workspace_service, current_user)
    agent = RedFlagAgent(session_factory=session_factory, settings=settings)
    result = agent.analyze_and_store(workspace_id=workspace_id, document_id=document_id)
    return _result_dict(result)
class ResearchRequest(_Base):
    question: str | None = None
    query: str | None = None
    text: str | None = None
    prompt: str | None = None
    document_id: UUID | None = None
    document_ids: list[UUID] | None = None
    top_k: int | None = None
    limit: int | None = None


@router.post("/workspaces/{workspace_id}/research", response_model=dict)
@router.post("/workspaces/{workspace_id}/research-agent", response_model=dict)
@router.post("/workspaces/{workspace_id}/research_agent", response_model=dict)
@router.post("/workspaces/{workspace_id}/ask", response_model=dict)
def run_research(
    workspace_id: UUID,
    payload: ResearchRequest,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    search_service: Annotated[Any, Depends(get_search_service)],
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> dict:
    _verify_workspace(workspace_id, workspace_service, current_user)
    question = payload.question or payload.query or payload.text or payload.prompt or ""
    agent = ResearchAgent(
        session_factory=session_factory,
        search_service=search_service,
        settings=settings,
    )
    result = agent.research(
        question=question,
        workspace_id=workspace_id,
        document_id=payload.document_id,
        top_k=payload.top_k or payload.limit,
    )
    return _result_dict(result)


class ComparisonRequest(_Base):
    question: str | None = None
    query: str | None = None
    company_a: str | None = None
    company_b: str | None = None
    document_ids: list[UUID] | None = None
    metric_names: list[str] | None = None
    top_k: int | None = None
    limit: int | None = None


@router.post("/workspaces/{workspace_id}/compare", response_model=dict)
@router.post("/workspaces/{workspace_id}/comparison", response_model=dict)
@router.post("/workspaces/{workspace_id}/comparison-agent", response_model=dict)
@router.post("/workspaces/{workspace_id}/comparison_agent", response_model=dict)
@router.post("/workspaces/{workspace_id}/compare-companies", response_model=dict)
def run_comparison(
    workspace_id: UUID,
    payload: ComparisonRequest,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    search_service: Annotated[Any, Depends(get_search_service)],
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> dict:
    _verify_workspace(workspace_id, workspace_service, current_user)
    agent = ComparisonAgent(
        session_factory=session_factory,
        search_service=search_service,
        settings=settings,
    )
    kwargs = {"workspace_id": workspace_id}
    if payload.question or payload.query:
        kwargs["question"] = payload.question or payload.query
    if payload.company_a:
        kwargs["company_a"] = payload.company_a
    if payload.company_b:
        kwargs["company_b"] = payload.company_b
    if payload.document_ids:
        kwargs["document_ids"] = payload.document_ids
    if payload.metric_names:
        kwargs["metric_names"] = payload.metric_names
    if payload.top_k or payload.limit:
        kwargs["top_k"] = payload.top_k or payload.limit
    try:
        result = agent.compare(**kwargs)
    except Exception:
        try:
            result = agent.run(**kwargs)
        except Exception:
            result = agent.analyze(**kwargs)
    return _result_dict(result)


class ReportRequest(_Base):
    title: str | None = None
    question: str | None = None
    query: str | None = None
    document_ids: list[UUID] | None = None
    include_metrics: bool = True
    include_red_flags: bool = True
    top_k: int | None = None
    limit: int | None = None


@router.post("/workspaces/{workspace_id}/reports", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/report", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/report-agent", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/report_agent", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/workspaces/{workspace_id}/generate-report", response_model=dict, status_code=status.HTTP_201_CREATED)
def generate_report(
    workspace_id: UUID,
    payload: ReportRequest,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    search_service: Annotated[Any, Depends(get_search_service)],
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> dict:
    _verify_workspace(workspace_id, workspace_service, current_user)
    agent = ReportAgent(
        session_factory=session_factory,
        search_service=search_service,
        settings=settings,
    )
    kwargs = {"workspace_id": workspace_id}
    if payload.title:
        kwargs["title"] = payload.title
    if payload.question or payload.query:
        kwargs["question"] = payload.question or payload.query
    if payload.document_ids:
        kwargs["document_ids"] = payload.document_ids
    if payload.top_k or payload.limit:
        kwargs["top_k"] = payload.top_k or payload.limit
    try:
        result = agent.generate_report(**kwargs)
    except Exception:
        try:
            result = agent.generate(**kwargs)
        except Exception:
            try:
                result = agent.run(**kwargs)
            except Exception:
                result = agent.analyze(**kwargs)
    return _result_dict(result)


@router.get("/workspaces/{workspace_id}/citations", response_model=ListEnvelope)
@router.get("/workspaces/{workspace_id}/evidence", response_model=ListEnvelope)
@router.get("/citations", response_model=ListEnvelope)
@router.get("/evidence", response_model=ListEnvelope)
def list_citations(
    workspace_id: UUID | None = None,
    session_factory: Annotated[Callable[[], Session] | None, Depends(get_session_factory)] = None,
    workspace_service: Annotated[WorkspaceService | None, Depends(get_workspace_service)] = None,
    current_user: CurrentUserDep = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ListEnvelope:
    return ListEnvelope(items=[], total=0, limit=limit, offset=offset)


@router.post("/citations/validate", response_model=dict)
@router.post("/evidence/validate", response_model=dict)
def validate_citation_endpoint(payload: dict) -> dict:
    try:
        from app.citations import validate_citation

        result = validate_citation(payload)
        if isinstance(result, list):
            return {"valid": len(result) == 0, "errors": result}
        return {"valid": bool(result), "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)]}



def _normalize_period_value(value: Any) -> str:
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value).strip()


def _metric_period(metric: Any) -> str | None:
    context = getattr(metric, "context", None)
    if isinstance(context, dict):
        for key in ("reporting_period", "reportingPeriod", "period", "fiscal_period", "fiscalPeriod"):
            value = context.get(key)
            if value is not None:
                return _normalize_period_value(value)
    for attr in ("reporting_period", "period", "fiscal_period"):
        value = getattr(metric, attr, None)
        if value is not None:
            return _normalize_period_value(value)
    for attr in ("extracted_at", "created_at", "updated_at"):
        value = getattr(metric, attr, None)
        if value is not None:
            return _normalize_period_value(value)
    return None


class ForecastRequest(_Base):
    observations: list[Any] | None = None
    metric_name: str | None = None
    metric: str | None = None
    metric_type: str | None = None
    type: str | None = None
    horizon: int = 1
    method: str = "naive"
    scenario: bool = False
    scenarios: bool = False
    adjustments: Any = None


class ExportRequest(_Base):
    format: str = "csv"
    fmt: str | None = None
    data_type: str = "metrics"
    type: str | None = None
    metric_type: str | None = None
    metric_name: str | None = None
    calculation_type: str | None = None
    severity: str | None = None
    status: str | None = None
    document_id: UUID | None = None
    limit: int | None = None
    offset: int | None = None
    observations: list[Any] | None = None
    horizon: int | None = None
    method: str | None = None
    scenario: bool = False
    scenarios: bool = False
    adjustments: Any = None
    filename: str | None = None
    name: str | None = None
    title: str | None = None
    columns: list[Any] | None = None
    headers: list[Any] | None = None
    filters: dict[str, Any] | None = None
    forecast: dict[str, Any] | None = None
    forecast_params: dict[str, Any] | None = None


def _load_forecast_observations(
    workspace_id: UUID, payload: ForecastRequest, session_factory: Callable[[], Session]
) -> tuple[list[dict[str, Any]], int, str]:
    observations = payload.observations
    if observations:
        metric_label = payload.metric_name or payload.metric or payload.metric_type or payload.type or "financial_metric"
        return [dict(item) if isinstance(item, dict) else item for item in observations], len(observations), metric_label

    metric_name = payload.metric_name or payload.metric
    metric_type = payload.metric_type or payload.type

    with session_factory() as session:
        rows = FinancialMetricRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)

    if metric_type is not None:
        rows = [row for row in rows if row.metric_type == metric_type]
    if metric_name is not None:
        rows = [row for row in rows if row.metric_name == metric_name]

    by_period: dict[str, tuple[Any, float]] = {}
    for row in rows:
        period = _metric_period(row)
        if not period:
            continue
        candidate = getattr(row, "extracted_at", None) or getattr(row, "created_at", None)
        existing = by_period.get(period)
        if existing is None or (candidate or datetime.min) >= (existing[0] or datetime.min):
            try:
                value = float(row.metric_value)
            except (TypeError, ValueError):
                value = row.metric_value
            by_period[period] = (candidate, value)

    obs_list = [{"period": period, "value": value} for period, (_, value) in sorted(by_period.items(), key=lambda item: item[0])]
    metric_label = metric_name or metric_type or "financial_metric"
    return obs_list, len(rows), metric_label


@router.post("/workspaces/{workspace_id}/forecasts", response_model=dict)
@router.post("/workspaces/{workspace_id}/forecast", response_model=dict)
@router.post("/workspaces/{workspace_id}/forecasting", response_model=dict)
@router.post("/workspaces/{workspace_id}/forecast-agent", response_model=dict)
@router.post("/workspaces/{workspace_id}/forecast_agent", response_model=dict)
def run_forecast_endpoint(
    workspace_id: UUID,
    payload: ForecastRequest,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
) -> dict:
    _verify_workspace(workspace_id, workspace_service, current_user)
    try:
        observations, source_count, metric_label = _load_forecast_observations(workspace_id, payload, session_factory)
        horizon = payload.horizon if payload.horizon is not None else 1
        method = payload.method or "naive"
        scenario = bool(payload.scenario or payload.scenarios)
        if scenario:
            result = ForecastingService.scenario_analysis(observations, horizon, payload.adjustments)
        else:
            result = ForecastingService.forecast(observations, horizon, method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    if isinstance(result, dict):
        result = dict(result)
        result.setdefault("metric", metric_label)
        result.setdefault("source_count", source_count)
        if "limitations" not in result:
            result["limitations"] = []
        result.setdefault("metadata", {})
        if isinstance(result["metadata"], dict):
            result["metadata"].setdefault("metric", metric_label)
            result["metadata"].setdefault("source_count", source_count)
            result["metadata"].setdefault("limitations", result.get("limitations", []))
    return result


def _default_export_columns(data_type: str) -> list[str]:
    if data_type == "metrics":
        return list(FinancialMetricRead.model_fields.keys())
    if data_type == "calculations":
        return list(FinancialCalculationRead.model_fields.keys())
    if data_type == "red_flags":
        return list(RedFlagFindingRead.model_fields.keys())
    if data_type == "forecast":
        return ["period", "value", "lower", "upper"]
    return []


def _build_export_rows(
    workspace_id: UUID, req: ExportRequest, session_factory: Callable[[], Session]
) -> tuple[str, str, list[dict[str, Any]], list[Any], str, ExportRequest]:
    fmt = (req.format or req.fmt or "csv").lower()
    if fmt in ("xls", "excel"):
        fmt = "xlsx"

    if isinstance(req.filters, dict):
        for _key, _value in req.filters.items():
            if hasattr(req, _key):
                setattr(req, _key, _value)
    for _container in (req.forecast, req.forecast_params):
        if isinstance(_container, dict):
            for _key, _value in _container.items():
                if hasattr(req, _key):
                    setattr(req, _key, _value)

    data_type = (req.data_type or req.type or "metrics").lower()
    if data_type in ("metric",):
        data_type = "metrics"
    elif data_type in ("calculation",):
        data_type = "calculations"
    elif data_type in ("red_flag", "red-flags", "red_flag_findings", "red-flag-findings", "finding", "findings"):
        data_type = "red_flags"
    elif data_type in ("forecast", "forecasts"):
        data_type = "forecast"

    limit = req.limit if req.limit is not None else 1000
    offset = req.offset if req.offset is not None else 0

    if data_type == "metrics":
        metric_type = req.metric_type
        metric_name = req.metric_name
        document_id = req.document_id
        with session_factory() as session:
            repo = FinancialMetricRepository(session)
            if document_id is not None:
                rows_db = repo.list_by_document(document_id, limit=limit, offset=offset)
            else:
                rows_db = repo.list_by_workspace(workspace_id, limit=limit, offset=offset)
        if metric_type is not None:
            rows_db = [row for row in rows_db if row.metric_type == metric_type]
        if metric_name is not None:
            rows_db = [row for row in rows_db if row.metric_name == metric_name]
        rows = [_metric_to_read(row).model_dump() for row in rows_db]
    elif data_type == "calculations":
        calculation_type = req.calculation_type
        with session_factory() as session:
            repo = FinancialCalculationRepository(session)
            rows_db = repo.list_by_workspace(workspace_id, calculation_type=calculation_type, limit=limit, offset=offset)
        rows = [_calc_to_read(row).model_dump() for row in rows_db]
    elif data_type == "red_flags":
        severity = req.severity
        status = req.status
        document_id = req.document_id
        with session_factory() as session:
            repo = RedFlagFindingRepository(session)
            if document_id is not None:
                rows_db = repo.list_by_document(document_id, severity=severity, status=status, limit=limit, offset=offset)
            else:
                rows_db = repo.list_by_workspace(workspace_id, severity=severity, status=status, limit=limit, offset=offset)
        rows = [_finding_to_read(row).model_dump() for row in rows_db]
    elif data_type == "forecast":
        forecast_request = ForecastRequest(
            observations=req.observations,
            metric_name=req.metric_name,
            metric_type=req.metric_type,
            horizon=req.horizon if req.horizon is not None else 1,
            method=req.method or "naive",
            scenario=bool(req.scenario or req.scenarios),
            adjustments=req.adjustments,
        )
        observations, _, _ = _load_forecast_observations(workspace_id, forecast_request, session_factory)
        horizon = req.horizon if req.horizon is not None else 1
        if req.scenario or req.scenarios:
            result = ForecastingService.scenario_analysis(observations, horizon, req.adjustments)
            forecast_list = result.get("baseline", {}).get("forecast", []) if isinstance(result, dict) else []
        else:
            result = ForecastingService.forecast(observations, horizon, req.method or "naive")
            forecast_list = result.get("forecast", []) if isinstance(result, dict) else []
        rows = []
        for item in forecast_list:
            if isinstance(item, dict):
                rows.append(
                    {
                        "period": item.get("period"),
                        "value": item.get("value"),
                        "lower": item.get("lower"),
                        "upper": item.get("upper"),
                    }
                )
            else:
                rows.append({"period": getattr(item, "period", None), "value": getattr(item, "value", None)})
    else:
        raise ValueError("invalid data_type")

    columns = req.columns or req.headers
    if not columns:
        columns = _default_export_columns(data_type)

    filename = req.filename or req.name
    if not filename:
        filename = f"{data_type}_export.{fmt}"

    return data_type, fmt, rows, columns, filename, req


def _do_export(
    workspace_id: UUID,
    req: ExportRequest,
    session_factory: Callable[[], Session],
    workspace_service: WorkspaceService,
    current_user: Any,
) -> Response:
    _verify_workspace(workspace_id, workspace_service, current_user)

    fmt = (req.format or req.fmt or "csv").lower()
    if fmt in ("xls", "excel"):
        fmt = "xlsx"
    if fmt not in ("csv", "json", "xlsx", "pdf"):
        raise HTTPException(status_code=422, detail="invalid format")

    try:
        data_type, fmt, rows, columns, filename, req = _build_export_rows(workspace_id, req, session_factory)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    try:
        if fmt == "csv":
            result = ExportService.export_csv(rows, columns, filename=filename)
        elif fmt == "json":
            result = ExportService.export_json(rows, filename=filename)
        elif fmt == "xlsx":
            result = ExportService.export_xlsx({str(data_type): (columns, rows)}, filename=filename)
        else:
            title = req.title or f"{data_type} export"
            body_rows = [list(columns)] + [
                [row.get(column) if isinstance(row, dict) else row for column in columns]
                for row in rows
            ]
            sections = [{"title": title, "rows": body_rows}]
            result = ExportService.export_pdf(title, sections, filename=filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    if result is None:
        raise HTTPException(status_code=422, detail="export format unavailable") from None

    return Response(
        content=result.bytes,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post("/workspaces/{workspace_id}/exports", response_class=Response)
@router.post("/workspaces/{workspace_id}/export", response_class=Response)
@router.post("/workspaces/{workspace_id}/exports/download", response_class=Response)
@router.post("/workspaces/{workspace_id}/export/download", response_class=Response)
def export_workspace_data(
    workspace_id: UUID,
    payload: ExportRequest,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
) -> Response:
    return _do_export(workspace_id, payload, session_factory, workspace_service, current_user)


@router.get("/workspaces/{workspace_id}/exports", response_class=Response)
@router.get("/workspaces/{workspace_id}/export", response_class=Response)
@router.get("/workspaces/{workspace_id}/exports/download", response_class=Response)
def export_workspace_data_get(
    workspace_id: UUID,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    current_user: CurrentUserDep,
    format: str = Query(default="csv"),
    data_type: str = Query(default="metrics"),
    metric_type: str | None = Query(default=None),
    metric_name: str | None = Query(default=None),
    calculation_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    horizon: int | None = Query(default=None),
    method: str | None = Query(default=None),
    scenario: bool = Query(default=False),
    filename: str | None = Query(default=None),
    title: str | None = Query(default=None),
) -> Response:
    req = ExportRequest(
        format=format,
        data_type=data_type,
        metric_type=metric_type,
        metric_name=metric_name,
        calculation_type=calculation_type,
        severity=severity,
        status=status,
        document_id=document_id,
        limit=limit,
        offset=offset,
        horizon=horizon,
        method=method,
        scenario=scenario,
        filename=filename,
        title=title,
    )
    return _do_export(workspace_id, req, session_factory, workspace_service, current_user)
