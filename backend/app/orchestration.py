"""Orchestration layer for the financial processing workflow."""

from __future__ import annotations

import contextlib
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

__all__ = [
    "FinancialOrchestrator",
    "FinancialWorkflowOrchestrator",
    "OrchestrationLayer",
    "OrchestrationOutcome",
    "OrchestrationResult",
    "OrchestrationService",
    "Orchestrator",
    "ProcessingOrchestrator",
    "WorkflowOrchestrator",
    "WorkflowOutcome",
    "WorkflowResult",
    "WorkflowService",
    "WorkflowStatus",
    "create_orchestrator",
    "get_orchestrator",
]


def _uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _now() -> datetime:
    return datetime.now(UTC)


def _log():
    try:
        from app.core.logging import get_logger

        return get_logger("app.orchestration")
    except Exception:
        import logging

        return logging.getLogger("app.orchestration")


logger = _log()


@dataclass
class WorkflowStatus:
    document: str = "pending"
    extraction: str = "pending"
    validation: str = "pending"
    red_flags: str = "pending"
    overall: str = "pending"

    def as_dict(self) -> dict[str, str]:
        return {
            "document": self.document,
            "extraction": self.extraction,
            "validation": self.validation,
            "red_flags": self.red_flags,
            "overall": self.overall,
        }

    @property
    def stages(self) -> dict[str, str]:
        return self.as_dict()


@dataclass
class OrchestrationResult:
    document_id: UUID
    status: str = "pending"
    stage_status: dict[str, str] = field(default_factory=dict)
    stages: dict[str, str] = field(default_factory=dict)
    extraction_result: Any = None
    validation_result: Any = None
    red_flag_result: Any = None
    metrics: list[Any] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    calculations: list[Any] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    attempt_count: int = 1
    attempts: int = 1
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    success: bool = False
    agent_run_id: UUID | None = None
    workspace_id: UUID | None = None
    duplicate: bool = False
    recovered: bool = False

    def __post_init__(self):
        if not self.stage_status and self.stages:
            self.stage_status = dict(self.stages)
        if not self.stages and self.stage_status:
            self.stages = dict(self.stage_status)
        self.attempts = self.attempt_count
        self.success = self.status in {"completed", "success", "ok"}

    @property
    def ok(self) -> bool:
        return self.success

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["document_id"] = str(self.document_id)
        if self.workspace_id is not None:
            data["workspace_id"] = str(self.workspace_id)
        if self.agent_run_id is not None:
            data["agent_run_id"] = str(self.agent_run_id)
        return data


