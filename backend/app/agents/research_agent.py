
"""The Research Agent: natural-language financial research over indexed documents."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

__all__ = [
    "ResearchAgent",
    "ResearchAnalysis",
    "ResearchAnswer",
    "ResearchFinding",
    "ResearchOutcome",
    "ResearchReport",
    "ResearchResult",
    "ResearchService",
    "analyze_research",
    "answer_question",
    "ask_research",
    "research",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = text.replace("$", "").replace("EUR", "").replace("USD", "")
    text = text.replace("(", "-").replace(")", "")
    text = text.strip()
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "as_dict") and callable(value.as_dict):
        try:
            return dict(value.as_dict())
        except Exception:
            pass
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return dict(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {k: v for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:
            pass
    return {"value": value}


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    data = _as_mapping(obj)
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
        if hasattr(obj, name):
            val = getattr(obj, name)
            if val is not None:
                return val
    lower = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name.lower() in lower and lower[name.lower()] is not None:
            return lower[name.lower()]
    return default


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, Mapping):
        if any(k in value for k in ("question", "query", "chunk_id", "content", "metric_name", "calculation_name")):
            return [value]
        out = []
        for v in value.values():
            if isinstance(v, (list, tuple)):
                out.extend(v)
            else:
                out.append(v)
        return out
    if hasattr(value, "results"):
        try:
            return list(value.results or [])
        except Exception:
            pass
    return [value]


def _norm(text: Any) -> str:
    return str(text or "").strip()
def _is_uuid_like(value: Any) -> bool:
    if isinstance(value, UUID):
        return True
    if isinstance(value, str):
        try:
            UUID(value)
            return True
        except (ValueError, AttributeError):
            return False
    return False


def _citation_from_item(item: Any) -> dict[str, Any]:
    def g(*names):
        return _get(item, *names, default=None)
    citation = {
        "chunk_id": g("chunk_id", "id"),
        "document_id": g("document_id"),
        "document_title": g("document_title", "title", "document_name"),
        "company_name": g("company_name", "company"),
        "document_type": g("document_type", "doc_type"),
        "fiscal_period": g("fiscal_period", "period", "reporting_period"),
        "page_start": g("page_start", "page", "page_number"),
        "page_end": g("page_end"),
        "section_heading": g("section_heading", "section", "heading"),
        "chunk_type": g("chunk_type", "type"),
        "score": g("score", "similarity", "relevance"),
        "content": g("content", "text", "excerpt", "source_text", "source_excerpt"),
    }
    metadata = g("metadata")
    if isinstance(metadata, Mapping):
        for key, val in metadata.items():
            if citation.get(key) is None and val is not None:
                citation[key] = val
    return citation


def _metric_name(metric: Any) -> str:
    return _norm(_get(metric, "metric_name", "name", "metric", "label", "title", default="metric"))


def _metric_value(metric: Any) -> Any:
    for name in ("metric_value", "value", "amount", "val", "result_value"):
        v = _get(metric, name, default=None)
        if v is not None:
            return v
    return None


def _metric_period(metric: Any) -> Any:
    return _get(metric, "reporting_period", "period", "fiscal_period", "period_label", default=None)


def _calc_name(calc: Any) -> str:
    return _norm(_get(calc, "calculation_name", "name", "ratio_name", "ratio", "calculation_type", "type", "metric", default="calculation"))


def _calc_value(calc: Any) -> Any:
    for name in ("result_value", "value", "result", "ratio_value", "calculated_value"):
        v = _get(calc, name, default=None)
        if v is not None:
            return v
    return None


def _calc_period(calc: Any) -> Any:
    p = _get(calc, "reporting_period", "period", "fiscal_period", default=None)
    if p is not None:
        return p
    inputs = _get(calc, "input_metrics", "inputs", default=None)
    if isinstance(inputs, (list, tuple)):
        for inp in inputs:
            pp = _get(inp, "reporting_period", "period", default=None)
            if pp is not None:
                return pp
    meta = _get(calc, "metadata", "calculation_metadata", default=None)
    if isinstance(meta, Mapping):
        for key in ("reporting_period", "period", "fiscal_period"):
            if meta.get(key) is not None:
                return meta[key]
    return None


def _normalize_metrics(value: Any) -> list[Any]:
    out = []
    for item in _to_list(value):
        if isinstance(item, (list, tuple)):
            out.extend(_normalize_metrics(item))
        else:
            out.append(item)
    return out


def _normalize_calcs(value: Any) -> list[Any]:
    out = []
    for item in _to_list(value):
        if isinstance(item, (list, tuple)):
            out.extend(_normalize_calcs(item))
        else:
            out.append(item)
    return out


def _normalize_search_results(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "results"):
        try:
            return list(value.results or [])
        except Exception:
            pass
    out = []
    for item in _to_list(value):
        if isinstance(item, (list, tuple)):
            out.extend(_normalize_search_results(item))
        else:
            out.append(item)
    return out


def _content_of(item: Any) -> str:
    v = _get(item, "content", "text", "excerpt", "source_text", "source_excerpt", "passage", default=None)
    if v is None:
        return ""
    return str(v)


def _dedup_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for c in citations:
        key = (
            c.get("chunk_id"),
            c.get("document_id"),
            c.get("page_start"),
            c.get("page_end"),
            (c.get("content") or "")[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
@dataclass
class ResearchFinding:
    question: str | None = None
    sub_question: str | None = None
    answer: str | None = None
    fact: str | None = None
    factual_observation: str | None = None
    observation: str | None = None
    calculation: str | None = None
    interpretation: str | None = None
    analysis: str | None = None
    assessment: str | None = None
    rationale: str | None = None
    missing_information: str | None = None
    gap: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.sub_question is None:
            self.sub_question = self.question
        if self.question is None:
            self.question = self.sub_question
        if self.fact is None:
            self.fact = self.factual_observation or self.observation
        if self.factual_observation is None:
            self.factual_observation = self.fact
        if self.observation is None:
            self.observation = self.fact
        if self.interpretation is None:
            self.interpretation = self.analysis or self.assessment or self.rationale
        if self.analysis is None:
            self.analysis = self.interpretation
        if self.assessment is None:
            self.assessment = self.interpretation
        if self.rationale is None:
            self.rationale = self.interpretation
        if self.missing_information is None:
            self.missing_information = self.gap
        if self.gap is None:
            self.gap = self.missing_information
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "sub_question": self.sub_question,
            "answer": self.answer,
            "fact": self.fact,
            "factual_observation": self.factual_observation,
            "observation": self.observation,
            "calculation": self.calculation,
            "interpretation": self.interpretation,
            "analysis": self.analysis,
            "assessment": self.assessment,
            "rationale": self.rationale,
            "missing_information": self.missing_information,
            "gap": self.gap,
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    to_dict = as_dict
@dataclass
class ResearchResult:
    question: str | None = None
    query: str | None = None
    research_question: str | None = None
    user_question: str | None = None
    answer: str | None = None
    response: str | None = None
    result: str | None = None
    final_answer: str | None = None
    summary: str | None = None
    text: str | None = None
    sub_questions: list[str] = field(default_factory=list)
    decomposed_questions: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    facts: list[Any] = field(default_factory=list)
    factual_statements: list[Any] = field(default_factory=list)
    evidence_facts: list[Any] = field(default_factory=list)
    observations: list[Any] = field(default_factory=list)
    calculations: list[Any] = field(default_factory=list)
    computed_values: list[Any] = field(default_factory=list)
    financial_calculations: list[Any] = field(default_factory=list)
    ratios: list[Any] = field(default_factory=list)
    interpretations: list[Any] = field(default_factory=list)
    analysis: list[Any] = field(default_factory=list)
    insights: list[Any] = field(default_factory=list)
    assessments: list[Any] = field(default_factory=list)
    missing_information: list[Any] = field(default_factory=list)
    gaps: list[Any] = field(default_factory=list)
    unknowns: list[Any] = field(default_factory=list)
    not_found: list[Any] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    retrieved_chunks: list[Any] = field(default_factory=list)
    search_results: list[Any] = field(default_factory=list)
    evidence_chunks: list[Any] = field(default_factory=list)
    hits: list[Any] = field(default_factory=list)
    metrics: list[Any] = field(default_factory=list)
    financial_metrics: list[Any] = field(default_factory=list)
    extracted_metrics: list[Any] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    research_findings: list[ResearchFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    confidence: Any = None
    confidence_score: Any = None
    workspace_id: Any = None
    document_id: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("question", "query", "research_question", "user_question"):
            val = getattr(self, name)
            if val is not None:
                for other in ("question", "query", "research_question", "user_question"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("answer", "response", "result", "final_answer", "summary", "text"):
            val = getattr(self, name)
            if val is not None:
                for other in ("answer", "response", "result", "final_answer", "summary", "text"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("sub_questions", "decomposed_questions", "parts", "questions"):
            val = getattr(self, name)
            if val:
                for other in ("sub_questions", "decomposed_questions", "parts", "questions"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("facts", "factual_statements", "evidence_facts", "observations"):
            val = getattr(self, name)
            if val:
                for other in ("facts", "factual_statements", "evidence_facts", "observations"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("calculations", "computed_values", "financial_calculations", "ratios"):
            val = getattr(self, name)
            if val:
                for other in ("calculations", "computed_values", "financial_calculations", "ratios"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("interpretations", "analysis", "insights", "assessments"):
            val = getattr(self, name)
            if val:
                for other in ("interpretations", "analysis", "insights", "assessments"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("missing_information", "gaps", "unknowns", "not_found"):
            val = getattr(self, name)
            if val:
                for other in ("missing_information", "gaps", "unknowns", "not_found"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("citations", "source_citations", "sources", "references", "evidence"):
            val = getattr(self, name)
            if val:
                for other in ("citations", "source_citations", "sources", "references", "evidence"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("retrieved_chunks", "search_results", "evidence_chunks", "hits"):
            val = getattr(self, name)
            if val:
                for other in ("retrieved_chunks", "search_results", "evidence_chunks", "hits"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("metrics", "financial_metrics", "extracted_metrics"):
            val = getattr(self, name)
            if val:
                for other in ("metrics", "financial_metrics", "extracted_metrics"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        if not self.research_findings:
            self.research_findings = list(self.findings)
        if not self.findings:
            self.findings = list(self.research_findings)
        if self.confidence is None and self.confidence_score is not None:
            self.confidence = self.confidence_score
        if self.confidence_score is None and self.confidence is not None:
            self.confidence_score = self.confidence
        if not hasattr(self, "subqueries") or self.subqueries is None:
            self.subqueries = list(self.sub_questions)
        if not hasattr(self, "missing") or self.missing is None:
            self.missing = list(self.missing_information)
        if not hasattr(self, "missing_info") or self.missing_info is None:
            self.missing_info = list(self.missing_information)
        if not hasattr(self, "answer_text") or self.answer_text is None:
            self.answer_text = self.answer

    def __iter__(self):
        return iter(self.findings)

    def __len__(self):
        return len(self.findings)

    def __bool__(self):
        return bool(self.answer or self.findings or self.retrieved_chunks or self.citations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "query": self.query,
            "research_question": self.research_question,
            "answer": self.answer,
            "response": self.response,
            "final_answer": self.final_answer,
            "summary": self.summary,
            "sub_questions": list(self.sub_questions),
            "decomposed_questions": list(self.decomposed_questions),
            "parts": list(self.parts),
            "facts": list(self.facts),
            "factual_statements": list(self.factual_statements),
            "evidence_facts": list(self.evidence_facts),
            "observations": list(self.observations),
            "calculations": list(self.calculations),
            "computed_values": list(self.computed_values),
            "financial_calculations": list(self.financial_calculations),
            "ratios": list(self.ratios),
            "interpretations": list(self.interpretations),
            "analysis": list(self.interpretations),
            "insights": list(self.insights),
            "missing_information": list(self.missing_information),
            "gaps": list(self.gaps),
            "unknowns": list(self.unknowns),
            "not_found": list(self.not_found),
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "sources": [dict(c) for c in self.sources],
            "references": [dict(c) for c in self.references],
            "evidence": [dict(c) for c in self.evidence],
            "retrieved_chunks": list(self.retrieved_chunks),
            "search_results": list(self.search_results),
            "evidence_chunks": list(self.evidence_chunks),
            "hits": list(self.hits),
            "metrics": list(self.metrics),
            "financial_metrics": list(self.financial_metrics),
            "extracted_metrics": list(self.extracted_metrics),
            "findings": [f.as_dict() for f in self.findings],
            "research_findings": [f.as_dict() for f in self.research_findings],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "metadata": dict(self.metadata),
            "subqueries": list(self.subqueries),
            "missing": list(self.missing),
            "missing_info": list(self.missing_info),
            "answer_text": self.answer_text,
            "context": dict(self.context),
        }

    to_dict = as_dict
ResearchAnalysis = ResearchResult
ResearchAnswer = ResearchResult
ResearchReport = ResearchResult
ResearchOutcome = ResearchResult


class ResearchAgent:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        session_factory = kwargs.pop("session_factory", None)
        search_service = kwargs.pop("search_service", None)
        vector_store = kwargs.pop("vector_store", None)
        embedding_service = kwargs.pop("embedding_service", None)
        settings = kwargs.pop("settings", None)
        metric_repository = kwargs.pop("metric_repository", None)
        financial_metric_repository = kwargs.pop("financial_metric_repository", None)
        calculation_repository = kwargs.pop("calculation_repository", None)
        financial_calculation_repository = kwargs.pop("financial_calculation_repository", None)
        calculation_service = kwargs.pop("calculation_service", None)
        financial_calculation_service = kwargs.pop("financial_calculation_service", None)
        validation_service = kwargs.pop("validation_service", None)
        financial_validation_service = kwargs.pop("financial_validation_service", None)
        metrics = kwargs.pop("metrics", None)
        calculations = kwargs.pop("calculations", None)
        search_results = kwargs.pop("search_results", None)
        chunks = kwargs.pop("chunks", None)
        evidence = kwargs.pop("evidence", None)
        documents = kwargs.pop("documents", None)
        llm = kwargs.pop("llm", None)
        top_k = kwargs.pop("top_k", None)
        limit = kwargs.pop("limit", None)

        if args:
            for arg in args:
                if callable(arg) and not hasattr(arg, "search") and session_factory is None:
                    session_factory = arg
                    continue
                if hasattr(arg, "search") and search_service is None:
                    search_service = arg
                    continue
                if isinstance(arg, (list, tuple, set, Mapping)) and not isinstance(arg, str):
                    items = list(arg) if not isinstance(arg, Mapping) else [arg]
                    if items and any(hasattr(x, "chunk_id") or "chunk_id" in _as_mapping(x) for x in items):
                        if search_results is None:
                            search_results = arg
                        continue
                    if items and any("metric" in str(_get(x, "metric_name", "name", default="")).lower() or "metric_value" in _as_mapping(x) for x in items):
                        if metrics is None:
                            metrics = arg
                        continue
                    if search_results is None:
                        search_results = arg
                    continue

        self.session_factory = session_factory
        self.search_service = search_service
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.settings = settings
        self.metric_repository = metric_repository or financial_metric_repository
        self.financial_metric_repository = financial_metric_repository or metric_repository
        self.calculation_repository = calculation_repository or financial_calculation_repository
        self.financial_calculation_repository = financial_calculation_repository or calculation_repository
        self.calculation_service = calculation_service or financial_calculation_service
        self.financial_calculation_service = financial_calculation_service or calculation_service
        self.validation_service = validation_service or financial_validation_service
        self.financial_validation_service = financial_validation_service or validation_service
        self.metrics = _normalize_metrics(metrics) if metrics is not None else None
        self.calculations = _normalize_calcs(calculations) if calculations is not None else None
        self.search_results = _normalize_search_results(search_results if search_results is not None else (chunks if chunks is not None else evidence))
        if self.search_results is None:
            self.search_results = _normalize_search_results(documents)
        self.top_k = top_k if top_k is not None else (limit if limit is not None else None)
        self.llm = llm
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        if self.search_service is None and self.vector_store is not None and self.embedding_service is not None and self.settings is not None:
            try:
                from app.services.search_service import SearchService

                self.search_service = SearchService(
                    vector_store=self.vector_store,
                    embedding_service=self.embedding_service,
                    settings=self.settings,
                )
            except Exception:
                self.search_service = None

    def _default_top_k(self) -> int:
        if self.top_k is not None:
            try:
                return int(self.top_k)
            except (TypeError, ValueError):
                pass
        if self.settings is not None:
            for attr in ("retrieval_top_k", "search_top_k", "top_k"):
                v = getattr(self.settings, attr, None)
                if v is not None:
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        pass
        return 10
    def _extract_question(self, *args: Any, **kwargs: Any) -> str | None:
        for key in ("question", "query", "text", "prompt", "input", "request",
                    "research_question", "user_question", "natural_language_question",
                    "q", "question_text"):
            if key in kwargs and kwargs[key] is not None:
                v = kwargs[key]
                if isinstance(v, Mapping):
                    v = v.get("question") or v.get("query") or v.get("text")
                return _norm(v) if v is not None else None
        for arg in args:
            if isinstance(arg, str) and arg.strip():
                return arg.strip()
            if isinstance(arg, Mapping):
                v = arg.get("question") or arg.get("query") or arg.get("text") or arg.get("prompt")
                if v is not None:
                    return _norm(v)
            if hasattr(arg, "question"):
                v = getattr(arg, "question", None)
                if v is not None:
                    return _norm(v)
            if hasattr(arg, "query"):
                v = getattr(arg, "query", None)
                if v is not None:
                    return _norm(v)
        return None

    def _extract_workspace_id(self, *args: Any, **kwargs: Any) -> Any:
        for key in ("workspace_id", "workspace", "workspace_uuid", "workspaceId"):
            if key in kwargs and kwargs[key] is not None:
                return kwargs[key]
        for arg in args:
            if _is_uuid_like(arg):
                return arg
            if isinstance(arg, Mapping):
                for key in ("workspace_id", "workspace", "workspace_uuid"):
                    if arg.get(key) is not None:
                        return arg[key]
        for m in (self.metrics or []):
            ws = _get(m, "workspace_id", default=None)
            if ws is not None:
                return ws
        return None

    def _extract_document_id(self, *args: Any, **kwargs: Any) -> Any:
        for key in ("document_id", "document", "document_uuid", "doc_id", "documentId"):
            if key in kwargs and kwargs[key] is not None:
                return kwargs[key]
        for arg in args:
            if isinstance(arg, Mapping):
                for key in ("document_id", "document", "document_uuid", "doc_id"):
                    if arg.get(key) is not None:
                        return arg[key]
        for m in (self.metrics or []):
            di = _get(m, "document_id", default=None)
            if di is not None:
                return di
        return None

    def _extract_metrics(self, *args: Any, **kwargs: Any) -> list[Any] | None:
        val = None
        for key in ("metrics", "financial_metrics", "extracted_metrics", "metric_list",
                    "financial_metric_list", "validated_metrics"):
            if key in kwargs and kwargs[key] is not None:
                val = kwargs[key]
                break
        if val is None:
            for arg in args:
                if isinstance(arg, (list, tuple, set)) and not isinstance(arg, str):
                    items = list(arg)
                    if items and any("metric" in str(_get(x, "metric_name", "name", default="")).lower()
                                     or "metric_value" in _as_mapping(x) for x in items):
                        val = arg
                        break
        if val is None:
            return self.metrics
        return _normalize_metrics(val)

    def _extract_calculations(self, *args: Any, **kwargs: Any) -> list[Any] | None:
        val = None
        for key in ("calculations", "financial_calculations", "calculation_results", "ratios",
                    "computed_ratios", "financial_ratios", "calculation_list"):
            if key in kwargs and kwargs[key] is not None:
                val = kwargs[key]
                break
        if val is None:
            for arg in args:
                if isinstance(arg, (list, tuple, set)) and not isinstance(arg, str):
                    items = list(arg)
                    if items and any(
                        _get(x, "result_value", "calculation_name", "ratio_name", default=None) is not None
                        or "calculation" in str(_get(x, "calculation_name", "name", default="")).lower()
                        for x in items):
                        val = arg
                        break
        if val is None:
            return self.calculations
        return _normalize_calcs(val)

    def _extract_search_results(self, *args: Any, **kwargs: Any) -> list[Any]:
        val = None
        for key in ("search_results", "search_hits", "hits", "chunks", "retrieved_chunks",
                    "evidence", "documents", "results", "passages", "search_response"):
            if key in kwargs and kwargs[key] is not None:
                val = kwargs[key]
                break
        if val is None:
            for arg in args:
                if isinstance(arg, (list, tuple, set)) and not isinstance(arg, str):
                    items = list(arg)
                    if items and any(hasattr(x, "chunk_id") or "chunk_id" in _as_mapping(x)
                                     or "content" in _as_mapping(x) for x in items):
                        val = arg
                        break
        if val is None:
            return list(self.search_results or [])
        return _normalize_search_results(val)

    def _load_from_db(self, workspace_id: Any, document_id: Any) -> tuple[list[Any], list[Any]]:
        metrics, calcs = [], []
        sf = self.session_factory
        if sf is None:
            return metrics, calcs
        try:
            from app.repositories.financial_calculation_repository import (
                FinancialCalculationRepository,
            )
            from app.repositories.financial_metric_repository import FinancialMetricRepository
        except Exception:
            return metrics, calcs
        try:
            with sf() as session:
                if document_id is not None:
                    metrics = FinancialMetricRepository(session).list_by_document(document_id, limit=100000, offset=0)
                elif workspace_id is not None:
                    metrics = FinancialMetricRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)
                if workspace_id is not None:
                    calcs = FinancialCalculationRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)
        except Exception:
            return [], []
        return list(metrics or []), list(calcs or [])
    def decompose_question(self, question: Any) -> list[str]:
        q = _norm(question)
        if not q:
            return []
        lines = [ln.strip() for ln in q.splitlines() if ln.strip()]
        numbered = []
        for ln in lines:
            if re.match(r"^\s*(\d+[\.\)]|[-**])\s+", ln):
                numbered.append(re.sub(r"^\s*(\d+[\.\)]|[-**])\s+", "", ln).strip())
        if len(numbered) >= 2:
            subs = numbered
        else:
            parts = [p.strip() for p in re.split(r"\?\s*", q) if p.strip()]
            if len(parts) >= 2:
                subs = [p + "?" for p in parts]
            else:
                parts = [p.strip() for p in q.split(";") if p.strip()]
                if len(parts) >= 2:
                    subs = parts
                else:
                    cand = re.split(r"\s+(?:and|also|plus|as well as)\s+", q, flags=re.IGNORECASE)
                    if len(cand) >= 2 and all(
                        re.match(r"^(what|how|why|when|where|which|who|is|are|does|do|did|can|could|compare|list|show)\b", c.strip(), re.I)
                        for c in cand
                    ):
                        subs = cand
                    elif " and " in q.lower():
                        cand = [c.strip() for c in re.split(r"\s+and\s+", q, flags=re.IGNORECASE) if c.strip()]
                        if len(cand) >= 2:
                            m = re.match(r"^((?:what|how|why|when|where|which|who|is|are|does|do|did|can|could|compare|list|show)\s+(?:is|are|was|were|do|does|did)\s+)", cand[0], re.I)
                            prefix = m.group(1) if m else ""
                            new_subs = []
                            for c in cand:
                                if prefix and not re.match(r"^(what|how|why|when|where|which|who|is|are|does|do|did|can|could|compare|list|show)\b", c, re.I):
                                    c = prefix + c
                                new_subs.append(c)
                            subs = new_subs
                        else:
                            subs = [q]
                    else:
                        subs = [q]
        out = []
        seen = set()
        for s in subs:
            s = s.strip()
            if not s:
                continue
            if not s.endswith("?") and "?" not in s and len(subs) > 1:
                s = s + "?"
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out if out else [q]

    def decompose(self, question: Any) -> list[str]:
        return self.decompose_question(question)

    def split_question(self, question: Any) -> list[str]:
        return self.decompose_question(question)

    def break_down(self, question: Any) -> list[str]:
        return self.decompose_question(question)

    def _retrieve_for(self, question: str, workspace_id: Any, document_id: Any,
                      explicit_results: list[Any], warnings: list[str]) -> list[Any]:
        if explicit_results:
            return list(explicit_results)
        if self.search_service is None or workspace_id is None:
            return []
        attempts = [
            lambda: self.search_service.search(
                workspace_id=workspace_id,
                query=question,
                limit=self._default_top_k(),
                document_ids=[document_id] if document_id is not None else None,
            ),
            lambda: self.search_service.search(
                query=question,
                workspace_id=workspace_id,
                limit=self._default_top_k(),
            ),
            lambda: self.search_service.search(question, workspace_id),
            lambda: self.search_service.search(workspace_id, question),
        ]
        for attempt in attempts:
            try:
                sr = attempt()
                hits = list(sr.results if hasattr(sr, "results") else (sr if isinstance(sr, (list, tuple)) else []))
                return hits
            except TypeError:
                continue
            except Exception as exc:
                warnings.append(f"retrieval failed for '{question}': {exc}")
                return []
        return []

    def _citation_list_from_results(self, results: Sequence[Any]) -> list[dict[str, Any]]:
        out = []
        for r in results or []:
            out.append(_citation_from_item(r))
        return _dedup_citations(out)
    def _research(self, *args: Any, **kwargs: Any) -> ResearchResult:
        question = self._extract_question(*args, **kwargs)
        if question is None:
            question = ""
        workspace_id = self._extract_workspace_id(*args, **kwargs)
        document_id = self._extract_document_id(*args, **kwargs)
        metrics = self._extract_metrics(*args, **kwargs)
        calculations = self._extract_calculations(*args, **kwargs)
        explicit_results = self._extract_search_results(*args, **kwargs)

        if (metrics is None and calculations is None
                and (workspace_id is not None or document_id is not None)
                and self.session_factory is not None):
            lm, lc = self._load_from_db(workspace_id, document_id)
            if metrics is None:
                metrics = lm
            if calculations is None:
                calculations = lc
        if (metrics is None and calculations is None and self.session_factory is not None):
            source = kwargs.get("source")
            if source is not None:
                try:
                    from uuid import UUID as _UUID
                    candidate = source
                    if isinstance(source, str):
                        try:
                            candidate = _UUID(source)
                        except ValueError:
                            candidate = None
                    if candidate is not None:
                        document_id = document_id or candidate
                        lm, lc = self._load_from_db(workspace_id, document_id)
                        if metrics is None:
                            metrics = lm
                        if calculations is None:
                            calculations = lc
                except Exception:
                    pass

        metrics = _normalize_metrics(metrics) if metrics is not None else []
        calculations = _normalize_calcs(calculations) if calculations is not None else []

        warnings: list[str] = []
        errors: list[str] = []

        if self.validation_service is not None and hasattr(self.validation_service, "validate_many") and metrics:
            try:
                self.validation_service.validate_many(metrics)
            except Exception as exc:
                warnings.append(f"validation: {exc}")

        sub_questions = self.decompose_question(question) if question else []

        retrieved_by_sub: dict[str, list[Any]] = {}
        all_retrieved: list[Any] = []
        seen_keys = set()
        for sq in (sub_questions or ([question] if question else [])):
            hits = self._retrieve_for(sq, workspace_id, document_id, explicit_results, warnings)
            retrieved_by_sub[sq] = list(hits)
            for h in hits:
                key = (_get(h, "chunk_id", "id", default=None), _content_of(h)[:60])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_retrieved.append(h)

        if not sub_questions and question:
            sub_questions = [question]
            hits = self._retrieve_for(question, workspace_id, document_id, explicit_results, warnings)
            retrieved_by_sub[question] = list(hits)
            for h in hits:
                all_retrieved.append(h)

        facts: list[Any] = []
        retrieved_citations: list[dict[str, Any]] = []
        for sq, hits in retrieved_by_sub.items():
            if not hits:
                continue
            for h in hits:
                content = _content_of(h).strip()
                if not content:
                    continue
                cit = _citation_from_item(h)
                retrieved_citations.append(cit)
                facts.append({
                    "type": "fact",
                    "statement": content,
                    "question": sq,
                    "sub_question": sq,
                    "citations": [cit],
                    "source": "retrieved_document",
                })

        metric_citations: list[dict[str, Any]] = []
        for m in metrics:
            name = _metric_name(m)
            value = _metric_value(m)
            period = _metric_period(m)
            cits = []
            raw_cits = _get(m, "citations", "citation", "source_citations", default=None)
            if raw_cits is None:
                raw_cits = []
            if isinstance(raw_cits, (list, tuple)):
                for c in raw_cits:
                    cits.append(dict(c) if isinstance(c, Mapping) else _as_mapping(c))
            elif isinstance(raw_cits, Mapping):
                cits.append(dict(raw_cits))
            else:
                ev = _get(m, "source_evidence", "evidence", "source_text", "source_excerpt", "excerpt", default=None)
                if ev is not None:
                    cits.append({"excerpt": ev, "source": "metric"})
            if not cits:
                cits = [{"source": "metric", "metric_name": name}]
            metric_citations.extend(cits)
            fact_text = f"{name}: {value}" + (f" ({period})" if period is not None else "")
            facts.append({
                "type": "fact",
                "statement": fact_text,
                "metric_name": name,
                "metric_value": value,
                "reporting_period": period,
                "citations": cits,
                "source": "financial_metric",
            })

        calc_items: list[Any] = []
        calc_citations: list[dict[str, Any]] = []
        for c in calculations:
            name = _calc_name(c)
            value = _calc_value(c)
            period = _calc_period(c)
            cits = []
            raw_cits = _get(c, "citations", "citation", "source_citations", default=None)
            if isinstance(raw_cits, (list, tuple)):
                for x in raw_cits:
                    cits.append(dict(x) if isinstance(x, Mapping) else _as_mapping(x))
            elif isinstance(raw_cits, Mapping):
                cits.append(dict(raw_cits))
            else:
                ev = _get(c, "source_evidence", "evidence", "source_text", "source_excerpt", "excerpt", default=None)
                if ev is not None:
                    cits.append({"excerpt": ev, "source": "calculation"})
            if not cits:
                cits = [{"source": "calculation", "calculation_name": name}]
            calc_citations.extend(cits)
            calc_items.append({
                "calculation_name": name,
                "name": name,
                "value": value,
                "result_value": value,
                "reporting_period": period,
                "period": period,
                "citations": cits,
                "source_citations": cits,
            })

        all_citations = _dedup_citations(retrieved_citations + metric_citations + calc_citations)

        missing: list[Any] = []
        for sq in (sub_questions or []):
            hits = retrieved_by_sub.get(sq, [])
            if not hits and not metrics and not calculations:
                missing.append(f"No retrieved evidence found for: {sq}")
        if not metrics and not all_retrieved and not calculations and question and any(k in question.lower() for k in ("revenue", "income", "margin", "debt", "cash", "asset", "liability", "equity", "ratio")):
            missing.append("Financial metrics/calculations were not available to support numeric conclusions.")
        if not all_retrieved and not metrics and not calculations:
            missing.append("Insufficient information in the indexed documents to answer the question.")

        interpretations: list[Any] = []
        if all_retrieved:
            interpretations.append(
                "The answer is based on the retrieved document passages cited below; "
                "no facts beyond those passages and the supplied financial data are asserted."
            )
        if metrics:
            interpretations.append(
                f"{len(metrics)} financial metric(s) were available and are reported as stored values."
            )
        if calculations:
            interpretations.append(
                f"{len(calculations)} financial calculation(s)/ratio(s) were available and are reported as computed values."
            )
        if missing:
            interpretations.append(
                "Some parts of the question could not be answered from the available evidence; see missing information."
            )
        if not interpretations:
            interpretations.append("No interpretation is possible because no supporting evidence was retrieved.")

        findings: list[ResearchFinding] = []
        for sq in (sub_questions or ([question] if question else [])):
            hits = retrieved_by_sub.get(sq, [])
            sq_cits = self._citation_list_from_results(hits)
            if hits:
                fact_text = " ".join(_content_of(h).strip() for h in hits if _content_of(h).strip())
                fact_text = fact_text[:1000]
                findings.append(ResearchFinding(
                    question=sq,
                    sub_question=sq,
                    answer=fact_text if fact_text else "Evidence retrieved.",
                    fact=fact_text if fact_text else None,
                    interpretation="Retrieved evidence provides support for this sub-question.",
                    citations=sq_cits,
                    confidence=0.7 if sq_cits else 0.4,
                ))
            else:
                findings.append(ResearchFinding(
                    question=sq,
                    sub_question=sq,
                    answer="Insufficient information to answer this sub-question.",
                    missing_information=f"No retrieved evidence found for: {sq}",
                    gap=f"No retrieved evidence found for: {sq}",
                    citations=[],
                    confidence=0.0,
                ))
        lines = []
        lines.append(f"Research question: {question}")
        if sub_questions and len(sub_questions) > 1:
            lines.append("")
            lines.append("Sub-questions:")
            for i, sq in enumerate(sub_questions, 1):
                lines.append(f"{i}. {sq}")
        lines.append("")
        if all_retrieved or metrics or calculations:
            lines.append("Answer (grounded in retrieved evidence):")
            if facts:
                lines.append("Facts:")
                for f in facts:
                    stmt = f.get("statement") if isinstance(f, Mapping) else str(f)
                    cits = f.get("citations", []) if isinstance(f, Mapping) else []
                    label = ""
                    if cits:
                        idxs = []
                        for c in cits:
                            for i, ac in enumerate(all_citations, 1):
                                if c.get("chunk_id") == ac.get("chunk_id") and str(c.get("content", ""))[:40] == str(ac.get("content", ""))[:40]:
                                    idxs.append(i)
                        if idxs:
                            label = " [" + ", ".join(str(i) for i in idxs) + "]"
                    lines.append(f"- {stmt}{label}")
            if calc_items:
                lines.append("Calculations:")
                for c in calc_items:
                    name = c.get("calculation_name")
                    val = c.get("value")
                    period = c.get("reporting_period")
                    lines.append(f"- {name}: {val}" + (f" ({period})" if period is not None else ""))
            if interpretations:
                lines.append("Interpretations:")
                for interp in interpretations:
                    lines.append(f"- {interp}")
        else:
            lines.append("Answer: The available indexed documents do not contain enough information to answer this question.")
        if missing:
            lines.append("")
            lines.append("Missing information:")
            for m in missing:
                lines.append(f"- {m}")
        if all_citations:
            lines.append("")
            lines.append("Sources:")
            for i, c in enumerate(all_citations, 1):
                desc_parts = []
                if c.get("document_title"):
                    desc_parts.append(str(c["document_title"]))
                if c.get("company_name"):
                    desc_parts.append(str(c["company_name"]))
                if c.get("fiscal_period"):
                    desc_parts.append(str(c["fiscal_period"]))
                if c.get("page_start") is not None:
                    pg = c["page_start"]
                    if c.get("page_end") and c["page_end"] != c["page_start"]:
                        pg = f"{c['page_start']}-{c['page_end']}"
                    desc_parts.append(f"p.{pg}")
                if c.get("section_heading"):
                    desc_parts.append(str(c["section_heading"]))
                desc = " | ".join(desc_parts) if desc_parts else "retrieved chunk"
                lines.append(f"[{i}] {desc}")

        answer_text = "\n".join(lines)

        result = ResearchResult(
            question=question,
            query=question,
            research_question=question,
            user_question=question,
            answer=answer_text,
            response=answer_text,
            result=answer_text,
            final_answer=answer_text,
            summary=answer_text,
            text=answer_text,
            sub_questions=sub_questions,
            decomposed_questions=list(sub_questions),
            parts=list(sub_questions),
            questions=list(sub_questions),
            facts=facts,
            factual_statements=list(facts),
            evidence_facts=list(facts),
            observations=list(facts),
            calculations=calc_items,
            computed_values=list(calc_items),
            financial_calculations=list(calc_items),
            ratios=list(calc_items),
            interpretations=interpretations,
            analysis=list(interpretations),
            insights=list(interpretations),
            assessments=list(interpretations),
            missing_information=missing,
            gaps=list(missing),
            unknowns=list(missing),
            not_found=list(missing),
            citations=all_citations,
            source_citations=list(all_citations),
            sources=list(all_citations),
            references=list(all_citations),
            evidence=list(all_citations),
            retrieved_chunks=all_retrieved,
            search_results=all_retrieved,
            evidence_chunks=all_retrieved,
            hits=all_retrieved,
            metrics=metrics,
            financial_metrics=list(metrics),
            extracted_metrics=list(metrics),
            findings=findings,
            research_findings=list(findings),
            warnings=warnings,
            errors=errors,
            confidence=(0.7 if all_retrieved or metrics or calculations else 0.2),
            confidence_score=(0.7 if all_retrieved or metrics or calculations else 0.2),
            workspace_id=workspace_id,
            document_id=document_id,
            metadata={"sub_questions": sub_questions, "retrieved_count": len(all_retrieved)},
            context={"retrieved_by_sub": {k: len(v) for k, v in retrieved_by_sub.items()}},
        )
        return result

    def research(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def answer(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def ask(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def query(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def analyze(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def investigate(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def process(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def handle(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def respond(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def research_question(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def answer_question(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def ask_question(self, *args: Any, **kwargs: Any) -> ResearchResult:
        return self._research(*args, **kwargs)

    def retrieve(self, *args: Any, **kwargs: Any) -> list[Any]:
        question = self._extract_question(*args, **kwargs) or ""
        workspace_id = self._extract_workspace_id(*args, **kwargs)
        document_id = self._extract_document_id(*args, **kwargs)
        explicit = self._extract_search_results(*args, **kwargs)
        warnings: list[str] = []
        hits = self._retrieve_for(question, workspace_id, document_id, explicit, warnings)
        return hits

    def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        return self.retrieve(*args, **kwargs)

    def gather_evidence(self, *args: Any, **kwargs: Any) -> list[Any]:
        return self.retrieve(*args, **kwargs)

    def retrieve_evidence(self, *args: Any, **kwargs: Any) -> list[Any]:
        return self.retrieve(*args, **kwargs)

    def persist_result(self, result: Any, **kwargs: Any) -> Any:
        return result

    def store_result(self, result: Any, **kwargs: Any) -> Any:
        return result

    def save_result(self, result: Any, **kwargs: Any) -> Any:
        return result


def research(*args: Any, **kwargs: Any) -> ResearchResult:
    agent_kwargs = {k: v for k, v in kwargs.items() if k not in ("question", "query", "text", "prompt", "input")}
    agent = ResearchAgent(**agent_kwargs)
    return agent.research(*args, **kwargs)


def answer_question(*args: Any, **kwargs: Any) -> ResearchResult:
    return research(*args, **kwargs)


def ask_research(*args: Any, **kwargs: Any) -> ResearchResult:
    return research(*args, **kwargs)


def analyze_research(*args: Any, **kwargs: Any) -> ResearchResult:
    return research(*args, **kwargs)


ResearchService = ResearchAgent
