"""Financial Extraction Agent."""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.citations import Citation

__all__ = [
    "Citation",
    "ExtractedFinancialMetric",
    "ExtractionAgent",
    "ExtractionResult",
    "ExtractionStrategy",
    "FinancialExtractionAgent",
    "FinancialExtractionResult",
    "FinancialMetricExtractor",
    "LLMExtractionStrategy",
    "MetricValidator",
    "TableExtractionStrategy",
    "TextExtractionStrategy",
    "validate_extracted_value",
]

_KNOWN_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD", "INR", "BRL",
    "SEK", "NOK", "DKK", "NZD", "ZAR", "HKD", "SGD", "KRW", "MXN", "RUB",
})

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "?": "INR"}
_UNIT_WORDS = ("billion", "million", "thousand", "percent", "%")


def _to_decimal(value):
    if value is None:
        return None
    if isinstance(value, bool):
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
    text = text.replace("$", "").replace("€", "").replace("£", "")
    text = text.replace("(", "-").replace(")", "")
    text = text.strip()
    for unit in _UNIT_WORDS:
        if text.lower().endswith(unit):
            text = text[: -len(unit)].strip()
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _currency_from_text(text):
    if not text:
        return None
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    upper = text.upper()
    for code in _KNOWN_CURRENCIES:
        if re.search(rf"\b{code}\b", upper):
            return code
    return None


def _unit_from_text(text):
    if not text:
        return None
    lowered = text.lower()
    for unit in _UNIT_WORDS:
        if unit in lowered:
            return unit
    return None


def _period_from_text(text):
    if not text:
        return None
    try:
        from app.ingestion.metadata import detect_fiscal_period
        label, _ = detect_fiscal_period(text)
        if label:
            return label
    except Exception:
        pass
    match = re.search(r"\bFY\s*[-/]?\s*(20\d{2})\b", text, re.IGNORECASE)
    if match:
        return f"FY{match.group(1)}"
    match = re.search(r"\bQ([1-4])\s*(20\d{2})\b", text, re.IGNORECASE)
    if match:
        return f"Q{match.group(1)} {match.group(2)}"
    return None


def _sentence_around(text, position, window=120):
    if not text:
        return ""
    start = max(0, position - window)
    end = min(len(text), position + window)
    return " ".join(text[start:end].split())


def _dedupe(metrics):
    seen = set()
    result = []
    for metric in metrics:
        key = (metric.metric_type, str(metric.metric_value), metric.reporting_period, metric.currency)
        if key in seen:
            continue
        seen.add(key)
        result.append(metric)
    return result
@dataclass
class ExtractedFinancialMetric:
    metric_type: str
    metric_name: str
    metric_value: Any
    currency: Any = None
    unit: Any = None
    reporting_period: Any = None
    period: Any = None
    source_evidence: Any = None
    evidence: Any = None
    source_text: Any = None
    source_excerpt: Any = None
    source_document_chunk: Any = None
    citation: Any = None
    citations: list = field(default_factory=list)
    confidence: float = 1.0
    strategy: str = "text"
    extraction_strategy: Any = None
    is_estimated: bool = False
    is_projected: bool = False
    is_valid: bool = True
    validated: bool = False
    validation_errors: list = field(default_factory=list)
    notes: Any = None
    context: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    id: Any = None

    def __post_init__(self):
        if self.period is None:
            self.period = self.reporting_period
        else:
            self.reporting_period = self.period
        if self.evidence is None:
            self.evidence = self.source_evidence
        if self.source_evidence is None:
            self.source_evidence = self.evidence
        if self.source_text is None:
            self.source_text = self.source_evidence
        if self.source_excerpt is None:
            self.source_excerpt = self.source_evidence
        if self.source_document_chunk is None:
            self.source_document_chunk = self.source_evidence
        if self.extraction_strategy is None:
            self.extraction_strategy = self.strategy
        else:
            self.strategy = self.extraction_strategy
        if self.citation is None:
            self.citation = {}
        if isinstance(self.citation, Citation):
            self.citation = self.citation.to_dict()
        if not isinstance(self.citation, (dict, list, tuple)):
            self.citation = {"value": self.citation}
        if not self.citations and isinstance(self.citation, dict) and self.citation:
            self.citations = [self.citation]
        if isinstance(self.currency, str):
            self.currency = self.currency.strip().upper() or None
        if self.currency is None:
            self.currency = _currency_from_text(str(self.source_evidence or ""))
        if self.unit is None:
            self.unit = _unit_from_text(str(self.source_evidence or ""))
        if self.reporting_period is None:
            self.reporting_period = _period_from_text(str(self.source_evidence or ""))
        self.period = self.reporting_period

    @property
    def value(self):
        return self.metric_value

    @property
    def name(self):
        return self.metric_name

    @property
    def type(self):
        return self.metric_type

    @property
    def metric(self):
        return self.metric_name

    def as_dict(self):
        return {
            "metric_type": self.metric_type,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "value": self.metric_value,
            "currency": self.currency,
            "unit": self.unit,
            "reporting_period": self.reporting_period,
            "period": self.reporting_period,
            "source_evidence": self.source_evidence,
            "evidence": self.source_evidence,
            "citation": self.citation,
            "citations": self.citations,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "is_estimated": self.is_estimated,
            "is_projected": self.is_projected,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "notes": self.notes,
            "context": self.context,
        }

    def to_dict(self):
        return self.as_dict()


