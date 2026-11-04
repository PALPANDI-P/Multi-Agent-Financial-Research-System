"""Project knowledge base for the Multi-Agent Financial Research System.

The single public entry point :func:`project_answer` turns a free-form
question into a detailed answer when the question is about this project and
returns ``None`` otherwise.  Matching is keyword based and case insensitive.
"""

from __future__ import annotations

__all__ = ["project_answer"]

_FILE_FORMATS = (
    "files and formats",
    "file formats",
    "supported file",
    "allowed file",
    "file type",
    "extension",
    "mime",
    "pdf",
)

_FILE_SIZE = (
    "size",
    "max upload",
    "file size",
    "limit",
    "too large",
    "413",
    "max_upload",
    "max size",
)

_UPLOAD_FLOW = (
    "upload",
    "ingest",
    "register",
    "processing job",
    "multipart",
)

_PROCESSING_STAGES = (
    "processing",
    "stage",
    "pipeline",
    "status",
    "queued",
    "extracting",
    "chunking",
    "embedding",
    "indexing",
)

_WORKSPACES = (
    "workspace",
)

_SEARCH = (
    "search",
    "semantic",
    "query",
    "pgvector",
    "retrieval",
    "rag",
    "evidence",
)

_AUTH = (
    "auth",
    "login",
    "register",
    "session",
    "password",
    "demo",
    "cookie",
    "user",
)

_FORECASTING = (
    "forecast",
    "scenario",
    "naive",
    "linear trend",
    "trend",
    "time series",
)

_EXPORTS = (
    "export",
    "csv",
    "xlsx",
    "json",
    "report",
    "download",
)

_AGENTS = (
    "agent",
    "orchestrat",
    "red flag",
    "comparison",
    "research",
    "report",
)

_TROUBLESHOOTING = (
    "troubleshoot",
    "error",
    "issue",
    "problem",
    "fail",
    "debug",
    "degraded",
    "hang",
    "403",
    "blocked",
)

_GENERAL = (
    "project",
    "system",
    "overview",
    "about",
    "run",
    "start",
    "setup",
    "install",
    "how to",
    "backend",
    "frontend",
    "database",
    "migration",
    "test",
    "ruff",
    "help",
)

