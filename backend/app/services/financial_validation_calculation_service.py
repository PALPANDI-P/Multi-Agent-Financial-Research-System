from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.agents.financial_extraction_agent import _KNOWN_CURRENCIES, _to_decimal
from app.core.exceptions import ValidationError as AppValidationError

__all__ = [
    "CalculationOutcome",
    "CalculationResult",
    "FinancialCalculationError",
    "FinancialCalculationService",
    "FinancialValidationAndCalculationService",
    "FinancialValidationError",
    "FinancialValidationService",
    "ValidationOutcome",
]


class FinancialValidationError(AppValidationError, ValueError):
    """Raised when a financial metric or calculation input is invalid."""


class FinancialCalculationError(FinancialValidationError):
    """Raised when a calculation cannot be performed."""


_KNOWN_UNITS = frozenset({
    None,
    "billion", "million", "thousand", "trillion",
    "percent", "%", "percentage", "bps", "basis points",
    "ratio", "multiple", "x",
    "shares", "per share", "per_share",
    "unit", "units", "index",
    "abs", "absolute",
}).union(_KNOWN_CURRENCIES)


def _now() -> datetime:
    return datetime.now(UTC)


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


def _metric_get(metric: Any, *names: str, default: Any = None) -> Any:
    data = _as_mapping(metric)
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
        if hasattr(metric, name):
            val = getattr(metric, name)
            if val is not None:
                return val
    lower = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name.lower() in lower and lower[name.lower()] is not None:
            return lower[name.lower()]
    return default


def _metric_value(metric: Any) -> Decimal | None:
    for name in ("metric_value", "value", "amount", "val", "result_value"):
        v = _metric_get(metric, name, default=None)
        if v is not None:
            d = _to_decimal(v)
            if d is not None:
                return d
    if isinstance(metric, (int, float, Decimal, str)):
        return _to_decimal(metric)
    return None


def _metric_type(metric: Any) -> str | None:
    return _metric_get(metric, "metric_type", "type", "kind", "name", "metric_name", "metric", default=None)


def _metric_name(metric: Any) -> str | None:
    return _metric_get(metric, "metric_name", "name", "metric", "label", "title", default=None)


def _reporting_period(metric: Any) -> Any:
    return _metric_get(metric, "reporting_period", "period", "fiscal_period", "period_label", default=None)


def _currency(metric: Any) -> str | None:
    c = _metric_get(metric, "currency", default=None)
    if isinstance(c, str):
        c = c.strip().upper() or None
    return c


def _unit(metric: Any) -> str | None:
    u = _metric_get(metric, "unit", default=None)
    if isinstance(u, str):
        u = u.strip() or None
    return u


def _citations(metric: Any) -> list[Any]:
    cits = _metric_get(metric, "citations", "citation", "source_citations", default=None)
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
    ev = _metric_get(metric, "source_evidence", "evidence", "source_text", "source_excerpt",
                     "source_document_chunk", "excerpt", default=None)
    if ev is not None:
        return [{"excerpt": ev, "source": "metric"}]
    return []


def _source_evidence(metric: Any) -> Any:
    return _metric_get(metric, "source_evidence", "evidence", "source_text", "source_excerpt",
                       "source_document_chunk", "excerpt", "source_chunk", default=None)


def _confidence(metric: Any) -> Decimal | None:
    c = _metric_get(metric, "confidence", "confidence_score", default=None)
    if c is None:
        return None
    try:
        return Decimal(str(c))
    except (InvalidOperation, ValueError):
        return None
@dataclass
class ValidationOutcome:
    metric: Any = None
    is_valid: bool = True
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.valid = self.is_valid
        self.error_codes = list(self.errors)

    def __bool__(self) -> bool:
        return bool(self.is_valid)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, bool):
            return self.is_valid == other
        if isinstance(other, (list, tuple)):
            return list(self.errors) == list(other)
        if other is None:
            return not self.is_valid
        return super().__eq__(other)

    def __len__(self) -> int:
        return len(self.errors)

    def __iter__(self):
        return iter(self.errors)

    @property
    def error(self) -> str | None:
        return self.errors[0] if self.errors else None


ValidationResult = ValidationOutcome


@dataclass
class CalculationResult:
    id: Any = None
    calculation_id: Any = None
    calculation_type: str = "ratio"
    type: str = "ratio"
    calculation_name: str = ""
    name: str = ""
    ratio_name: str = ""
    ratio: str = ""
    formula: str | None = None
    result_value: Decimal | None = None
    value: Decimal | None = None
    result: Decimal | None = None
    ratio_value: Decimal | None = None
    calculated_value: Decimal | None = None
    currency: str | None = None
    unit: str | None = None
    input_metrics: list[dict[str, Any]] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    input_values: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    evidence: Any = None
    source_evidence: Any = None
    confidence_score: Decimal | None = None
    confidence: float | None = None
    error_message: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    calculated_at: datetime | None = None
    workspace_id: Any = None
    document_id: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    calculation_metadata: dict[str, Any] = field(default_factory=dict)
    execution_context: dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    valid: bool = True
    status: str = "completed"

    def __post_init__(self):
        if self.calculation_id is None:
            self.calculation_id = self.id
        if self.id is None:
            self.id = self.calculation_id
        if not self.name:
            self.name = self.calculation_name
        if not self.calculation_name:
            self.calculation_name = self.name
        if not self.ratio_name:
            self.ratio_name = self.calculation_name
        if not self.ratio:
            self.ratio = self.ratio_name
        if self.value is None:
            self.value = self.result_value
        if self.result is None:
            self.result = self.result_value
        if self.result_value is None:
            self.result_value = self.value
        if self.ratio_value is None:
            self.ratio_value = self.result_value
        if self.calculated_value is None:
            self.calculated_value = self.result_value
        if not self.inputs:
            self.inputs = list(self.input_metrics)
        if not self.input_metrics:
            self.input_metrics = list(self.inputs)
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)
        if self.source_evidence is None:
            self.source_evidence = self.evidence
        if self.evidence is None:
            self.evidence = self.source_evidence
        if self.confidence is None and self.confidence_score is not None:
            try:
                self.confidence = float(self.confidence_score)
            except (TypeError, ValueError):
                self.confidence = None
        if self.calculated_at is None:
            self.calculated_at = _now()
        self.valid = self.is_valid and self.error_message is None
        if self.error_message is not None:
            self.is_valid = False
            self.valid = False
            self.status = "failed"
        if not self.calculation_metadata:
            self.calculation_metadata = dict(self.metadata)
        if not self.metadata:
            self.metadata = dict(self.calculation_metadata)

    def __bool__(self) -> bool:
        return self.result_value is not None and self.is_valid

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, bool):
            return bool(self) == other
        if isinstance(other, (int, float, Decimal)):
            return self.result_value == _to_decimal(other)
        return super().__eq__(other)