OrchestrationOutcome = OrchestrationResult
WorkflowResult = OrchestrationResult
WorkflowOutcome = OrchestrationResult
class Orchestrator:
    def __init__(
        self,
        *,
        document_agent: Any = None,
        extraction_agent: Any = None,
        financial_extraction_agent: Any = None,
        validation_service: Any = None,
        financial_validation_service: Any = None,
        red_flag_agent: Any = None,
        session_factory: Any = None,
        job_runner: Any = None,
        max_attempts: int = 1,
        retry_delay: float = 0.0,
        max_retries: int | None = None,
        settings: Any = None,
        logger: Any = None,
        **kwargs: Any,
    ) -> None:
        self.document_agent = (
            document_agent
            or kwargs.get("document_agent")
            or kwargs.get("document_processor")
            or kwargs.get("processor")
            or kwargs.get("doc_agent")
        )
        self.extraction_agent = (
            extraction_agent
            or financial_extraction_agent
            or kwargs.get("extraction_agent")
            or kwargs.get("financial_extraction_agent")
            or kwargs.get("extractor")
            or kwargs.get("financial_extractor")
            or kwargs.get("extraction_service")
        )
        self.financial_extraction_agent = self.extraction_agent
        self.validation_service = (
            validation_service
            or financial_validation_service
            or kwargs.get("validation_service")
            or kwargs.get("financial_validation_service")
            or kwargs.get("validator")
            or kwargs.get("validation")
            or kwargs.get("financial_validator")
            or kwargs.get("validation_agent")
        )
        self.financial_validation_service = self.validation_service
        self.red_flag_agent = (
            red_flag_agent
            or kwargs.get("red_flag_agent")
            or kwargs.get("redflag_agent")
            or kwargs.get("red_flag")
            or kwargs.get("risk_agent")
            or kwargs.get("redflag")
        )
        self.session_factory = (
            session_factory
            or kwargs.get("session_factory")
            or kwargs.get("sessionmaker")
            or kwargs.get("db_session_factory")
            or kwargs.get("session_maker")
        )
        self.job_runner = job_runner or kwargs.get("job_runner")
        self.max_attempts = max_attempts if max_retries is None else max_retries
        if max_retries is not None:
            self.max_attempts = max_retries
        self.retry_delay = retry_delay
        self.settings = settings or kwargs.get("settings")
        self.logger = logger or _log()
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        if self.session_factory is not None:
            for agent in (self.extraction_agent, self.red_flag_agent):
                if agent is not None and getattr(agent, "session_factory", None) is None:
                    with contextlib.suppress(Exception):
                        agent.session_factory = self.session_factory

        self._lock = threading.RLock()
        self._in_progress: set[UUID] = set()
        self._completed: set[UUID] = set()
        self._results: dict[UUID, OrchestrationResult] = {}
        self._stage_durations: dict[str, float] = {}

    def process(self, document_id: Any, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self._process(document_id, *args, **kwargs)

    def process_document(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        document_id = kwargs.pop("document_id", None)
        if document_id is None and args:
            document_id = args[0]
            args = args[1:]
        return self._process(document_id, *args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def orchestrate(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def coordinate(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def handle(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def handle_document(self, *args: Any, **kwargs: Any) -> OrchestrationResult:
        return self.process_document(*args, **kwargs)

    def process_workspace(self, workspace_id: Any, **kwargs: Any) -> list[OrchestrationResult]:
        ids = self._list_documents(workspace_id)
        return [self.process(document_id) for document_id in ids]

    def retry(self, document_id: Any, **kwargs: Any) -> OrchestrationResult:
        return self._process(document_id, force=True, **kwargs)

    def retry_document(self, document_id: Any, **kwargs: Any) -> OrchestrationResult:
        return self.retry(document_id, **kwargs)

    def reprocess(self, document_id: Any, **kwargs: Any) -> OrchestrationResult:
        return self.retry(document_id, **kwargs)

    def run_pending(self) -> int:
        count = 0
        for document_id in self._pending_document_ids():
            try:
                self.process(document_id)
                count += 1
            except Exception:
                self.logger.exception("recovery failed for document %s", document_id)
        return count

    def recover(self) -> int:
        return self.run_pending()

    def recover_pending(self) -> int:
        return self.run_pending()

    def resume(self, *args: Any, **kwargs: Any) -> Any:
        if args or "document_id" in kwargs:
            return self.process_document(*args, **kwargs)
        return self.run_pending()

    def status(self, document_id: Any) -> OrchestrationResult | None:
        document_id = _uuid(document_id)
        cached = self._results.get(document_id)
        if cached is not None:
            return cached
        return None

    def get_status(self, document_id: Any) -> OrchestrationResult | None:
        return self.status(document_id)

    def workflow_status(self, document_id: Any) -> WorkflowStatus:
        result = self.status(document_id)
        if result is None:
            return WorkflowStatus()
        return WorkflowStatus(
            document=result.stage_status.get("document", "pending"),
            extraction=result.stage_status.get("extraction", "pending"),
            validation=result.stage_status.get("validation", "pending"),
            red_flags=result.stage_status.get("red_flags", "pending"),
            overall=result.status,
        )

    def stage_durations(self) -> dict[str, float]:
        return dict(self._stage_durations)
    def _process(self, document_id: Any, *args: Any, **kwargs: Any) -> OrchestrationResult:
        document_id = _uuid(document_id)
        force = bool(kwargs.pop("force", False))
        max_attempts = int(kwargs.pop("max_attempts", self.max_attempts) or 1)

        with self._lock:
            cached = self._results.get(document_id)
            if (not force and cached is not None
                    and cached.status in {"completed", "success", "ok"}):
                cached.duplicate = True
                return cached
            self._in_progress.add(document_id)

        started_at = _now()
        start = time.perf_counter()
        stage_status = {
            "document": "pending",
            "extraction": "pending",
            "validation": "pending",
            "red_flags": "pending",
        }
        result: OrchestrationResult | None = None
        agent_run_id: UUID | None = None
        workspace_id: UUID | None = None
        metrics: list[Any] = []
        findings: list[Any] = []
        calculations: list[Any] = []
        extraction_result: Any = None
        validation_result: Any = None
        red_flag_result: Any = None
        error_code: str | None = None
        error_message: str | None = None
        attempt_count = 0

        try:
            workspace_id = self._workspace_id(document_id)
        except Exception:
            workspace_id = None

        agent_run_id = self._start_agent_run(document_id, workspace_id, kwargs)

        try:
            for attempt in range(1, max_attempts + 1):
                attempt_count = attempt
                stage_status = {k: "pending" for k in stage_status}
                try:
                    if attempt > 1:
                        self._retry_document(document_id)

                    stage_start = time.perf_counter()
                    stage_status["document"] = "running"
                    self.logger.info(
                        "orchestration stage started",
                        extra={
                            "document_id": str(document_id),
                            "stage": "document",
                            "attempt": attempt,
                        },
                    )
                    doc_outcome = self._run_document(document_id)
                    if doc_outcome is not None:
                        doc_status = getattr(doc_outcome, "status", None)
                        if str(doc_status).lower() not in {"completed", "success", "ok"}:
                            raise RuntimeError(
                                getattr(doc_outcome, "error_message", None)
                                or "document processing failed"
                            )
                    stage_status["document"] = "completed"
                    self._record_stage_duration("document", stage_start)

                    stage_start = time.perf_counter()
                    stage_status["extraction"] = "running"
                    self.logger.info(
                        "orchestration stage started",
                        extra={
                            "document_id": str(document_id),
                            "stage": "extraction",
                            "attempt": attempt,
                        },
                    )
                    extraction_result = self._run_extraction(
                        document_id, workspace_id, **kwargs
                    )
                    metrics = list(getattr(extraction_result, "metrics", None) or [])
                    stage_status["extraction"] = "completed"
                    self._record_stage_duration("extraction", stage_start)

                    stage_start = time.perf_counter()
                    stage_status["validation"] = "running"
                    self.logger.info(
                        "orchestration stage started",
                        extra={
                            "document_id": str(document_id),
                            "stage": "validation",
                            "attempt": attempt,
                        },
                    )
                    validation_result = self._run_validation(
                        extraction_result, document_id, workspace_id, **kwargs
                    )
                    calculations = list(
                        getattr(validation_result, "calculations", None)
                        or getattr(validation_result, "results", None)
                        or []
                    )
                    stage_status["validation"] = "completed"
                    self._record_stage_duration("validation", stage_start)

                    stage_start = time.perf_counter()
                    stage_status["red_flags"] = "running"
                    self.logger.info(
                        "orchestration stage started",
                        extra={
                            "document_id": str(document_id),
                            "stage": "red_flags",
                            "attempt": attempt,
                        },
                    )
                    self._clear_red_flags(document_id)
                    red_flag_result = self._run_red_flags(
                        extraction_result, validation_result, document_id, workspace_id,
                        **kwargs,
                    )
                    findings = list(getattr(red_flag_result, "findings", None) or [])
                    stage_status["red_flags"] = "completed"
                    self._record_stage_duration("red_flags", stage_start)

                    result = OrchestrationResult(
                        document_id=document_id,
                        status="completed",
                        stage_status=dict(stage_status),
                        stages=dict(stage_status),
                        extraction_result=extraction_result,
                        validation_result=validation_result,
                        red_flag_result=red_flag_result,
                        metrics=metrics,
                        findings=findings,
                        calculations=calculations,
                        attempt_count=attempt,
                        started_at=started_at,
                        completed_at=_now(),
                        duration_ms=int((time.perf_counter() - start) * 1000),
                        agent_run_id=agent_run_id,
                        workspace_id=workspace_id,
                    )
                    break
                except Exception as exc:
                    error_code = getattr(exc, "error_code", None) or getattr(exc, "code", None)
                    if not isinstance(error_code, str) or not error_code:
                        error_code = type(exc).__name__
                    error_message = str(exc)
                    stage_status = {
                        key: ("failed" if stage_status.get(key) == "running" else stage_status.get(key, "pending"))
                        for key in stage_status
                    }
                    self.logger.error(
                        "orchestration stage failed",
                        extra={
                            "document_id": str(document_id),
                            "stage": next(
                                (k for k, v in stage_status.items() if v == "failed"),
                                "unknown",
                            ),
                            "attempt": attempt,
                            "error_code": error_code,
                            "error_message": error_message,
                        },
                    )
                    if attempt >= max_attempts:
                        result = OrchestrationResult(
                            document_id=document_id,
                            status="failed",
                            stage_status=dict(stage_status),
                            stages=dict(stage_status),
                            extraction_result=extraction_result,
                            validation_result=validation_result,
                            red_flag_result=red_flag_result,
                            metrics=metrics,
                            findings=findings,
                            calculations=calculations,
                            error_code=error_code,
                            error_message=error_message,
                            attempt_count=attempt,
                            started_at=started_at,
                            completed_at=_now(),
                            duration_ms=int((time.perf_counter() - start) * 1000),
                            agent_run_id=agent_run_id,
                            workspace_id=workspace_id,
                        )
                        break
                    if self.retry_delay:
                        time.sleep(self.retry_delay)
        finally:
            with self._lock:
                self._in_progress.discard(document_id)
                if result is not None and result.status in {"completed", "success", "ok"}:
                    self._completed.add(document_id)
                    self._results[document_id] = result
            self._finish_agent_run(agent_run_id, result, error_message)

        self.logger.info(
            "orchestration finished",
            extra={
                "document_id": str(document_id),
                "status": result.status if result is not None else "failed",
                "duration_ms": result.duration_ms if result is not None else None,
                "attempt_count": attempt_count,
            },
        )
        return result if result is not None else OrchestrationResult(
            document_id=document_id,
            status="failed",
            stage_status=dict(stage_status),
            stages=dict(stage_status),
            error_code=error_code,
            error_message=error_message,
            attempt_count=attempt_count,
            started_at=started_at,
            completed_at=_now(),
            duration_ms=int((time.perf_counter() - start) * 1000),
            agent_run_id=agent_run_id,
            workspace_id=workspace_id,
        )
    def _run_document(self, document_id: UUID) -> Any:
        agent = self.document_agent or getattr(self, "document_processor", None) or getattr(self, "processor", None) or getattr(self, "doc_agent", None)
        if agent is None:
            return None
        for name in ("process", "run", "process_document", "execute"):
            method = getattr(agent, name, None)
            if callable(method):
                try:
                    return method(document_id)
                except TypeError:
                    continue
        return None

    def _run_extraction(self, document_id: UUID, workspace_id: UUID | None, **kwargs: Any) -> Any:
        agent = self.extraction_agent or getattr(self, "extraction_service", None) or getattr(self, "extractor", None) or getattr(self, "financial_extractor", None)
        if agent is None:
            return None
        for name in ("extract_and_store", "extract_and_persist", "extract_and_save"):
            method = getattr(agent, name, None)
            if callable(method):
                try:
                    return method(
                        document_id,
                        session_factory=self.session_factory,
                        workspace_id=workspace_id,
                        **kwargs,
                    )
                except TypeError:
                    try:
                        return method(document_id, workspace_id=workspace_id, **kwargs)
                    except TypeError:
                        try:
                            return method(document_id, **kwargs)
                        except Exception:
                            continue
                except Exception:
                    continue
        for name in ("extract", "run", "process", "extract_financial_metrics", "extract_metrics"):
            method = getattr(agent, name, None)
            if callable(method):
                try:
                    return method(
                        document_id,
                        session_factory=self.session_factory,
                        workspace_id=workspace_id,
                        **kwargs,
                    )
                except TypeError:
                    try:
                        return method(document_id=document_id, workspace_id=workspace_id, **kwargs)
                    except TypeError:
                        try:
                            return method(str(document_id), **kwargs)
                        except Exception:
                            continue
                except Exception:
                    continue
        return None

    def _run_validation(
        self, extraction_result: Any, document_id: UUID, workspace_id: UUID | None, **kwargs: Any
    ) -> Any:
        service = self.validation_service or getattr(self, "validator", None) or getattr(self, "validation", None)
        if service is None:
            return None
        metrics = kwargs.pop("metrics", None)
        if metrics is None:
            metrics = getattr(extraction_result, "metrics", None)
        metrics = list(metrics or [])
        for name in ("validate_metrics", "validate_many", "validate_all", "validate_extracted_values",
                     "validate_values", "validate", "run", "process", "calculate_and_validate",
                     "validate_and_calculate"):
            method = getattr(service, name, None)
            if not callable(method):
                continue
            for call in (
                lambda m=method: m(metrics, workspace_id=workspace_id, document_id=document_id, **kwargs),
                lambda m=method: m(metrics, **kwargs),
                lambda m=method: m(metrics),
                lambda m=method: m(metrics=metrics, **kwargs),
            ):
                try:
                    return call()
                except TypeError:
                    continue
                except Exception:
                    continue
        return None

    def _run_red_flags(
        self, extraction_result: Any, validation_result: Any, document_id: UUID,
        workspace_id: UUID | None, **kwargs: Any,
    ) -> Any:
        agent = self.red_flag_agent or getattr(self, "red_flag", None) or getattr(self, "risk_agent", None) or getattr(self, "redflag", None)
        if agent is None:
            return None
        metrics = kwargs.pop("metrics", None)
        if metrics is None:
            metrics = getattr(extraction_result, "metrics", None)
        metrics = list(metrics or [])
        calculations = kwargs.pop("calculations", None)
        if calculations is None:
            calculations = []
            if validation_result is not None:
                calculations = (
                    getattr(validation_result, "calculations", None)
                    or getattr(validation_result, "results", None)
                    or []
                )
        calculations = list(calculations or [])
        for name in ("analyze_and_store", "detect_and_store", "run_and_store",
                     "analyze", "run", "process", "detect", "evaluate"):
            method = getattr(agent, name, None)
            if not callable(method):
                continue
            for call in (
                lambda m=method: m(
                    metrics,
                    calculations,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    session_factory=self.session_factory,
                    **kwargs,
                ),
                lambda m=method: m(
                    metrics=metrics,
                    calculations=calculations,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    session_factory=self.session_factory,
                    **kwargs,
                ),
                lambda m=method: m(
                    document_id,
                    workspace_id=workspace_id,
                    session_factory=self.session_factory,
                    **kwargs,
                ),
            ):
                try:
                    return call()
                except TypeError:
                    continue
                except Exception:
                    continue
        return None

    def _clear_red_flags(self, document_id: UUID) -> None:
        if self.session_factory is None:
            return
        try:
            from app.repositories.red_flag_finding_repository import RedFlagFindingRepository

            with self.session_factory() as session:
                repo = RedFlagFindingRepository(session)
                findings = repo.list_by_document(document_id)
                for finding in findings:
                    repo.delete(finding, commit=False)
                session.commit()
        except Exception:
            pass

    def _retry_document(self, document_id: UUID) -> None:
        service = getattr(self, "document_service", None)
        if service is None:
            service = getattr(self, "doc_service", None)
        if service is not None and hasattr(service, "retry_document"):
            with contextlib.suppress(Exception):
                service.retry_document(document_id)

    def _workspace_id(self, document_id: UUID) -> UUID | None:
        for attr in ("document_service", "doc_service", "document_svc"):
            service = getattr(self, attr, None)
            if service is not None and hasattr(service, "get_document"):
                try:
                    summary = service.get_document(document_id)
                    ws = getattr(summary, "workspace_id", None)
                    if ws is not None:
                        return _uuid(ws)
                except Exception:
                    pass
        if self.session_factory is not None:
            try:
                from app.repositories.document_repository import DocumentRepository

                with self.session_factory() as session:
                    row = DocumentRepository(session).get(document_id)
                    if row is not None and getattr(row, "workspace_id", None) is not None:
                        return _uuid(row.workspace_id)
            except Exception:
                pass
        return None

    def _list_documents(self, workspace_id: Any) -> list[UUID]:
        if self.session_factory is None:
            return []
        try:
            from app.repositories.document_repository import DocumentRepository

            with self.session_factory() as session:
                repo = DocumentRepository(session)
                if hasattr(repo, "list_by_workspace"):
                    rows = repo.list_by_workspace(_uuid(workspace_id), limit=1000, offset=0)
                else:
                    rows = []
                return [_uuid(getattr(r, "id", r)) for r in rows]
        except Exception:
            return []

    def _pending_document_ids(self) -> list[UUID]:
        if self.session_factory is None:
            return []
        try:
            from sqlalchemy import select

            from app.db.models.document import Document

            with self.session_factory() as session:
                stmt = select(Document).where(
                    Document.processing_status.in_(["queued", "failed"])
                )
                rows = session.execute(stmt).scalars().all()
                ids = []
                for row in rows or []:
                    ids.append(_uuid(getattr(row, "id", row)))
                return ids
        except Exception:
            return []

    def _record_stage_duration(self, stage: str, started_at: float) -> None:
        self._stage_durations[stage] = (time.perf_counter() - started_at) * 1000.0

    def _start_agent_run(self, document_id: UUID, workspace_id: UUID | None, payload: dict[str, Any]) -> UUID | None:
        if self.session_factory is None:
            return None
        try:
            from app.db.models.agent_run import AgentRun

            run_id = uuid.uuid4()
            with self.session_factory() as session:
                row = AgentRun(
                    id=run_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    agent_name="orchestrator",
                    agent_type="orchestration",
                    status="running",
                    task_description="financial processing workflow",
                    input_payload={"document_id": str(document_id)},
                    started_at=_now(),
                )
                session.add(row)
                session.commit()
            return run_id
        except Exception:
            return None

    def _finish_agent_run(
        self, run_id: UUID | None, result: OrchestrationResult | None, error_message: str | None
    ) -> None:
        if run_id is None or self.session_factory is None:
            return
        try:
            from app.db.models.agent_run import AgentRun

            with self.session_factory() as session:
                row = session.get(AgentRun, run_id)
                if row is None:
                    return
                if result is not None and result.status in {"completed", "success", "ok"}:
                    row.status = "completed"
                    row.output_payload = result.to_dict()
                else:
                    row.status = "failed"
                    row.error_message = error_message
                row.completed_at = _now()
                if result is not None and result.duration_ms is not None:
                    row.duration_ms = int(result.duration_ms)
                session.commit()
        except Exception:
            pass


for _alias in (
    "process_financial_document",
    "run_workflow",
    "execute_workflow",
    "orchestrate_document",
    "process_all",
    "start",
    "run_document",
    "execute_document",
    "process_one",
):
    setattr(Orchestrator, _alias, Orchestrator.process_document)


FinancialOrchestrator = Orchestrator
OrchestrationLayer = Orchestrator
OrchestrationService = Orchestrator
WorkflowOrchestrator = Orchestrator
ProcessingOrchestrator = Orchestrator
FinancialWorkflowOrchestrator = Orchestrator
WorkflowService = Orchestrator


def create_orchestrator(*args: Any, **kwargs: Any) -> Orchestrator:
    return Orchestrator(*args, **kwargs)


def get_orchestrator(*args: Any, **kwargs: Any) -> Orchestrator:
    return Orchestrator(*args, **kwargs)


OrchestrationStatus = WorkflowStatus
StageStatus = WorkflowStatus
Status = WorkflowStatus