FinancialMetricExtraction = ExtractedFinancialMetric
ExtractedMetric = ExtractedFinancialMetric
MetricExtraction = ExtractedFinancialMetric
ExtractionMetric = ExtractedFinancialMetric
class ExtractionResult:
    def __init__(self, metrics=None, *, extracted_metrics=None, financial_metrics=None,
                 reporting_periods=None, periods=None, currencies=None, strategies=None,
                 extraction_strategies=None, warnings=None, errors=None, metadata=None,
                 context=None, document_id=None, workspace_id=None):
        resolved = metrics
        if resolved is None:
            resolved = extracted_metrics
        if resolved is None:
            resolved = financial_metrics
        self.metrics = list(resolved or [])
        self.extracted_metrics = self.metrics
        self.financial_metrics = self.metrics
        self.reporting_periods = list(reporting_periods if reporting_periods is not None else (periods or []))
        self.periods = self.reporting_periods
        self.currencies = list(currencies or [])
        self.strategies = list(strategies if strategies is not None else (extraction_strategies or []))
        self.extraction_strategies = self.strategies
        self.warnings = list(warnings or [])
        self.errors = list(errors or [])
        self.metadata = dict(metadata or {})
        self.context = dict(context or {})
        self.document_id = document_id
        self.workspace_id = workspace_id

    def __iter__(self):
        return iter(self.metrics)

    def __len__(self):
        return len(self.metrics)

    def __getitem__(self, index):
        return self.metrics[index]

    def __bool__(self):
        return bool(self.metrics)

    def to_list(self):
        return [m.as_dict() for m in self.metrics]

    def to_dict(self):
        return {
            "metrics": [m.as_dict() for m in self.metrics],
            "reporting_periods": self.reporting_periods,
            "currencies": self.currencies,
            "strategies": self.strategies,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    @property
    def data(self):
        return self.metrics


FinancialExtractionResult = ExtractionResult
@runtime_checkable
class ExtractionStrategy(Protocol):
    name: str

    def extract(self, text="", *, tables=None, context=None, **kwargs):
        ...

class TextExtractionStrategy:
    name = "text"

    def __init__(self, patterns=None):
        self.patterns = dict(patterns or {})

    def extract(self, text="", *, tables=None, context=None, **kwargs):
        context = context or {}
        text = text or kwargs.get("document_text") or kwargs.get("content") or ""
        if not isinstance(text, str):
            text = str(text or "")
        metrics = []
        keyword_groups = {
            "revenue": ["revenue", "net sales", "total revenue", "net revenue"],
            "net_income": ["net income", "net profit", "profit for the period", "net earnings"],
            "operating_income": ["operating income", "operating profit", "income from operations"],
            "gross_profit": ["gross profit"],
            "ebitda": ["ebitda"],
            "eps": ["earnings per share", "eps", "diluted eps", "basic eps"],
            "total_assets": ["total assets"],
            "total_liabilities": ["total liabilities"],
            "cash_and_equivalents": ["cash and cash equivalents", "cash and equivalents"],
            "operating_cash_flow": ["operating cash flow", "cash from operations"],
        }
        keyword_groups.update({k: list(v) for k, v in self.patterns.items()})
        global_period = _period_from_text(text)
        global_currency = _currency_from_text(text)
        for metric_type, keywords in keyword_groups.items():
            for keyword in keywords:
                for match in re.finditer(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
                    ws = max(0, match.start() - 80)
                    we = min(len(text), match.end() + 80)
                    window = text[ws:we]
                    num_match = re.search(
                        r"[\$€£¥?]?\s*\(?\d[\d,\.]*\)?\s*(?:billion|million|thousand|percent|%|bps)?",
                        window, re.IGNORECASE,
                    )
                    if num_match is None:
                        continue
                    value = _to_decimal(num_match.group(0))
                    if value is None:
                        continue
                    currency = _currency_from_text(window) or global_currency
                    unit = _unit_from_text(num_match.group(0)) or _unit_from_text(window)
                    period = _period_from_text(window) or global_period
                    evidence = _sentence_around(text, match.start())
                    citation = {
                        "strategy": "text",
                        "excerpt": evidence,
                        "page": context.get("page") if isinstance(context, Mapping) else None,
                        "page_start": context.get("page_start") if isinstance(context, Mapping) else None,
                        "page_end": context.get("page_end") if isinstance(context, Mapping) else None,
                        "section": context.get("section") if isinstance(context, Mapping) else None,
                        "document_id": context.get("document_id") if isinstance(context, Mapping) else None,
                    }
                    metrics.append(ExtractedFinancialMetric(
                        metric_type=metric_type,
                        metric_name=keyword.title(),
                        metric_value=value,
                        currency=currency,
                        unit=unit,
                        reporting_period=period,
                        source_evidence=evidence,
                        citation=citation,
                        confidence=0.7,
                        strategy="text",
                    ))
        return _dedupe(metrics)
class TableExtractionStrategy:
    name = "table"

    def __init__(self, header_period_row=True):
        self.header_period_row = header_period_row

    def _normalize_tables(self, tables):
        result = []
        if tables is None:
            return result
        if isinstance(tables, Mapping):
            for key, value in tables.items():
                if isinstance(value, (list, tuple)):
                    for item in value:
                        result.append((int(key) if str(key).isdigit() else None, item))
                else:
                    result.append((int(key) if str(key).isdigit() else None, value))
            return result
        if isinstance(tables, (list, tuple)):
            for item in tables:
                if isinstance(item, (list, tuple)) and item and isinstance(item[0], (list, tuple)):
                    result.append((None, item))
                elif hasattr(item, "rows"):
                    result.append((getattr(item, "page_number", None), item))
                else:
                    result.append((None, item))
        return result

    def _table_rows(self, table):
        if hasattr(table, "header") and hasattr(table, "rows"):
            rows = [list(table.header)] if getattr(table, "header", None) else []
            rows.extend(list(r) for r in getattr(table, "rows", ()))
            return rows
        if isinstance(table, (list, tuple)):
            return [list(r) if isinstance(r, (list, tuple)) else [str(r)] for r in table]
        if isinstance(table, Mapping):
            keys = list(table.keys())
            length = max((len(v) if isinstance(v, Sequence) else 1) for v in table.values()) if table else 0
            rows = [keys]
            for i in range(length):
                rows.append([table[k][i] if isinstance(table[k], Sequence) else table[k] for k in keys])
            return rows
        return [[str(table)]]

    def extract(self, text="", *, tables=None, context=None, **kwargs):
        context = context or {}
        tables = tables if tables is not None else kwargs.get("tables")
        metrics = []
        for page_number, table in self._normalize_tables(tables):
            rows = self._table_rows(table)
            if not rows:
                continue
            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            column_periods = []
            for col in header:
                column_periods.append(_period_from_text(col) or (col if col else None))
            table_index = getattr(table, "table_index", None)
            for row_index, row in enumerate(rows[1:], start=1):
                if not row:
                    continue
                cells = [str(c).strip() if c is not None else "" for c in row]
                metric_name = cells[0] if cells else ""
                if not metric_name:
                    continue
                if metric_name.lower() in {"metric", "item", "description"}:
                    continue
                metric_type = metric_name.lower().replace(" ", "_")
                for col_index, cell in enumerate(cells[1:], start=1):
                    value = _to_decimal(cell)
                    if value is None:
                        continue
                    period = column_periods[col_index] if col_index < len(column_periods) else None
                    currency = _currency_from_text(header[col_index] if col_index < len(header) else "") or _currency_from_text(cell)
                    unit = _unit_from_text(cell) or _unit_from_text(header[col_index] if col_index < len(header) else "")
                    citation = {
                        "strategy": "table",
                        "page": page_number,
                        "page_start": page_number,
                        "page_end": page_number,
                        "table_index": table_index,
                        "row_index": row_index,
                        "excerpt": " | ".join(cells),
                        "document_id": context.get("document_id") if isinstance(context, Mapping) else None,
                    }
                    metrics.append(ExtractedFinancialMetric(
                        metric_type=metric_type,
                        metric_name=metric_name,
                        metric_value=value,
                        currency=currency,
                        unit=unit,
                        reporting_period=period,
                        source_evidence=" | ".join(cells),
                        citation=citation,
                        confidence=0.85,
                        strategy="table",
                    ))
        return _dedupe(metrics)
class LLMExtractionStrategy:
    name = "llm"

    def __init__(self, llm=None, *, prompt_template=None, model=None, client=None):
        self.llm = llm
        self.model = model
        self.client = client
        self.prompt_template = prompt_template or (
            "Extract financial metrics from the following document. "
            "Return a JSON list of objects with keys: metric_type, metric_name, "
            "metric_value, currency, unit, reporting_period, source_evidence.\n\n"
            "TEXT:\n{text}\n\nTABLES:\n{tables}"
        )

    def _call_llm(self, prompt):
        if self.llm is not None:
            return self.llm(prompt)
        if self.client is not None and hasattr(self.client, "complete"):
            return self.client.complete(prompt)
        if self.model is not None and hasattr(self.model, "predict"):
            return self.model.predict(prompt)
        return None

    def _parse_response(self, response):
        if response is None:
            return []
        if isinstance(response, (list, tuple)):
            return [item for item in response if isinstance(item, Mapping)]
        if isinstance(response, Mapping):
            for key in ("metrics", "extracted_metrics", "financial_metrics", "data", "results"):
                if isinstance(response.get(key), (list, tuple)):
                    return [item for item in response[key] if isinstance(item, Mapping)]
            if "metric_name" in response or "metric_type" in response:
                return [response]
            return []
        text = str(response)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [item for item in parsed if isinstance(item, Mapping)]
            except json.JSONDecodeError:
                pass
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, Mapping)]
            if isinstance(parsed, Mapping):
                return self._parse_response(parsed)
        except json.JSONDecodeError:
            pass
        return []

    def extract(self, text="", *, tables=None, context=None, **kwargs):
        context = context or {}
        text = text or kwargs.get("document_text") or kwargs.get("content") or ""
        if not isinstance(text, str):
            text = str(text or "")
        tables = tables if tables is not None else kwargs.get("tables")
        prompt = self.prompt_template.format(text=text, tables=tables)
        try:
            response = self._call_llm(prompt)
        except Exception:
            return []
        items = self._parse_response(response)
        metrics = []
        for item in items:
            value = _to_decimal(item.get("metric_value", item.get("value")))
            if value is None:
                continue
            metrics.append(ExtractedFinancialMetric(
                metric_type=str(item.get("metric_type") or item.get("type") or "financial_metric"),
                metric_name=str(item.get("metric_name") or item.get("name") or item.get("metric") or "metric"),
                metric_value=value,
                currency=item.get("currency"),
                unit=item.get("unit"),
                reporting_period=item.get("reporting_period", item.get("period")),
                source_evidence=item.get("source_evidence", item.get("evidence", item.get("source_text"))),
                citation=item.get("citation", {}),
                confidence=float(item.get("confidence", 0.9)),
                strategy="llm",
            ))
        return _dedupe(metrics)
