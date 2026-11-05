"""Document-aware chatbot endpoint.

This module provides a conversational AI endpoint that answers questions
based on the content of documents uploaded into a workspace.

Capabilities
------------
* **Document Q&A**: answers questions grounded in the indexed chunks of the
  workspace (revenue, profit, losses, forecasts, market rates, risks …).
* **Project Q&A**: answers questions about the application itself - how to
  upload files, supported formats, file size limits, workflow, etc.
* **History**: the caller may pass a conversation history so the bot can
  follow up naturally.
* **Citations**: every answer includes the source chunks that were used.
"""

from __future__ import annotations

import re
import time
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    CurrentUserDep,
    get_search_service,
    get_workspace_service,
    owner_scope,
)
from app.core.exceptions import NotFoundError
from app.services.search_service import SearchService
from app.services.workspace_service import WorkspaceService

__all__ = ["router"]

router = APIRouter(tags=["chatbot"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single turn in a conversation."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    """Body of a chat request."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(..., min_length=1, max_length=2000, description="The user question")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Previous turns of the conversation (oldest first)",
    )
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Restrict context to these documents (all workspace docs when omitted)",
    )
    top_k: int = Field(default=8, ge=1, le=30, description="Number of chunks to retrieve")


class SourceChunk(BaseModel):
    """A document chunk used to answer the question."""

    chunk_id: str
    document_id: str
    document_title: str | None = None
    company_name: str | None = None
    document_type: str | None = None
    fiscal_period: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_heading: str | None = None
    content: str
    score: float


class ChatResponse(BaseModel):
    """The chatbot answer with metadata."""

    message_id: str
    answer: str
    sources: list[SourceChunk]
    took_ms: float
    document_count: int
    source_count: int


# ---------------------------------------------------------------------------
# Project knowledge  (FAQ about the application itself)
# ---------------------------------------------------------------------------

_PROJECT_FAQ: list[tuple[list[str], str]] = [
    (
        ["upload", "file", "how to upload", "add document"],
        (
            "**How to upload a document**\n\n"
            "1. Open or create a workspace on the Dashboard.\n"
            "2. Inside the workspace click **Upload Document**.\n"
            "3. Select a PDF file from your computer (max 50 MB).\n"
            "4. Optionally fill in company name, document type and fiscal period metadata.\n"
            "5. Click **Upload** - the system validates, extracts, chunks and indexes the "
            "document automatically. Status transitions: *queued → validating → extracting "
            "→ chunking → embedding → indexing → completed*.\n\n"
            "Once status is **completed** you can search and ask questions about it."
        ),
    ),
    (
        ["format", "file type", "supported", "extension", "pdf"],
        (
            "**Supported file formats**\n\n"
            "Currently only **PDF** (`.pdf`) files are accepted.\n"
            "The system validates the PDF magic bytes, not just the file extension, "
            "so a renamed file is rejected.\n\n"
            "Support for Excel, Word and plain-text files may be added in future releases."
        ),
    ),
    (
        ["size", "limit", "maximum", "max", "large"],
        (
            "**File size limit**\n\n"
            "The maximum upload size is **50 MB** (52 428 800 bytes).\n"
            "Documents larger than this are rejected with HTTP 413.\n\n"
            "Very large PDFs (e.g. annual reports with many images) may take several "
            "minutes to process because every page is extracted and embedded."
        ),
    ),
    (
        ["workspace", "what is workspace", "workspaces"],
        (
            "**Workspaces**\n\n"
            "A workspace is a container for a research project.  You can create as many "
            "workspaces as you like - one per company, one per sector, one per theme.\n\n"
            "Documents uploaded into a workspace are only searchable within that workspace, "
            "so your Apple and JPMorgan research never mixes."
        ),
    ),
    (
        ["search", "semantic search", "how search"],
        (
            "**Semantic search**\n\n"
            "The search bar uses *vector similarity* (BGE-small embeddings, 384 dimensions) "
            "to find the most relevant passages in the workspace even if the exact words "
            "differ.  Results are ranked by cosine similarity.\n\n"
            "You can also filter by document, chunk type or fiscal period."
        ),
    ),
    (
        ["red flag", "risk", "concern"],
        (
            "**Red flag analysis**\n\n"
            "The Red Flag Agent scans a document for financial warning signals such as:\n"
            "• Declining margins or revenues\n"
            "• High debt-to-equity ratios\n"
            "• Auditor qualifications\n"
            "• Unusual related-party transactions\n"
            "• Going-concern disclosures\n\n"
            "Red flags are classified as **High / Medium / Low** severity."
        ),
    ),
    (
        ["forecast", "prediction", "future", "projection"],
        (
            "**Forecasting**\n\n"
            "The Forecasting Service can project future values from a time-series of "
            "observations using linear or exponential methods.\n"
            "The research chatbot also synthesises forward-looking statements found in "
            "the uploaded documents (management guidance, analyst commentary, etc.)."
        ),
    ),
    (
        ["export", "download", "csv", "json", "xlsx"],
        (
            "**Export**\n\n"
            "Financial metrics, calculations and forecasts can be exported as:\n"
            "• **CSV** - comma-separated values\n"
            "• **JSON** - machine-readable object array\n"
            "• **XLSX** - Excel spreadsheet\n\n"
            "Use the Export panel inside a workspace or POST to "
            "`/api/v1/workspaces/{id}/exports`."
        ),
    ),
    (
        ["api", "rest", "endpoint", "documentation", "openapi", "swagger"],
        (
            "**API documentation**\n\n"
            "Interactive docs are served at **`/api/docs`** (Swagger UI) and "
            "`/api/redoc` (ReDoc).\n\n"
            "All endpoints require a session cookie obtained via `POST /api/v1/auth/login`. "
            "The cookie is `HttpOnly; SameSite=Lax` and lasts 24 hours by default."
        ),
    ),
    (
        ["chatbot", "chat", "ask", "question"],
        (
            "**Document chatbot**\n\n"
            "The chatbot answers questions about the documents in a workspace.  "
            "It retrieves the most relevant passages (semantic search) and synthesises "
            "a detailed answer with cited sources.\n\n"
            "Example questions you can ask:\n"
            "• *What was the revenue in FY2024?*\n"
            "• *What are the main risk factors?*\n"
            "• *How did gross margin change year-over-year?*\n"
            "• *What does management say about future growth?*\n"
            "• *Are there any going-concern disclosures?*"
        ),
    ),
]


