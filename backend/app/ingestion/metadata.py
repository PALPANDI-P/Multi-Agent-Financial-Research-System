"""Deterministic metadata detection for financial documents.

Every function in this module is **pure**: it takes text (and sometimes a
file name) and returns a value.  There is no I/O, no global state, no
clock and no randomness, therefore the same input always produces the same
output and the whole module can be unit tested without a database.

The detection heuristics are intentionally conservative.  When a value
cannot be established with reasonable confidence the function returns
``None`` instead of guessing: a wrong company name or a wrong fiscal
period is worse than a missing one, because both end up in the vector
store metadata and are therefore used for retrieval.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.core.enums import DocumentType
from app.ingestion.contracts import DocumentExtractionMetadata

__all__ = [
    "build_document_metadata",
    "detect_company_name",
    "detect_document_title",
    "detect_fiscal_period",
    "infer_document_type",
]

#: Maximum number of characters of a document that are scanned for the
#: loose "reports ... results" earnings pattern.  The wording is common in
#: running prose, therefore it is only trusted in the header region.
_HEADER_WINDOW = 4000

#: Maximum number of lines that are inspected in front of the registrant
#: boilerplate before the search gives up.
_MAX_LOOKBACK_LINES = 8

#: Maximum number of lines that are inspected for a company name when the
#: registrant boilerplate is missing.
_MAX_HEADER_LINES = 5


# ---------------------------------------------------------------------------
# fiscal period
# ---------------------------------------------------------------------------

_MONTH_PATTERN = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
)

_QUARTERLY_RE = re.compile(
    rf"(?:for\s+the\s+)?(?:(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+)?"
    rf"quarter(?:ly)?(?:\s+period)?\s+ended\s+"
    rf"({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)

_FISCAL_YEAR_RE = re.compile(
    rf"fiscal\s+year\s+ended\s+"
    rf"({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)

_YEAR_ENDED_RE = re.compile(
    rf"year\s+ended\s+"
    rf"({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)

_PERIOD_ENDED_RE = re.compile(
    rf"(?:fiscal\s+|quarterly\s+)?period\s+ended\s+"
    rf"({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)

_FISCAL_YEAR_NUMBER_RE = re.compile(r"fiscal\s+year\s+(20\d{2})", re.IGNORECASE)

_FY_LABEL_RE = re.compile(r"\bFY\s*[-/]?\s*(20\d{2})\b", re.IGNORECASE)

_MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _fiscal_label(year: int) -> str:
    """Return the ``FY<year>`` label for a period that ended in *year*."""
    return f"FY{year}"


def _quarter_label(month: int, year: int) -> str:
    """Return the ``Q<n> <year>`` label of a quarter that ended in *month*."""
    quarter = (month - 1) // 3 + 1
    return f"Q{quarter} {year}"


def _collapse(text: str) -> str:
    """Return *text* with collapsed whitespace."""
    return " ".join(text.split())


def detect_fiscal_period(text: str) -> tuple[str | None, str | None]:
    """Return the fiscal period of *text* and the evidence for it.

    The label is normalised to ``FY<year>`` for a full year and to
    ``Q<n> <year>`` for a quarter.  The fiscal year of a period is derived
    from the year the period *ended* in (a period that ends on
    ``January 31, 2026`` is ``FY2026``, a period that ends on
    ``December 31, 2025`` is ``FY2025``).  The quarter is derived from the
    month the period ended in.

    Returns
    -------
    tuple[str | None, str | None]
        ``(label, evidence)``.  Both are ``None`` when no period could be
        detected; ``evidence`` is the verbatim source text the label was
        derived from.
    """
    if not text:
        return (None, None)

    match = _QUARTERLY_RE.search(text)
    if match is not None:
        month = _MONTHS[match.group(1).casefold()]
        year = int(match.group(3))
        return (_quarter_label(month, year), _collapse(match.group(0)))

    for pattern in (_FISCAL_YEAR_RE, _YEAR_ENDED_RE, _PERIOD_ENDED_RE):
        match = pattern.search(text)
        if match is not None:
            year = int(match.group(3))
            return (_fiscal_label(year), _collapse(match.group(0)))

    match = _FISCAL_YEAR_NUMBER_RE.search(text)
    if match is not None:
        year = int(match.group(1))
        return (_fiscal_label(year), _collapse(match.group(0)))

    match = _FY_LABEL_RE.search(text)
    if match is not None:
        year = int(match.group(1))
        return (_fiscal_label(year), _collapse(match.group(0)))

    return (None, None)


# ---------------------------------------------------------------------------
# document type
# ---------------------------------------------------------------------------

_FORM_10K_RE = re.compile(r"FORM\s+10-K", re.IGNORECASE)
_FORM_10Q_RE = re.compile(r"FORM\s+10-Q", re.IGNORECASE)

_EARNINGS_STRICT_RE = re.compile(r"earnings\s+release", re.IGNORECASE)
_EARNINGS_REPORTS_RE = re.compile(r"reports?\s+.{0,60}?\bresults\b", re.IGNORECASE | re.DOTALL)
_EARNINGS_ANNOUNCES_RE = re.compile(
    r"announces?\s+.{0,60}?\bresults\b", re.IGNORECASE | re.DOTALL
)
_EARNINGS_QUARTER_RE = re.compile(
    r"quarter(?:ly)?\s+(?:financial\s+)?results", re.IGNORECASE
)

_ANNUAL_LETTER_RE = re.compile(
    r"letter\s+to\s+(?:our\s+|the\s+)?shareholders", re.IGNORECASE
)
_SHAREHOLDER_LETTER_RE = re.compile(r"shareholder(?:'s|s)?\s+letter", re.IGNORECASE)
_STOCKHOLDER_LETTER_RE = re.compile(r"letter\s+to\s+stockholders", re.IGNORECASE)

_CONSOLIDATED_STATEMENTS_RE = re.compile(
    r"consolidated\s+financial\s+statements", re.IGNORECASE
)
_ANNUAL_REPORT_RE = re.compile(r"annual\s+report", re.IGNORECASE)
_TEN_K_MARKER_RE = re.compile(r"10-K", re.IGNORECASE)


def _infer_document_type_with_evidence(
    filename: str,
    text: str,
) -> tuple[str | None, str | None]:
    """Return the document type and the evidence it was derived from."""
    haystack = text or ""
    header = haystack[:_HEADER_WINDOW]

    match = _FORM_10K_RE.search(haystack)
    if match is not None:
        return (DocumentType.FORM_10K.value, _collapse(match.group(0)))

    match = _FORM_10Q_RE.search(haystack)
    if match is not None:
        return (DocumentType.FORM_10Q.value, _collapse(match.group(0)))

    match = _EARNINGS_STRICT_RE.search(haystack)
    if match is not None:
        return (DocumentType.EARNINGS_RELEASE.value, _collapse(match.group(0)))

    # The remaining earnings patterns are loose ("reports ... results") and
    # are therefore only trusted in the header region of the document.
    for pattern in (_EARNINGS_REPORTS_RE, _EARNINGS_ANNOUNCES_RE, _EARNINGS_QUARTER_RE):
        match = pattern.search(header)
        if match is not None:
            return (DocumentType.EARNINGS_RELEASE.value, _collapse(match.group(0)))

    for pattern in (_ANNUAL_LETTER_RE, _SHAREHOLDER_LETTER_RE, _STOCKHOLDER_LETTER_RE):
        match = pattern.search(haystack)
        if match is not None:
            return (DocumentType.ANNUAL_LETTER.value, _collapse(match.group(0)))

    match = _CONSOLIDATED_STATEMENTS_RE.search(haystack)
    if match is not None and _TEN_K_MARKER_RE.search(haystack) is None:
        return (DocumentType.FINANCIAL_STATEMENTS.value, _collapse(match.group(0)))

    match = _ANNUAL_REPORT_RE.search(haystack)
    if match is not None:
        return (DocumentType.ANNUAL_REPORT.value, _collapse(match.group(0)))

    return (None, None)


def infer_document_type(filename: str, text: str) -> str | None:
    """Return the :class:`~app.core.enums.DocumentType` value of a document.

    The decision order is fixed:

    ``form_10k`` -> ``form_10q`` -> ``earnings_release`` ->
    ``annual_letter`` -> ``financial_statements`` -> ``annual_report``.

    ``None`` is returned when the document does not match any of them.
    The file name is only used as a last resort and never overrules the
    content of the document.
    """
    document_type, _ = _infer_document_type_with_evidence(filename, text)
    return document_type


# ---------------------------------------------------------------------------
# company name
# ---------------------------------------------------------------------------

_REGISTRANT_MARKER = "exact name of registrant as specified in its charter"
_REGISTRANT_MARKER_RE = re.compile(
    r"exact\s+name\s+of\s+registrant\s+as\s+specified\s+in\s+its\s+charter",
    re.IGNORECASE,
)

_COMPANY_NAME_SHAPE_RE = re.compile(r"^[A-Z][\w&.\- ]{2,60}$")

_COMPANY_NAME_KEYWORDS: tuple[str, ...] = (
    "inc",
    "corp",
    "corporation",
    "company",
    "co",
    "ltd",
    "plc",
    "llc",
    "lp",
    "ag",
    "nv",
    "sa",
    "holdings",
    "holding",
    "chase",
    "group",
)

#: Suffixes a company name is allowed to end with.  A name that ends with
#: a full stop but with none of them is a sentence, not a company name.
_COMPANY_NAME_SUFFIXES: tuple[str, ...] = (
    "inc.",
    "inc",
    "corp.",
    "corp",
    "corporation",
    "co.",
    "co",
    "ltd.",
    "ltd",
    "plc",
    "llc",
    "l.p.",
    "lp",
    "n.v.",
    "nv",
    "s.a.",
    "sa",
    "ag",
    "gmbh",
    "a.g.",
    "oy",
    "ab",
)

#: Maximum number of words a company name may have.
_MAX_COMPANY_NAME_WORDS = 8

#: First words of a line that mark a section heading instead of a name.
_SECTION_WORDS: frozenset[str] = frozenset(
    {
        "item",
        "part",
        "section",
        "chapter",
        "table",
        "note",
        "notes",
        "exhibit",
        "figure",
        "appendix",
        "schedule",
        "introduction",
        "overview",
        "summary",
    }
)

_BOILERPLATE_MARKERS: tuple[str, ...] = (
    "united states securities",
    "securities and exchange commission",
    "washington, d.c.",
    "washington dc",
    "form 10-k",
    "form 10-q",
    "commission file number",
    "exact name of registrant",
    "state or other jurisdiction",
    "irs employer",
    "incorporated in",
    "annual report",
    "table of contents",
    "commission file",
    "sec.gov",
    "check the appropriate box",
)

_BOILERPLATE_PAREN_RE = re.compile(
    r"\s*\([^()]*?"
    r"(?:exact name of registrant|state or other jurisdiction|irs employer|incorporated in)"
    r"[^()]*?\)\s*",
    re.IGNORECASE,
)


def _strip_registrant_boilerplate(line: str) -> str:
    """Remove the trailing registrant boilerplate from *line*."""
    cleaned = _BOILERPLATE_PAREN_RE.sub(" ", line)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ,;|-\u2014")


def _looks_like_company_name(line: str) -> bool:
    """Return ``True`` when *line* has the shape of a company name.

    A company name is a short label, never a sentence: it has at most
    eight words and it does not end with a full stop unless it ends with a
    known company suffix (``Inc.``, ``Ltd.``, ...).
    """
    if not line or len(line) > 120:
        return False
    if len(line.split()) > _MAX_COMPANY_NAME_WORDS:
        return False
    lowered = line.casefold()
    for keyword in _COMPANY_NAME_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return True

    # The generic shape is a weak signal: a line that reads like a sentence
    # or like the heading of a section is not a company name.
    if ". " in line:
        return False
    words = lowered.split()
    if words and words[0] in _SECTION_WORDS:
        return False
    if line.endswith(".") and not lowered.endswith(_COMPANY_NAME_SUFFIXES):
        return False
    return bool(_COMPANY_NAME_SHAPE_RE.match(line))


def _is_boilerplate(line: str) -> bool:
    """Return ``True`` when *line* is SEC/registrant boilerplate."""
    lowered = line.casefold()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _clean_company_candidate(line: str) -> str | None:
    """Return the cleaned company name of *line* or ``None``."""
    cleaned = _strip_registrant_boilerplate(line)
    if not cleaned or len(cleaned) > 120:
        return None
    if len(cleaned.split()) > 14:
        return None
    if _is_boilerplate(cleaned):
        return None
    return cleaned


def _detect_company_name_with_evidence(text: str) -> tuple[str | None, str | None]:
    """Return the company name of *text* and the evidence for it."""
    if not text:
        return (None, None)

    marker_match = _REGISTRANT_MARKER_RE.search(text)
    if marker_match is not None:
        preceding = text[: marker_match.start()]
        lines = preceding.splitlines()
        inspected = 0
        for raw_line in reversed(lines):
            line = raw_line.strip()
            if not line:
                continue
            inspected += 1
            if inspected > _MAX_LOOKBACK_LINES:
                break
            if _is_boilerplate(line):
                continue
            candidate = _clean_company_candidate(line)
            if candidate is not None and _looks_like_company_name(candidate):
                return (candidate, raw_line.strip())

    for raw_line in text.splitlines()[:_MAX_HEADER_LINES]:
        line = raw_line.strip()
        if not line or _is_boilerplate(line):
            continue
        candidate = _clean_company_candidate(line)
        if candidate is not None and _looks_like_company_name(candidate):
            return (candidate, line)

    return (None, None)


def detect_company_name(text: str) -> str | None:
    """Return the company name that produced *text*.

    The name is looked up in two places:

    1. directly above the ``Exact name of registrant as specified in its
       charter`` boilerplate of a Form 10-K (the closest preceding
       non-empty line that is not itself boilerplate), and
    2. in the first lines of the document, where a line has the shape of a
       company name.

    ``None`` is returned when no plausible name is found.
    """
    company_name, _ = _detect_company_name_with_evidence(text)
    return company_name


# ---------------------------------------------------------------------------
# document title
# ---------------------------------------------------------------------------

_TITLE_LINE_RE = re.compile(r"annual\s+report|form\s+10-k|form\s+10-q", re.IGNORECASE)


def _smart_title_token(token: str) -> str:
    """Return *token* with a sensible capitalisation."""
    if not token:
        return token
    if any(character.isdigit() for character in token):
        for index, character in enumerate(token):
            if character.isalpha():
                return token[:index] + character.upper() + token[index + 1 :]
        return token
    if token.isupper():
        return token.capitalize()
    return token[0].upper() + token[1:]


def _title_from_filename(filename: str) -> str | None:
    """Return a human readable title derived from *filename*."""
    if not filename:
        return None
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    tokens = [token for token in re.split(r"[\s_\-.]+", stem) if token]
    if not tokens:
        return None
    title = " ".join(_smart_title_token(token) for token in tokens)
    return title[:200] or None


def detect_document_title(text: str, filename: str) -> str | None:
    """Return the title of a document.

    An explicit title line near the top of the document (``Annual Report``,
    ``Form 10-K``, ...) always wins.  Otherwise the file name is used as a
    fallback and title cased.
    """
    for raw_line in (text or "").splitlines()[:_MAX_HEADER_LINES * 6]:
        line = raw_line.strip()
        if not line or len(line) > 200:
            continue
        if _TITLE_LINE_RE.search(line):
            return _collapse(line)
    return _title_from_filename(filename)


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def build_document_metadata(
    text_by_page: Sequence[str],
    filename: str | None = None,
) -> DocumentExtractionMetadata:
    """Build the metadata of a document from the text of its pages.

    Parameters
    ----------
    text_by_page:
        The extracted text of every page, in page order.
    filename:
        The original file name of the document (may be ``None``).

    Returns
    -------
    DocumentExtractionMetadata
        The metadata of the document.  The raw evidence of every detection
        is stored in ``extra`` under ``fiscal_period_evidence``,
        ``document_type_evidence`` and ``company_name_evidence`` so that a
        human can review why a value was chosen.
    """
    pages = [page or "" for page in text_by_page]
    full_text = "\n".join(pages)
    name = filename or ""

    fiscal_period, fiscal_evidence = detect_fiscal_period(full_text)
    document_type, document_type_evidence = _infer_document_type_with_evidence(name, full_text)
    company_name, company_name_evidence = _detect_company_name_with_evidence(full_text)
    document_title = detect_document_title(full_text, name)

    return DocumentExtractionMetadata(
        company_name=company_name,
        document_title=document_title,
        document_type=document_type,
        fiscal_period=fiscal_period,
        page_count=len(pages),
        detected_language=None,
        extra={
            "fiscal_period_evidence": fiscal_evidence or "",
            "document_type_evidence": document_type_evidence or "",
            "company_name_evidence": company_name_evidence or "",
        },
    )