def validate_extracted_value(metric, *, max_value=Decimal("999999999999.99")):
    errors = []
    value = _to_decimal(metric.metric_value)
    if value is None:
        errors.append("invalid_value")
    else:
        if abs(value) > max_value:
            errors.append("value_out_of_range")
    if not metric.metric_name:
        errors.append("missing_metric_name")
    if not metric.metric_type:
        errors.append("missing_metric_type")
    if metric.currency is not None and metric.currency not in _KNOWN_CURRENCIES:
        errors.append("unknown_currency")
    if metric.reporting_period is None:
        errors.append("missing_reporting_period")
    if not (metric.source_evidence or metric.source_document_chunk or metric.source_text):
        errors.append("missing_source_evidence")
    return errors


class MetricValidator:
    def __init__(self, *, max_value=Decimal("999999999999.99"), require_period=False, require_currency=False):
        self.max_value = max_value
        self.require_period = require_period
        self.require_currency = require_currency

    def validate(self, metric):
        errors = validate_extracted_value(metric, max_value=self.max_value)
        if not self.require_period and "missing_reporting_period" in errors:
            errors = [e for e in errors if e != "missing_reporting_period"]
        if not self.require_currency and "unknown_currency" in errors and metric.currency is None:
            errors = [e for e in errors if e != "unknown_currency"]
        metric.validation_errors = errors
        metric.is_valid = not errors
        metric.validated = True
        return errors

    def validate_many(self, metrics):
        for metric in metrics:
            self.validate(metric)
        return list(metrics)
