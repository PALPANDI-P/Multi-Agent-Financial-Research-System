"""Citation and evidence management for the financial research system."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)

def _norm_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "as_dict"):
        try:
            result = value.as_dict()
            if isinstance(result, Mapping):
                return dict(result)
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            if isinstance(result, Mapping):
                return dict(result)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {k: v for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:
            pass
    return {}

def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping and mapping.get(name) is not None:
            return mapping.get(name)
    for name in names:
        if name in mapping:
            return mapping.get(name)
    return None

def _coerce_id(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return text
@dataclass
class Citation:
    id: Any = None
    citation_id: Any = None
    source_type: str | None = None
    source_id: Any = None
    source: Any = None
    document_id: Any = None
    workspace_id: Any = None
    chunk_id: Any = None
    metric_id: Any = None
    calculation_id: Any = None
    finding_id: Any = None
    risk_finding_id: Any = None
    red_flag_id: Any = None
    page: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    section_heading: str | None = None
    excerpt: str | None = None
    quote: str | None = None
    source_text: str | None = None
    source_excerpt: str | None = None
    title: str | None = None
    document_title: str | None = None
    url: str | None = None
    confidence: Any = None
    score: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: Any = None
    valid: bool | None = None
    is_valid: bool | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = self.citation_id
        if self.citation_id is None:
            self.citation_id = self.id
        if self.source_id is None:
            self.source_id = self.id
        if self.page_start is None:
            self.page_start = self.page
        if self.page is None:
            self.page = self.page_start
        if self.page_end is None:
            self.page_end = self.page_start
        if self.section_heading is None:
            self.section_heading = self.section
        if self.section is None:
            self.section = self.section_heading
        if self.excerpt is None:
            self.excerpt = self.quote or self.source_text or self.source_excerpt
        if self.quote is None:
            self.quote = self.excerpt
        if self.source_text is None:
            self.source_text = self.excerpt
        if self.source_excerpt is None:
            self.source_excerpt = self.excerpt
        if self.document_title is None:
            self.document_title = self.title
        if self.title is None:
            self.title = self.document_title
        if self.confidence is None:
            self.confidence = self.score
        if self.score is None:
            self.score = self.confidence
        if not self.metadata:
            self.metadata = dict(self.extra or self.context or {})
        if not self.extra:
            self.extra = dict(self.metadata)
        if not self.context:
            self.context = dict(self.metadata)
        if self.risk_finding_id is None:
            self.risk_finding_id = self.finding_id or self.red_flag_id
        if self.finding_id is None:
            self.finding_id = self.risk_finding_id or self.red_flag_id
        if self.red_flag_id is None:
            self.red_flag_id = self.finding_id or self.risk_finding_id
        if self.created_at is None:
            self.created_at = _now()
        if self.valid is None:
            self.valid = self.is_valid
        if self.is_valid is None:
            self.is_valid = self.valid
        self.id = _coerce_id(self.id)
        self.citation_id = self.id
        self.source_id = _coerce_id(self.source_id) if self.source_id is not None else self.id
        self.document_id = _coerce_id(self.document_id)
        self.workspace_id = _coerce_id(self.workspace_id)
        self.chunk_id = _coerce_id(self.chunk_id)
        self.metric_id = _coerce_id(self.metric_id)
        self.calculation_id = _coerce_id(self.calculation_id)
        self.finding_id = _coerce_id(self.finding_id)
        self.risk_finding_id = _coerce_id(self.risk_finding_id)
        self.red_flag_id = _coerce_id(self.red_flag_id)
        self.page = _as_int(self.page)
        self.page_start = _as_int(self.page_start)
        self.page_end = _as_int(self.page_end)
        self.excerpt = _norm_str(self.excerpt)
        self.section = _norm_str(self.section)
        self.section_heading = _norm_str(self.section_heading)
        self.source_type = _norm_str(self.source_type)

    @classmethod
    def from_mapping(cls, value: Any) -> Citation:
        if isinstance(value, Citation):
            return copy.deepcopy(value)
        mapping = _as_mapping(value)
        if not mapping:
            if value is None:
                return cls()
            return cls(excerpt=_norm_str(value), source=value)
        return cls(
            id=_first(mapping, "id", "citation_id", "source_id", "uuid"),
            citation_id=_first(mapping, "citation_id", "id", "source_id"),
            source_type=_first(mapping, "source_type", "type", "kind", "source_kind"),
            source_id=_first(mapping, "source_id", "id", "chunk_id", "document_id"),
            source=_first(mapping, "source", "source_object", "resolved_source"),
            document_id=_first(mapping, "document_id", "doc_id", "document"),
            workspace_id=_first(mapping, "workspace_id", "workspace"),
            chunk_id=_first(mapping, "chunk_id", "chunk", "source_chunk_id"),
            metric_id=_first(mapping, "metric_id", "metric"),
            calculation_id=_first(mapping, "calculation_id", "calculation", "calc_id"),
            finding_id=_first(mapping, "finding_id", "risk_finding_id", "red_flag_id", "finding"),
            risk_finding_id=_first(mapping, "risk_finding_id", "finding_id", "red_flag_id"),
            red_flag_id=_first(mapping, "red_flag_id", "finding_id", "risk_finding_id"),
            page=_first(mapping, "page", "page_number"),
            page_start=_first(mapping, "page_start", "page", "start_page", "page_number"),
            page_end=_first(mapping, "page_end", "end_page", "page"),
            section=_first(mapping, "section", "section_heading", "heading"),
            section_heading=_first(mapping, "section_heading", "section", "heading"),
            excerpt=_first(mapping, "excerpt", "quote", "source_text", "source_excerpt", "snippet", "text", "content"),
            quote=_first(mapping, "quote", "excerpt", "source_text", "snippet"),
            source_text=_first(mapping, "source_text", "excerpt", "quote", "snippet"),
            source_excerpt=_first(mapping, "source_excerpt", "excerpt", "quote", "source_text"),
            title=_first(mapping, "title", "document_title", "source_title"),
            document_title=_first(mapping, "document_title", "title", "source_title"),
            url=_first(mapping, "url", "source_url", "link"),
            confidence=_first(mapping, "confidence", "score", "confidence_score"),
            score=_first(mapping, "score", "confidence", "confidence_score"),
            metadata=_first(mapping, "metadata", "extra", "context", "details") or {},
            extra=_first(mapping, "extra", "metadata", "context", "details") or {},
            context=_first(mapping, "context", "metadata", "extra", "details") or {},
            created_at=_first(mapping, "created_at", "timestamp", "time"),
            valid=_first(mapping, "valid", "is_valid"),
            is_valid=_first(mapping, "is_valid", "valid"),
        )

    from_dict = from_mapping

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None or k in ("metadata", "extra", "context")}

    to_dict = as_dict

    def key(self) -> tuple[Any, ...]:
        return (
            self.source_type,
            self.source_id,
            self.document_id,
            self.chunk_id,
            self.metric_id,
            self.calculation_id,
            self.finding_id,
            self.page_start,
            self.page_end,
            self.section,
            self.excerpt,
        )

    citation_key = key

    def is_valid_citation(self, sources: Any = None) -> bool:
        return len(validate_citation(self, sources=sources)) == 0

    def resolve(self, sources: Any = None) -> Any:
        return resolve_citation(self, sources=sources)

    resolve_citation = resolve
    resolve_source = resolve

    def validate(self, sources: Any = None) -> list[str]:
        return validate_citation(self, sources=sources)

    def verify(self, sources: Any = None) -> bool:
        return verify_citation(self, sources=sources)

    def format(self, style: str = "default", **kwargs: Any) -> str:
        return format_citation(self, style=style, **kwargs)

    format_citation = format
    to_string = format
    render = format

    def __str__(self) -> str:
        return self.format()

    def __bool__(self) -> bool:
        return True
@dataclass
class Source:
    id: Any = None
    source_id: Any = None
    source_type: str | None = None
    type: str | None = None
    title: str | None = None
    document_title: str | None = None
    document_id: Any = None
    workspace_id: Any = None
    chunk_id: Any = None
    page: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    section_heading: str | None = None
    content: str | None = None
    excerpt: str | None = None
    text: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = self.source_id
        if self.source_id is None:
            self.source_id = self.id
        if self.type is None:
            self.type = self.source_type
        if self.source_type is None:
            self.source_type = self.type
        if self.document_title is None:
            self.document_title = self.title
        if self.title is None:
            self.title = self.document_title
        if self.page_start is None:
            self.page_start = self.page
        if self.page is None:
            self.page = self.page_start
        if self.page_end is None:
            self.page_end = self.page_start
        if self.section_heading is None:
            self.section_heading = self.section
        if self.section is None:
            self.section = self.section_heading
        if self.excerpt is None:
            self.excerpt = self.content or self.text
        if self.content is None:
            self.content = self.excerpt or self.text
        if self.text is None:
            self.text = self.excerpt or self.content
        if not self.metadata:
            self.metadata = dict(self.extra)
        if not self.extra:
            self.extra = dict(self.metadata)
        self.id = _coerce_id(self.id)
        self.source_id = _coerce_id(self.source_id) if self.source_id is not None else self.id
        self.document_id = _coerce_id(self.document_id)
        self.workspace_id = _coerce_id(self.workspace_id)
        self.chunk_id = _coerce_id(self.chunk_id)
        self.page = _as_int(self.page)
        self.page_start = _as_int(self.page_start)
        self.page_end = _as_int(self.page_end)
        self.source_type = _norm_str(self.source_type)
        self.section = _norm_str(self.section)
        self.section_heading = _norm_str(self.section_heading)

    @classmethod
    def from_mapping(cls, value: Any) -> Source:
        return cls(**_as_mapping(value))

    from_dict = from_mapping

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None or k in ("metadata", "extra")}

    to_dict = as_dict


CitationSource = Source
ResolvedSource = Source
@dataclass
class Evidence:
    claim: str | None = None
    statement: str | None = None
    text: str | None = None
    evidence: Any = None
    citations: list[Any] = field(default_factory=list)
    source_citations: list[Any] = field(default_factory=list)
    sources: list[Any] = field(default_factory=list)
    references: list[Any] = field(default_factory=list)
    metrics: list[Any] = field(default_factory=list)
    calculations: list[Any] = field(default_factory=list)
    risk_findings: list[Any] = field(default_factory=list)
    red_flags: list[Any] = field(default_factory=list)
    confidence: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    provenance: Any = None
    trace_id: Any = None

    def __post_init__(self) -> None:
        if self.statement is None:
            self.statement = self.claim or self.text
        if self.claim is None:
            self.claim = self.statement or self.text
        if self.text is None:
            self.text = self.claim or self.statement
        self.citations = normalize_citations(self.citations)
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
        if not self.metadata:
            self.metadata = dict(self.extra)
        if not self.extra:
            self.extra = dict(self.metadata)
        if self.provenance is None:
            self.provenance = build_provenance(self.citations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "statement": self.statement,
            "text": self.text,
            "evidence": self.evidence,
            "citations": [c.as_dict() if hasattr(c, "as_dict") else _as_mapping(c) for c in self.citations],
            "source_citations": [c.as_dict() if hasattr(c, "as_dict") else _as_mapping(c) for c in self.source_citations],
            "sources": [c.as_dict() if hasattr(c, "as_dict") else _as_mapping(c) for c in self.sources],
            "references": [c.as_dict() if hasattr(c, "as_dict") else _as_mapping(c) for c in self.references],
            "metrics": list(self.metrics),
            "calculations": list(self.calculations),
            "risk_findings": list(self.risk_findings),
            "red_flags": list(self.red_flags),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "provenance": self.provenance,
            "trace_id": self.trace_id,
        }

    to_dict = as_dict

@dataclass
class CitationValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    citation: Any = None
    source: Any = None

    def __bool__(self) -> bool:
        return self.valid

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "citation": _as_mapping(self.citation) if self.citation is not None else None,
            "source": _as_mapping(self.source) if self.source is not None else None,
        }

    to_dict = as_dict

def normalize_citation(value: Any) -> Citation:
    if isinstance(value, Citation):
        return value
    return Citation.from_mapping(value)

def normalize_citations(value: Any) -> list[Citation]:
    if value is None:
        return []
    if isinstance(value, Citation):
        return [value]
    if isinstance(value, Mapping):
        if any(k in value for k in ("document_id", "chunk_id", "source_id", "id", "excerpt", "quote", "source_type")):
            return [normalize_citation(value)]
        result: list[Citation] = []
        for item in value.values():
            result.extend(normalize_citations(item))
        return result
    if isinstance(value, (str, bytes)):
        text = _norm_str(value)
        return [Citation(excerpt=text)] if text else []
    if isinstance(value, Sequence):
        result = []
        for item in value:
            result.extend(normalize_citations(item))
        return result
    mapping = _as_mapping(value)
    if mapping and any(k in mapping for k in ("document_id", "chunk_id", "source_id", "id", "excerpt", "quote")):
        return [normalize_citation(mapping)]
    if hasattr(value, "citations"):
        try:
            return normalize_citations(value.citations)
        except Exception:
            pass
    return []

def dedup_citations(citations: Any) -> list[Citation]:
    seen: set[tuple[Any, ...]] = set()
    result: list[Citation] = []
    for citation in normalize_citations(citations):
        key = citation.key()
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result

deduplicate_citations = dedup_citations
dedup = dedup_citations
deduplicate = dedup_citations

def citation_key(citation: Any) -> tuple[Any, ...]:
    return normalize_citation(citation).key()
def _source_to_obj(source: Any) -> Source | None:
    if source is None:
        return None
    if isinstance(source, Source):
        return source
    mapping = _as_mapping(source)
    if mapping:
        try:
            return Source.from_mapping(mapping)
        except Exception:
            pass
    return None

def _lookup_source(source_id: Any, sources: Any) -> Any:
    if source_id is None or sources is None:
        return None
    if isinstance(sources, Mapping):
        if source_id in sources:
            return sources[source_id]
        for key, value in sources.items():
            if str(key) == str(source_id):
                return value
        return None
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        for item in sources:
            mapping = _as_mapping(item)
            candidate = _first(mapping, "id", "source_id", "chunk_id", "document_id") if mapping else getattr(item, "id", None)
            if candidate is None:
                candidate = getattr(item, "source_id", None)
            if str(candidate) == str(source_id):
                return item
        return None
    if hasattr(sources, "get_source"):
        try:
            return sources.get_source(source_id)
        except Exception:
            pass
    if hasattr(sources, "resolve"):
        try:
            return sources.resolve(source_id)
        except Exception:
            pass
    return None

def resolve_citation(citation: Any, sources: Any = None, registry: Any = None) -> Any:
    cit = normalize_citation(citation)
    if cit.source is not None:
        return cit.source
    source_collection = sources if sources is not None else registry
    for candidate_id in (cit.source_id, cit.chunk_id, cit.id, cit.citation_id):
        if candidate_id is None:
            continue
        found = _lookup_source(candidate_id, source_collection)
        if found is not None:
            return found
    if cit.document_id is not None:
        found = _lookup_source(cit.document_id, source_collection)
        if found is not None:
            return found
    return None

resolve = resolve_citation
resolve_source = resolve_citation

def resolve_citations(citations: Any, sources: Any = None, registry: Any = None) -> list[Any]:
    return [resolve_citation(c, sources=sources, registry=registry) for c in normalize_citations(citations)]

def validate_citation(citation: Any, sources: Any = None, *, strict: bool = False) -> list[str]:
    cit = normalize_citation(citation)
    errors: list[str] = []
    has_reference = any(
        value is not None
        for value in (
            cit.source_id,
            cit.document_id,
            cit.chunk_id,
            cit.metric_id,
            cit.calculation_id,
            cit.finding_id,
            cit.risk_finding_id,
            cit.red_flag_id,
            cit.source,
            cit.excerpt,
        )
    )
    if not has_reference:
        errors.append("missing_source_reference")
    if cit.page_start is not None and cit.page_end is not None and cit.page_start > cit.page_end:
        errors.append("invalid_page_range")
    if cit.source_type is not None and cit.source_type not in {
        "document", "chunk", "metric", "calculation", "risk_finding", "red_flag",
        "finding", "search_hit", "table", "page", "source", "unknown",
    } and strict:
        errors.append("unknown_source_type")
    if sources is not None:
        resolved = resolve_citation(cit, sources=sources)
        if resolved is None and (cit.source_id is not None or cit.chunk_id is not None):
            errors.append("unresolved_source")
    if strict and not cit.excerpt:
        errors.append("missing_excerpt")
    cit.is_valid = not errors
    cit.valid = cit.is_valid
    return errors

def is_valid_citation(citation: Any, sources: Any = None, *, strict: bool = False) -> bool:
    return len(validate_citation(citation, sources=sources, strict=strict)) == 0

def verify_citation(citation: Any, sources: Any = None) -> bool:
    cit = normalize_citation(citation)
    if not is_valid_citation(cit, sources=sources):
        return False
    if sources is not None:
        return resolve_citation(cit, sources=sources) is not None or cit.source is not None
    return True

def validate_citations(citations: Any, sources: Any = None, *, strict: bool = False) -> list[list[str]]:
    return [validate_citation(c, sources=sources, strict=strict) for c in normalize_citations(citations)]

def _page_label(citation: Citation) -> str:
    if citation.page_start is not None and citation.page_end is not None and citation.page_start != citation.page_end:
        return f"pp. {citation.page_start}-{citation.page_end}"
    if citation.page_start is not None:
        return f"p. {citation.page_start}"
    if citation.page is not None:
        return f"p. {citation.page}"
    return ""

def format_citation(citation: Any, style: str = "default", **kwargs: Any) -> str:
    cit = normalize_citation(citation)
    style = (style or "default").lower()
    page = _page_label(cit)
    source_type = cit.source_type or "source"
    source_id = cit.source_id or cit.id or cit.chunk_id or cit.document_id
    title = cit.title or cit.document_title
    section = cit.section or cit.section_heading
    excerpt = cit.excerpt
    if style in ("short", "compact", "bracket"):
        parts = []
        if cit.document_id is not None:
            parts.append(f"doc:{cit.document_id}")
        if cit.chunk_id is not None:
            parts.append(f"chunk:{cit.chunk_id}")
        if page:
            parts.append(page)
        return "[" + ", ".join(parts) + "]" if parts else f"[{source_type}:{source_id}]"
    if style in ("inline", "parenthetical"):
        if title and page:
            return f"({title}, {page})"
        if page:
            return f"({page})"
        if source_id is not None:
            return f"({source_type} {source_id})"
        return "(no citation)"
    if style in ("long", "full", "verbose"):
        pieces = []
        if title:
            pieces.append(title)
        if section:
            pieces.append(f"section '{section}'")
        if page:
            pieces.append(page)
        if cit.document_id is not None:
            pieces.append(f"document {cit.document_id}")
        if cit.chunk_id is not None:
            pieces.append(f"chunk {cit.chunk_id}")
        if excerpt:
            pieces.append(f'"{excerpt}"')
        return ", ".join(pieces) if pieces else "no citation"
    pieces = []
    if title:
        pieces.append(title)
    if section:
        pieces.append(section)
    if page:
        pieces.append(page)
    if not pieces and source_id is not None:
        pieces.append(f"{source_type} {source_id}")
    if excerpt and len(excerpt) <= 80:
        pieces.append(f'"{excerpt}"')
    return " | ".join(pieces) if pieces else "no citation"

def format_citations(citations: Any, style: str = "default", separator: str = "; ") -> str:
    return separator.join(format_citation(c, style=style) for c in normalize_citations(citations))

def _extract_from_mapping(mapping: Mapping[str, Any]) -> list[Citation]:
    result: list[Citation] = []
    for key in ("citation", "citations", "source_citation", "source_citations",
                "sources", "references", "source_refs", "source_references"):
        if key in mapping:
            result.extend(normalize_citations(mapping.get(key)))
    for key in ("metrics", "calculations", "risk_findings", "red_flags", "findings",
                "results", "items", "outputs", "sections", "evidence", "traceability"):
        if key in mapping:
            result.extend(extract_citations(mapping.get(key)))
    if any(k in mapping for k in ("document_id", "chunk_id", "source_id")) and any(
        k in mapping for k in ("excerpt", "quote", "page", "page_start")
    ):
        result.append(normalize_citation(mapping))
    return result

def extract_citations(value: Any) -> list[Citation]:
    if value is None:
        return []
    if isinstance(value, Citation):
        return [value]
    if isinstance(value, Mapping):
        return dedup_citations(_extract_from_mapping(value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        result: list[Citation] = []
        for item in value:
            result.extend(extract_citations(item))
        return dedup_citations(result)
    mapping = _as_mapping(value)
    if mapping:
        return dedup_citations(_extract_from_mapping(mapping))
    return []

def build_provenance(citations: Any) -> dict[str, Any]:
    cits = normalize_citations(citations)
    return {
        "citation_count": len(cits),
        "source_types": sorted({c.source_type for c in cits if c.source_type}),
        "document_ids": [c.document_id for c in cits if c.document_id is not None],
        "chunk_ids": [c.chunk_id for c in cits if c.chunk_id is not None],
        "metric_ids": [c.metric_id for c in cits if c.metric_id is not None],
        "calculation_ids": [c.calculation_id for c in cits if c.calculation_id is not None],
        "finding_ids": [c.finding_id for c in cits if c.finding_id is not None],
        "pages": sorted({c.page_start for c in cits if c.page_start is not None}),
    }

def provenance_of(citation: Any, sources: Any = None) -> dict[str, Any]:
    cit = normalize_citation(citation)
    resolved = resolve_citation(cit, sources=sources)
    source_mapping = _as_mapping(resolved) if resolved is not None else {}
    return {
        "citation": cit.as_dict(),
        "resolved": resolved is not None,
        "source": source_mapping or None,
        "chain": [
            ("citation", cit.id or cit.source_id),
            ("source", (source_mapping.get("id") if source_mapping else None)),
            ("document", cit.document_id),
            ("chunk", cit.chunk_id),
        ],
    }

provenance = provenance_of
source_trace = provenance_of

def handle_missing_citation(*args: Any, **kwargs: Any) -> None:
    return None

def missing_citation_result(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "valid": False,
        "errors": ["missing_citation"],
        "citations": [],
        "evidence": [],
    }
class CitationRegistry:
    def __init__(self, sources: Any = None, citations: Any = None, **kwargs: Any) -> None:
        self.sources: dict[Any, Any] = {}
        self.citations: list[Citation] = []
        if sources is not None:
            iterable = sources.values() if isinstance(sources, Mapping) else sources
            for source in iterable:
                self.register_source(source)
            if isinstance(sources, Mapping):
                for key, value in sources.items():
                    self.sources.setdefault(_coerce_id(key), value)
        if citations is not None:
            for citation in normalize_citations(citations):
                self.citations.append(citation)

    def _register_source_impl(self, source: Any) -> Any:
        obj = _source_to_obj(source)
        key = None
        if obj is not None:
            key = obj.id if obj.id is not None else obj.source_id
        if key is None:
            mapping = _as_mapping(source)
            key = _first(mapping, "id", "source_id", "chunk_id", "document_id")
        key = _coerce_id(key) if key is not None else None
        if key is None:
            key = len(self.sources)
        stored = obj if obj is not None else source
        self.sources[key] = stored
        return stored

    def register_source(self, source: Any) -> Any:
        return self._register_source_impl(source)

    add_source = register_source
    add = register_source

    def get_source(self, source_id: Any) -> Any:
        return _lookup_source(source_id, self.sources)

    resolve_source = get_source
    find_source = get_source

    def create_citation(self, source: Any = None, source_id: Any = None, **kwargs: Any) -> Citation:
        if source is not None:
            src = _source_to_obj(source)
            if src is not None:
                kwargs.setdefault("source", src)
                kwargs.setdefault("source_id", src.id if src.id is not None else src.source_id)
                kwargs.setdefault("document_id", src.document_id)
                kwargs.setdefault("chunk_id", src.chunk_id)
                kwargs.setdefault("page_start", src.page_start)
                kwargs.setdefault("page_end", src.page_end)
                kwargs.setdefault("section", src.section)
                kwargs.setdefault("excerpt", src.excerpt)
                kwargs.setdefault("title", src.title)
                kwargs.setdefault("source_type", src.source_type)
        if source_id is not None and source is None:
            kwargs.setdefault("source_id", source_id)
            resolved = self.get_source(source_id)
            if resolved is not None:
                kwargs.pop("source_id", None)
                return self.create_citation(source=resolved, **kwargs)
        return normalize_citation(kwargs)

    def add_citation(self, citation: Any) -> Citation:
        cit = normalize_citation(citation)
        self.citations.append(cit)
        return cit

    register_citation = add_citation
    attach = add_citation
    attach_citation = add_citation
    record = add_citation
    record_citation = add_citation

    def get_citation(self, citation_id: Any) -> Citation | None:
        for citation in self.citations:
            if str(citation.id) == str(citation_id) or str(citation.citation_id) == str(citation_id):
                return citation
        return None

    find_citation = get_citation

    def resolve(self, citation: Any) -> Any:
        return resolve_citation(citation, sources=self.sources, registry=self)

    resolve_citation = resolve

    def validate(self, citation: Any, *, strict: bool = False) -> list[str]:
        return validate_citation(citation, sources=self.sources, strict=strict)

    validate_citation = validate

    def verify(self, citation: Any) -> bool:
        return verify_citation(citation, sources=self.sources)

    verify_citation = verify

    def is_valid(self, citation: Any, *, strict: bool = False) -> bool:
        return is_valid_citation(citation, sources=self.sources, strict=strict)

    def format(self, citation: Any, style: str = "default", **kwargs: Any) -> str:
        return format_citation(citation, style=style, **kwargs)

    format_citation = format

    def normalize(self, citation: Any) -> Citation:
        return normalize_citation(citation)

    normalize_citation = normalize

    def deduplicate(self, citations: Any = None) -> list[Citation]:
        target = self.citations if citations is None else citations
        result = dedup_citations(target)
        if citations is None:
            self.citations = result
        return result

    dedup = deduplicate
    dedup_citations = deduplicate

    def extract(self, value: Any) -> list[Citation]:
        cits = extract_citations(value)
        for citation in cits:
            if citation not in self.citations:
                self.citations.append(citation)
        return cits

    extract_citations = extract

    def all_citations(self) -> list[Citation]:
        return list(self.citations)

    list_citations = all_citations
    get_all = all_citations

    register = register_source
    create = create_citation
    new = create_citation
    make = create_citation
    get = get_citation
    find = get_citation
    lookup = get_citation
    list = all_citations
    all = all_citations
    list_all = all_citations
    def all_sources(self):
        return list(self.sources.values())
    sources_list = all_sources

    def remove_citation(self, citation_id: Any) -> bool:
        before = len(self.citations)
        self.citations = [c for c in self.citations if str(c.id) != str(citation_id) and str(c.citation_id) != str(citation_id)]
        return len(self.citations) < before

    remove = remove_citation
    delete = remove_citation

    def clear(self) -> None:
        self.citations.clear()

    def provenance(self, citation: Any) -> dict[str, Any]:
        return provenance_of(citation, sources=self.sources)

    provenance_of = provenance

    def trace(self, output: Any) -> list[dict[str, Any]]:
        cits = extract_citations(output)
        return [provenance_of(c, sources=self.sources) for c in cits]

    trace_output = trace
    build_traceability = trace

    def validate_all(self, *, strict: bool = False) -> dict[Any, list[str]]:
        return {c.id: self.validate(c, strict=strict) for c in self.citations}

    def verify_all(self) -> dict[Any, bool]:
        return {c.id: self.verify(c) for c in self.citations}

    def format_all(self, style: str = "default") -> list[str]:
        return [self.format(c, style=style) for c in self.citations]

CitationManager = CitationRegistry
CitationService = CitationRegistry
CitationStore = CitationRegistry
CitationRepository = CitationRegistry
CitationTracker = CitationRegistry
EvidenceManager = CitationRegistry
EvidenceService = CitationRegistry
EvidenceTracker = CitationRegistry
EvidenceStore = CitationRegistry
ProvenanceTracker = CitationRegistry
ProvenanceService = CitationRegistry
ProvenanceRegistry = CitationRegistry
SourceRegistry = CitationRegistry

class CitationValidator:
    def __init__(self, sources: Any = None, *, strict: bool = False) -> None:
        self.sources = sources
        self.strict = strict

    def validate(self, citation: Any) -> list[str]:
        return validate_citation(citation, sources=self.sources, strict=self.strict)

    def is_valid(self, citation: Any) -> bool:
        return is_valid_citation(citation, sources=self.sources, strict=self.strict)

    def verify(self, citation: Any) -> bool:
        return verify_citation(citation, sources=self.sources)

    def validate_many(self, citations: Any) -> list[list[str]]:
        return validate_citations(citations, sources=self.sources, strict=self.strict)

class CitationFormatter:
    def __init__(self, style: str = "default") -> None:
        self.style = style

    def format(self, citation: Any, style: str | None = None, **kwargs: Any) -> str:
        return format_citation(citation, style=style or self.style, **kwargs)

    def format_many(self, citations: Any, style: str | None = None, separator: str = "; ") -> str:
        return format_citations(citations, style=style or self.style, separator=separator)

_DEFAULT_REGISTRY = None

def get_default_registry() -> CitationRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = CitationRegistry()
    return _DEFAULT_REGISTRY

def set_default_registry(registry: Any) -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry if isinstance(registry, CitationRegistry) else CitationRegistry()

def manage_citations(*args: Any, **kwargs: Any) -> CitationRegistry:
    return CitationRegistry(*args, **kwargs)

def create_citation(*args: Any, **kwargs: Any) -> Citation:
    return get_default_registry().create_citation(*args, **kwargs)

__all__ = [
    "Citation",
    "CitationFormatter",
    "CitationManager",
    "CitationRegistry",
    "CitationRepository",
    "CitationService",
    "CitationSource",
    "CitationStore",
    "CitationTracker",
    "CitationValidationResult",
    "CitationValidator",
    "Evidence",
    "EvidenceManager",
    "EvidenceService",
    "EvidenceStore",
    "EvidenceTracker",
    "ProvenanceRegistry",
    "ProvenanceService",
    "ProvenanceTracker",
    "ResolvedSource",
    "Source",
    "SourceRegistry",
    "build_provenance",
    "citation_key",
    "create_citation",
    "dedup",
    "dedup_citations",
    "deduplicate",
    "deduplicate_citations",
    "extract_citations",
    "format_citation",
    "format_citations",
    "get_default_registry",
    "handle_missing_citation",
    "is_valid_citation",
    "manage_citations",
    "missing_citation_result",
    "normalize_citation",
    "normalize_citations",
    "provenance",
    "provenance_of",
    "resolve",
    "resolve_citation",
    "resolve_citations",
    "resolve_source",
    "set_default_registry",
    "source_trace",
    "validate_citation",
    "validate_citations",
    "verify_citation",
]
