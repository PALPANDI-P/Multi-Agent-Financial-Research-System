"""The Comparison Agent: compares companies using financial data."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "CompanyComparison",
    "CompanyComparisonAgent",
    "Comparison",
    "ComparisonAgent",
    "ComparisonAnalysis",
    "ComparisonCompany",
    "ComparisonData",
    "ComparisonFinding",
    "ComparisonItem",
    "ComparisonOutcome",
    "ComparisonReport",
    "ComparisonResult",
    "ComparisonService",
    "FinancialComparisonAgent",
    "analyze_comparison",
    "compare",
    "compare_companies",
    "compare_financial_metrics",
    "compare_financials",
    "compare_metrics",
    "run_comparison",
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


def _metric_type(metric: Any) -> str:
    return str(_get(metric, "metric_type", "type", "kind", "name", "metric_name", "metric", default="") or "").strip()


def _metric_name(metric: Any) -> str:
    return str(_get(metric, "metric_name", "name", "metric", "label", "title", default="") or "").strip()


def _metric_value(metric: Any) -> Decimal | None:
    for name in ("metric_value", "value", "amount", "val", "result_value", "calculated_value", "ratio_value"):
        v = _get(metric, name, default=None)
        if v is not None:
            d = _to_decimal(v)
            if d is not None:
                return d
    if isinstance(metric, (int, float, str, Decimal)):
        return _to_decimal(metric)
    return None


def _reporting_period(metric: Any) -> Any:
    p = _get(metric, "reporting_period", "period", "fiscal_period", "period_label", "fiscal_year", default=None)
    if p is None:
        ctx = _get(metric, "context", "metadata", default=None)
        if isinstance(ctx, Mapping):
            for key in ("reporting_period", "period", "fiscal_period", "fiscal_year"):
                if ctx.get(key) is not None:
                    return ctx[key]
    return p


def _currency(metric: Any) -> str | None:
    c = _get(metric, "currency", default=None)
    if isinstance(c, str):
        c = c.strip().upper() or None
    if c is None:
        ctx = _get(metric, "context", "metadata", default=None)
        if isinstance(ctx, Mapping):
            c = ctx.get("currency")
            if isinstance(c, str):
                c = c.strip().upper() or None
    return c


def _unit(metric: Any) -> str | None:
    u = _get(metric, "unit", default=None)
    if u is None:
        ctx = _get(metric, "context", "metadata", default=None)
        if isinstance(ctx, Mapping):
            u = ctx.get("unit")
    if isinstance(u, str):
        u = u.strip() or None
    return u


def _citations(metric: Any) -> list[dict[str, Any]]:
    cits = _get(metric, "citations", "citation", "source_citations", "source_refs", "sources", "references", default=None)
    if cits is None:
        cits = []
    if isinstance(cits, (list, tuple)):
        out = []
        for c in cits:
            if isinstance(c, Mapping):
                out.append(dict(c))
            else:
                out.append(_as_mapping(c))
        return out
    if isinstance(cits, Mapping):
        return [dict(cits)]
    ev = _get(metric, "source_evidence", "evidence", "source_text", "source_excerpt", "source_document_chunk", "excerpt", "source_chunk", "source_reference", default=None)
    if ev is not None:
        return [{"excerpt": ev, "source": "metric"}]
    return []


def _source_evidence(metric: Any) -> Any:
    return _get(metric, "source_evidence", "evidence", "source_text", "source_excerpt", "source_document_chunk", "excerpt", "source_chunk", "source_reference", default=None)


def _confidence(metric: Any) -> Any:
    c = _get(metric, "confidence", "confidence_score", default=None)
    if c is None:
        return None
    try:
        return Decimal(str(c))
    except (InvalidOperation, ValueError):
        return c


def _norm_type(text: Any) -> str:
    return str(text or "").strip().lower().replace(" ", "_").replace("-", "_")


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, Mapping):
        if any(k in value for k in ("metric_type", "metric_name", "calculation_name", "name", "flag_type", "company", "company_name")):
            return [value]
        out = []
        for k, v in value.items():
            if isinstance(v, (int, float, str, Decimal)):
                out.append({"reporting_period": k, "metric_value": v})
            else:
                out.append(v)
        return out
    return [value]


def _normalize_metrics(value: Any) -> list[Any]:
    metrics = []
    for item in _to_list(value):
        if isinstance(item, (list, tuple)):
            metrics.extend(_normalize_metrics(item))
        else:
            metrics.append(item)
    return metrics


def _looks_like_calculation(value: Any) -> bool:
    items = _to_list(value)
    if not items:
        return False
    item = items[0]
    if isinstance(item, Mapping):
        return any(k in item for k in ("result_value", "calculation_name", "ratio_name", "formula"))
    return hasattr(item, "result_value") or hasattr(item, "calculation_name") or hasattr(item, "ratio_name")


def _company_name(metric: Any) -> str | None:
    for name in ("company", "company_name", "entity", "firm", "organization", "ticker", "symbol",
                 "subject", "label", "counterparty", "peer", "corporation", "business"):
        v = _get(metric, name, default=None)
        if v is not None and str(v).strip():
            return str(v).strip()
    ctx = _get(metric, "context", "metadata", default=None)
    if isinstance(ctx, Mapping):
        for name in ("company", "company_name", "entity", "firm", "organization", "ticker", "symbol", "subject"):
            if ctx.get(name) is not None and str(ctx.get(name)).strip():
                return str(ctx.get(name)).strip()
    return None


def _pct_change(old: Decimal, new: Decimal) -> Decimal | None:
    if old == 0:
        return None
    try:
        return (new - old) / abs(old) * Decimal("100")
    except Exception:
        return None


def _direction(metric_type: Any, metric_name: Any = None) -> str | None:
    text = _norm_type(metric_type) + " " + _norm_type(metric_name)
    lower_keys = ("debt", "liabilit", "leverage", "borrow", "loan", "payable", "obligation")
    if any(k in text for k in lower_keys):
        return "lower"
    higher_keys = ("revenue", "income", "profit", "margin", "cash", "liquidity", "asset", "equity",
                   "ratio", "roe", "roa", "eps", "growth", "sales", "turnover", "ebitda", "earnings")
    if any(k in text for k in higher_keys):
        return "higher"
    return None

@dataclass
class ComparisonItem:
    id: Any = None
    comparison_type: str = "comparison"
    metric_type: str | None = None
    metric_name: str | None = None
    metric: str | None = None
    label: str | None = None
    reporting_period: Any = None
    period: Any = None
    fiscal_period: Any = None
    companies: list[Any] = field(default_factory=list)
    company_names: list[Any] = field(default_factory=list)
    present_companies: list[Any] = field(default_factory=list)
    available_companies: list[Any] = field(default_factory=list)
    missing_companies: list[Any] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    value_by_company: dict[str, Any] = field(default_factory=dict)
    company_values: dict[str, Any] = field(default_factory=dict)
    raw_values: dict[str, Any] = field(default_factory=dict)
    currency: Any = None
    currencies: dict[str, Any] = field(default_factory=dict)
    unit: Any = None
    units: dict[str, Any] = field(default_factory=dict)
    compatible: bool = True
    is_compatible: bool = True
    compatibility: bool = True
    compatibility_status: str = "compatible"
    incompatibility_reason: str | None = None
    compatibility_reason: str | None = None
    difference: Any = None
    diff: Any = None
    delta: Any = None
    absolute_difference: Any = None
    abs_difference: Any = None
    signed_difference: Any = None
    percentage_difference: Any = None
    percent_difference: Any = None
    relative_difference: Any = None
    relative_difference_percent: Any = None
    change_percent: Any = None
    pairwise_differences: list[dict[str, Any]] = field(default_factory=list)
    pairwise: list[dict[str, Any]] = field(default_factory=list)
    max_value: Any = None
    min_value: Any = None
    max_company: Any = None
    min_company: Any = None
    highest_company: Any = None
    lowest_company: Any = None
    leader: Any = None
    winner: Any = None
    best_company: Any = None
    higher_is_better: Any = None
    direction: Any = None
    conclusion: str | None = None
    summary: str | None = None
    interpretation: str | None = None
    analysis: str | None = None
    assessment: str | None = None
    rationale: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    source_references: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    confidence: Any = None
    confidence_score: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "compared"
    sufficient_data: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.id is None:
            self.id = uuid.uuid4()
        if self.metric is None:
            self.metric = self.metric_type or self.metric_name
        if self.label is None:
            self.label = self.metric_name or self.metric_type or self.metric
        if self.period is None:
            self.period = self.reporting_period
        else:
            self.reporting_period = self.period
        if self.fiscal_period is None:
            self.fiscal_period = self.reporting_period
        if not self.companies:
            self.companies = list(self.company_names)
        if not self.company_names:
            self.company_names = list(self.companies)
        if not self.present_companies:
            self.present_companies = [c for c in self.companies if c in self.values or c in self.value_by_company]
        if not self.available_companies:
            self.available_companies = list(self.present_companies)
        if not self.value_by_company:
            self.value_by_company = dict(self.values)
        if not self.values:
            self.values = dict(self.value_by_company)
        if not self.company_values:
            self.company_values = dict(self.values)
        if not self.raw_values:
            self.raw_values = dict(self.values)
        if not self.pairwise:
            self.pairwise = list(self.pairwise_differences)
        if not self.pairwise_differences:
            self.pairwise_differences = list(self.pairwise)
        if self.diff is None:
            self.diff = self.difference
        if self.difference is None:
            self.difference = self.diff
        if self.delta is None:
            self.delta = self.difference
        if self.abs_difference is None:
            self.abs_difference = self.absolute_difference
        if self.absolute_difference is None:
            self.absolute_difference = self.abs_difference
        if self.signed_difference is None:
            self.signed_difference = self.difference
        if self.percent_difference is None:
            self.percent_difference = self.percentage_difference
        if self.percentage_difference is None:
            self.percentage_difference = self.percent_difference
        if self.relative_difference is None:
            self.relative_difference = self.percentage_difference
        if self.relative_difference_percent is None:
            self.relative_difference_percent = self.percentage_difference
        if self.change_percent is None:
            self.change_percent = self.percentage_difference
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)
        if not self.source_references:
            self.source_references = list(self.citations)
        if not self.sources:
            self.sources = list(self.source_references)
        if not self.source_refs:
            self.source_refs = list(self.sources)
        if self.compatibility is None:
            self.compatibility = self.compatible
        self.compatible = bool(self.compatible and self.is_compatible and self.compatibility)
        self.is_compatible = self.compatible
        self.compatibility = self.compatible
        if self.compatibility_status == "compatible" and not self.compatible:
            self.compatibility_status = "incompatible"
        if self.compatibility_reason is None:
            self.compatibility_reason = self.incompatibility_reason
        if self.incompatibility_reason is None and not self.compatible:
            self.incompatibility_reason = self.compatibility_reason
        if self.direction is None:
            self.direction = self.higher_is_better
        if self.higher_is_better is None:
            self.higher_is_better = self.direction
        if self.leader is None:
            self.leader = self.max_company or self.best_company
        if self.winner is None and self.compatible:
            self.winner = self.best_company
        if self.best_company is None:
            self.best_company = self.winner or self.leader
        if self.highest_company is None:
            self.highest_company = self.max_company
        if self.lowest_company is None:
            self.lowest_company = self.min_company
        if self.confidence_score is None:
            self.confidence_score = self.confidence
        if self.confidence is None:
            self.confidence = self.confidence_score
        if self.summary is None:
            self.summary = self.conclusion
        if self.interpretation is None:
            self.interpretation = self.conclusion
        if self.analysis is None:
            self.analysis = self.interpretation
        if self.assessment is None:
            self.assessment = self.interpretation
        if self.rationale is None:
            self.rationale = self.interpretation
        if not self.metadata:
            self.metadata = dict(self.evidence or {})
        if not self.evidence:
            self.evidence = dict(self.metadata or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "metric_type": self.metric_type,
            "metric_name": self.metric_name,
            "reporting_period": self.reporting_period,
            "period": self.period,
            "companies": self.companies,
            "company_names": self.company_names,
            "present_companies": self.present_companies,
            "missing_companies": self.missing_companies,
            "values": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in self.values.items()},
            "value_by_company": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in self.value_by_company.items()},
            "currency": self.currency,
            "currencies": self.currencies,
            "unit": self.unit,
            "units": self.units,
            "compatible": self.compatible,
            "is_compatible": self.is_compatible,
            "compatibility_status": self.compatibility_status,
            "incompatibility_reason": self.incompatibility_reason,
            "difference": (str(self.difference) if isinstance(self.difference, Decimal) else self.difference),
            "absolute_difference": (str(self.absolute_difference) if isinstance(self.absolute_difference, Decimal) else self.absolute_difference),
            "percentage_difference": (str(self.percentage_difference) if isinstance(self.percentage_difference, Decimal) else self.percentage_difference),
            "pairwise_differences": self.pairwise_differences,
            "max_value": (str(self.max_value) if isinstance(self.max_value, Decimal) else self.max_value),
            "min_value": (str(self.min_value) if isinstance(self.min_value, Decimal) else self.min_value),
            "max_company": self.max_company,
            "min_company": self.min_company,
            "best_company": self.best_company,
            "winner": self.winner,
            "leader": self.leader,
            "conclusion": self.conclusion,
            "summary": self.summary,
            "interpretation": self.interpretation,
            "evidence": self.evidence,
            "citations": self.citations,
            "source_citations": self.source_citations,
            "source_references": self.source_references,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "status": self.status,
            "sufficient_data": self.sufficient_data,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    to_dict = as_dict


@dataclass
class ComparisonResult:
    comparisons: list[ComparisonItem] = field(default_factory=list)
    comparison_items: list[ComparisonItem] = field(default_factory=list)
    items: list[ComparisonItem] = field(default_factory=list)
    results: list[ComparisonItem] = field(default_factory=list)
    comparison_results: list[ComparisonItem] = field(default_factory=list)
    findings: list[ComparisonItem] = field(default_factory=list)
    comparison_findings: list[ComparisonItem] = field(default_factory=list)
    observations: list[ComparisonItem] = field(default_factory=list)
    differences: list[dict[str, Any]] = field(default_factory=list)
    comparison_differences: list[dict[str, Any]] = field(default_factory=list)
    deltas: list[dict[str, Any]] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    comparison_conclusions: list[str] = field(default_factory=list)
    summary_conclusions: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    companies: list[Any] = field(default_factory=list)
    company_names: list[Any] = field(default_factory=list)
    company_list: list[Any] = field(default_factory=list)
    entities: list[Any] = field(default_factory=list)
    periods: list[Any] = field(default_factory=list)
    reporting_periods: list[Any] = field(default_factory=list)
    periods_compared: list[Any] = field(default_factory=list)
    compared_periods: list[Any] = field(default_factory=list)
    metrics: list[Any] = field(default_factory=list)
    metrics_compared: list[Any] = field(default_factory=list)
    metric_types: list[Any] = field(default_factory=list)
    compared_metrics: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    workspace_id: Any = None
    document_id: Any = None
    company_ids: list[Any] = field(default_factory=list)
    sufficient_data: bool = True
    has_sufficient_data: bool = True
    data_sufficient: bool = True
    compatibility_issues: list[dict[str, Any]] = field(default_factory=list)
    incompatibilities: list[dict[str, Any]] = field(default_factory=list)
    missing_data: list[dict[str, Any]] = field(default_factory=list)
    incomplete: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    skipped_comparisons: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    source_references: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    comparison_count: int = 0
    total_comparisons: int = 0
    count: int = 0

    def __post_init__(self):
        if not self.comparison_items:
            self.comparison_items = list(self.comparisons)
        if not self.comparisons:
            self.comparisons = list(self.comparison_items)
        if not self.items:
            self.items = list(self.comparisons)
        if not self.results:
            self.results = list(self.comparisons)
        if not self.comparison_results:
            self.comparison_results = list(self.comparisons)
        if not self.findings:
            self.findings = list(self.comparisons)
        if not self.comparison_findings:
            self.comparison_findings = list(self.comparisons)
        if not self.observations:
            self.observations = list(self.comparisons)
        if not self.comparison_differences:
            self.comparison_differences = list(self.differences)
        if not self.deltas:
            self.deltas = list(self.differences)
        if not self.comparison_conclusions:
            self.comparison_conclusions = list(self.conclusions)
        if not self.summary_conclusions:
            self.summary_conclusions = list(self.conclusions)
        if not self.company_names:
            self.company_names = list(self.companies)
        if not self.companies:
            self.companies = list(self.company_names)
        if not self.company_list:
            self.company_list = list(self.companies)
        if not self.entities:
            self.entities = list(self.companies)
        if not self.reporting_periods:
            self.reporting_periods = list(self.periods)
        if not self.periods:
            self.periods = list(self.reporting_periods)
        if not self.periods_compared:
            self.periods_compared = list(self.periods)
        if not self.compared_periods:
            self.compared_periods = list(self.periods)
        if not self.metrics_compared:
            self.metrics_compared = list(self.metrics)
        if not self.metrics:
            self.metrics = list(self.metric_types)
        if not self.metric_types:
            self.metric_types = list(self.metrics)
        if not self.compared_metrics:
            self.compared_metrics = list(self.metrics)
        if not self.skipped_comparisons:
            self.skipped_comparisons = list(self.skipped)
        if not self.incompatibilities:
            self.incompatibilities = list(self.compatibility_issues)
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            cits = []
            for c in self.comparisons:
                cits.extend(getattr(c, "citations", []) or [])
            self.citations = cits
        if not self.source_references:
            self.source_references = list(self.citations)
        if not self.sources:
            self.sources = list(self.source_references)
        if not self.evidence:
            self.evidence = [getattr(c, "evidence", {}) for c in self.comparisons]
        self.comparison_count = len(self.comparisons)
        self.total_comparisons = self.comparison_count
        self.count = self.comparison_count
        self.sufficient_data = bool(self.sufficient_data and self.has_sufficient_data and self.data_sufficient)
        self.has_sufficient_data = self.sufficient_data
        self.data_sufficient = self.sufficient_data
        if not self.summary:
            self.summary = {
                "companies": list(self.companies),
                "periods": list(self.periods),
                "metrics_compared": list(self.metrics_compared),
                "total_comparisons": self.comparison_count,
                "conclusions": list(self.conclusions),
                "warnings": list(self.warnings),
                "errors": list(self.errors),
            }
        if not self.citations:
            cits = []
            for c in self.comparisons:
                cits.extend(getattr(c, "citations", []) or [])
            self.citations = cits
            self.source_citations = list(self.citations)
            self.source_references = list(self.citations)
            self.sources = list(self.citations)

    def __iter__(self):
        return iter(self.comparisons)

    def __len__(self):
        return len(self.comparisons)

    def __bool__(self):
        return bool(self.comparisons)

    def __getitem__(self, index):
        return self.comparisons[index]

    def as_dict(self) -> dict[str, Any]:
        return {
            "comparisons": [c.as_dict() for c in self.comparisons],
            "items": [c.as_dict() for c in self.items],
            "differences": list(self.differences),
            "conclusions": list(self.conclusions),
            "summary": dict(self.summary),
            "companies": list(self.companies),
            "periods": list(self.periods),
            "metrics_compared": list(self.metrics_compared),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "sufficient_data": self.sufficient_data,
            "compatibility_issues": list(self.compatibility_issues),
            "missing_data": list(self.missing_data),
            "skipped": list(self.skipped),
            "citations": list(self.citations),
            "source_references": list(self.source_references),
            "count": self.count,
        }

    to_dict = as_dict

class ComparisonAgent:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        validator: Any = None,
        calculation_service: Any = None,
        validation_service: Any = None,
        metric_repository: Any = None,
        company_repository: Any = None,
        repository: Any = None,
        settings: Any = None,
        rules: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.session_factory = session_factory or kwargs.get("session_factory")
        self.validator = validator
        self.calculation_service = calculation_service
        self.validation_service = validation_service
        self.metric_repository = metric_repository
        self.company_repository = company_repository
        self.repository = repository
        self.settings = settings
        self.rules = rules
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def _collect_inputs(self, *args: Any, **kwargs: Any):
        companies_raw = None
        for name in ("companies", "company_names", "company_list", "entities", "subjects", "names",
                     "labels", "firms", "organizations", "company_ids", "tickers", "symbols",
                     "counterparties", "peers", "comparators", "company_a", "company_b",
                     "company_1", "company_2", "company1", "company2", "first_company",
                     "second_company"):
            if name in kwargs and kwargs[name] is not None:
                companies_raw = kwargs.pop(name)
                break

        data_raw = None
        for name in ("data", "company_data", "companies_data", "company_metrics", "metrics_by_company",
                     "inputs", "comparison_inputs", "comparison_data", "dataset", "records",
                     "financial_data", "company_financials", "financials", "comparison_inputs_list"):
            if name in kwargs and kwargs[name] is not None:
                data_raw = kwargs.pop(name)
                break

        metrics_raw = None
        for name in ("metrics", "financial_metrics", "extracted_metrics", "validated_metrics",
                     "metric_list", "financial_metric_list", "all_metrics", "source_metrics",
                     "financial_metric_values"):
            if name in kwargs and kwargs[name] is not None:
                metrics_raw = kwargs.pop(name)
                break

        calcs_raw = None
        for name in ("calculations", "financial_calculations", "calculation_results", "ratios",
                     "computed_ratios", "financial_ratios", "calculation_list"):
            if name in kwargs and kwargs[name] is not None:
                calcs_raw = kwargs.pop(name)
                break

        workspace_id = kwargs.pop("workspace_id", None)
        document_id = kwargs.pop("document_id", None)
        source = kwargs.pop("source", None)
        text = kwargs.pop("text", None)
        tables = kwargs.pop("tables", None)
        context = kwargs.pop("context", None) or {}
        context = dict(context) if isinstance(context, Mapping) else {"value": context}

        if args:
            if len(args) == 1:
                first = args[0]
                if isinstance(first, Mapping) and any(k in first for k in ("companies", "metrics", "data", "company_data")):
                    if "companies" in first and companies_raw is None:
                        companies_raw = first.get("companies")
                    if "metrics" in first and metrics_raw is None:
                        metrics_raw = first.get("metrics")
                    if "data" in first and data_raw is None:
                        data_raw = first.get("data")
                    if "company_data" in first and data_raw is None:
                        data_raw = first.get("company_data")
                elif isinstance(first, (list, tuple, set)):
                    if metrics_raw is None and data_raw is None and companies_raw is None:
                        if first and isinstance(first[0], Mapping) and any(k in first[0] for k in ("metric_type", "metric_value", "value")):
                            metrics_raw = first
                        elif first and isinstance(first[0], Mapping) and any(k in first[0] for k in ("metrics", "financial_metrics")):
                            data_raw = first
                        else:
                            companies_raw = first
                else:
                    if source is None:
                        source = first
            elif len(args) >= 2:
                if companies_raw is None:
                    companies_raw = args[0]
                if metrics_raw is None and data_raw is None:
                    second = args[1]
                    if isinstance(second, Mapping) and any(k in second for k in ("metrics", "financial_metrics", "data")):
                        data_raw = second
                    else:
                        metrics_raw = second
                if len(args) >= 3 and calcs_raw is None:
                    calcs_raw = args[2]

        company_data: dict[Any, Any] = OrderedDict()
        companies: list[Any] = []
        all_metrics: list[Any] = _normalize_metrics(metrics_raw) if metrics_raw is not None else []
        all_calcs: list[Any] = _normalize_metrics(calcs_raw) if calcs_raw is not None else []

        def _store_company(name, metrics=None, calcs=None, raw=None):
            name = str(name).strip() if name is not None else f"Company {len(company_data) + 1}"
            if name not in company_data:
                company_data[name] = {"metrics": [], "calculations": []}
            if metrics is not None:
                company_data[name]["metrics"].extend(_normalize_metrics(metrics))
            if calcs is not None:
                company_data[name]["calculations"].extend(_normalize_metrics(calcs))
            if raw is not None:
                for item in _normalize_metrics(raw):
                    if _looks_like_calculation(item):
                        company_data[name]["calculations"].append(item)
                    else:
                        company_data[name]["metrics"].append(item)

        if companies_raw is not None:
            if isinstance(companies_raw, Mapping):
                for k, v in companies_raw.items():
                    if isinstance(v, Mapping) and any(kk in v for kk in ("metrics", "financial_metrics", "extracted_metrics", "calculations", "ratios", "data")):
                        ms = None
                        for mn in ("metrics", "financial_metrics", "extracted_metrics", "validated_metrics", "metric_list"):
                            if v.get(mn) is not None:
                                ms = v.get(mn)
                                break
                        cs = None
                        for cn in ("calculations", "financial_calculations", "calculation_results", "ratios", "computed_ratios"):
                            if v.get(cn) is not None:
                                cs = v.get(cn)
                                break
                        _store_company(k, metrics=ms, calcs=cs, raw=v.get("data") if ms is None and cs is None else None)
                    elif isinstance(v, (list, tuple, set)):
                        if v and isinstance(v[0], Mapping) and any(kk in v[0] for kk in ("metric_type", "metric_value", "value", "result_value")):
                            _store_company(k, metrics=v)
                        else:
                            _store_company(k, raw=v)
                    else:
                        companies.append(k)
            elif isinstance(companies_raw, (list, tuple, set)):
                for item in companies_raw:
                    if isinstance(item, Mapping):
                        name = _get(item, "name", "company", "company_name", "entity", "firm", "organization", "ticker", "symbol", "label", default=None)
                        if name is None and len(item) == 1:
                            k, v = next(iter(item.items()))
                            name = k
                            item = dict(item)
                        if name is None:
                            name = f"Company {len(company_data) + len(companies) + 1}"
                        ms = None
                        for mn in ("metrics", "financial_metrics", "extracted_metrics", "validated_metrics", "metric_list", "financial_metric_list"):
                            if isinstance(item, Mapping) and item.get(mn) is not None:
                                ms = item.get(mn)
                                break
                        cs = None
                        for cn in ("calculations", "financial_calculations", "calculation_results", "ratios", "computed_ratios", "financial_ratios"):
                            if isinstance(item, Mapping) and item.get(cn) is not None:
                                cs = item.get(cn)
                                break
                        if ms is not None or cs is not None:
                            _store_company(name, metrics=ms, calcs=cs)
                        else:
                            if isinstance(item, Mapping) and any(kk in item for kk in ("metric_type", "metric_value", "value", "result_value")):
                                all_metrics.append(item)
                            else:
                                companies.append(name)
                    else:
                        companies.append(item)

        if data_raw is not None:
            if isinstance(data_raw, Mapping):
                for k, v in data_raw.items():
                    if isinstance(v, Mapping) and any(kk in v for kk in ("metrics", "financial_metrics", "extracted_metrics", "calculations", "ratios", "data", "company")):
                        ms = None
                        for mn in ("metrics", "financial_metrics", "extracted_metrics", "validated_metrics", "metric_list"):
                            if isinstance(v, Mapping) and v.get(mn) is not None:
                                ms = v.get(mn)
                                break
                        cs = None
                        for cn in ("calculations", "financial_calculations", "calculation_results", "ratios", "computed_ratios", "financial_ratios"):
                            if isinstance(v, Mapping) and v.get(cn) is not None:
                                cs = v.get(cn)
                                break
                        name = _get(v, "name", "company", "company_name", "entity", default=k)
                        _store_company(name, metrics=ms, calcs=cs, raw=v.get("data") if ms is None and cs is None else None)
                    elif isinstance(v, (list, tuple, set)):
                        if v and isinstance(v[0], Mapping) and any(kk in v[0] for kk in ("metric_type", "metric_value", "value", "result_value")):
                            _store_company(k, metrics=v)
                        else:
                            _store_company(k, raw=v)
                    else:
                        companies.append(k)
                if isinstance(data_raw, Mapping):
                    if "companies" in data_raw and isinstance(data_raw.get("companies"), (list, tuple)):
                        for item in data_raw["companies"]:
                            companies.append(item)
                    if "metrics" in data_raw:
                        all_metrics.extend(_normalize_metrics(data_raw.get("metrics")))
                    if "calculations" in data_raw:
                        all_calcs.extend(_normalize_metrics(data_raw.get("calculations")))
            elif isinstance(data_raw, (list, tuple, set)):
                for item in data_raw:
                    if isinstance(item, Mapping) and any(kk in item for kk in ("metrics", "financial_metrics", "extracted_metrics", "calculations", "ratios")):
                        name = _get(item, "name", "company", "company_name", "entity", default=f"Company {len(company_data) + 1}")
                        ms = None
                        for mn in ("metrics", "financial_metrics", "extracted_metrics", "validated_metrics", "metric_list"):
                            if item.get(mn) is not None:
                                ms = item.get(mn)
                                break
                        cs = None
                        for cn in ("calculations", "financial_calculations", "calculation_results", "ratios", "computed_ratios", "financial_ratios"):
                            if item.get(cn) is not None:
                                cs = item.get(cn)
                                break
                        _store_company(name, metrics=ms, calcs=cs)
                    elif isinstance(item, Mapping) and any(kk in item for kk in ("metric_type", "metric_value", "value", "result_value")):
                        all_metrics.append(item)
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        _store_company(item[0], raw=item[1])
                    else:
                        companies.append(item)

        all_metrics = _normalize_metrics(all_metrics)
        all_calcs = _normalize_metrics(all_calcs)

        metrics_by_company: dict[Any, list[Any]] = OrderedDict()
        calcs_by_company: dict[Any, list[Any]] = OrderedDict()
        for name in company_data:
            metrics_by_company[name] = list(company_data[name].get("metrics", []))
            calcs_by_company[name] = list(company_data[name].get("calculations", []))

        for m in all_metrics:
            comp = _company_name(m)
            if comp is not None:
                metrics_by_company.setdefault(comp, []).append(m)
                calcs_by_company.setdefault(comp, [])
            else:
                metrics_by_company.setdefault("__unassigned__", []).append(m)

        for c in all_calcs:
            comp = _company_name(c)
            if comp is not None:
                calcs_by_company.setdefault(comp, []).append(c)
                metrics_by_company.setdefault(comp, [])
            else:
                calcs_by_company.setdefault("__unassigned__", []).append(c)

        if (not metrics_by_company or all(not v for v in metrics_by_company.values())) and self.session_factory is not None and (workspace_id is not None or document_id is not None or source is not None):
            lm, lc = [], []
            try:
                from app.repositories.document_repository import DocumentRepository
                from app.repositories.financial_calculation_repository import (
                    FinancialCalculationRepository,
                )
                from app.repositories.financial_metric_repository import FinancialMetricRepository
                with self.session_factory() as session:
                    if document_id is not None:
                        lm = FinancialMetricRepository(session).list_by_document(document_id, limit=100000, offset=0)
                    elif workspace_id is not None:
                        lm = FinancialMetricRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)
                    if workspace_id is not None:
                        lc = FinancialCalculationRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)
                    docs = {}
                    try:
                        if workspace_id is not None:
                            docs_list = DocumentRepository(session).list_by_workspace(workspace_id, limit=100000, offset=0)
                        else:
                            docs_list = []
                        for d in docs_list:
                            docs[getattr(d, "id", None)] = getattr(d, "company_name", None)
                    except Exception:
                        docs = {}
                for m in lm or []:
                    comp = docs.get(getattr(m, "document_id", None)) or _company_name(m) or "Unknown"
                    metrics_by_company.setdefault(comp, []).append(m)
                    calcs_by_company.setdefault(comp, [])
                for c in lc or []:
                    comp = _company_name(c) or "Unknown"
                    calcs_by_company.setdefault(comp, []).append(c)
                    metrics_by_company.setdefault(comp, [])
            except Exception:
                pass

        company_candidates = list(companies) + [c for c in metrics_by_company if c != "__unassigned__"]
        seen = set()
        companies_clean = []
        for c in company_candidates:
            key = str(c)
            if key in seen:
                continue
            seen.add(key)
            companies_clean.append(c)
        if "__unassigned__" in companies_clean:
            companies_clean = [c for c in companies_clean if c != "__unassigned__"]

        if metrics_by_company.get("__unassigned__"):
            if "Unknown" not in [str(c) for c in companies_clean]:
                companies_clean.append("Unknown")
            metrics_by_company.setdefault("Unknown", []).extend(metrics_by_company.pop("__unassigned__"))
            calcs_by_company.setdefault("Unknown", []).extend(calcs_by_company.pop("__unassigned__", []))

        for c in companies_clean:
            metrics_by_company.setdefault(c, [])
            calcs_by_company.setdefault(c, [])

        return {
            "companies": companies_clean,
            "metrics_by_company": metrics_by_company,
            "calcs_by_company": calcs_by_company,
            "workspace_id": workspace_id,
            "document_id": document_id,
            "source": source,
            "text": text,
            "tables": tables,
            "context": context,
            "warnings": [],
            "errors": [],
        }

    def _compare(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        parsed = self._collect_inputs(*args, **kwargs)
        companies = parsed["companies"]
        metrics_by_company = parsed["metrics_by_company"]
        calcs_by_company = parsed["calcs_by_company"]
        workspace_id = parsed["workspace_id"]
        document_id = parsed["document_id"]
        warnings = list(parsed["warnings"])
        errors = list(parsed["errors"])
        context = parsed["context"] or {}

        companies = [c for c in companies if c is not None]
        seen = set()
        unique_companies = []
        for c in companies:
            if str(c) in seen:
                continue
            seen.add(str(c))
            unique_companies.append(c)
        companies = unique_companies

        if len(companies) < 2:
            warnings.append("At least two companies are required for a comparison.")
            result = ComparisonResult(
                comparisons=[],
                companies=companies,
                warnings=warnings,
                errors=errors,
                workspace_id=workspace_id,
                document_id=document_id,
                sufficient_data=False,
                context=context,
            )
            return result

        all_metrics_flat = []
        for c in companies:
            all_metrics_flat.extend(metrics_by_company.get(c, []))
        if self.validator is not None and hasattr(self.validator, "validate_many"):
            try:
                self.validator.validate_many(all_metrics_flat)
            except Exception as exc:
                warnings.append(f"validation: {exc}")

        metric_types = set()
        raw_metric_labels = {}
        for c in companies:
            for m in metrics_by_company.get(c, []):
                mt = _metric_type(m)
                if not mt:
                    mt = _metric_name(m)
                if mt:
                    metric_types.add(_norm_type(mt))
                    raw_metric_labels[_norm_type(mt)] = mt
        for c in companies:
            for calc in calcs_by_company.get(c, []):
                cn = _get(calc, "calculation_name", "name", "ratio_name", "metric", default=None)
                if cn is not None:
                    metric_types.add(_norm_type(cn))
                    raw_metric_labels[_norm_type(cn)] = cn

        periods_set = set()
        for c in companies:
            for m in metrics_by_company.get(c, []):
                p = _reporting_period(m)
                periods_set.add(p if p is not None else "unknown")
            for calc in calcs_by_company.get(c, []):
                p = _get(calc, "reporting_period", "period", "fiscal_period", default=None)
                if p is None:
                    inp = _get(calc, "input_metrics", "inputs", default=None)
                    if isinstance(inp, (list, tuple)):
                        for inp_item in inp:
                            pp = _get(inp_item, "reporting_period", "period", default=None)
                            if pp is not None:
                                p = pp
                                break
                periods_set.add(p if p is not None else "unknown")
        if not periods_set:
            periods_set.add("unknown")

        comparisons: list[ComparisonItem] = []
        skipped: list[dict[str, Any]] = []
        compatibility_issues: list[dict[str, Any]] = []
        missing_data: list[dict[str, Any]] = []
        all_citations: list[dict[str, Any]] = []

        def _metrics_for(c, ntype, period):
            out = []
            for m in metrics_by_company.get(c, []):
                mt = _metric_type(m) or _metric_name(m)
                if _norm_type(mt) != ntype:
                    continue
                rp = _reporting_period(m)
                rp = rp if rp is not None else "unknown"
                if str(rp) != str(period):
                    continue
                out.append(m)
            return out

        def _calcs_for(c, ntype, period):
            out = []
            for calc in calcs_by_company.get(c, []):
                cn = _get(calc, "calculation_name", "name", "ratio_name", "metric", default=None)
                if _norm_type(cn) != ntype:
                    continue
                p = _get(calc, "reporting_period", "period", "fiscal_period", default=None)
                if p is None:
                    inp = _get(calc, "input_metrics", "inputs", default=None)
                    if isinstance(inp, (list, tuple)):
                        for inp_item in inp:
                            pp = _get(inp_item, "reporting_period", "period", default=None)
                            if pp is not None:
                                p = pp
                                break
                p = p if p is not None else "unknown"
                if str(p) != str(period):
                    continue
                out.append(calc)
            return out

        for ntype in sorted(metric_types):
            label = raw_metric_labels.get(ntype, ntype)
            dirn = _direction(ntype, label)
            higher_is_better = None
            if dirn == "higher":
                higher_is_better = True
            elif dirn == "lower":
                higher_is_better = False
            for period in sorted(periods_set, key=lambda x: (x is None, str(x))):
                values: dict[str, Decimal] = {}
                currencies: dict[str, Any] = {}
                units: dict[str, Any] = {}
                citations: list[dict[str, Any]] = []
                missing: list[str] = []
                compatible = True
                reasons: list[str] = []
                source_metrics: dict[str, Any] = {}
                for c in companies:
                    cs = str(c)
                    ms = _metrics_for(c, ntype, period)
                    if not ms:
                        cs_list = _calcs_for(c, ntype, period)
                        if cs_list:
                            calc = cs_list[0]
                            v = _get(calc, "result_value", "value", "result", "ratio_value", "calculated_value", default=None)
                            dv = _to_decimal(v)
                            if dv is not None:
                                values[cs] = dv
                                currencies[cs] = _get(calc, "currency", default=None)
                                units[cs] = _get(calc, "unit", default=None)
                                citations.extend(_citations(calc))
                                source_metrics[cs] = calc
                                continue
                    if ms:
                        m = ms[0]
                        v = _metric_value(m)
                        if v is not None:
                            values[cs] = v
                            currencies[cs] = _currency(m)
                            units[cs] = _unit(m)
                            citations.extend(_citations(m))
                            source_metrics[cs] = m
                        else:
                            missing.append(cs)
                    else:
                        missing.append(cs)

                cur_vals = [currencies[c] for c in values if currencies.get(c) is not None]
                if len(set(str(x) for x in cur_vals)) > 1:
                    compatible = False
                    reasons.append(f"incompatible currencies: {', '.join(str(currencies[c]) for c in values)}")
                unit_vals = [units[c] for c in values if units.get(c) is not None]
                if len(set(str(x) for x in unit_vals)) > 1:
                    compatible = False
                    reasons.append(f"incompatible units: {', '.join(str(units[c]) for c in values)}")

                currency = None
                if cur_vals:
                    currency = cur_vals[0] if len(set(str(x) for x in cur_vals)) == 1 else None
                unit = None
                if unit_vals:
                    unit = unit_vals[0] if len(set(str(x) for x in unit_vals)) == 1 else None

                if len(values) < 2:
                    skipped.append({
                        "metric_type": ntype,
                        "metric_name": label,
                        "reporting_period": period,
                        "reason": "insufficient data (fewer than two companies)",
                        "available_companies": list(values.keys()),
                        "missing_companies": missing,
                    })
                    if missing:
                        missing_data.append({
                            "metric_type": ntype,
                            "metric_name": label,
                            "reporting_period": period,
                            "missing_companies": missing,
                        })
                    continue

                if not compatible:
                    compatibility_issues.append({
                        "metric_type": ntype,
                        "metric_name": label,
                        "reporting_period": period,
                        "reason": "; ".join(reasons),
                        "currencies": dict(currencies),
                        "units": dict(units),
                    })

                companies_present = [str(c) for c in companies if str(c) in values]
                pairwise = []
                if compatible:
                    for i in range(len(companies_present)):
                        for j in range(i + 1, len(companies_present)):
                            a = companies_present[i]
                            b = companies_present[j]
                            diff = values[b] - values[a]
                            pct = _pct_change(values[a], values[b])
                            pairwise.append({
                                "company_a": a,
                                "company_b": b,
                                "value_a": values[a],
                                "value_b": values[b],
                                "difference": diff,
                                "absolute_difference": abs(diff),
                                "percentage_difference": pct,
                            })
                if len(companies_present) >= 2:
                    a0 = companies_present[0]
                    b0 = companies_present[1]
                    signed_diff = values[a0] - values[b0] if compatible else None
                    pct_diff = _pct_change(values[b0], values[a0]) if compatible else None
                else:
                    signed_diff = None
                    pct_diff = None
                if compatible and len(companies_present) >= 2:
                    max_company = max(companies_present, key=lambda c: values[c])
                    min_company = min(companies_present, key=lambda c: values[c])
                    max_val = values[max_company]
                    min_val = values[min_company]
                    overall_diff = max_val - min_val
                else:
                    max_company = None
                    min_company = None
                    max_val = None
                    min_val = None
                    overall_diff = None

                if compatible and higher_is_better is True:
                    best = max(companies_present, key=lambda c: values[c]) if companies_present else None
                elif compatible and higher_is_better is False:
                    best = min(companies_present, key=lambda c: values[c]) if companies_present else None
                else:
                    best = max(companies_present, key=lambda c: values[c]) if (compatible and companies_present) else None

                if not compatible:
                    conclusion = (f"Comparison not possible for {label} in {period}: "
                                  f"{'; '.join(reasons)}.")
                elif len(companies_present) == 2:
                    a0, b0 = companies_present[0], companies_present[1]
                    diff = values[a0] - values[b0]
                    pct = _pct_change(values[b0], values[a0])
                    pct_str = f" ({pct:.2f}%)" if pct is not None else ""
                    if higher_is_better is False:
                        better = a0 if values[a0] < values[b0] else b0
                        other = b0 if better == a0 else a0
                        conclusion = (f"{better} has lower {label} than {other} in {period} "
                                      f"({values[a0]} vs {values[b0]}).")
                    else:
                        better = a0 if values[a0] > values[b0] else b0
                        other = b0 if better == a0 else a0
                        conclusion = (f"{better} has higher {label} than {other} in {period} "
                                      f"({values[a0]} vs {values[b0]}, difference {diff}{pct_str}).")
                else:
                    conclusion = (f"Across {len(companies_present)} companies, {max_company} has the "
                                  f"highest {label} and {min_company} the lowest in {period} "
                                  f"({min_val} to {max_val}).")
                if missing:
                    conclusion += f" Missing data for: {', '.join(missing)}."
                    missing_data.append({
                        "metric_type": ntype,
                        "metric_name": label,
                        "reporting_period": period,
                        "missing_companies": missing,
                    })

                item = ComparisonItem(
                    comparison_type="company_comparison",
                    metric_type=ntype,
                    metric_name=label,
                    label=label,
                    reporting_period=period if period != "unknown" else None,
                    period=period if period != "unknown" else None,
                    fiscal_period=period if period != "unknown" else None,
                    companies=list(companies),
                    company_names=list(companies),
                    present_companies=companies_present,
                    available_companies=companies_present,
                    missing_companies=missing,
                    values={k: values[k] for k in values},
                    value_by_company={k: values[k] for k in values},
                    company_values={k: values[k] for k in values},
                    raw_values={k: values[k] for k in values},
                    currency=currency,
                    currencies=dict(currencies),
                    unit=unit,
                    units=dict(units),
                    compatible=compatible,
                    is_compatible=compatible,
                    compatibility=compatible,
                    compatibility_status="compatible" if compatible else "incompatible",
                    incompatibility_reason="; ".join(reasons) if reasons else None,
                    compatibility_reason="; ".join(reasons) if reasons else None,
                    difference=signed_diff if signed_diff is not None else overall_diff,
                    diff=signed_diff if signed_diff is not None else overall_diff,
                    delta=signed_diff if signed_diff is not None else overall_diff,
                    absolute_difference=(abs(signed_diff) if signed_diff is not None else overall_diff),
                    abs_difference=(abs(signed_diff) if signed_diff is not None else overall_diff),
                    signed_difference=signed_diff,
                    percentage_difference=pct_diff,
                    percent_difference=pct_diff,
                    relative_difference=pct_diff,
                    relative_difference_percent=pct_diff,
                    change_percent=pct_diff,
                    pairwise_differences=pairwise,
                    pairwise=pairwise,
                    max_value=max_val,
                    min_value=min_val,
                    max_company=max_company,
                    min_company=min_company,
                    highest_company=max_company,
                    lowest_company=min_company,
                    leader=best,
                    winner=best if compatible else None,
                    best_company=best if compatible else None,
                    higher_is_better=higher_is_better,
                    direction="higher" if higher_is_better is True else ("lower" if higher_is_better is False else None),
                    conclusion=conclusion,
                    summary=conclusion,
                    interpretation=conclusion,
                    analysis=conclusion,
                    assessment=conclusion,
                    rationale=conclusion,
                    evidence={
                        "metric_type": ntype,
                        "metric_name": label,
                        "reporting_period": period,
                        "companies": [str(c) for c in companies],
                        "values": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in values.items()},
                        "difference": (str(signed_diff) if isinstance(signed_diff, Decimal) else signed_diff),
                        "percentage_difference": (str(pct_diff) if isinstance(pct_diff, Decimal) else pct_diff),
                        "compatible": compatible,
                        "incompatibility_reason": ("; ".join(reasons) if reasons else None),
                        "missing_companies": missing,
                        "source_citations": citations,
                        "currencies": dict(currencies),
                        "units": dict(units),
                        "higher_is_better": higher_is_better,
                    },
                    citations=list(citations),
                    source_citations=list(citations),
                    source_references=list(citations),
                    sources=list(citations),
                    source_refs=list(citations),
                    confidence=Decimal("0.8") if citations else Decimal("0.6"),
                    confidence_score=Decimal("0.8") if citations else Decimal("0.6"),
                    metadata={
                        "rule": "comparison",
                        "metric_type": ntype,
                        "reporting_period": period,
                        "compatible": compatible,
                    },
                    context=dict(context),
                    status="compared" if compatible else "incompatible",
                    sufficient_data=True,
                    warnings=(["; ".join(reasons)] if reasons else []) + ([f"Missing data for: {', '.join(missing)}"] if missing else []),
                )
                comparisons.append(item)
                all_citations.extend(citations)

        differences = []
        for c in comparisons:
            for pw in c.pairwise_differences:
                differences.append({
                    "metric_type": c.metric_type,
                    "metric_name": c.metric_name,
                    "reporting_period": c.reporting_period,
                    "company_a": pw.get("company_a"),
                    "company_b": pw.get("company_b"),
                    "value_a": pw.get("value_a"),
                    "value_b": pw.get("value_b"),
                    "difference": pw.get("difference"),
                    "absolute_difference": pw.get("absolute_difference"),
                    "percentage_difference": pw.get("percentage_difference"),
                })
            if not c.pairwise_differences and c.difference is not None:
                differences.append({
                    "metric_type": c.metric_type,
                    "metric_name": c.metric_name,
                    "reporting_period": c.reporting_period,
                    "difference": c.difference,
                    "absolute_difference": c.absolute_difference,
                    "percentage_difference": c.percentage_difference,
                })

        conclusions = [c.conclusion for c in comparisons if c.conclusion]
        if comparisons:
            wins = {str(c): 0 for c in companies}
            for comp in comparisons:
                if comp.best_company is not None and comp.compatible:
                    b = str(comp.best_company)
                    if b in wins:
                        wins[b] += 1
            if wins and any(v > 0 for v in wins.values()):
                top = max(wins.items(), key=lambda kv: kv[1])
                conclusions.append(f"Overall, {top[0]} leads in {top[1]} of {len(comparisons)} compared metrics.")
        if not comparisons:
            conclusions.append("No comparable metrics were found across the provided companies.")
            warnings.append("No comparable metrics were found across the provided companies.")

        periods_list = sorted([p for p in periods_set if p != "unknown"], key=lambda x: str(x))
        if "unknown" in periods_set:
            periods_list = [*periods_list, "unknown"]
        periods_out = [p for p in periods_list if p != "unknown"]
        if not periods_out:
            periods_out = list(periods_set)

        metrics_out = sorted(raw_metric_labels.values()) if raw_metric_labels else sorted(metric_types)

        result = ComparisonResult(
            comparisons=comparisons,
            differences=differences,
            conclusions=conclusions,
            companies=companies,
            periods=periods_out,
            metrics=metrics_out,
            metric_types=sorted(metric_types),
            warnings=warnings,
            errors=errors,
            workspace_id=workspace_id,
            document_id=document_id,
            sufficient_data=len(comparisons) > 0,
            compatibility_issues=compatibility_issues,
            missing_data=missing_data,
            skipped=skipped,
            citations=all_citations,
            context={**context, "companies": [str(c) for c in companies], "periods": periods_out, "metrics": metrics_out},
        )
        return result

    def compare(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def analyze(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def process(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def evaluate(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def assess(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def compare_companies(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def compare_financials(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def compare_metrics(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def compare_financial_metrics(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def run_comparison(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def analyze_comparison(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)

    def get_comparison(self, *args: Any, **kwargs: Any) -> ComparisonResult:
        return self._compare(*args, **kwargs)


ComparisonService = ComparisonAgent
CompanyComparisonAgent = ComparisonAgent
FinancialComparisonAgent = ComparisonAgent
CompareAgent = ComparisonAgent
Comparer = ComparisonAgent


def compare_companies(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().compare(*args, **kwargs)


def compare(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().compare(*args, **kwargs)


def compare_financials(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().compare_financials(*args, **kwargs)


def compare_metrics(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().compare_metrics(*args, **kwargs)


def compare_financial_metrics(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().compare_financial_metrics(*args, **kwargs)


def analyze_comparison(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().analyze_comparison(*args, **kwargs)


def run_comparison(*args: Any, **kwargs: Any) -> ComparisonResult:
    return ComparisonAgent().run_comparison(*args, **kwargs)


_EXTRA_COMPARE_NAMES = [
    "analyze_document", "analyze_workspace", "analyze_financial_data", "analyze_metrics",
    "analyze_companies", "run_for_document", "run_for_workspace", "compare_documents",
    "compare_workspaces", "evaluate_document", "evaluate_workspace", "evaluate_financial_data",
    "evaluate_metrics", "check", "compare_all", "compare_entities",
]
for _name in _EXTRA_COMPARE_NAMES:
    setattr(ComparisonAgent, _name, ComparisonAgent.compare)

Comparison = ComparisonItem
ComparisonFinding = ComparisonItem
ComparisonData = ComparisonResult
ComparisonReport = ComparisonResult
ComparisonAnalysis = ComparisonResult
ComparisonOutcome = ComparisonResult
CompanyComparison = ComparisonResult
ComparisonCompany = None
ComparisonService = ComparisonAgent
CompanyComparisonAgent = ComparisonAgent
FinancialComparisonAgent = ComparisonAgent
CompareAgent = ComparisonAgent
Comparer = ComparisonAgent
ComparisonAgent = ComparisonAgent
ComparisonResult = ComparisonResult
ComparisonItem = ComparisonItem