def _project_answer(question: str) -> str | None:
    """Return a canned answer for project-related questions, or None."""
    q_lower = question.lower()
    for keywords, answer in _PROJECT_FAQ:
        for kw in keywords:
            # Use word-boundary matching for short keywords to avoid false positives
            # e.g. "api" should not match inside "capital"
            if len(kw) <= 5:
                # Match whole word only
                if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                    return answer
            else:
                if kw in q_lower:
                    return answer
    return None


# ---------------------------------------------------------------------------
# Answer synthesis
# ---------------------------------------------------------------------------

_FINANCIAL_PATTERNS = {
    "revenue": re.compile(
        r"(?:revenue|net\s+sales|total\s+sales|turnover)[^\n]*?(\$[\d,\.]+\s*(?:billion|million|B|M|K)?|\d[\d,\.]+\s*(?:billion|million))",
        re.IGNORECASE,
    ),
    "profit": re.compile(
        r"(?:net\s+income|profit|earnings|EPS|operating\s+income)[^\n]*?(\$[\d,\.]+\s*(?:billion|million|B|M|K)?|-?\d[\d,\.]+)",
        re.IGNORECASE,
    ),
    "loss": re.compile(
        r"(?:net\s+loss|operating\s+loss|deficit)[^\n]*?(\$[\d,\.]+\s*(?:billion|million|B|M|K)?|\d[\d,\.]+)",
        re.IGNORECASE,
    ),
    "margin": re.compile(
        r"(?:gross\s+margin|operating\s+margin|net\s+margin|EBITDA\s+margin)[^\n]*?(\d+\.?\d*\s*%)",
        re.IGNORECASE,
    ),
}


def _extract_numbers(text: str, pattern_key: str) -> list[str]:
    """Extract formatted numbers for a financial concept from text."""
    pat = _FINANCIAL_PATTERNS.get(pattern_key)
    if not pat:
        return []
    matches = pat.findall(text)
    return [m.strip() for m in matches[:3] if m.strip()]


def _classify_question(question: str) -> str:
    """Return one of: revenue | profit | loss | forecast | risk | margin | general."""
    q = question.lower()
    if any(w in q for w in ("revenue", "sales", "turnover", "income from operations")):
        return "revenue"
    if any(w in q for w in ("net income", "profit", "earnings", "eps")):
        return "profit"
    if any(w in q for w in ("loss", "deficit", "impairment")):
        return "loss"
    if any(w in q for w in ("forecast", "predict", "future", "guidance", "outlook", "projection")):
        return "forecast"
    if any(w in q for w in ("risk", "red flag", "concern", "warn", "going concern")):
        return "risk"
    if any(w in q for w in ("margin", "gross margin", "operating margin", "ebitda")):
        return "margin"
    if any(w in q for w in ("market", "share price", "stock", "market rate", "valuation")):
        return "market"
    return "general"


