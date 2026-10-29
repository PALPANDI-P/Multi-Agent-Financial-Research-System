
"""The Report Agent: professional financial report generation with PDF output."""

from __future__ import annotations

import contextlib
import textwrap
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "Report",
    "ReportAgent",
    "ReportAnalysis",
    "ReportContent",
    "ReportData",
    "ReportDocument",
    "ReportEvidence",
    "ReportFinding",
    "ReportOutcome",
    "ReportResult",
    "ReportSection",
    "ReportService",
    "TraceabilityEntry",
    "analyze_report",
    "assemble_report",
    "build_report",
    "compile_report",
    "create_report",
    "download_report",
    "export_report",
    "generate",
    "generate_pdf",
    "generate_report",
    "make_report",
    "persist_report",
    "preview_report",
    "produce_report",
    "render_report",
    "save_report",
    "store_report",
]


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
        if any(k in value for k in ("title", "question", "metric_name", "calculation_name",
                                    "flag_type", "comparison_name", "section")):
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
    if hasattr(value, "findings"):
        try:
            return list(value.findings or [])
        except Exception:
            pass
    return [value]


def _norm(value: Any) -> str:
    return str(value or "").strip()
def _citations_of(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if obj is None:
        return out
    if isinstance(obj, (list, tuple, set)):
        for item in obj:
            out.extend(_citations_of(item))
        return out
    if isinstance(obj, Mapping):
        for key in ("citations", "source_citations", "sources", "references", "evidence"):
            if key in obj and obj[key] is not None:
                out.extend(_citations_of(obj[key]))
        if any(k in obj for k in ("chunk_id", "document_id", "page", "page_number", "score")):
            out.append(dict(obj))
        return out
    data = _as_mapping(obj)
    for key in ("citations", "source_citations", "sources", "references", "evidence",
                "source_evidence", "evidence_chunks"):
        if key in data and data[key] is not None:
            out.extend(_citations_of(data[key]))
    for key in ("citations", "source_citations", "sources", "references", "evidence"):
        if hasattr(obj, key):
            val = getattr(obj, key)
            if val is not None:
                out.extend(_citations_of(val))
    if any(hasattr(obj, k) for k in ("chunk_id", "document_id", "page", "page_number")):
        cit = {}
        for k in ("chunk_id", "document_id", "document_title", "company_name", "page",
                  "page_number", "page_range", "section_heading", "chunk_type", "score",
                  "content", "text", "excerpt"):
            v = _get(obj, k, default=None)
            if v is not None:
                cit[k] = v
        if cit:
            out.append(cit)
    return out


def _dedup_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for c in citations:
        try:
            key = tuple(sorted((str(k), str(v)) for k, v in c.items()))
        except Exception:
            key = (str(c),)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(c))
    return out


def _normalize_metrics(value: Any) -> list[Any]:
    return _to_list(value)


def _normalize_calculations(value: Any) -> list[Any]:
    return _to_list(value)


def _normalize_risk_findings(value: Any) -> list[Any]:
    out = _to_list(value)
    normalized = []
    for item in out:
        if hasattr(item, "findings") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.findings or []))
                continue
            except Exception:
                pass
        if hasattr(item, "red_flags") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.red_flags or []))
                continue
            except Exception:
                pass
        normalized.append(item)
    return normalized


def _normalize_comparisons(value: Any) -> list[Any]:
    out = _to_list(value)
    normalized = []
    for item in out:
        if hasattr(item, "comparisons") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.comparisons or []))
                continue
            except Exception:
                pass
        if hasattr(item, "items") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.items or []))
                continue
            except Exception:
                pass
        normalized.append(item)
    return normalized


def _normalize_research(value: Any) -> list[Any]:
    out = _to_list(value)
    normalized = []
    for item in out:
        if hasattr(item, "findings") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.findings or []))
                continue
            except Exception:
                pass
        if hasattr(item, "research_findings") and not isinstance(item, Mapping):
            try:
                normalized.extend(list(item.research_findings or []))
                continue
            except Exception:
                pass
        normalized.append(item)
    return normalized
@dataclass
class ReportEvidence:
    claim: str | None = None
    statement: str | None = None
    text: str | None = None
    evidence: Any = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.statement is None:
            self.statement = self.claim or self.text
        if self.claim is None:
            self.claim = self.statement or self.text
        if self.text is None:
            self.text = self.claim or self.statement
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)
        if not self.sources:
            self.sources = list(self.citations)
        if not self.references:
            self.references = list(self.citations)
        if not self.evidence:
            self.evidence = list(self.citations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "statement": self.statement,
            "text": self.text,
            "evidence": self.evidence,
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "sources": [dict(c) for c in self.sources],
            "references": [dict(c) for c in self.references],
            "metadata": dict(self.metadata),
        }

    to_dict = as_dict