class FinancialExtractionAgent:
    def __init__(self, *, strategies=None, text_strategy=None, table_strategy=None,
                 llm_strategy=None, llm=None, validator=None, session_factory=None, **kwargs):
        if strategies is not None:
            self.strategies = list(strategies)
        else:
            built = []
            built.append(text_strategy or TextExtractionStrategy())
            built.append(table_strategy or TableExtractionStrategy())
            llm_strat = llm_strategy
            if llm_strat is None and llm is not None:
                llm_strat = LLMExtractionStrategy(llm=llm)
            if llm_strat is not None:
                built.append(llm_strat)
            self.strategies = built
        self.validator = validator or MetricValidator()
        self.session_factory = session_factory or kwargs.get("session_factory")
        self._llm = llm

    def extract(self, source=None, *, text=None, tables=None, document=None, chunks=None,
                document_text=None, content=None, reporting_period=None, currency=None,
                validate=True, **kwargs):
        if source is not None:
            if isinstance(source, str):
                text = source if text is None else text
            elif hasattr(source, "pages"):
                document = source
            elif isinstance(source, (list, tuple)):
                chunks = source if chunks is None else chunks
            else:
                text = str(source) if text is None else text
        if text is None:
            text = document_text if document_text is not None else content
        doc_id = kwargs.get("document_id")
        if (document is None and chunks is None and not text and doc_id is not None
                and self.session_factory is not None):
            try:
                from app.repositories.chunk_repository import ChunkRepository
                with self.session_factory() as session:
                    loaded = ChunkRepository(session).list_by_document(
                        UUID(str(doc_id)), limit=100000, offset=0
                    )
                    text = "\n".join(getattr(c, "content", str(c)) for c in loaded)
            except Exception:
                text = text or ""
        if source is not None and isinstance(source, str):
            try:
                candidate = UUID(source)
            except (ValueError, AttributeError, TypeError):
                candidate = None
            if candidate is not None and document is None and chunks is None and not text and self.session_factory is not None:
                try:
                    from app.repositories.chunk_repository import ChunkRepository
                    with self.session_factory() as session:
                        loaded = ChunkRepository(session).list_by_document(candidate, limit=100000, offset=0)
                        text = "\n".join(getattr(c, "content", str(c)) for c in loaded)
                except Exception:
                    text = str(source)
        if document is not None:
            text, tables = self._from_document(document, text, tables)
        if chunks is not None:
            text = self._from_chunks(chunks, text)
        text = text or ""
        tables = tables if tables is not None else kwargs.get("tables")
        context = {}
        if isinstance(kwargs.get("context"), Mapping):
            context.update(kwargs["context"])
        if kwargs.get("document_id") is not None:
            context["document_id"] = kwargs.get("document_id")
        if kwargs.get("page") is not None:
            context["page"] = kwargs.get("page")
        if reporting_period is not None:
            context["reporting_period"] = reporting_period
        if currency is not None:
            context["currency"] = currency

        metrics = []
        warnings = []
        strategies_used = []
        for strategy in self.strategies:
            name = getattr(strategy, "name", strategy.__class__.__name__)
            try:
                produced = strategy.extract(text=text, tables=tables, context=context, **kwargs)
            except Exception as exc:
                warnings.append(f"{name}: {exc}")
                continue
            strategies_used.append(name)
            for metric in produced or []:
                if not isinstance(metric, ExtractedFinancialMetric):
                    metric = self._coerce_metric(metric, name)
                if reporting_period is not None and metric.reporting_period is None:
                    metric.reporting_period = reporting_period
                    metric.period = reporting_period
                if currency is not None and metric.currency is None:
                    metric.currency = currency
                metrics.append(metric)

        metrics = _dedupe(metrics)
        if validate:
            self.validator.validate_many(metrics)

        periods = sorted({m.reporting_period for m in metrics if m.reporting_period})
        if not periods:
            detected = _period_from_text(text)
            if detected:
                periods = [detected]
        currencies = sorted({m.currency for m in metrics if m.currency})

        return ExtractionResult(
            metrics=metrics,
            reporting_periods=periods,
            currencies=currencies,
            strategies=strategies_used,
            warnings=warnings,
            document_id=kwargs.get("document_id"),
            workspace_id=kwargs.get("workspace_id"),
            context=context,
        )

    def _from_document(self, document, text, tables):
        if hasattr(document, "pages"):
            page_texts = []
            collected_tables = [] if tables is None else tables
            for page in getattr(document, "pages", ()):
                page_texts.append(getattr(page, "text", "") or "")
                if tables is None:
                    collected_tables.extend(getattr(page, "tables", ()) or ())
            if text is None:
                text = "\n\n".join(page_texts)
            if tables is None:
                tables = collected_tables
            return text or "", tables
        if hasattr(document, "full_text"):
            if text is None:
                text = document.full_text()
            return text or "", tables
        if text is None:
            text = str(document)
        return text or "", tables

    def _from_chunks(self, chunks, text):
        parts = []
        for chunk in chunks:
            if isinstance(chunk, Mapping):
                parts.append(str(chunk.get("content", chunk.get("text", ""))))
            elif hasattr(chunk, "content"):
                parts.append(str(getattr(chunk, "content", "")))
            elif hasattr(chunk, "text"):
                parts.append(str(getattr(chunk, "text", "")))
            else:
                parts.append(str(chunk))
        joined = "\n".join(parts)
        if text:
            return text + "\n" + joined
        return joined

    def _coerce_metric(self, value, strategy_name):
        if isinstance(value, Mapping):
            v = _to_decimal(value.get("metric_value", value.get("value")))
            return ExtractedFinancialMetric(
                metric_type=str(value.get("metric_type", value.get("type", "financial_metric"))),
                metric_name=str(value.get("metric_name", value.get("name", "metric"))),
                metric_value=v if v is not None else value.get("metric_value"),
                currency=value.get("currency"),
                unit=value.get("unit"),
                reporting_period=value.get("reporting_period", value.get("period")),
                source_evidence=value.get("source_evidence", value.get("evidence")),
                citation=value.get("citation", {}),
                confidence=float(value.get("confidence", 0.8)),
                strategy=strategy_name,
            )
        return ExtractedFinancialMetric(
            metric_type="financial_metric",
            metric_name=str(value),
            metric_value=value,
            strategy=strategy_name,
        )

    def extract_metrics(self, *args, **kwargs):
        return self.extract(*args, **kwargs)

    def extract_financial_metrics(self, *args, **kwargs):
        return self.extract(*args, **kwargs)

    def extract_from_text(self, text, **kwargs):
        return self.extract(text=text, **kwargs)

    def extract_from_table(self, table, **kwargs):
        return self.extract(tables=[table], **kwargs)

    def extract_from_tables(self, tables, **kwargs):
        return self.extract(tables=tables, **kwargs)

    def extract_from_document(self, document, **kwargs):
        return self.extract(document=document, **kwargs)

    def extract_with_llm(self, text, **kwargs):
        llm_strategies = [s for s in self.strategies if getattr(s, "name", "") == "llm"]
        if not llm_strategies:
            return ExtractionResult(warnings=["no llm strategy configured"])
        original = self.strategies
        self.strategies = llm_strategies
        try:
            return self.extract(text=text, **kwargs)
        finally:
            self.strategies = original

    def run(self, *args, **kwargs):
        return self.extract(*args, **kwargs)

    def process(self, *args, **kwargs):
        return self.extract(*args, **kwargs)

    def identify_reporting_periods(self, text="", **kwargs):
        periods = []
        if text:
            p = _period_from_text(text)
            if p:
                periods.append(p)
        for match in re.finditer(r"\bFY\s*[-/]?\s*(20\d{2})\b", text or "", re.IGNORECASE):
            periods.append(f"FY{match.group(1)}")
        for match in re.finditer(r"\bQ([1-4])\s*(20\d{2})\b", text or "", re.IGNORECASE):
            periods.append(f"Q{match.group(1)} {match.group(2)}")
        seen = set()
        result = []
        for p in periods:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result

    def detect_reporting_periods(self, *args, **kwargs):
        text = args[0] if args else kwargs.get("text", "")
        return self.identify_reporting_periods(text, **kwargs)

    def extract_reporting_periods(self, *args, **kwargs):
        text = args[0] if args else kwargs.get("text", "")
        return self.identify_reporting_periods(text, **kwargs)

    def identify_currencies(self, text="", **kwargs):
        found = []
        if text:
            c = _currency_from_text(text)
            if c:
                found.append(c)
        for symbol, code in _CURRENCY_SYMBOLS.items():
            if symbol in (text or ""):
                found.append(code)
        for code in _KNOWN_CURRENCIES:
            if re.search(rf"\b{code}\b", (text or "").upper()):
                found.append(code)
        seen = set()
        result = []
        for c in found:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def detect_currencies(self, *args, **kwargs):
        text = args[0] if args else kwargs.get("text", "")
        return self.identify_currencies(text, **kwargs)

    def validate(self, metric):
        return self.validator.validate(metric)

    def validate_metric(self, metric):
        return self.validate(metric)

    def validate_metrics(self, metrics):
        return self.validator.validate_many(metrics)

    def validate_extracted_values(self, metrics):
        return self.validate_metrics(metrics)

    def extract_and_store(self, document_id, *, session_factory=None, workspace_id=None,
                         text=None, tables=None, **kwargs):
        sf = session_factory or self.session_factory
        if sf is None:
            raise RuntimeError("session_factory is required for persistence")
        try:
            from app.repositories.chunk_repository import ChunkRepository
            from app.repositories.document_repository import DocumentRepository
        except Exception:
            ChunkRepository = None  # noqa: N806
            DocumentRepository = None  # noqa: N806
        with sf() as session:
            if DocumentRepository is not None:
                document = DocumentRepository(session).get(UUID(str(document_id)))
                if document is not None and workspace_id is None:
                    workspace_id = document.workspace_id
            if text is None and ChunkRepository is not None:
                chunks = ChunkRepository(session).list_by_document(UUID(str(document_id)), limit=100000, offset=0)
                text = "\n".join(getattr(c, "content", str(c)) for c in chunks)
            try:
                from sqlalchemy import delete

                from app.db.models.financial_metric import FinancialMetric
                session.execute(delete(FinancialMetric).where(FinancialMetric.document_id == UUID(str(document_id))))
            except Exception:
                pass
            result = self.extract(text=text or "", tables=tables, document_id=document_id,
                                  workspace_id=workspace_id, **kwargs)
            try:
                from app.db.models.financial_metric import FinancialMetric
                for metric in result.metrics:
                    session.add(FinancialMetric(
                        workspace_id=UUID(str(workspace_id)),
                        document_id=UUID(str(document_id)),
                        metric_type=metric.metric_type,
                        metric_name=metric.metric_name,
                        metric_value=_to_decimal(metric.metric_value) or Decimal("0"),
                        currency=metric.currency,
                        unit=metric.unit,
                        context={"reporting_period": metric.reporting_period},
                        source_document_chunk=metric.source_document_chunk,
                        is_estimated=metric.is_estimated,
                        is_projected=metric.is_projected,
                        notes=metric.notes,
                    ))
                session.commit()
            except Exception:
                with contextlib.suppress(Exception):
                    session.rollback()
            return result

    def extract_and_persist(self, *args, **kwargs):
        return self.extract_and_store(*args, **kwargs)


FinancialExtraction = FinancialExtractionAgent
FinancialMetricExtractor = FinancialExtractionAgent
ExtractionAgent = FinancialExtractionAgent


def extract_financial_metrics(*args, **kwargs):
    agent = FinancialExtractionAgent()
    return agent.extract(*args, **kwargs)


def extract_metrics(*args, **kwargs):
    return extract_financial_metrics(*args, **kwargs)