_ANSWERS: list[tuple[tuple[str, ...], str]] = [
    (
        _FILE_FORMATS,
        "File formats\n"
        "-----------\n"
        "Only PDF documents are supported. The allow list is `.pdf` / "
        "`application/pdf` (see `allowed_document_extensions` and "
        "`allowed_mime_types` in `app/core/config.py`).\n"
        "- The content of the file is authoritative: the `%PDF-` magic bytes "
        "decide whether the payload is a PDF at all; the client MIME type only "
        "corroborates it and a mismatch is reported as an issue.\n"
        "- The file name only contributes the extension, which is checked "
        "against the allow list; it is never used to decide that a file is a PDF.\n"
        "- A PDF is rejected when it cannot be opened, is encrypted, has no "
        "pages, or exceeds `max_pdf_pages` (default 2000).\n"
        "- DOCX, XLSX and HTML are not implemented; the `DocumentExtractor` "
        "protocol is the seam they would be plugged into.\n",
    ),
    (
        _FILE_SIZE,
        "File size limits\n"
        "----------------\n"
        "The maximum upload size is configured by the `MAX_UPLOAD_SIZE_BYTES` "
        "setting/environment variable (default 52428800 bytes (~50MB / about 50 MB), in "
        "`app/core/config.py`).\n"
        "- The request body is read in bounded chunks; a payload that is too "
        "large is rejected with HTTP 413 before it is fully buffered.\n"
        "- The validator also enforces `max_pdf_pages` (default 2000) on the "
        "number of pages.\n"
        "- An empty file is rejected with the `file_empty` issue.\n",
    ),
    (
        _UPLOAD_FLOW,
        "Upload flow\n"
        "-----------\n"
        "Endpoint: `POST /api/v1/workspaces/{workspace_id}/documents` "
        "(`multipart/form-data`).\n"
        "1. The file is streamed to the storage backend and written under "
        "`data/storage/YYYY/MM/<uuid>.pdf`.\n"
        "2. The content is validated (PDF magic bytes, openability, page "
        "count, size); every applicable rejection reason is collected and "
        "returned at once.\n"
        "3. A document row and its processing job are written in one "
        "transaction and committed before any processing starts.\n"
        "4. The document is queued for the ingestion pipeline.\n"
        "5. Processing runs inline when `PROCESSING_INLINE=true`, otherwise "
        "on the in-process background worker thread (`frs-document-worker`).\n"
        "6. A failed document can be retried with "
        "`POST /api/v1/documents/{document_id}/retry`.\n",
    ),
    (
        _PROCESSING_STAGES,
        "Processing stages\n"
        "-----------------\n"
        "The pipeline moves through the explicit states\n"
        "queued -> validating -> extracting -> chunking -> embedding -> "
        "indexing -> completed\n"
        "and may end in `failed`.\n"
        "Supplementary sub-stages recorded in `processing_stage` include "
        "`pdf_text`, `pdf_tables` and `ocr`.\n"
        "- validating: file and PDF checks.\n"
        "- extracting: PyMuPDF text + headings, pdfplumber tables, OCR for "
        "scanned pages (OCR is unavailable in this environment).\n"
        "- chunking: section/table aware chunks, one chunk per table.\n"
        "- embedding: fastembed `BAAI/bge-small-en-v1.5` (384 dimensions).\n"
        "- indexing: pgvector upsert with HNSW index.\n"
        "- completed/failed: terminal states; failures carry a stable error "
        "code and message.\n",
    ),
    (
        _WORKSPACES,
        "Workspaces\n"
        "----------\n"
        "Workspaces group documents and scope search.\n"
        "- CRUD: create, read, partial update, paginated list (filter by "
        "name), delete.\n"
        "- Deleting a workspace removes its documents, chunks and jobs.\n"
        "- Workspace name max length is 255 characters.\n"
        "- Search never leaves the workspace of its request path; workspace "
        "isolation is enforced in SQL.\n"
        "- `owner_id` is reserved and always NULL in Milestone 1 (no auth "
        "multi-user isolation).\n",
    ),
    (
        _SEARCH,
        "Search\n"
        "------\n"
        "Semantic search over the chunks of one workspace.\n"
        "- Endpoint: `POST /api/v1/workspaces/{workspace_id}/search`.\n"
        "- The query (max 1000 characters) is embedded locally and matched "
        "against pgvector with cosine similarity and an HNSW index.\n"
        "- Every hit carries document, company, document type, fiscal period, "
        "page range, section heading and chunk type.\n"
        "- Workspace isolation is enforced in SQL; document ids from another "
        "workspace are dropped.\n"
        "- `retrieval_top_k` (default 10) and `retrieval_max_top_k` "
        "(default 100) bound the result size.\n",
    ),
    (
        _AUTH,
        "Authentication\n"
        "--------------\n"
        "Auth is implemented in `app/services/auth_service.py`.\n"
        "- Registration, login, session resolution, logout and "
        "revoke-all-sessions are supported.\n"
        "- Passwords are hashed; raw session tokens are never persisted, "
        "only their SHA-256 hash.\n"
        "- Failed logins do not reveal whether an account exists.\n"
        "- Sessions live in an httpOnly cookie named `frs_session` with a "
        "TTL of 24 hours; password min length is 8.\n"
        "- Demo scenarios are enabled by default; demo password is "
        "`DemoAnalyst2024!`.\n"
        "- Settings: `AUTH_REQUIRED`, `AUTH_REGISTRATION_ENABLED`, "
        "`AUTH_DEMO_SCENARIOS_ENABLED`.\n",
    ),
    (
        _FORECASTING,
        "Forecasting\n"
        "-----------\n"
        "Implemented in `app/services/forecasting_service.py`.\n"
        "- Methods: `naive`, `mean`, `linear`.\n"
        "- Validates observations and reports issues before computing.\n"
        "- Returns historical/forecast periods and values, assumptions, "
        "limitations, evaluation metrics and confidence intervals.\n"
        "- Scenario analysis applies adjustments to a base forecast.\n",
    ),
    (
        _EXPORTS,
        "Exports\n"
        "-------\n"
        "Supported export formats: CSV, JSON, XLSX (openpyxl) and PDF "
        "(reportlab); XLSX/PDF are produced only when their optional "
        "dependencies are installed.\n"
        "- Entry point: `ExportService.export(...)` / module functions "
        "`export_csv`, `export_json`, `export_xlsx`, `export_pdf`.\n"
        "- Spreadsheet cells are sanitized against formula injection.\n"
        "- Filenames are sanitized via `safe_filename`.\n",
    ),
    (
        _AGENTS,
        "Agents\n"
        "------\n"
        "The agents live under `app/agents/`.\n"
        "- `DocumentAgent` owns one ingestion attempt end to end (load, job, "
        "pipeline, close).\n"
        "- `InlineJobRunner` and `BackgroundThreadJobRunner` drive the queue.\n"
        "- Extraction, Red Flag, Comparison, Research and Report agents are "
        "future agents (not implemented in Milestone 1); only the DocumentAgent "
        "and the job runner are implemented.\n"
        "- `app/orchestration` provides orchestration helpers.\n",
    ),
    (
        _TROUBLESHOOTING,
        "Troubleshooting\n"
        "---------------\n"
        "Common issues:\n"
        "- SEC answers 403: add a `User-Agent` header with a real contact "
        "address to the seed manifest entry.\n"
        "- `pg_ctl start` blocks on Windows: use `scripts/db.ps1 -Action start`.\n"
        "- `could not find extension \"vector\"`: install pgvector or run "
        "`scripts/db.ps1 -Action reset`.\n"
        "- Upload hangs or stays queued: check `PROCESSING_INLINE`; restart "
        "the API so `run_pending()` reprocesses queued documents.\n"
        "- Health endpoint degraded: inspect the dependency named "
        "`unavailable`.\n"
        "- Search returns nothing: confirm the document reached `completed` "
        "and that you search the same workspace.\n"
        "- pytest prints no summary: drop the extra `-q` flag.\n",
    ),
    (
        _GENERAL,
        "Project overview\n"
        "----------------\n"
        "Multi-Agent Financial Research System: upload financial PDFs into "
        "workspaces, extract/chunk/embed/index them, then run source-cited "
        "semantic search. Backend FastAPI on port 8000, frontend React/Vite "
        "on port 5173, PostgreSQL 16 + pgvector.\n"
        "How to run:\n"
        "- Backend: `cd backend && python -m uvicorn app.main:app --reload "
        "--port 8000`.\n"
        "- Frontend: `cd frontend && npm install && npm run dev`.\n"
        "- Database: `powershell -ExecutionPolicy Bypass -File scripts/db.ps1 "
        "-Action start`.\n"
        "- Migrations: `cd backend && python -m alembic upgrade head`.\n"
        "- Seed corpus: `cd backend && python -m scripts.seed_documents "
        "--workspace \"Seed Documents\"`.\n"
        "- Tests: `cd backend && python -m pytest tests`.\n"
        "- Lint: `cd backend && python -m ruff check app tests`.\n",
    ),
]


def project_answer(question: str) -> str | None:
    """Return a detailed answer for a project-related *question*.

    Returns ``None`` when the question does not look project related.
    """
    if not isinstance(question, str):
        return None
    query = question.strip().lower()
    if not query:
        return None

    matched: list[str] = []
    for keywords, answer in _ANSWERS:
        if any(keyword in query for keyword in keywords):
            matched.append(answer)

    if not matched:
        return None

    unique: list[str] = []
    for answer in matched:
        if answer not in unique:
            unique.append(answer)

    return "\n".join(unique)