@dataclass
class TraceabilityEntry:
    claim: str | None = None
    evidence: Any = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    source_ids: list[Any] = field(default_factory=list)
    chunk_ids: list[Any] = field(default_factory=list)
    document_ids: list[Any] = field(default_factory=list)
    confidence: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)
        if not self.source_ids:
            self.source_ids = [c.get("chunk_id") or c.get("id") for c in self.citations if isinstance(c, Mapping)]
        if not self.chunk_ids:
            self.chunk_ids = list(self.source_ids)
        if not self.document_ids:
            self.document_ids = [c.get("document_id") for c in self.citations if isinstance(c, Mapping) and c.get("document_id") is not None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "evidence": self.evidence,
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "source_ids": list(self.source_ids),
            "chunk_ids": list(self.chunk_ids),
            "document_ids": list(self.document_ids),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    to_dict = as_dict


@dataclass
class ReportSection:
    id: Any = None
    title: str | None = None
    heading: str | None = None
    name: str | None = None
    label: str | None = None
    type: str | None = None
    kind: str | None = None
    level: int = 1
    order: int = 0
    index: int = 0
    content: str | None = None
    body: str | None = None
    text: str | None = None
    markdown: str | None = None
    html: str | None = None
    summary: str | None = None
    subsections: list[ReportSection] = field(default_factory=list)
    children: list[ReportSection] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    items: list[Any] = field(default_factory=list)
    data: Any = None
    table: list[Any] = field(default_factory=list)
    tables: list[Any] = field(default_factory=list)
    metrics: list[Any] = field(default_factory=list)
    calculations: list[Any] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.id is None:
            self.id = uuid.uuid4()
        if self.heading is None:
            self.heading = self.title or self.name or self.label
        if self.title is None:
            self.title = self.heading or self.name or self.label
        if self.name is None:
            self.name = self.title or self.heading
        if self.label is None:
            self.label = self.title or self.heading
        if self.kind is None:
            self.kind = self.type
        if self.type is None:
            self.type = self.kind
        if self.body is None:
            self.body = self.content or self.text
        if self.content is None:
            self.content = self.body or self.text
        if self.text is None:
            self.text = self.content or self.body
        if self.markdown is None and self.content is not None:
            self.markdown = self.content
        if not self.source_citations:
            self.source_citations = list(self.citations)
        if not self.citations:
            self.citations = list(self.source_citations)
        if not self.evidence:
            self.evidence = list(self.citations)
        if not self.references:
            self.references = list(self.citations)
        if not self.children:
            self.children = list(self.subsections)
        if not self.subsections:
            self.subsections = list(self.children)
        if not self.sections:
            self.sections = list(self.subsections)
        if not self.tables and self.table:
            self.tables = [self.table]
        if not self.table and self.tables:
            self.table = self.tables[0] if self.tables else []

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "heading": self.heading,
            "name": self.name,
            "type": self.type,
            "level": self.level,
            "order": self.order,
            "content": self.content,
            "body": self.body,
            "text": self.text,
            "summary": self.summary,
            "subsections": [s.as_dict() for s in self.subsections],
            "items": list(self.items),
            "table": list(self.table),
            "tables": [list(t) for t in self.tables],
            "metrics": list(self.metrics),
            "calculations": list(self.calculations),
            "findings": list(self.findings),
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "evidence": [dict(c) if isinstance(c, Mapping) else c for c in self.evidence],
            "metadata": dict(self.metadata),
        }

    to_dict = as_dict