def _synthesise_answer(question: str, chunks: list[Any]) -> str:
    """Build a detailed answer from retrieved chunks."""
    if not chunks:
        return (
            "I could not find relevant information in the uploaded documents to answer "
            "your question.  Please make sure the workspace contains processed documents "
            "that cover this topic, or rephrase your question."
        )

    q_type = _classify_question(question)
    combined_text = "\n\n".join(c.content for c in chunks)

    # --- Build a detailed structured answer ---
    lines: list[str] = []
    lines.append("**Based on the uploaded documents:**\n")

    # Pull out key numbers where relevant
    if q_type == "revenue":
        numbers = _extract_numbers(combined_text, "revenue")
        if numbers:
            lines.append(f"**Revenue figures found:** {', '.join(numbers)}\n")

    elif q_type == "profit":
        numbers = _extract_numbers(combined_text, "profit")
        if numbers:
            lines.append(f"**Profit/income figures found:** {', '.join(numbers)}\n")

    elif q_type == "loss":
        numbers = _extract_numbers(combined_text, "loss")
        if numbers:
            lines.append(f"**Loss figures found:** {', '.join(numbers)}\n")

    elif q_type == "margin":
        numbers = _extract_numbers(combined_text, "margin")
        if numbers:
            lines.append(f"**Margin figures found:** {', '.join(numbers)}\n")

    # Pull the most relevant sentences from each chunk
    lines.append("**Key findings from the documents:**\n")
    seen_content: set[str] = set()
    for i, chunk in enumerate(chunks[:6], 1):
        content = chunk.content.strip()
        # Avoid exact duplicates
        content_key = content[:100]
        if content_key in seen_content:
            continue
        seen_content.add(content_key)

        heading = chunk.section_heading or ""
        doc_label = chunk.document_title or chunk.company_name or f"Document {i}"
        page_info = ""
        if chunk.page_start:
            page_info = f" (p. {chunk.page_start})"

        lines.append(f"**[{doc_label}{page_info}]** {heading}")

        # Trim very long passages
        if len(content) > 600:
            content = content[:600].rsplit(" ", 1)[0] + " …"
        lines.append(content)
        lines.append("")

    # --- Type-specific synthesis ---
    if q_type == "forecast":
        lines.append(
            "**Forward-looking statements synthesis:**\n"
            "The passages above contain management guidance, outlook statements or "
            "analyst projections.  For a quantitative forecast use the Forecast panel "
            "in the workspace to run a linear or exponential model on historical metrics."
        )
    elif q_type == "risk":
        lines.append(
            "**Risk / red flag summary:**\n"
            "The passages highlight the concerns described above.  Run the **Red Flag "
            "Analysis** in the workspace for a full structured assessment with severity "
            "ratings (High / Medium / Low)."
        )
    elif q_type == "market":
        lines.append(
            "**Note on market data:**\n"
            "The chatbot answers from the uploaded documents only.  For live market "
            "rates, share prices and valuations consult a real-time data provider."
        )

    lines.append(
        f"\n*Answer synthesised from {len(chunks)} document chunk(s).  "
        f"See the sources below for the original passages.*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/chat",
    response_model=ChatResponse,
    summary="Ask a question about the documents in a workspace",
)
def chat(
    workspace_id: UUID,
    payload: ChatRequest,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    search_service: Annotated[SearchService, Depends(get_search_service)],
    current_user: CurrentUserDep,
) -> ChatResponse:
    """Answer a natural-language question using the workspace documents.

    The endpoint:

    1. Checks for a **project-level** answer (questions about the app itself).
    2. Performs a **semantic search** over the workspace chunks.
    3. **Synthesises** a detailed answer from the top-k chunks.
    4. Returns the answer with cited source chunks.

    The ``history`` field lets the client send previous turns so the model
    can follow up naturally; the last user turn is prepended to the query.
    """
    t0 = time.perf_counter()

    # Verify the workspace exists and the user may access it.
    scope = owner_scope(current_user)
    try:
        workspace_service.get_workspace(workspace_id, owner_id=scope)
    except NotFoundError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workspace not found") from None

    question = payload.question.strip()

    # 1. Project-level FAQ
    project_ans = _project_answer(question)
    if project_ans:
        took_ms = (time.perf_counter() - t0) * 1000
        return ChatResponse(
            message_id=str(uuid4()),
            answer=project_ans,
            sources=[],
            took_ms=round(took_ms, 2),
            document_count=0,
            source_count=0,
        )

    # Enrich query with recent history context
    if payload.history:
        # Append last assistant answer as context hint
        last_assistant = next(
            (m.content for m in reversed(payload.history) if m.role == "assistant"), None
        )
        if last_assistant:
            question = f"{question} [Context: {last_assistant[:300]}]"

    # 2. Semantic search
    results = search_service.search(
        workspace_id=workspace_id,
        query=question,
        limit=payload.top_k,
        document_ids=payload.document_ids,
        owner_id=scope,
    )

    # 3. Synthesise answer
    answer = _synthesise_answer(payload.question, results.results)

    # 4. Build source citations
    sources = [
        SourceChunk(
            chunk_id=str(r.chunk_id),
            document_id=str(r.document_id),
            document_title=r.document_title,
            company_name=r.company_name,
            document_type=r.document_type,
            fiscal_period=r.fiscal_period,
            page_start=r.page_start,
            page_end=r.page_end,
            section_heading=r.section_heading,
            content=r.content[:800],
            score=round(r.score, 4),
        )
        for r in results.results
    ]

    took_ms = (time.perf_counter() - t0) * 1000
    return ChatResponse(
        message_id=str(uuid4()),
        answer=answer,
        sources=sources,
        took_ms=round(took_ms, 2),
        document_count=results.total,
        source_count=len(sources),
    )