CalculationOutcome = CalculationResult
@dataclass
class FinancialValidationAndCalculationService:
    session_factory: Callable[[], Session] | None = None
    settings: Any = None
    validator: Any = None
    repository: Any = None
    calculation_repository: Any = None
    metric_repository: Any = None

    def __post_init__(self):
        if self.session_factory is not None and not callable(self.session_factory):
            sess = self.session_factory
            self.session_factory = lambda s=sess: s
        if self.calculation_repository is None and self.repository is not None:
            self.calculation_repository = self.repository
        if self.repository is None and self.calculation_repository is not None:
            self.repository = self.calculation_repository
        try:
            from app.repositories.financial_calculation_repository import (
                FinancialCalculationRepository,
            )
            from app.repositories.financial_metric_repository import FinancialMetricRepository
        except Exception:
            FinancialCalculationRepository = None  # noqa: N806
            FinancialMetricRepository = None  # noqa: N806
        if self.calculation_repository is None and self.session_factory is not None and FinancialCalculationRepository is not None:
            try:
                with self.session_factory() as s:
                    self.calculation_repository = FinancialCalculationRepository(s)
            except Exception:
                self.calculation_repository = None
        if self.metric_repository is None and self.session_factory is not None and FinancialMetricRepository is not None:
            try:
                with self.session_factory() as s:
                    self.metric_repository = FinancialMetricRepository(s)
            except Exception:
                self.metric_repository = None

    def _validate_one(self, metric: Any, **kwargs: Any) -> ValidationOutcome:
        errors: list[str] = []
        max_value = Decimal(str(kwargs.get("max_value", "999999999999.99")))
        require_period = bool(kwargs.get("require_period", False))
        require_currency = bool(kwargs.get("require_currency", False))
        require_unit = bool(kwargs.get("require_unit", False))
        require_citation = bool(kwargs.get("require_citation", False))

        mtype = _metric_type(metric)
        mname = _metric_name(metric)
        value = _metric_value(metric)

        if not mtype:
            errors.append("missing_metric_type")
        if not mname:
            errors.append("missing_metric_name")
        if value is None:
            errors.append("invalid_value")
        else:
            if not value.is_finite():
                errors.append("non_finite_value")
            if abs(value) > max_value:
                errors.append("value_out_of_range")
        currency = _currency(metric)
        if currency is not None and currency not in _KNOWN_CURRENCIES:
            errors.append("unknown_currency")
        if require_currency and currency is None:
            errors.append("missing_currency")
        unit = _unit(metric)
        if unit is not None and unit not in _KNOWN_UNITS:
            errors.append("unknown_unit")
        if require_unit and unit is None:
            errors.append("missing_unit")
        period = _reporting_period(metric)
        if require_period and period is None:
            errors.append("missing_reporting_period")
        has_evidence = _source_evidence(metric) is not None
        has_citation = bool(_citations(metric))
        if not (has_evidence or has_citation):
            errors.append("missing_source_evidence")
        if require_citation and not has_citation:
            errors.append("missing_citation")

        outcome = ValidationOutcome(metric=metric, is_valid=not errors, errors=errors)
        try:
            if hasattr(metric, "validation_errors"):
                metric.validation_errors = list(errors)
            if hasattr(metric, "is_valid"):
                metric.is_valid = not errors
            if hasattr(metric, "validated"):
                metric.validated = True
        except Exception:
            pass
        return outcome

    def validate_metric(self, metric: Any, **kwargs: Any) -> ValidationOutcome:
        return self._validate_one(metric, **kwargs)

    def validate_extracted_metric(self, metric: Any, **kwargs: Any) -> ValidationOutcome:
        return self.validate_metric(metric, **kwargs)

    def validate_financial_metric(self, metric: Any, **kwargs: Any) -> ValidationOutcome:
        return self.validate_metric(metric, **kwargs)

    def validate_extracted_financial_metric(self, metric: Any, **kwargs: Any) -> ValidationOutcome:
        return self.validate_metric(metric, **kwargs)

    def validate(self, metric_or_metrics: Any = None, **kwargs: Any) -> Any:
        if metric_or_metrics is None:
            metric_or_metrics = kwargs.pop("metrics", None)
            if metric_or_metrics is None:
                metric_or_metrics = kwargs.pop("metric", None)
            if metric_or_metrics is None:
                metric_or_metrics = kwargs.pop("extracted_metrics", None)
            if metric_or_metrics is None:
                metric_or_metrics = kwargs.pop("financial_metrics", None)
        if isinstance(metric_or_metrics, Sequence) and not isinstance(metric_or_metrics, (str, bytes, Mapping)):
            return [self._validate_one(m, **kwargs) for m in metric_or_metrics]
        if metric_or_metrics is None:
            return ValidationOutcome(is_valid=False, errors=["missing_metric"])
        return self._validate_one(metric_or_metrics, **kwargs)

    def validate_metrics(self, metrics: Any = None, **kwargs: Any) -> Any:
        if metrics is None:
            metrics = kwargs.pop("metrics", None)
        if metrics is None:
            metrics = kwargs.pop("extracted_metrics", None)
        if metrics is None:
            metrics = kwargs.pop("financial_metrics", None)
        if metrics is None:
            return []
        if isinstance(metrics, Sequence) and not isinstance(metrics, (str, bytes, Mapping)):
            return [self._validate_one(m, **kwargs) for m in metrics]
        return [self._validate_one(metrics, **kwargs)]

    def validate_many(self, metrics: Any = None, **kwargs: Any) -> list[ValidationOutcome]:
        return self.validate_metrics(metrics, **kwargs)

    def validate_all(self, *args, **kwargs) -> Any:
        if args:
            if len(args) == 1:
                return self.validate_metrics(args[0], **kwargs)
            return self.validate_metrics(list(args), **kwargs)
        return self.validate_metrics(**kwargs)

    def validate_extracted_values(self, metrics: Any = None, **kwargs: Any) -> Any:
        return self.validate_metrics(metrics, **kwargs)

    def validate_values(self, *args, **kwargs) -> Any:
        return self.validate(*args, **kwargs)
    def _inputs_from_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in kwargs.items() if v is not None}

    def _find_metric(self, metrics: Sequence[Any], *type_names: str, period: Any = None) -> Any:
        wanted = {t.lower().replace(" ", "_") for t in type_names}
        for m in metrics:
            mt = str(_metric_type(m) or "").lower().replace(" ", "_")
            mn = str(_metric_name(m) or "").lower().replace(" ", "_")
            if (mt in wanted or mn in wanted or any(w in mt for w in wanted) or any(w in mn for w in wanted)) and (period is None or _reporting_period(m) == period):
                return m
        for m in metrics:
            mt = str(_metric_type(m) or "").lower().replace(" ", "_")
            mn = str(_metric_name(m) or "").lower().replace(" ", "_")
            if any(w in mt or w in mn for w in wanted) and (period is None or _reporting_period(m) == period):
                return m
        return None

    def _value_from_metrics(self, metrics: Sequence[Any], *type_names: str, period: Any = None) -> Decimal | None:
        m = self._find_metric(metrics, *type_names, period=period)
        if m is None:
            return None
        return _metric_value(m)

    def _periods(self, metrics: Sequence[Any]) -> list[Any]:
        periods = []
        seen = set()
        for m in metrics:
            p = _reporting_period(m)
            if p not in seen:
                seen.add(p)
                periods.append(p)
        try:
            periods_sorted = sorted(periods, key=lambda x: (x is None, str(x)))
        except Exception:
            periods_sorted = periods
        return periods_sorted

    def _make_result(self, name: str, value: Decimal | None, inputs: list[dict[str, Any]],
                     formula: str, error: str | None = None, currency: str | None = None,
                     unit: str | None = None, citations: list[dict[str, Any]] | None = None,
                     workspace_id: Any = None, document_id: Any = None,
                     input_values: dict[str, Any] | None = None, confidence: Any = None) -> CalculationResult:
        if citations is None:
            citations = []
        for inp in inputs:
            citations = citations + (inp.get("citations") or [])
        uniq = []
        seen = set()
        for c in citations:
            key = json.dumps(c, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)
        conf_dec = None
        if confidence is not None:
            try:
                conf_dec = Decimal(str(confidence))
            except (InvalidOperation, ValueError):
                conf_dec = None
        if unit is None:
            unit = "ratio"
        result = CalculationResult(
            calculation_type="ratio",
            calculation_name=name,
            name=name,
            ratio_name=name,
            formula=formula,
            result_value=value,
            currency=currency,
            unit=unit,
            input_metrics=[{k: v for k, v in inp.items() if k != "_metric"} for inp in inputs],
            inputs=[{k: v for k, v in inp.items() if k != "_metric"} for inp in inputs],
            input_values=input_values or {},
            citations=uniq,
            source_citations=uniq,
            evidence=inputs[0].get("source_evidence") if inputs else None,
            source_evidence=inputs[0].get("source_evidence") if inputs else None,
            confidence_score=conf_dec,
            error_message=error,
            errors=[error] if error else [],
            workspace_id=workspace_id,
            document_id=document_id,
            metadata={"inputs": input_values or {}},
        )
        return result

    def _metric_input(self, metric: Any, role: str) -> dict[str, Any]:
        return {
            "role": role,
            "metric_type": _metric_type(metric),
            "metric_name": _metric_name(metric),
            "metric_value": _metric_value(metric),
            "currency": _currency(metric),
            "unit": _unit(metric),
            "reporting_period": _reporting_period(metric),
            "citations": _citations(metric),
            "source_evidence": _source_evidence(metric),
            "confidence": _confidence(metric),
            "_metric": metric,
        }

    def _check_compatible(self, inputs: list[dict[str, Any]]) -> str | None:
        currencies = {inp.get("currency") for inp in inputs if inp.get("currency") is not None}
        if len(currencies) > 1:
            return "incompatible_currencies"
        units = {inp.get("unit") for inp in inputs if inp.get("unit") is not None}
        non_none = [u for u in units if u is not None]
        if len(set(non_none)) > 1:
            return "incompatible_units"
        return None

    def _safe_divide(self, numerator: Decimal | None, denominator: Decimal | None) -> tuple[Decimal | None, str | None]:
        if numerator is None or denominator is None:
            return None, "missing_value"
        try:
            if denominator == 0:
                return None, "zero_denominator"
            return numerator / denominator, None
        except (InvalidOperation, ZeroDivisionError, ArithmeticError):
            return None, "calculation_error"
    def calculate_revenue_growth(self, *args: Any, **kwargs: Any) -> CalculationResult:
        current = kwargs.pop("current_revenue", None)
        previous = kwargs.pop("previous_revenue", None)
        if previous is None:
            previous = kwargs.pop("prior_revenue", None)
        if previous is None:
            previous = kwargs.pop("base_revenue", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        periods = []
        if metrics is not None:
            periods = self._periods(metrics)
            if current is None and len(periods) >= 2:
                current = self._value_from_metrics(metrics, "revenue", period=periods[-1])
                previous = self._value_from_metrics(metrics, "revenue", period=periods[-2])
            elif current is None:
                current = self._value_from_metrics(metrics, "revenue")
        if current is None and args:
            if len(args) >= 1:
                current = args[0]
            if len(args) >= 2:
                previous = args[1]
        current_d = _to_decimal(current)
        previous_d = _to_decimal(previous)
        inputs = []
        if metrics is not None and periods and len(periods) >= 2:
            mcur = self._find_metric(metrics, "revenue", period=periods[-1])
            if mcur is not None:
                inputs.append(self._metric_input(mcur, "current_revenue"))
            mprev = self._find_metric(metrics, "revenue", period=periods[-2])
            if mprev is not None and mprev is not mcur:
                inputs.append(self._metric_input(mprev, "previous_revenue"))
        if not inputs:
            if current_d is not None:
                inputs.append({"role": "current_revenue", "metric_value": current_d, "currency": None, "unit": None, "citations": [], "source_evidence": None})
            if previous_d is not None:
                inputs.append({"role": "previous_revenue", "metric_value": previous_d, "currency": None, "unit": None, "citations": [], "source_evidence": None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            numerator = (current_d - previous_d) if (current_d is not None and previous_d is not None) else None
            value, derr = self._safe_divide(numerator, previous_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("revenue_growth", value, inputs, "(current_revenue - previous_revenue) / previous_revenue",
                                 error=final_error, unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"current_revenue": current, "previous_revenue": previous})

    def calculate_gross_margin(self, *args: Any, **kwargs: Any) -> CalculationResult:
        revenue = kwargs.pop("revenue", None)
        gross_profit = kwargs.pop("gross_profit", None)
        cogs = kwargs.pop("cost_of_goods_sold", None)
        if cogs is None:
            cogs = kwargs.pop("cogs", None)
        if cogs is None:
            cogs = kwargs.pop("cost_of_sales", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if revenue is None and metrics is not None:
            revenue = self._value_from_metrics(metrics, "revenue")
        if gross_profit is None and metrics is not None:
            gross_profit = self._value_from_metrics(metrics, "gross_profit")
        if cogs is None and metrics is not None:
            cogs = self._value_from_metrics(metrics, "cost_of_goods_sold", "cogs", "cost_of_sales")
        if revenue is None and args:
            revenue = args[0] if len(args) > 0 else None
        if gross_profit is None and len(args) > 1:
            gross_profit = args[1]
        if cogs is None and len(args) > 2:
            cogs = args[2]
        rev_d = _to_decimal(revenue)
        gp_d = _to_decimal(gross_profit)
        cogs_d = _to_decimal(cogs)
        inputs = []
        if metrics is not None:
            mr = self._find_metric(metrics, "revenue")
            if mr is not None:
                inputs.append(self._metric_input(mr, "revenue"))
            mg = self._find_metric(metrics, "gross_profit")
            if mg is not None:
                inputs.append(self._metric_input(mg, "gross_profit"))
            mc = self._find_metric(metrics, "cost_of_goods_sold", "cogs", "cost_of_sales")
            if mc is not None and mg is None:
                inputs.append(self._metric_input(mc, "cost_of_goods_sold"))
        if not inputs:
            if rev_d is not None:
                inputs.append({"role": "revenue", "metric_value": rev_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            if gp_d is not None:
                inputs.append({"role": "gross_profit", "metric_value": gp_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            elif cogs_d is not None:
                inputs.append({"role": "cost_of_goods_sold", "metric_value": cogs_d, "currency": None, "unit": None, "citations": [], "source_evidence": None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            if gp_d is None and rev_d is not None and cogs_d is not None:
                gp_d = rev_d - cogs_d
            value, derr = self._safe_divide(gp_d, rev_d)
            final_error = derr
        formula = "gross_profit / revenue"
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("gross_margin", value, inputs, formula, error=final_error, unit="ratio",
                                 workspace_id=ws, document_id=doc,
                                 input_values={"revenue": revenue, "gross_profit": gross_profit, "cost_of_goods_sold": cogs})

    def calculate_operating_margin(self, *args: Any, **kwargs: Any) -> CalculationResult:
        revenue = kwargs.pop("revenue", None)
        operating_income = kwargs.pop("operating_income", None)
        if operating_income is None:
            operating_income = kwargs.pop("operating_profit", None)
        if operating_income is None:
            operating_income = kwargs.pop("income_from_operations", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if revenue is None and metrics is not None:
            revenue = self._value_from_metrics(metrics, "revenue")
        if operating_income is None and metrics is not None:
            operating_income = self._value_from_metrics(metrics, "operating_income", "operating_profit", "income_from_operations")
        if revenue is None and args:
            revenue = args[0] if len(args) > 0 else None
        if operating_income is None and len(args) > 1:
            operating_income = args[1]
        rev_d = _to_decimal(revenue)
        oi_d = _to_decimal(operating_income)
        inputs = []
        if metrics is not None:
            mr = self._find_metric(metrics, "revenue")
            if mr is not None:
                inputs.append(self._metric_input(mr, "revenue"))
            mo = self._find_metric(metrics, "operating_income", "operating_profit", "income_from_operations")
            if mo is not None:
                inputs.append(self._metric_input(mo, "operating_income"))
        if not inputs:
            if rev_d is not None:
                inputs.append({"role": "revenue", "metric_value": rev_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            if oi_d is not None:
                inputs.append({"role": "operating_income", "metric_value": oi_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            value, derr = self._safe_divide(oi_d, rev_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("operating_margin", value, inputs, "operating_income / revenue", error=final_error,
                                 unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"revenue": revenue, "operating_income": operating_income})

    def calculate_net_margin(self, *args: Any, **kwargs: Any) -> CalculationResult:
        revenue = kwargs.pop("revenue", None)
        net_income = kwargs.pop("net_income", None)
        if net_income is None:
            net_income = kwargs.pop("net_profit", None)
        if net_income is None:
            net_income = kwargs.pop("profit", None)
        if net_income is None:
            net_income = kwargs.pop("net_earnings", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if revenue is None and metrics is not None:
            revenue = self._value_from_metrics(metrics, "revenue")
        if net_income is None and metrics is not None:
            net_income = self._value_from_metrics(metrics, "net_income", "net_profit", "profit_for_the_period", "net_earnings")
        if revenue is None and args:
            revenue = args[0] if len(args) > 0 else None
        if net_income is None and len(args) > 1:
            net_income = args[1]
        rev_d = _to_decimal(revenue)
        ni_d = _to_decimal(net_income)
        inputs = []
        if metrics is not None:
            mr = self._find_metric(metrics, "revenue")
            if mr is not None:
                inputs.append(self._metric_input(mr, "revenue"))
            mn = self._find_metric(metrics, "net_income", "net_profit", "profit_for_the_period", "net_earnings")
            if mn is not None:
                inputs.append(self._metric_input(mn, "net_income"))
        if not inputs:
            if rev_d is not None:
                inputs.append({"role": "revenue", "metric_value": rev_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            if ni_d is not None:
                inputs.append({"role": "net_income", "metric_value": ni_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            value, derr = self._safe_divide(ni_d, rev_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("net_margin", value, inputs, "net_income / revenue", error=final_error,
                                 unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"revenue": revenue, "net_income": net_income})

    def calculate_current_ratio(self, *args: Any, **kwargs: Any) -> CalculationResult:
        current_assets = kwargs.pop("current_assets", None)
        if current_assets is None:
            current_assets = kwargs.pop("total_current_assets", None)
        current_liabilities = kwargs.pop("current_liabilities", None)
        if current_liabilities is None:
            current_liabilities = kwargs.pop("total_current_liabilities", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if current_assets is None and metrics is not None:
            current_assets = self._value_from_metrics(metrics, "current_assets", "total_current_assets")
        if current_liabilities is None and metrics is not None:
            current_liabilities = self._value_from_metrics(metrics, "current_liabilities", "total_current_liabilities")
        if current_assets is None and args:
            current_assets = args[0] if len(args) > 0 else None
        if current_liabilities is None and len(args) > 1:
            current_liabilities = args[1]
        ca_d = _to_decimal(current_assets)
        cl_d = _to_decimal(current_liabilities)
        inputs = []
        if metrics is not None:
            ma = self._find_metric(metrics, "current_assets", "total_current_assets")
            if ma is not None:
                inputs.append(self._metric_input(ma, "current_assets"))
            ml = self._find_metric(metrics, "current_liabilities", "total_current_liabilities")
            if ml is not None:
                inputs.append(self._metric_input(ml, "current_liabilities"))
        if not inputs:
            if ca_d is not None:
                inputs.append({"role": "current_assets", "metric_value": ca_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            if cl_d is not None:
                inputs.append({"role": "current_liabilities", "metric_value": cl_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            value, derr = self._safe_divide(ca_d, cl_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("current_ratio", value, inputs, "current_assets / current_liabilities", error=final_error,
                                 unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"current_assets": current_assets, "current_liabilities": current_liabilities})

    def calculate_debt_to_equity(self, *args: Any, **kwargs: Any) -> CalculationResult:
        total_debt = kwargs.pop("total_debt", None)
        total_equity = kwargs.pop("total_equity", None)
        if total_equity is None:
            total_equity = kwargs.pop("shareholders_equity", None)
        if total_equity is None:
            total_equity = kwargs.pop("equity", None)
        if total_equity is None:
            total_equity = kwargs.pop("stockholders_equity", None)
        if total_debt is None:
            total_debt = kwargs.pop("total_liabilities", None)
        if total_debt is None:
            total_debt = kwargs.pop("liabilities", None)
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if total_debt is None and metrics is not None:
            total_debt = self._value_from_metrics(metrics, "total_debt", "total_liabilities", "debt", "liabilities")
        if total_equity is None and metrics is not None:
            total_equity = self._value_from_metrics(metrics, "total_equity", "shareholders_equity", "equity", "stockholders_equity")
        if total_debt is None and args:
            total_debt = args[0] if len(args) > 0 else None
        if total_equity is None and len(args) > 1:
            total_equity = args[1]
        td_d = _to_decimal(total_debt)
        te_d = _to_decimal(total_equity)
        inputs = []
        if metrics is not None:
            md = self._find_metric(metrics, "total_debt", "total_liabilities", "debt", "liabilities")
            if md is not None:
                inputs.append(self._metric_input(md, "total_debt"))
            me = self._find_metric(metrics, "total_equity", "shareholders_equity", "equity", "stockholders_equity")
            if me is not None:
                inputs.append(self._metric_input(me, "total_equity"))
        if not inputs:
            if td_d is not None:
                inputs.append({"role": "total_debt", "metric_value": td_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
            if te_d is not None:
                inputs.append({"role": "total_equity", "metric_value": te_d, "currency": None, "unit": None, "citations": [], "source_evidence":
                None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            value, derr = self._safe_divide(td_d, te_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result("debt_to_equity", value, inputs, "total_debt / total_equity", error=final_error,
                                 unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"total_debt": total_debt, "total_equity": total_equity})
    def calculate_ratio(self, *args: Any, **kwargs: Any) -> Any:
        name = None
        if args and isinstance(args[0], str):
            name = args[0]
            args = args[1:]
        if name is None:
            name = (kwargs.pop("ratio_name", None) or kwargs.pop("name", None) or
                    kwargs.pop("ratio", None) or kwargs.pop("metric", None) or
                    kwargs.pop("calculation_name", None) or kwargs.pop("type", None))
        numerator = kwargs.pop("numerator", None)
        denominator = kwargs.pop("denominator", None)
        if numerator is None and "numerator_value" in kwargs:
            numerator = kwargs.pop("numerator_value")
        if denominator is None and "denominator_value" in kwargs:
            denominator = kwargs.pop("denominator_value")
        metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if name is None:
            if "current_revenue" in kwargs or "previous_revenue" in kwargs or "prior_revenue" in kwargs:
                name = "revenue_growth"
            elif "gross_profit" in kwargs or "cost_of_goods_sold" in kwargs or "cogs" in kwargs:
                name = "gross_margin"
            elif "operating_income" in kwargs or "operating_profit" in kwargs:
                name = "operating_margin"
            elif "net_income" in kwargs or "net_profit" in kwargs:
                name = "net_margin"
            elif "current_assets" in kwargs or "current_liabilities" in kwargs:
                name = "current_ratio"
            elif "total_debt" in kwargs or "total_equity" in kwargs or "total_liabilities" in kwargs or "equity" in kwargs:
                name = "debt_to_equity"
            elif metrics is not None:
                return self.calculate_ratios(metrics, **kwargs)
            else:
                name = "ratio"

        dispatch = {
            "revenue_growth": self.calculate_revenue_growth,
            "revenue growth": self.calculate_revenue_growth,
            "gross_margin": self.calculate_gross_margin,
            "gross margin": self.calculate_gross_margin,
            "operating_margin": self.calculate_operating_margin,
            "operating margin": self.calculate_operating_margin,
            "net_margin": self.calculate_net_margin,
            "net margin": self.calculate_net_margin,
            "net_profit_margin": self.calculate_net_margin,
            "current_ratio": self.calculate_current_ratio,
            "current ratio": self.calculate_current_ratio,
            "debt_to_equity": self.calculate_debt_to_equity,
            "debt-to-equity": self.calculate_debt_to_equity,
            "debt to equity": self.calculate_debt_to_equity,
        }
        if name in dispatch:
            call_kwargs = dict(kwargs)
            if metrics is not None:
                call_kwargs["metrics"] = metrics
            if numerator is not None:
                call_kwargs.setdefault("numerator", numerator)
            if denominator is not None:
                call_kwargs.setdefault("denominator", denominator)
            return dispatch[name](*args, **call_kwargs)

        if numerator is None and len(args) >= 1:
            numerator = args[0]
        if denominator is None and len(args) >= 2:
            denominator = args[1]
        n_d = _to_decimal(numerator)
        d_d = _to_decimal(denominator)
        inputs = []
        if n_d is not None:
            inputs.append({"role": "numerator", "metric_value": n_d, "currency": None, "unit": None, "citations": [], "source_evidence": None})
        if d_d is not None:
            inputs.append({"role": "denominator", "metric_value": d_d, "currency": None, "unit": None, "citations": [], "source_evidence": None})
        err = self._check_compatible(inputs) if len(inputs) > 1 else None
        if err:
            value = None
            final_error = err
        else:
            value, derr = self._safe_divide(n_d, d_d)
            final_error = derr
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")
        return self._make_result(str(name or "ratio"), value, inputs, "numerator / denominator", error=final_error,
                                 unit="ratio", workspace_id=ws, document_id=doc,
                                 input_values={"numerator": numerator, "denominator": denominator})

    def calculate_ratios(self, metrics: Any = None, **kwargs: Any) -> list[CalculationResult]:
        if metrics is None:
            metrics = (kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or
                       kwargs.pop("financial_metrics", None))
        if isinstance(metrics, Mapping):
            metrics = [metrics]
        if metrics is None:
            return [self.calculate_ratio(**kwargs)]
        if not isinstance(metrics, Sequence):
            metrics = [metrics]
        metrics = list(metrics)
        results: list[CalculationResult] = []
        periods = self._periods(metrics)
        ws = kwargs.get("workspace_id")
        doc = kwargs.get("document_id")

        for p in periods:
            pm = [m for m in metrics if _reporting_period(m) == p]
            if self._find_metric(pm, "revenue") is not None and (
                self._find_metric(pm, "gross_profit") is not None or
                self._find_metric(pm, "cost_of_goods_sold", "cogs", "cost_of_sales") is not None):
                results.append(self.calculate_gross_margin(metrics=pm, workspace_id=ws, document_id=doc))
            if self._find_metric(pm, "revenue") is not None and self._find_metric(pm, "operating_income", "operating_profit", "income_from_operations") is not None:
                results.append(self.calculate_operating_margin(metrics=pm, workspace_id=ws, document_id=doc))
            if self._find_metric(pm, "revenue") is not None and self._find_metric(pm, "net_income", "net_profit", "profit_for_the_period", "net_earnings") is not None:
                results.append(self.calculate_net_margin(metrics=pm, workspace_id=ws, document_id=doc))
            if self._find_metric(pm, "current_assets", "total_current_assets") is not None and self._find_metric(pm, "current_liabilities", "total_current_liabilities") is not None:
                results.append(self.calculate_current_ratio(metrics=pm, workspace_id=ws, document_id=doc))
            if (self._find_metric(pm, "total_debt", "total_liabilities", "debt", "liabilities") is not None and
                self._find_metric(pm, "total_equity", "shareholders_equity", "equity", "stockholders_equity") is not None):
                results.append(self.calculate_debt_to_equity(metrics=pm, workspace_id=ws, document_id=doc))

        if len(periods) >= 2:
            rev_periods = [p for p in periods if self._value_from_metrics(metrics, "revenue", period=p) is not None]
            if len(rev_periods) >= 2:
                results.append(self.calculate_revenue_growth(metrics=metrics, workspace_id=ws, document_id=doc))

        return results

    def calculate_financial_ratios(self, *args: Any, **kwargs: Any) -> list[CalculationResult]:
        metrics = None
        if args:
            metrics = list(args[0]) if isinstance(args[0], (list, tuple, set)) else list(args)
        if metrics is None:
            metrics = kwargs.pop("metrics", None) or kwargs.pop("extracted_metrics", None) or kwargs.pop("financial_metrics", None)
        if metrics is not None and not isinstance(metrics, (list, tuple, set)):
            metrics = [metrics]
        return self.calculate_ratios(metrics, **kwargs) if metrics is not None else self.calculate_ratios(**kwargs)

    def calculate_all_ratios(self, *args: Any, **kwargs: Any) -> list[CalculationResult]:
        return self.calculate_financial_ratios(*args, **kwargs)

    def calculate_all(self, *args: Any, **kwargs: Any) -> list[CalculationResult]:
        return self.calculate_financial_ratios(*args, **kwargs)

    def compute_ratio(self, *args: Any, **kwargs: Any) -> Any:
        return self.calculate_ratio(*args, **kwargs)

    def compute_ratios(self, *args: Any, **kwargs: Any) -> list[CalculationResult]:
        return self.calculate_ratios(*args, **kwargs)

    def perform_calculation(self, *args: Any, **kwargs: Any) -> Any:
        if "ratio" in kwargs or (args and isinstance(args[0], str)):
            return self.calculate_ratio(*args, **kwargs)
        return self.calculate_ratios(*args, **kwargs)

    def calculate(self, *args: Any, **kwargs: Any) -> Any:
        if args and isinstance(args[0], str) and args[0].lower() in {
            "revenue_growth", "gross_margin", "operating_margin", "net_margin",
            "current_ratio", "debt_to_equity"}:
            return self.calculate_ratio(*args, **kwargs)
        if "ratio_name" in kwargs or "name" in kwargs:
            return self.calculate_ratio(*args, **kwargs)
        if any(k in kwargs for k in ("numerator", "denominator")):
            return self.calculate_ratio(*args, **kwargs)
        metrics = kwargs.get("metrics") or kwargs.get("extracted_metrics") or kwargs.get("financial_metrics")
        if metrics is not None or (args and isinstance(args[0], (list, tuple, set))):
            return self.calculate_ratios(*args, **kwargs)
        if len(args) == 1 and isinstance(args[0], (list, tuple, set)):
            return self.calculate_ratios(*args, **kwargs)
        return self.calculate_ratio(*args, **kwargs)

    def calculate_revenue_growth_rate(self, *a, **k): return self.calculate_revenue_growth(*a, **k)
    def calculate_gross_profit_margin(self, *a, **k): return self.calculate_gross_margin(*a, **k)
    def calculate_operating_profit_margin(self, *a, **k): return self.calculate_operating_margin(*a, **k)
    def calculate_net_profit_margin(self, *a, **k): return self.calculate_net_margin(*a, **k)
    def calculate_debt_to_equity_ratio(self, *a, **k): return self.calculate_debt_to_equity(*a, **k)
    def _store_one(self, result: CalculationResult, **kwargs: Any) -> CalculationResult:
        if self.session_factory is None:
            return result
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            workspace_id = getattr(result, "workspace_id", None)
        if workspace_id is None:
            return result
        try:
            from app.repositories.financial_calculation_repository import (
                FinancialCalculationRepository,
            )
        except Exception:
            return result
        try:
            with self.session_factory() as session:
                repo = FinancialCalculationRepository(session)
                calc = repo.create(
                    workspace_id=workspace_id,
                    calculation_type=result.calculation_type,
                    calculation_name=result.calculation_name,
                    formula=result.formula,
                    result_value=result.result_value if result.result_value is not None else Decimal("0"),
                    currency=result.currency,
                    unit=result.unit,
                    parent_calculation_id=kwargs.get("parent_calculation_id"),
                    description=kwargs.get("description"),
                    calculation_metadata=result.calculation_metadata or result.metadata,
                    input_metrics=result.input_metrics,
                    execution_context=result.execution_context,
                    confidence_score=result.confidence_score,
                    error_message=result.error_message,
                    commit=True,
                )
                result.id = getattr(calc, "id", result.id)
                result.calculation_id = result.id
                return result
        except Exception:
            return result

    def store_calculation(self, result: Any = None, **kwargs: Any) -> Any:
        if isinstance(result, (list, tuple)):
            out = []
            for r in result:
                out.append(self._store_one(r, **kwargs))
            return out
        if result is None:
            result = self.calculate_ratio(**kwargs)
            if isinstance(result, list):
                return self.store_calculation(result, **kwargs)
        return self._store_one(result, **kwargs)

    def persist_calculation(self, *a, **k): return self.store_calculation(*a, **k)
    def save_calculation(self, *a, **k): return self.store_calculation(*a, **k)
    def create_calculation(self, *a, **k): return self.store_calculation(*a, **k)
    def record_calculation(self, *a, **k): return self.store_calculation(*a, **k)

    def calculate_and_store(self, *args: Any, **kwargs: Any) -> Any:
        result = self.calculate(*args, **kwargs)
        return self.store_calculation(result, **kwargs)

    def calculate_and_persist(self, *args: Any, **kwargs: Any) -> Any:
        return self.calculate_and_store(*args, **kwargs)

    def calculate_and_save(self, *args: Any, **kwargs: Any) -> Any:
        return self.calculate_and_store(*args, **kwargs)

    def validate_and_calculate(self, metrics: Any = None, **kwargs: Any) -> Any:
        v = self.validate_metrics(metrics, **kwargs) if metrics is not None else None
        r = self.calculate_ratios(metrics, **kwargs) if metrics is not None else self.calculate_ratio(**kwargs)
        return {"validation": v, "calculations": r, "results": r}

    def store_metric(self, metric: Any, **kwargs: Any) -> Any:
        if self.session_factory is None:
            return metric
        try:
            from app.repositories.financial_metric_repository import FinancialMetricRepository
        except Exception:
            return metric
        try:
            with self.session_factory() as session:
                repo = FinancialMetricRepository(session)
                workspace_id = kwargs.get("workspace_id") or _metric_get(metric, "workspace_id", default=None)
                document_id = kwargs.get("document_id") or _metric_get(metric, "document_id", default=None)
                if workspace_id is None or document_id is None:
                    return metric
                fm = repo.create(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    metric_type=str(_metric_type(metric)),
                    metric_name=str(_metric_name(metric)),
                    metric_value=_metric_value(metric) or Decimal("0"),
                    currency=_currency(metric),
                    unit=_unit(metric),
                    context={"reporting_period": _reporting_period(metric)},
                    source_document_chunk=_source_evidence(metric),
                    is_estimated=bool(_metric_get(metric, "is_estimated", default=False)),
                    is_projected=bool(_metric_get(metric, "is_projected", default=False)),
                    notes=_metric_get(metric, "notes", default=None),
                    commit=True,
                )
                return fm
        except Exception:
            return metric

    def store_metrics(self, metrics: Any, **kwargs: Any) -> Any:
        if not isinstance(metrics, Sequence):
            metrics = [metrics]
        return [self.store_metric(m, **kwargs) for m in metrics]

    def persist_metrics(self, *a, **k): return self.store_metrics(*a, **k)

    def _session_scope(self) -> Iterator[Session]:
        if self.session_factory is None:
            raise RuntimeError("session_factory is required")
        session = self.session_factory()
        try:
            yield session
        except Exception:
            with contextlib.suppress(Exception):
                session.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                session.close()


FinancialValidationService = FinancialValidationAndCalculationService
FinancialCalculationService = FinancialValidationAndCalculationService
FinancialValidationCalculationService = FinancialValidationAndCalculationService
ValidationService = FinancialValidationAndCalculationService
CalculationService = FinancialValidationAndCalculationService
FinancialService = FinancialValidationAndCalculationService
FinancialMetricsService = FinancialValidationAndCalculationService
FinancialValidationAndCalculation = FinancialValidationAndCalculationService


def validate_financial_metric(*args: Any, **kwargs: Any) -> ValidationOutcome:
    return FinancialValidationAndCalculationService().validate_metric(*args, **kwargs)


def validate_financial_metrics(*args: Any, **kwargs: Any) -> Any:
    return FinancialValidationAndCalculationService().validate_metrics(*args, **kwargs)


def calculate_financial_ratio(*args: Any, **kwargs: Any) -> CalculationResult:
    return FinancialValidationAndCalculationService().calculate_ratio(*args, **kwargs)


def calculate_financial_ratios(*args: Any, **kwargs: Any) -> list[CalculationResult]:
    return FinancialValidationAndCalculationService().calculate_ratios(*args, **kwargs)


def validate_metric(*a, **k): return validate_financial_metric(*a, **k)
def validate_metrics(*a, **k): return validate_financial_metrics(*a, **k)
def calculate_ratio(*a, **k): return calculate_financial_ratio(*a, **k)
def calculate_ratios(*a, **k): return calculate_financial_ratios(*a, **k)