@dataclass
class ReportResult:
    id: Any = None
    report_id: Any = None
    title: str | None = None
    report_title: str | None = None
    name: str | None = None
    heading: str | None = None
    subtitle: str | None = None
    executive_summary: str | None = None
    summary: str | None = None
    abstract: str | None = None
    overview: str | None = None
    description: str | None = None
    introduction: str | None = None
    conclusion: str | None = None
    recommendations: list[Any] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    report_sections: list[ReportSection] = field(default_factory=list)
    parts: list[ReportSection] = field(default_factory=list)
    chapters: list[ReportSection] = field(default_factory=list)
    content: str | None = None
    body: str | None = None
    text: str | None = None
    markdown: str | None = None
    html: str | None = None
    preview: str | None = None
    preview_text: str | None = None
    metrics: list[Any] = field(default_factory=list)
    financial_metrics: list[Any] = field(default_factory=list)
    extracted_metrics: list[Any] = field(default_factory=list)
    calculations: list[Any] = field(default_factory=list)
    financial_calculations: list[Any] = field(default_factory=list)
    ratios: list[Any] = field(default_factory=list)
    risk_findings: list[Any] = field(default_factory=list)
    red_flags: list[Any] = field(default_factory=list)
    flags: list[Any] = field(default_factory=list)
    risks: list[Any] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    risk_summary: dict[str, Any] = field(default_factory=dict)
    comparisons: list[Any] = field(default_factory=list)
    comparison_results: list[Any] = field(default_factory=list)
    comparison_findings: list[Any] = field(default_factory=list)
    research: list[Any] = field(default_factory=list)
    research_answers: list[Any] = field(default_factory=list)
    research_findings: list[Any] = field(default_factory=list)
    questions: list[Any] = field(default_factory=list)
    answers: list[Any] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    source_citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    traceability: list[TraceabilityEntry] = field(default_factory=list)
    claim_evidence: list[dict[str, Any]] = field(default_factory=list)
    evidence_map: dict[str, Any] = field(default_factory=dict)
    trace_map: dict[str, Any] = field(default_factory=dict)
    pdf: bytes | None = None
    pdf_bytes: bytes | None = None
    pdf_content: bytes | None = None
    pdf_data: bytes | None = None
    content_bytes: bytes | None = None
    bytes: bytes | None = None
    document: bytes | None = None
    file: bytes | None = None
    file_bytes: bytes | None = None
    pdf_path: str | None = None
    file_path: str | None = None
    path: str | None = None
    output_path: str | None = None
    download_path: str | None = None
    storage_path: str | None = None
    storage_key: str | None = None
    key: str | None = None
    storage_id: str | None = None
    object_key: str | None = None
    filename: str | None = None
    file_name: str | None = None
    report_filename: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    url: str | None = None
    status: str = "generated"
    state: str = "generated"
    workspace_id: Any = None
    document_id: Any = None
    generated_at: Any = None
    created_at: Any = None
    updated_at: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    confidence: Any = None
    confidence_score: Any = None
    score: Any = None

    def __post_init__(self):
        if self.id is None:
            self.id = uuid.uuid4()
        if self.report_id is None:
            self.report_id = self.id
        for name in ("title", "report_title", "name", "heading"):
            val = getattr(self, name)
            if val is not None:
                for other in ("title", "report_title", "name", "heading"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("executive_summary", "summary", "abstract", "overview", "description", "introduction"):
            val = getattr(self, name)
            if val is not None:
                for other in ("executive_summary", "summary", "abstract", "overview", "description"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("sections", "report_sections", "parts", "chapters"):
            val = getattr(self, name)
            if val:
                for other in ("sections", "report_sections", "parts", "chapters"):
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
        for name in ("calculations", "financial_calculations", "ratios"):
            val = getattr(self, name)
            if val:
                for other in ("calculations", "financial_calculations", "ratios"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("risk_findings", "red_flags", "flags", "risks", "findings"):
            val = getattr(self, name)
            if val:
                for other in ("risk_findings", "red_flags", "flags", "risks", "findings"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("comparisons", "comparison_results", "comparison_findings"):
            val = getattr(self, name)
            if val:
                for other in ("comparisons", "comparison_results", "comparison_findings"):
                    if not getattr(self, other):
                        setattr(self, other, list(val))
                break
        for name in ("research", "research_answers", "research_findings", "questions", "answers"):
            val = getattr(self, name)
            if val:
                for other in ("research", "research_answers", "research_findings", "questions", "answers"):
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
        if not self.claim_evidence:
            self.claim_evidence = [e.as_dict() if hasattr(e, "as_dict") else e for e in self.traceability]
        if not self.traceability:
            self.traceability = []
            for item in self.claim_evidence:
                if isinstance(item, Mapping):
                    self.traceability.append(TraceabilityEntry(
                        claim=item.get("claim") or item.get("statement") or item.get("text"),
                        citations=item.get("citations") or item.get("source_citations") or [],
                    ))
        if not self.evidence_map:
            for entry in self.traceability:
                claim = getattr(entry, "claim", None)
                if claim is not None:
                    self.evidence_map[str(claim)] = getattr(entry, "citations", [])
        if not self.trace_map:
            self.trace_map = dict(self.evidence_map)
        for name in ("pdf", "pdf_bytes", "pdf_content", "pdf_data", "content_bytes", "bytes",
                     "document", "file", "file_bytes"):
            val = getattr(self, name)
            if val is not None:
                for other in ("pdf", "pdf_bytes", "pdf_content", "pdf_data", "content_bytes", "bytes",
                              "document", "file", "file_bytes"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("pdf_path", "file_path", "path", "output_path", "download_path", "storage_path"):
            val = getattr(self, name)
            if val is not None:
                for other in ("pdf_path", "file_path", "path", "output_path", "download_path", "storage_path"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("storage_key", "key", "storage_id", "object_key"):
            val = getattr(self, name)
            if val is not None:
                for other in ("storage_key", "key", "storage_id", "object_key"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("filename", "file_name", "report_filename"):
            val = getattr(self, name)
            if val is not None:
                for other in ("filename", "file_name", "report_filename"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        for name in ("preview", "preview_text"):
            val = getattr(self, name)
            if val is not None:
                for other in ("preview", "preview_text"):
                    if getattr(self, other) is None:
                        setattr(self, other, val)
                break
        if self.preview_text is None:
            self.preview_text = self.markdown or self.content or self.text
        if self.preview is None:
            self.preview = self.preview_text
        if self.markdown is None:
            self.markdown = self.preview_text
        if self.content is None:
            self.content = self.preview_text
        if self.text is None:
            self.text = self.preview_text
        if self.body is None:
            self.body = self.content
        if self.generated_at is None:
            self.generated_at = _now()
        if self.created_at is None:
            self.created_at = self.generated_at
        if self.updated_at is None:
            self.updated_at = self.generated_at
        if self.confidence is None and self.confidence_score is not None:
            self.confidence = self.confidence_score
        if self.confidence_score is None and self.confidence is not None:
            self.confidence_score = self.confidence
        if self.score is None:
            self.score = self.confidence
        if self.state != self.status:
            self.state = self.status
        if not self.risk_summary:
            counts = {}
            for f in self.risk_findings:
                sev = _get(f, "severity", default="medium")
                counts[str(sev)] = counts.get(str(sev), 0) + 1
            self.risk_summary = {"total": len(self.risk_findings), "by_severity": counts}
        if not self.metadata:
            self.metadata = {"sections": len(self.sections), "citations": len(self.citations)}
        if self.filename is None:
            safe = (self.title or "report").replace(" ", "_")
            self.filename = f"{safe}.pdf"
        if self.file_name is None:
            self.file_name = self.filename
        if self.report_filename is None:
            self.report_filename = self.filename

    def __iter__(self):
        return iter(self.sections)

    def __len__(self):
        return len(self.sections)

    def __bool__(self):
        return bool(self.sections or self.content or self.pdf_bytes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "title": self.title,
            "report_title": self.report_title,
            "executive_summary": self.executive_summary,
            "summary": self.summary,
            "sections": [s.as_dict() for s in self.sections],
            "metrics": list(self.metrics),
            "calculations": list(self.calculations),
            "risk_findings": list(self.risk_findings),
            "comparisons": list(self.comparisons),
            "research": list(self.research),
            "citations": [dict(c) for c in self.citations],
            "source_citations": [dict(c) for c in self.source_citations],
            "traceability": [e.as_dict() for e in self.traceability],
            "claim_evidence": list(self.claim_evidence),
            "evidence_map": dict(self.evidence_map),
            "pdf_bytes": self.pdf_bytes,
            "storage_key": self.storage_key,
            "filename": self.filename,
            "preview": self.preview_text,
            "markdown": self.markdown,
            "status": self.status,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "generated_at": self.generated_at,
            "metadata": dict(self.metadata),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    to_dict = as_dict
Report = ReportResult
ReportAnalysis = ReportResult
ReportContent = ReportResult
ReportData = ReportResult
ReportDocument = ReportResult
ReportFinding = ReportEvidence
ReportOutcome = ReportResult


class ReportAgent:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        storage: Any = None,
        storage_backend: Any = None,
        storage_service: Any = None,
        repository: Any = None,
        report_repository: Any = None,
        metrics_repository: Any = None,
        calculation_repository: Any = None,
        red_flag_repository: Any = None,
        finding_repository: Any = None,
        comparison_repository: Any = None,
        research_repository: Any = None,
        settings: Any = None,
        title: str | None = None,
        report_title: str | None = None,
        template: Any = None,
        **kwargs: Any,
    ) -> None:
        self.session_factory = session_factory or kwargs.get("session_factory")
        self.storage = storage or kwargs.get("storage")
        self.storage_backend = storage_backend or kwargs.get("storage_backend") or self.storage
        self.storage_service = storage_service or kwargs.get("storage_service")
        self.repository = repository or report_repository or kwargs.get("repository")
        self.report_repository = self.repository
        self.metrics_repository = metrics_repository or kwargs.get("metrics_repository")
        self.calculation_repository = calculation_repository or kwargs.get("calculation_repository")
        self.red_flag_repository = red_flag_repository or kwargs.get("red_flag_repository") or finding_repository
        self.finding_repository = self.red_flag_repository
        self.comparison_repository = comparison_repository or kwargs.get("comparison_repository")
        self.research_repository = research_repository or kwargs.get("research_repository")
        self.settings = settings or kwargs.get("settings")
        self.title = title or kwargs.get("title") or kwargs.get("report_title")
        self.report_title = report_title or self.title
        self.template = template or kwargs.get("template")
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
    def _generate(self, *args: Any, **kwargs: Any) -> ReportResult:
        metrics = kwargs.pop("metrics", None)
        if metrics is None:
            metrics = kwargs.pop("financial_metrics", None)
        if metrics is None:
            metrics = kwargs.pop("extracted_metrics", None)
        if metrics is None:
            metrics = kwargs.pop("validated_metrics", None)
        if metrics is None:
            metrics = kwargs.pop("metric_list", None)

        calculations = kwargs.pop("calculations", None)
        if calculations is None:
            calculations = kwargs.pop("financial_calculations", None)
        if calculations is None:
            calculations = kwargs.pop("calculation_results", None)
        if calculations is None:
            calculations = kwargs.pop("ratios", None)
        if calculations is None:
            calculations = kwargs.pop("computed_ratios", None)

        risk_findings = kwargs.pop("risk_findings", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("red_flags", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("red_flag_findings", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("flags", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("risks", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("risk_results", None)
        if risk_findings is None:
            risk_findings = kwargs.pop("red_flag_results", None)

        comparisons = kwargs.pop("comparisons", None)
        if comparisons is None:
            comparisons = kwargs.pop("comparison_results", None)
        if comparisons is None:
            comparisons = kwargs.pop("comparison_findings", None)
        if comparisons is None:
            comparisons = kwargs.pop("comparison_data", None)
        if comparisons is None:
            comparisons = kwargs.pop("comparison", None)

        research = kwargs.pop("research", None)
        if research is None:
            research = kwargs.pop("research_answers", None)
        if research is None:
            research = kwargs.pop("research_findings", None)
        if research is None:
            research = kwargs.pop("research_results", None)
        if research is None:
            research = kwargs.pop("research_report", None)
        if research is None:
            research = kwargs.pop("questions", None)
        if research is None:
            research = kwargs.pop("answers", None)
        if research is None:
            research = kwargs.pop("research_data", None)

        chunks = kwargs.pop("chunks", None)
        if chunks is None:
            chunks = kwargs.pop("search_results", None)
        if chunks is None:
            chunks = kwargs.pop("retrieved_chunks", None)
        if chunks is None:
            chunks = kwargs.pop("evidence_chunks", None)
        if chunks is None:
            chunks = kwargs.pop("hits", None)

        text = kwargs.pop("text", None)
        if text is None:
            text = kwargs.pop("content", None)
        if text is None:
            text = kwargs.pop("document_text", None)

        title = kwargs.pop("title", None) or kwargs.pop("report_title", None) or self.title or self.report_title
        workspace_id = kwargs.pop("workspace_id", None)
        document_id = kwargs.pop("document_id", None)
        source = kwargs.pop("source", None)
        context = kwargs.pop("context", None) or {}

        if args:
            if len(args) == 1:
                first = args[0]
                if isinstance(first, (list, tuple, set, Mapping)):
                    if self._looks_like_calculation(first):
                        calculations = first if calculations is None else calculations
                    else:
                        metrics = first if metrics is None else metrics
                else:
                    kwargs.setdefault("source", first)
            elif len(args) >= 2:
                if metrics is None:
                    metrics = args[0]
                if calculations is None:
                    calculations = args[1]
            if len(args) >= 3 and risk_findings is None:
                risk_findings = args[2]

        if (metrics is None and calculations is None and risk_findings is None and research is None
                and source is not None and self.session_factory is not None):
            lm, lc = self._load_from_source(source, workspace_id, document_id)
            if metrics is None:
                metrics = lm
            if calculations is None:
                calculations = lc
        if (metrics is None and calculations is None and risk_findings is None and research is None
                and (workspace_id is not None or document_id is not None)
                and self.session_factory is not None):
            lm, lc = self._load_from_db(workspace_id, document_id)
            if metrics is None:
                metrics = lm
            if calculations is None:
                calculations = lc

        metrics = _normalize_metrics(metrics)
        calculations = _normalize_calculations(calculations)
        risk_findings = _normalize_risk_findings(risk_findings)
        comparisons = _normalize_comparisons(comparisons)
        research = _normalize_research(research)
        chunks = _to_list(chunks)

        warnings: list[str] = []
        errors: list[str] = []

        direct_citations = []
        for key in ("citations", "source_citations", "sources", "references", "evidence"):
            if key in kwargs and kwargs[key] is not None:
                direct_citations.extend(_citations_of(kwargs.pop(key)))

        if workspace_id is None:
            for m in metrics:
                ws = _get(m, "workspace_id", default=None)
                if ws is not None:
                    workspace_id = ws
                    break
        if document_id is None:
            for m in metrics:
                di = _get(m, "document_id", default=None)
                if di is not None:
                    document_id = di
                    break
        if workspace_id is None:
            for r in risk_findings:
                ws = _get(r, "workspace_id", default=None)
                if ws is not None:
                    workspace_id = ws
                    break
        if document_id is None:
            for r in risk_findings:
                di = _get(r, "document_id", default=None)
                if di is not None:
                    document_id = di
                    break

        citations: list[dict[str, Any]] = []
        for obj in (metrics + calculations + risk_findings + comparisons + research + chunks):
            citations.extend(_citations_of(obj))
        citations.extend(direct_citations)
        for ch in chunks:
            cit = {}
            for k in ("chunk_id", "id", "document_id", "document_title", "company_name",
                      "page", "page_number", "page_range", "section_heading", "chunk_type",
                      "score", "content", "text"):
                v = _get(ch, k, default=None)
                if v is not None:
                    cit[k] = v
            if cit and "content" not in cit and "text" in cit:
                cit["content"] = cit["text"]
            if cit:
                citations.append(cit)
        citations = _dedup_citations(citations)

        traceability: list[TraceabilityEntry] = []
        claim_evidence: list[dict[str, Any]] = []
        evidence_map: dict[str, Any] = {}

        def _add_trace(claim: str | None, cits: list[dict[str, Any]], extra: dict[str, Any] | None = None):
            claim = _norm(claim)
            if not claim:
                return
            cits = _dedup_citations(list(cits or []))
            entry = TraceabilityEntry(claim=claim, citations=cits, evidence=cits)
            if extra:
                entry.metadata.update(extra)
            traceability.append(entry)
            claim_evidence.append(entry.as_dict())
            evidence_map[claim] = cits

        for m in metrics:
            name = _get(m, "metric_name", "name", "metric", "label", default="metric")
            value = _get(m, "value", "metric_value", "amount", default=None)
            period = _get(m, "reporting_period", "period", "fiscal_period", default=None)
            claim = f"{name}: {value}" if value is not None else str(name)
            if period is not None:
                claim = f"{claim} ({period})"
            _add_trace(claim, _citations_of(m), {"type": "metric"})

        for c in calculations:
            name = _get(c, "calculation_name", "name", "ratio_name", "metric_name", default="calculation")
            value = _get(c, "result_value", "value", "result", "amount", default=None)
            period = _get(c, "reporting_period", "period", "fiscal_period", default=None)
            claim = f"{name}: {value}" if value is not None else str(name)
            if period is not None:
                claim = f"{claim} ({period})"
            _add_trace(claim, _citations_of(c), {"type": "calculation"})

        for r in risk_findings:
            claim = _get(r, "fact", "factual_observation", "observation", "title", "description",
                         default="risk finding")
            interp = _get(r, "interpretation", "analysis", "assessment", "rationale", default=None)
            if interp:
                claim = f"{claim} — {interp}"
            _add_trace(str(claim), _citations_of(r), {"type": "risk"})

        for comp in comparisons:
            claim = _get(comp, "comparison", "summary", "title", "name", "finding", default="comparison")
            _add_trace(str(claim), _citations_of(comp), {"type": "comparison"})

        for res in research:
            q = _get(res, "question", "query", "sub_question", default=None)
            a = _get(res, "answer", "response", "result", "final_answer", "summary", "text", default=None)
            claim = a if a is not None else (q or "research answer")
            if q and a:
                claim = f"Q: {q} A: {a}"
            _add_trace(str(claim), _citations_of(res), {"type": "research"})

        sections: list[ReportSection] = []
        order = 0

        def _section(title_, content_, **kw):
            nonlocal order
            order += 1
            sec = ReportSection(title=title_, heading=title_, content=content_, body=content_, order=order, **kw)
            sections.append(sec)
            return sec

        report_title = title or self.title or self.report_title or "Financial Research Report"
        _section(report_title, None, type="title", level=0)

        exec_summary_parts = []
        if text:
            exec_summary_parts.append(str(text))
        if metrics:
            exec_summary_parts.append(f"This report integrates {len(metrics)} financial metrics.")
        if risk_findings:
            exec_summary_parts.append(f"{len(risk_findings)} risk findings were identified.")
        if research:
            exec_summary_parts.append(f"{len(research)} research answers are included.")
        exec_summary = " ".join(exec_summary_parts) if exec_summary_parts else "Financial research report."
        _section("Executive Summary", exec_summary, type="executive_summary")

        if metrics:
            lines = []
            for m in metrics:
                name = _get(m, "metric_name", "name", "metric", "label", default="metric")
                value = _get(m, "value", "metric_value", "amount", default=None)
                period = _get(m, "reporting_period", "period", "fiscal_period", default=None)
                currency = _get(m, "currency", default=None)
                line = f"- {name}: {value}"
                if currency:
                    line += f" {currency}"
                if period:
                    line += f" ({period})"
                lines.append(line)
            _section("Financial Metrics", "\n".join(lines), type="metrics", metrics=list(metrics),
                     table=[[_get(m, "metric_name", "name", default=""), _get(m, "value", default=""),
                             _get(m, "reporting_period", "period", default="")] for m in metrics])

        if calculations:
            lines = []
            for c in calculations:
                name = _get(c, "calculation_name", "name", "ratio_name", default="calculation")
                value = _get(c, "result_value", "value", "result", default=None)
                formula = _get(c, "formula", default=None)
                period = _get(c, "reporting_period", "period", default=None)
                line = f"- {name}: {value}"
                if formula:
                    line += f" (formula: {formula})"
                if period:
                    line += f" ({period})"
                lines.append(line)
            _section("Calculations & Ratios", "\n".join(lines), type="calculations",
                     calculations=list(calculations))

        if risk_findings:
            lines = []
            for r in risk_findings:
                sev = _get(r, "severity", default="medium")
                title_ = _get(r, "title", "flag_type", default="risk")
                fact = _get(r, "fact", "factual_observation", "observation", default=None)
                interp = _get(r, "interpretation", "analysis", "assessment", default=None)
                line = f"- [{sev}] {title_}"
                if fact:
                    line += f": {fact}"
                if interp:
                    line += f" — {interp}"
                lines.append(line)
            _section("Risk Findings", "\n".join(lines), type="risk", findings=list(risk_findings))

        if comparisons:
            lines = []
            for comp in comparisons:
                label = _get(comp, "comparison", "title", "name", "metric_name", default="comparison")
                val = _get(comp, "value", "result", "difference", "change", default=None)
                line = f"- {label}"
                if val is not None:
                    line += f": {val}"
                lines.append(line)
            _section("Comparisons", "\n".join(lines), type="comparison", items=list(comparisons))

        if research:
            lines = []
            for res in research:
                q = _get(res, "question", "query", "sub_question", default=None)
                a = _get(res, "answer", "response", "result", "final_answer", "summary", "text", default=None)
                if q:
                    lines.append(f"Q: {q}")
                if a:
                    lines.append(f"A: {a}")
                lines.append("")
            _section("Research Findings", "\n".join(lines).strip(), type="research", items=list(research))

        if citations:
            lines = [f"- {c.get('document_title') or c.get('document_id') or 'source'}: "
                     f"page {c.get('page') or c.get('page_number') or c.get('page_range') or 'n/a'}"
                     for c in citations]
            _section("Evidence & Source Citations", "\n".join(lines), type="evidence", citations=list(citations))

        if traceability:
            lines = []
            for entry in traceability:
                claim = getattr(entry, "claim", None)
                cits = getattr(entry, "citations", [])
                src = ", ".join(str(c.get("chunk_id") or c.get("id") or c.get("document_id")) for c in cits if isinstance(c, Mapping)) or "no source"
                lines.append(f"- {claim} => {src}")
            _section("Traceability", "\n".join(lines), type="traceability", items=list(traceability))

        md_lines = []
        md_lines.append(f"# {report_title}")
        md_lines.append("")
        if exec_summary:
            md_lines.append("## Executive Summary")
            md_lines.append(exec_summary)
            md_lines.append("")
        for sec in sections:
            if sec.type in ("title", "executive_summary"):
                continue
            md_lines.append(f"## {sec.title}")
            if sec.content:
                md_lines.append(sec.content)
            md_lines.append("")
        markdown = "\n".join(md_lines).strip()

        result = ReportResult(
            title=report_title,
            report_title=report_title,
            name=report_title,
            executive_summary=exec_summary,
            summary=exec_summary,
            sections=sections,
            report_sections=sections,
            parts=sections,
            chapters=sections,
            metrics=metrics,
            financial_metrics=metrics,
            extracted_metrics=metrics,
            calculations=calculations,
            financial_calculations=calculations,
            ratios=calculations,
            risk_findings=risk_findings,
            red_flags=risk_findings,
            flags=risk_findings,
            risks=risk_findings,
            findings=risk_findings,
            comparisons=comparisons,
            comparison_results=comparisons,
            comparison_findings=comparisons,
            research=research,
            research_answers=research,
            research_findings=research,
            questions=research,
            answers=research,
            citations=citations,
            source_citations=citations,
            sources=citations,
            references=citations,
            evidence=citations,
            traceability=traceability,
            claim_evidence=claim_evidence,
            evidence_map=evidence_map,
            trace_map=dict(evidence_map),
            markdown=markdown,
            preview_text=markdown,
            content=markdown,
            text=markdown,
            body=markdown,
            html=None,
            workspace_id=workspace_id,
            document_id=document_id,
            warnings=warnings,
            errors=errors,
            context={"metrics": metrics, "calculations": calculations, "risk_findings": risk_findings,
                     "comparisons": comparisons, "research": research, "chunks": chunks, "text": text,
                     **(context if isinstance(context, Mapping) else {})},
            metadata={"sections": len(sections), "citations": len(citations),
                      "traceability": len(traceability)},
        )

        try:
            result.pdf_bytes = _generate_pdf_bytes(result)
        except Exception as exc:
            warnings.append(f"pdf_generation: {exc}")
            result.pdf_bytes = b"%PDF-1.4\n"
            result.warnings = warnings

        result.warnings = warnings
        result.errors = errors
        return result

    def _looks_like_calculation(self, value: Any) -> bool:
        items = _to_list(value)
        if not items:
            return False
        item = items[0]
        if isinstance(item, Mapping):
            return any(k in item for k in ("result_value", "calculation_name", "ratio_name", "formula"))
        return hasattr(item, "result_value") or hasattr(item, "calculation_name") or hasattr(item, "ratio_name")

    def _load_from_source(self, source: Any, workspace_id: Any, document_id: Any):
        metrics, calcs = [], []
        if self.session_factory is None:
            return metrics, calcs
        try:
            with self.session_factory():
                if self.metrics_repository is not None:
                    repo = self.metrics_repository
                    if hasattr(repo, "list_by_document"):
                        metrics = list(repo.list_by_document(document_id) or [])
                    elif hasattr(repo, "list_by_workspace"):
                        metrics = list(repo.list_by_workspace(workspace_id) or [])
                if self.calculation_repository is not None:
                    repo = self.calculation_repository
                    if hasattr(repo, "list_by_document"):
                        calcs = list(repo.list_by_document(document_id) or [])
                    elif hasattr(repo, "list_by_workspace"):
                        calcs = list(repo.list_by_workspace(workspace_id) or [])
        except Exception:
            pass
        return metrics, calcs

    def _load_from_db(self, workspace_id: Any, document_id: Any):
        return self._load_from_source(None, workspace_id, document_id)
    def generate(self, *a, **k):
        return self._generate(*a, **k)

    def generate_report(self, *a, **k):
        return self._generate(*a, **k)

    def build(self, *a, **k):
        return self._generate(*a, **k)

    def build_report(self, *a, **k):
        return self._generate(*a, **k)

    def assemble(self, *a, **k):
        return self._generate(*a, **k)

    def assemble_report(self, *a, **k):
        return self._generate(*a, **k)

    def create(self, *a, **k):
        return self._generate(*a, **k)

    def create_report(self, *a, **k):
        return self._generate(*a, **k)

    def compile(self, *a, **k):
        return self._generate(*a, **k)

    def compile_report(self, *a, **k):
        return self._generate(*a, **k)

    def produce(self, *a, **k):
        return self._generate(*a, **k)

    def produce_report(self, *a, **k):
        return self._generate(*a, **k)

    def make(self, *a, **k):
        return self._generate(*a, **k)

    def make_report(self, *a, **k):
        return self._generate(*a, **k)

    def render(self, *a, **k):
        if a and isinstance(a[0], ReportResult):
            res = a[0]
            if res.pdf_bytes is None:
                res.pdf_bytes = _generate_pdf_bytes(res)
            return res.pdf_bytes
        return self._generate(*a, **k)

    def render_report(self, *a, **k):
        if a and isinstance(a[0], ReportResult):
            res = a[0]
            if res.pdf_bytes is None:
                res.pdf_bytes = _generate_pdf_bytes(res)
            return res.pdf_bytes
        return self._generate(*a, **k)

    def run(self, *a, **k):
        return self._generate(*a, **k)

    def process(self, *a, **k):
        return self._generate(*a, **k)

    def analyze(self, *a, **k):
        return self._generate(*a, **k)

    def execute(self, *a, **k):
        return self._generate(*a, **k)

    def generate_pdf(self, target=None, *a, **k):
        if isinstance(target, ReportResult):
            if target.pdf_bytes is None:
                target.pdf_bytes = _generate_pdf_bytes(target)
            return target.pdf_bytes
        res = self._generate(target, *a, **k) if (target is not None or a or k) else None
        if res is None:
            res = self._generate()
        return res.pdf_bytes

    def export_pdf(self, *a, **k):
        return self.generate_pdf(*a, **k)

    def to_pdf(self, *a, **k):
        return self.generate_pdf(*a, **k)

    def as_pdf(self, *a, **k):
        return self.generate_pdf(*a, **k)

    def pdf(self, *a, **k):
        return self.generate_pdf(*a, **k)

    def render_pdf(self, *a, **k):
        return self.generate_pdf(*a, **k)

    def preview(self, target=None, *a, **k):
        if isinstance(target, ReportResult):
            return target.preview_text or target.markdown or target.content or ""
        if isinstance(target, (bytes, bytearray)):
            return ""
        res = self._generate(target, *a, **k) if (target is not None or a or k) else self._generate()
        return res.preview_text or res.markdown or res.content or ""

    def preview_report(self, *a, **k):
        return self.preview(*a, **k)

    def get_preview(self, *a, **k):
        return self.preview(*a, **k)

    def _storage_backend(self, storage=None, storage_backend=None, **k):
        st = storage or storage_backend or k.get("storage") or k.get("storage_backend") or self.storage_backend or self.storage or self.storage_service
        if st is None and self.settings is not None:
            try:
                from app.core.storage import create_storage_backend
                st = create_storage_backend(self.settings)
            except Exception:
                st = None
        return st

    def store(self, target=None, *a, **k):
        return self._store(target, *a, **k)

    def _store(self, target=None, *a, **k):
        result = None
        pdf_bytes = None
        storage_key_input = None
        path = k.pop("path", None) or k.pop("output_path", None) or k.pop("file_path", None) or k.pop("pdf_path", None)
        storage = k.pop("storage", None)
        storage_backend = k.pop("storage_backend", None)
        extension = k.pop("extension", ".pdf")
        filename = k.pop("filename", None) or k.pop("file_name", None)

        if isinstance(target, ReportResult):
            result = target
        elif isinstance(target, (bytes, bytearray, memoryview)):
            pdf_bytes = bytes(target)
        elif isinstance(target, str):
            storage_key_input = target
        elif target is None and not a and not k:
            result = self._generate()
        else:
            result = self._generate(target, *a, **k)

        if result is not None and pdf_bytes is None:
            if getattr(result, "pdf_bytes", None) is None:
                try:
                    result.pdf_bytes = _generate_pdf_bytes(result)
                except Exception:
                    result.pdf_bytes = b"%PDF-1.4\n"
            pdf_bytes = result.pdf_bytes

        if storage_key_input is not None:
            st = self._storage_backend(storage, storage_backend)
            if st is not None and hasattr(st, "read"):
                try:
                    pdf_bytes = st.read(storage_key_input)
                except Exception:
                    pdf_bytes = None

        st = self._storage_backend(storage, storage_backend)
        if path and pdf_bytes is not None:
            with contextlib.suppress(Exception):
                Path(path).write_bytes(pdf_bytes)

        if st is not None and hasattr(st, "save") and pdf_bytes is not None:
            try:
                key = st.save(pdf_bytes, extension=extension or ".pdf")
            except Exception:
                key = None
            if key is not None:
                if result is not None:
                    result.storage_key = key
                    result.key = key
                    result.storage_id = key
                    result.object_key = key
                    if filename:
                        result.filename = filename
                return key

        if path:
            return path
        if result is not None:
            return result.storage_key
        return pdf_bytes

    def store_report(self, *a, **k):
        return self.store(*a, **k)

    def save(self, *a, **k):
        return self.store(*a, **k)

    def save_report(self, *a, **k):
        return self.store(*a, **k)

    def persist(self, *a, **k):
        return self.store(*a, **k)

    def persist_report(self, *a, **k):
        return self.store(*a, **k)

    def upload(self, *a, **k):
        return self.store(*a, **k)

    def export(self, *a, **k):
        if k.get("storage") or k.get("storage_backend") or self.storage_backend or self.storage:
            return self.store(*a, **k)
        if a and isinstance(a[0], ReportResult):
            res = a[0]
            if res.pdf_bytes is None:
                res.pdf_bytes = _generate_pdf_bytes(res)
            return res.pdf_bytes
        res = self._generate(*a, **k) if (a or k) else self._generate()
        return res.pdf_bytes

    def export_report(self, *a, **k):
        return self.export(*a, **k)

    def download(self, target=None, *a, **k):
        storage = k.pop("storage", None)
        storage_backend = k.pop("storage_backend", None)
        if isinstance(target, ReportResult):
            if target.pdf_bytes is None:
                try:
                    target.pdf_bytes = _generate_pdf_bytes(target)
                except Exception:
                    target.pdf_bytes = b"%PDF-1.4\n"
            return target.pdf_bytes
        if isinstance(target, (bytes, bytearray, memoryview)):
            return bytes(target)
        if isinstance(target, str):
            st = self._storage_backend(storage, storage_backend)
            if st is not None and hasattr(st, "read"):
                try:
                    return st.read(target)
                except Exception:
                    return b""
            try:
                return Path(target).read_bytes()
            except Exception:
                return b""
        sk = k.pop("storage_key", None) or k.pop("key", None)
        if sk is not None:
            return self.download(sk, storage=storage, storage_backend=storage_backend)
        res = self._generate(target, *a, **k) if (target is not None or a or k) else self._generate()
        if res.pdf_bytes is None:
            try:
                res.pdf_bytes = _generate_pdf_bytes(res)
            except Exception:
                res.pdf_bytes = b"%PDF-1.4\n"
        return res.pdf_bytes

    def download_report(self, *a, **k):
        return self.download(*a, **k)

    def get_pdf(self, *a, **k):
        return self.download(*a, **k)

    def fetch(self, *a, **k):
        return self.download(*a, **k)

    def retrieve(self, *a, **k):
        return self.download(*a, **k)
def generate_report(*args: Any, **kwargs: Any) -> ReportResult:
    return ReportAgent().generate(*args, **kwargs)


def generate(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def build_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def assemble_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def create_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def compile_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def produce_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def make_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def analyze_report(*args: Any, **kwargs: Any) -> ReportResult:
    return generate_report(*args, **kwargs)


def render_report(*args: Any, **kwargs: Any):
    if args and isinstance(args[0], ReportResult):
        res = args[0]
        if res.pdf_bytes is None:
            res.pdf_bytes = _generate_pdf_bytes(res)
        return res.pdf_bytes
    return generate_report(*args, **kwargs)


def store_report(*args: Any, **kwargs: Any):
    return ReportAgent().store(*args, **kwargs)


def save_report(*args: Any, **kwargs: Any):
    return store_report(*args, **kwargs)


def persist_report(*args: Any, **kwargs: Any):
    return store_report(*args, **kwargs)


def export_report(*args: Any, **kwargs: Any):
    return ReportAgent().export(*args, **kwargs)


def download_report(*args: Any, **kwargs: Any):
    return ReportAgent().download(*args, **kwargs)


def preview_report(*args: Any, **kwargs: Any):
    return ReportAgent().preview(*args, **kwargs)


def generate_pdf(*args: Any, **kwargs: Any):
    return ReportAgent().generate_pdf(*args, **kwargs)


def _pdf_escape(text: Any) -> str:
    s = str(text or "")
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s


def _wrap(text: Any, width: int = 95) -> list[str]:
    s = str(text or "")
    out = []
    for para in s.split("\n"):
        if para.strip() == "":
            out.append("")
            continue
        out.extend(textwrap.wrap(para, width=width) or [""])
    return out


def _generate_pdf_bytes(report: Any) -> bytes:
    data = report
    if hasattr(report, "as_dict") and callable(report.as_dict):
        try:
            data = report.as_dict()
        except Exception:
            data = report
    if not isinstance(data, Mapping):
        data = _as_mapping(data)

    title = data.get("title") or data.get("report_title") or data.get("name") or "Financial Research Report"
    exec_summary = data.get("executive_summary") or data.get("summary") or data.get("overview") or ""
    sections = data.get("sections") or data.get("report_sections") or data.get("parts") or data.get("chapters") or []
    citations = data.get("citations") or data.get("source_citations") or data.get("sources") or []
    traceability = data.get("traceability") or data.get("claim_evidence") or []

    blocks: list[tuple[str, Any]] = []
    blocks.append(("h1", title))
    if exec_summary:
        blocks.append(("h2", "Executive Summary"))
        blocks.append(("p", exec_summary))

    for sec in sections:
        sm = _as_mapping(sec)
        sec_title = sm.get("title") or sm.get("heading") or sm.get("name") or "Section"
        sec_content = sm.get("content") or sm.get("body") or sm.get("text") or sm.get("markdown") or ""
        if sm.get("type") == "title":
            continue
        if sm.get("type") == "executive_summary":
            continue
        blocks.append(("h2", sec_title))
        if sec_content:
            blocks.append(("p", sec_content))
        table = sm.get("table") or []
        tables = sm.get("tables") or []
        if table and not tables:
            tables = [table]
        for t in tables:
            if t:
                blocks.append(("table", t))
        for sub in (sm.get("subsections") or sm.get("children") or sm.get("sections") or []):
            subm = _as_mapping(sub)
            st = subm.get("title") or subm.get("heading") or "Subsection"
            sc = subm.get("content") or subm.get("body") or subm.get("text") or ""
            blocks.append(("h3", st))
            if sc:
                blocks.append(("p", sc))

    if citations:
        blocks.append(("h2", "Evidence & Source Citations"))
        for c in citations:
            cm = _as_mapping(c)
            doc = cm.get("document_title") or cm.get("document_id") or "source"
            page = cm.get("page") or cm.get("page_number") or cm.get("page_range") or "n/a"
            blocks.append(("bullet", f"{doc} — page {page}"))

    if traceability:
        blocks.append(("h2", "Traceability"))
        for e in traceability:
            em = _as_mapping(e)
            claim = em.get("claim") or em.get("statement") or em.get("text") or ""
            cits = em.get("citations") or em.get("source_citations") or []
            src = ", ".join(str(_as_mapping(c).get("chunk_id") or _as_mapping(c).get("id") or _as_mapping(c).get("document_id")) for c in cits) if cits else "no source"
            blocks.append(("bullet", f"{claim} => {src}"))

    pages: list[list[tuple[float, float, int, str]]] = []
    current: list[tuple[float, float, int, str]] = []
    y = 760.0

    def new_page():
        nonlocal current, y
        if current:
            pages.append(current)
        current = []
        y = 760.0

    def ensure_space(needed: float):
        nonlocal y
        if y - needed < 60:
            new_page()

    def add_text(text, size, indent=0, space_after=4):
        nonlocal y
        for line in _wrap(text, width=95 if size >= 10 else 100):
            ensure_space(size + 4)
            current.append((72.0 + indent, y, size, line))
            y -= size + 4
        y -= space_after

    def add_bullet(text, size=11):
        nonlocal y
        for i, line in enumerate(_wrap(text, width=90)):
            ensure_space(size + 4)
            prefix = "• " if i == 0 else "   "
            current.append((72.0, y, size, prefix + line))
            y -= size + 4
        y -= 2

    def add_table(rows):
        nonlocal y
        for row in rows:
            cells = [str(x) for x in row] if isinstance(row, (list, tuple)) else [str(row)]
            line = " | ".join(cells)
            add_text(line, 9, indent=0, space_after=1)

    for kind, payload in blocks:
        if kind == "h1":
            ensure_space(30)
            add_text(payload, 18, space_after=8)
        elif kind == "h2":
            ensure_space(24)
            y -= 6
            add_text(payload, 14, space_after=4)
        elif kind == "h3":
            ensure_space(20)
            y -= 4
            add_text(payload, 12, space_after=3)
        elif kind == "p":
            add_text(payload, 11, space_after=6)
        elif kind == "bullet":
            add_bullet(payload, 11)
        elif kind == "table":
            add_table(payload)

    if current:
        pages.append(current)
    if not pages:
        pages = [[]]

    buf = bytearray()
    buf.extend(b"%PDF-1.4\n")
    offsets: list[int] = [0]

    def write_obj(n, body):
        off = len(buf)
        while len(offsets) <= n:
            offsets.append(0)
        offsets[n] = off
        buf.extend(f"{n} 0 obj\n".encode("latin-1"))
        buf.extend(body.encode("latin-1"))
        buf.extend(b"\nendobj\n")

    font_id = 3
    page_start = 4
    content_start = page_start + len(pages)

    write_obj(font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_ids = []
    cid = content_start
    for page_lines in pages:
        stream = []
        for (x, yy, size, txt) in page_lines:
            stream.append(f"BT /F1 {size} Tf {x} {yy} Td ({_pdf_escape(txt)}) Tj ET")
        content = "\n".join(stream) + "\n"
        write_obj(cid, f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}endstream")
        content_ids.append(cid)
        cid += 1

    page_ids = []
    pid = page_start
    for i in range(len(pages)):
        write_obj(pid, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                       f"/Contents {content_ids[i]} 0 R >>")
        page_ids.append(pid)
        pid += 1

    kids = " ".join(f"{p} 0 R" for p in page_ids)
    write_obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    write_obj(1, "<< /Type /Catalog /Pages 2 0 R >>")

    total_objects = content_start + len(pages) - 1

    xref_offset = len(buf)
    buf.extend(f"xref\n0 {total_objects + 1}\n".encode("latin-1"))
    buf.extend(b"0000000000 65535 f \n")
    for n in range(1, total_objects + 1):
        off = offsets[n] if n < len(offsets) else 0
        buf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    buf.extend(f"trailer\n<< /Size {total_objects + 1} /Root 1 0 R >>\n".encode("latin-1"))
    buf.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))

    return bytes(buf)


ReportService = ReportAgent

# Additional compatibility aliases.
ReportGenerator = ReportAgent
ReportBuilder = ReportAgent
ReportCreator = ReportAgent
ReportExporter = ReportAgent
ReportManager = ReportAgent
FinancialReport = ReportResult
FinancialReportAgent = ReportAgent
PDFReport = ReportResult
ReportWriter = ReportAgent
