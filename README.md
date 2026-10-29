# Multi-Agent Financial Research System

A research platform for financial documents: upload annual reports and
audited financial statements, let the system extract, chunk and embed them,
and then ask semantic questions that come back with a **citation** to the
page they were found on.

**Milestone 1** delivers the *retrieval and evidence foundation* only: the
workspaces, the document ingestion pipeline, the pgvector index and the
source-cited search.  The Extraction, Red Flag, Comparison, Research and
Report **agents are not implemented yet** - see
[Known limitations](#13-known-limitations).

---

## 1. Overview

The system stores a corpus of financial documents (PDF) and makes it
searchable by meaning rather than by keyword.  A document is uploaded into a
**workspace**, validated, registered with a processing job and then pushed
through an eight stage ingestion pipeline: validate, extract the text, extract
the tables, OCR the scanned pages, chunk, embed, index, complete.  Every stage
reports its progress, so the state of a document is always visible.  A search
turns a natural language question into a vector, runs it against pgvector
inside the scope of one workspace and returns the matching chunks **with
their document, page range, section heading and chunk type** - the evidence
that a later agent will reason over.

Milestone 1 in three sentences: the ingestion pipeline, the pgvector index
and the source-cited search are implemented, tested end to end and verified
against a corpus of four real seed documents; the API is complete for the
scopes that exist; and the agents that consume the retrieved evidence are
**not** part of this milestone.

---

## 2. Architecture summary

```
  Browser --> React SPA (:5173) --HTTP/JSON--> FastAPI /api/v1 (:8000)
                                                   request-id . CORS . size limit
  +--------------------------------------------------------------------+
  | API layer (v1, schemas) | Services (ws, doc, search) | DocumentAgent|
  |          |               |                           | + JobRunner  |
  |          v               v                           v (inline|thrd)|
  | Repositories (ws, doc,   |              IngestionPipeline:          |
  |  chunk, job)             |              validate->extract->chunk->  |
  |          |               |              embed->index                |
  |          |               v                           v              |
  |          |   +-----------------------------------------------+    |
  |          |   | Embeddings: local ONNX bge-small, 384d          |    |
  |          |   | VectorStore: pgvector + HNSW                    |    |
  |          |   +--------------------------+--------------------+    |
  |          v                              v                        |
  |  +--------------------------------------------------------------+ |
  |  | PostgreSQL 16 + pgvector 0.8.6                              | |
  |  | workspaces . documents . document_chunks(vector) . jobs     | |
  |  +-----------------------------+--------------------------------+ |
  |                                | metadata only                    |
  |                                v                                  |
  |  +--------------------------------------------------------------+ |
  |  | StorageBackend (local FS): data/storage/YYYY/MM/<uuid>.pdf  | |
  |  +--------------------------------------------------------------+ |
  +--------------------------------------------------------------------+
```

The embedding model runs **locally in the API process**; the database is the
only external service; the documents live behind the `StorageBackend`
protocol.

More detail: [`docs/architecture.md`](docs/architecture.md).

---

## 3. Features implemented in Milestone 1

* **Workspaces** - create, read, update (partial), list (paginated, filter by
  name) and delete.  Deleting a workspace removes its documents, their chunks
  and their jobs.
* **Document upload with real validation** - the *content* of the file decides
  whether it is a PDF; the announced MIME type only corroborates it and a
  mismatch is reported.  Every reason for a rejection is collected and
  returned at once.  The body is read in bounded chunks and a payload that is
  too large is rejected with `413` before it is buffered.
* **PDF text and table extraction** - PyMuPDF reads the text layer and
  detects the headings (size rule and bold rule, merged with the bookmarks of
  the PDF); pdfplumber reads the tables on a best effort basis.
* **Section and table aware chunking** - a chunk never spans two pages and
  never mixes two sections; every table becomes exactly one chunk whose
  content carries the header, every row, the caption and the units.
* **Real local embeddings** - `fastembed` runs the ONNX model
  `BAAI/bge-small-en-v1.5` (384 dimensions) in the API process.  The vectors
  are validated (count, dimension, finiteness, non degeneracy) and the
  transient failures are retried.
* **pgvector indexing** - the chunks are written with an idempotent
  `INSERT ... ON CONFLICT (document_id, chunk_index) DO UPDATE` into a
  `vector(384)` column that carries an HNSW index (`m=16`,
  `ef_construction=64`, `vector_cosine_ops`).
* **Source cited search** - a semantic search over the chunks of one
  workspace.  Every hit carries the document, the company, the document type,
  the fiscal period, the page range, the section heading and the chunk type.
  The workspace isolation is enforced **in SQL**.
* **Processing status and retry** - eight explicit states
  (`queued → validating → extracting → chunking → embedding → indexing →
  completed`, plus `failed`), the failure is recorded with a stable error
  code and a message, and a failed document can be retried with
  `POST /api/v1/documents/{id}/retry`.
* **Seed corpus** - four real documents (Walmart FY2026 10-K, JPMorgan Chase
  FY2025 audited financial statements, Netflix FY2025 10-K, Apple FY2025
  10-K) are downloaded through a manifest that pins their SHA-256 checksum,
  ingested by the real pipeline and verified against the real database.
* **A complete HTTP API** under `/api/v1` with a standard error envelope, a
  request id header, pagination and a health endpoint that never leaks a
  secret.

---

## 4. Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Python | 3.12 | the backend |
| `uv` | any recent | the virtual environment and the dependency installation |
| Node.js | 20 or 24 | the frontend (`npm install`, `npm run dev`, `npm run build`) |
| PostgreSQL | 16 | the database |
| pgvector | 0.8 (0.8.6 verified) | the `vector` column type |
| Docker | any recent - **optional** | the container stack (see the note below) |

### Two ways to get PostgreSQL + pgvector

#### a) Docker Compose (authored, NOT executed on the development machine)

```bash
copy .env.example .env      # replace the password placeholder
docker compose up --build
```

> **The compose stack was never run on the development machine.**  Docker is
> not installed there (no `docker` on PATH, no Docker Desktop, no WSL), so
> `docker compose config` fails with
> `The term 'docker' is not recognized`.  Only the YAML syntax was validated.
> The **verified** path is the micromamba one below.

The stack provides three services: `postgres` (`pgvector/pgvector:pg16` with
a healthcheck), `backend` (built from `backend/Dockerfile`, runs the
migrations and then uvicorn) and `frontend` (built from `frontend/Dockerfile`,
serves the built SPA with nginx on port 8080 and proxies `/api/` to the
backend).  The document storage and the database data live in named volumes.

#### b) micromamba (the way that was actually used and verified)

micromamba installs PostgreSQL **and** pgvector into one environment, which
removes the "the extension is not available on this platform" problem:

```powershell
# 1. the environment (E:\mamba is the micromamba root prefix)
micromamba create -n frs -c conda-forge postgresql=16.15 pgvector=0.8.6

# 2. the cluster
$env:PATH = "E:\mamba\envs\frs\Library\bin;E:\mamba\envs\frs\Library\lib;$env:PATH"
initdb -D E:\pgdata\frs -U postgres -E UTF8 --locale=C -A md5
pg_ctl -D E:\pgdata\frs -l E:\pgdata\frs\server.log `
        -o "-p 55432 -c listen_addresses=127.0.0.1" -w start
```

The **port 55432** is used on purpose: it does not collide with a PostgreSQL
that is already installed on the machine.

The role and the two databases are then created with the superuser:

```sql
CREATE ROLE frs LOGIN PASSWORD '<password>';
CREATE DATABASE financial_research      OWNER frs;
CREATE DATABASE financial_research_test OWNER frs;
CREATE EXTENSION IF NOT EXISTS vector;   -- in both databases
```

> **pgvector is not a trusted extension in the Windows build.**  The
> `CREATE EXTENSION vector` therefore has to be run by the **owner role**
> (or by the superuser, which then hands the extension over with
> `ALTER EXTENSION vector OWNER TO frs;` and
> `UPDATE pg_extension SET extowner = 'frs'::regrole WHERE extname = 'vector';`).
> This is exactly what `scripts/db.ps1 -Action reset` does.

---

## 5. Environment setup

### The virtual environment

```powershell
cd "E:\Multi-Agent Financial Research System"
uv venv --python 3.12 backend/.venv
uv pip install -e "backend[dev]"
```

The `dev` extra adds `pytest`, `pytest-asyncio`, `httpx` and `ruff`.

### The configuration

```powershell
copy backend\.env.example backend\.env
copy .env.example .env          # only needed for the compose stack
```

`backend/.env` is read by the application.  It is **ignored by git**, so a
real password never reaches the repository.  The values you normally have to
change:

| Variable | What to change |
| --- | --- |
| `DATABASE_URL` | The password of the `frs` role. The template carries the placeholder `CHANGE_ME`. |
| `DATABASE_URL` (the test database) | The integration and API tests read `TEST_DATABASE_URL`; it defaults to `.../financial_research_test`. |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | Only together - the dimension must match the model, and a change needs a new migration. |
| `PROCESSING_INLINE` | `true` processes an upload in the request (the strategy of the scripts and the tests); `false` (the default of the setting) uses the background thread. |
| `CORS_ORIGINS` | The origins of the frontend. |
| `STORAGE_ROOT` | Where the uploaded PDFs are written. |

Every setting of `backend/app/core/config.py` is documented in
`backend/.env.example` with its default.

### The database lifecycle helper

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action status
powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action start
powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action stop
powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action reset
```

`reset` re-creates the cluster (`initdb`), the role, both databases and the
pgvector extension.  The script exists because of a real problem: **`pg_ctl
start` does not return on Windows** - it keeps waiting on the postmaster
process handle.  The script therefore launches `pg_ctl` as a *detached*
process and polls `pg_isready` until the server accepts connections.

---

## 6. Database startup

Two paths, one URI.

### The local (micromamba) path - verified

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action start
```

```
postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research
```

The test database uses the same host, port, role and password:

```
postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test
```

### The container path - authored, not executed

```bash
docker compose up -d postgres
```

The database is then reachable on `127.0.0.1:55432` with the credentials of
the repository root `.env`.

---

## 7. Migrations

Run from the `backend/` directory:

```powershell
python -m alembic upgrade head     # apply every migration
python -m alembic downgrade -1      # undo the last migration
python -m alembic current           # show the applied revision
python -m alembic check             # assert that the schema matches the models
```

The current revision of the development database is
`0002_expand_processing_status (head)`.

* The migration `0001_initial` creates the four tables, their indexes and
  **the `vector` extension** (`CREATE EXTENSION IF NOT EXISTS vector`).
  **pgvector must therefore be installed server side**, otherwise the
  migration fails with `could not find extension "vector"`.
* The migration `0002_expand_processing_status` replaces the coarse
  `processing` value of `documents.processing_status` with the eight explicit
  states and backfills the affected rows to `queued`.
* The schema is **never** created with `Base.metadata.create_all()`; the
  migrations are the only source of truth.  `alembic check` belongs into a CI
  pipeline.

---

## 8. Backend startup

```powershell
cd "E:\Multi-Agent Financial Research System\backend"
python -m uvicorn app.main:app --reload --port 8000
```

* Interactive documentation: <http://localhost:8000/docs>
* OpenAPI document: <http://localhost:8000/openapi.json>
* Health: <http://localhost:8000/api/v1/health>

The application validates its configuration at startup and **refuses to start**
when the configuration is self-contradictory or unsafe for the selected
environment (for example `APP_ENV=production` with the development
credentials, with `DEBUG=true` or with `CORS_ORIGINS=["*"]`).

---

## 9. Frontend startup

```powershell
cd "E:\Multi-Agent Financial Research System\frontend"
npm install
npm run dev
```

The dev server listens on <http://localhost:5173> (port 5173, `strictPort`).

Two ways to reach the backend:

| `VITE_API_BASE_URL` | Effect |
| --- | --- |
| `http://localhost:8000/api/v1` (the default, see `frontend/.env.example`) | The browser calls the backend directly; the backend must allow the origin in `CORS_ORIGINS` (it does by default). |
| `/api/v1` | The browser calls the **Vite dev proxy**, which forwards `/api` to `VITE_DEV_PROXY_TARGET` (default `http://localhost:8000`).  No CORS is needed during development. |

```powershell
copy frontend\.env.example frontend\.env
```

Other frontend commands: `npm run build` (the production bundle),
`npm run lint`, `npm run typecheck`, `npm run preview` (port 4173).

---

## 10. Seed document loading

```powershell
cd "E:\Multi-Agent Financial Research System\backend"

python -m scripts.seed_documents --workspace "Seed Documents"
python -m scripts.verify_index --workspace "Seed Documents"
```

The loader downloads the documents that are missing, registers them through
the **real** services and runs the **real** ingestion pipeline through the
inline job runner, therefore the summary it prints is the state of the
database.  Useful flags: `--only <COMPANY>` (repeatable), `--skip-download`
(only use the local files), `--force` (re-download and re-ingest),
`--no-process` (register only) and `--verify` (run the verification
afterwards).

### The corpus

| Company | Document | Fiscal period | Pages | Source |
| --- | --- | --- | --- | --- |
| Walmart Inc. | Form 10-K for the fiscal year ended January 31, 2026 | FY2026 | 100 | <https://www.sec.gov/Archives/edgar/data/104169/000010416926000091/wmtfy26annualreport-final.pdf> |
| JPMorgan Chase & Co. | Audited Consolidated Financial Statements 2025 | FY2025 | 167 | <https://www.jpmorganchase.com/content/dam/jpmc/jpmorgan-chase-and-co/investor-relations/documents/audited-financial-statements-2025.pdf> |
| Netflix, Inc. | Form 10-K for the fiscal year ended December 31, 2025 | FY2025 | 122 | <https://s22.q4cdn.com/959853165/files/doc_financials/2025/ar/99482238-46b2-4d0d-b292-40e6781bdf03.pdf> |
| Apple Inc. | Form 10-K for the fiscal year ended September 27, 2025 | FY2025 | 80 | <https://s2.q4cdn.com/470004039/files/doc_financials/2025/ar/_10-K-2025-As-Filed.pdf> |

The manifest `data/seed_manifest.json` **pins the SHA-256 checksum** of every
document.  A file whose checksum does not match is never ingested: the loader
removes it and reports the mismatch.  The manifest also pins the metadata and
the search probe that the verification uses.

> **The SEC requires a `User-Agent` header.**  A request to `sec.gov` without
> one is answered with `403`.  The manifest pins a `User-Agent` per document
> (`FinancialResearchSeedLoader/1.0 (contact@example.com)`) and the loader
> falls back to that value.  **Replace the contact address with a real one
> before you use the loader against the SEC.**

The loader is **idempotent**: a document that is already present in the
workspace is reported as *already present* and is not ingested a second time
(unless `--force` is given).  The same bytes in another workspace are **not**
a duplicate.

---

## 11. API documentation

* Interactive documentation (Swagger UI): <http://localhost:8000/docs>
* OpenAPI document: <http://localhost:8000/openapi.json>
* Base URL: `http://localhost:8000/api/v1`

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | The index of the API (name, version, entry points). |
| `GET` | `/api/v1/health` | The health of the service and of its dependencies. |
| `POST` | `/api/v1/workspaces` | Create a workspace. |
| `GET` | `/api/v1/workspaces` | List the workspaces (`limit`, `offset`, `name`). |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Read a workspace. |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | Update a workspace. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | Delete a workspace and everything it owns. |
| `POST` | `/api/v1/workspaces/{workspace_id}/documents` | Upload a PDF (`multipart/form-data`). |
| `GET` | `/api/v1/workspaces/{workspace_id}/documents` | List the documents (`limit`, `offset`, `status`, `document_type`, `company_name`). |
| `GET` | `/api/v1/documents/{document_id}` | Read a document. |
| `POST` | `/api/v1/documents/{document_id}/retry` | Retry a failed document. |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete a document and its chunks. |
| `POST` | `/api/v1/workspaces/{workspace_id}/search` | Search the chunks of a workspace. |

Every non 2xx response carries the same envelope:

```json
{"error": {"code": "not_found", "message": "...", "details": {}, "request_id": "..."}}
```

The full reference (every parameter, every status code, a curl example per
endpoint group) is in [`docs/api-reference.md`](docs/api-reference.md).

---

## 12. Test commands

From the `backend/` directory:

```powershell
python -m pytest tests                       # the whole suite
python -m pytest tests/unit                  # the fast, isolated tests
python -m pytest tests/integration           # against the real test database
python -m pytest tests/api                   # against the real application
python -m ruff check app tests               # the linter
```

The **real** result of the last run:

| Suite | Command | Result |
| --- | --- | --- |
| Unit | `python -m pytest tests/unit` | **215 passed** in 2.91s |
| Integration | `python -m pytest tests/integration` | **76 passed** in 11.71s |
| API | `python -m pytest tests/api` | **42 passed**, 1 warning in 11.15s |
| **Total** | `python -m pytest tests` | **333 passed**, 1 warning in 38.85s (0:00:38) |
| Lint | `python -m ruff check app tests` | `All checks passed!` |

The one warning is the deprecation notice of Starlette about `httpx` in the
test client; it comes from the third party library, not from the project.

**The integration and API tests need the test database.**  They read the
`TEST_DATABASE_URL` environment variable and fall back to
`postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test`.
The `clean_database` fixture empties the four tables before and after every
integration test, so the test database must exist and must be reachable.

> **Do not add a second `-q`.**  `backend/pyproject.toml` already sets
> `addopts = "-q --strict-markers"`.  A second `-q` on the command line turns
> it into `-qq`, which **suppresses the summary line** - the run then ends
> with the progress dots and no "N passed" line.  Use
> `--override-ini "addopts=--strict-markers"` when you want the summary.

---

## 13. Known limitations

These are real limitations of Milestone 1, not a wish list:

1. **No authentication, therefore no multi-user isolation.**  The API is
   unauthenticated: anybody who can reach it can read, create and delete
   every workspace and every document.  The `workspaces.owner_id` column is
   **reserved and always `NULL`**.  The workspace isolation that *does* exist
   is a *data* isolation (a search never leaves the workspace of its path),
   not a security boundary.
2. **OCR is not installed.**  Neither the `pytesseract` package nor the
   `tesseract` executable is available on the development machine.  A scanned
   PDF is therefore **not** extracted: the upload is rejected with the issue
   `scanned_document_ocr_unavailable`, and a single scanned page inside an
   otherwise readable document is reported as `ocr_unavailable` with a
   warning.  The text is never fabricated.
3. **The background runner is an in-process thread, not a durable queue.**
   A job that is queued is **lost when the process exits**; the queue lives
   in the memory of the process.  The mitigation is the recovery at startup
   (`run_pending()`), which reprocesses the documents that are still
   `queued`.  A real queue (Celery, RQ, Arq) is still missing.
4. **The embeddings are a local ONNX model, not a hosted API.**  The model
   (`BAAI/bge-small-en-v1.5`, 384 dimensions) runs in the API process and is
   downloaded once into the `fastembed` cache.  The first embedding call pays
   the model load.  A hosted embedding provider is not implemented.
5. **Docker was not available on the development machine.**  The compose
   stack, the two Dockerfiles and the nginx configuration were **authored but
   never executed**: no image was built and no container was started.  Only
   the YAML syntax of `docker-compose.yml` was validated.  The **verified**
   deployment path is the micromamba / uv one described above.
6. **Only the retrieval and evidence foundation exists.**  The Extraction,
   Red Flag, Comparison, Research and Report **agents are NOT implemented** -
   there is no code, no configuration and no test for them.  What exists is
   the layer they will consume (`SearchService`, `VectorStore`,
   `EmbeddingProvider`, `Chunker`, `DocumentExtractor`).
7. **Two settings are declared but not consulted by the code yet**:
   `PROCESSING_MAX_ATTEMPTS` (the retry of a failed document is an explicit
   API call, there is no automatic retry loop) and
   `TABLE_EXTRACTION_ENABLED` (the table stage of the pipeline always runs).
8. **The frontend has no test suite.**  Only `npm run lint` and
   `npm run typecheck` exist.  There is also no CI pipeline in the
   repository.
9. **Only PDF is supported.**  The upload allow list is `.pdf` /
   `application/pdf`.  DOCX, XLSX and HTML are not implemented - the
   `DocumentExtractor` protocol is the seam they would be plugged into.
10. **The metadata detection is heuristic.**  The company name, the title,
    the document type and the fiscal period are detected from the text of the
    document with conservative regular expressions; a value that cannot be
    established with confidence is left `NULL` rather than guessed.  The
    seed loader overwrites the detection with the pinned manifest values.

---

## 14. Troubleshooting

**The SEC answers `403`.**
`sec.gov` requires a `User-Agent` header.  Every entry of
`data/seed_manifest.json` pins one; if you add a document, add a
`request_headers` object with a `User-Agent` that carries a real contact
address.  Without it the download fails with
`the download of <url> failed with HTTP 403 Forbidden`.

**`pg_ctl start` blocks and never returns.**
This is a Windows behaviour: `pg_ctl` keeps waiting on the postmaster process
handle.  Use `scripts\db.ps1 -Action start`, which launches `pg_ctl` as a
detached process and polls `pg_isready` until the server accepts
connections.  The `-o` value must stay a single quoted argument, otherwise
`pg_ctl` reads the port as the operation mode and fails with
`unrecognized operation mode`.

**`could not find extension "vector"`.**
pgvector is not installed in the database, or the role may not create the
extension.  On the Windows build of pgvector 0.8.6 the extension is **not a
trusted extension**, therefore `CREATE EXTENSION vector` has to be run by the
owner role (or by the superuser, which then hands the extension over with
`ALTER EXTENSION vector OWNER TO frs;`).  `scripts\db.ps1 -Action reset` does
exactly that for both databases.

**`pytest` prints no summary line.**
`backend/pyproject.toml` already sets `addopts = "-q --strict-markers"`.  A
second `-q` on the command line makes it `-qq`, which suppresses the summary.
Drop the extra `-q` or use `--override-ini "addopts=--strict-markers"`.

**The upload hangs or the document stays `queued`.**
With `PROCESSING_INLINE=false` (the default of the setting - note that the
shipped `backend/.env` sets it to `true`) the document is processed by the
background thread of the API process.  Check the log for the worker
(`frs-document-worker`).  If the process was killed while the job was queued,
the job is lost - restart the API: the startup hook calls `run_pending()` and
reprocesses the documents that are still `queued`.  With
`PROCESSING_INLINE=true` the document is processed inside the request, which
makes the upload slow but deterministic.

**The health endpoint answers `200` but the status is `degraded`.**
The endpoint never fails; it reports the state of every dependency
(`database`, `pgvector`, `embeddings`, `storage`).  A dependency that starts
with `unavailable` names the problem - for example
`unavailable: the pgvector extension is not installed`.

**The `X-Request-ID` header is missing from the response.**
The header is written by the request id middleware and by the handler of the
unexpected errors.  If a response has neither, the error happened before the
middleware was reached - the log record of the request carries the id.

**The search returns nothing.**
Check that the document reached the state `completed` (`GET
/api/v1/documents/{id}`) - a document that is still `queued` or `failed` has
no chunks.  Then check the workspace: the search never leaves the workspace of
its path, and the document ids of a request that belong to another workspace
are dropped.

---

## Repository layout

```
Multi-Agent Financial Research System/
├── README.md                     this file
├── docker-compose.yml            the container stack (authored, not executed)
├── .env.example                  the configuration of the container stack
├── .gitignore
├── backend/
│   ├── .env                      the local configuration (not tracked)
│   ├── .env.example              the template of the local configuration
│   ├── Dockerfile                the backend image
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py               the FastAPI application factory
│   │   ├── agents/               document_agent.py, job_runner.py
│   │   ├── api/                  deps.py, errors.py, router.py, v1/
│   │   ├── core/                 config.py, enums.py, exceptions.py,
│   │   │                         logging.py, storage.py
│   │   ├── db/                   base.py, session.py, models/
│   │   ├── embeddings/           base.py, provider.py, service.py, testing.py
│   │   ├── ingestion/            chunking.py, contracts.py, metadata.py,
│   │   │                         pipeline.py, validators.py, extractors/
│   │   ├── repositories/         chunk_repository.py, document_repository.py,
│   │   │                         job_repository.py, workspace_repository.py
│   │   ├── schemas/              common.py, document.py, search.py,
│   │   │                         workspace.py
│   │   ├── services/             document_service.py, search_service.py,
│   │   │                         workspace_service.py
│   │   └── vectorstore/          base.py, in_memory_store.py,
│   │                             pgvector_store.py
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/             0001_initial.py,
│   │                             0002_expand_processing_status.py
│   ├── scripts/                  seed_documents.py, verify_index.py
│   └── tests/                    conftest.py, api/, integration/, unit/
├── data/
│   ├── seed_manifest.json        the pinned seed corpus
│   ├── documents/                the downloaded seed documents
│   └── storage/                  the uploaded documents (YYYY/MM/<uuid>.pdf)
├── docs/
│   ├── api-reference.md
│   ├── architecture.md
│   ├── database-schema.md
│   ├── ingestion-pipeline.md
│   └── milestone-1-checklist.md
├── frontend/
│   ├── .env.example
│   ├── Dockerfile                the frontend image (node build -> nginx)
│   ├── nginx.conf                the SPA server and the /api reverse proxy
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── api/                  client.ts, documents.ts, health.ts,
│       │                         search.ts, workspaces.ts, types.ts
│       ├── components/           the reusable UI components
│       ├── features/             documents/, search/, workspaces/
│       ├── hooks/                useDocuments, useSearch, useWorkspaces
│       ├── lib/                  cn.ts, format.ts
│       ├── pages/                DashboardPage, WorkspaceDetailPage, ...
│       └── routes/               the router of the SPA
└── scripts/
    └── db.ps1                    the lifecycle of the local PostgreSQL
```

---

## License and attribution

The **code** of this repository is proprietary: `backend/pyproject.toml`
declares `license = { text = "Proprietary" }`.

The **seed documents** are third party public documents.  They are owned by
their respective issuers and are used here as the demonstration corpus of the
Milestone 1 milestone:

| Document | Issuer | Source |
| --- | --- | --- |
| Walmart Inc. Form 10-K for the fiscal year ended January 31, 2026 | Walmart Inc. | <https://www.sec.gov/Archives/edgar/data/104169/000010416926000091/wmtfy26annualreport-final.pdf> |
| JPMorgan Chase & Co. Audited Consolidated Financial Statements 2025 | JPMorgan Chase & Co. | <https://www.jpmorganchase.com/content/dam/jpmc/jpmorgan-chase-and-co/investor-relations/documents/audited-financial-statements-2025.pdf> |
| Netflix, Inc. Form 10-K for the fiscal year ended December 31, 2025 | Netflix, Inc. | <https://s22.q4cdn.com/959853165/files/doc_financials/2025/ar/99482238-46b2-4d0d-b292-40e6781bdf03.pdf> |
| Apple Inc. Form 10-K for the fiscal year ended September 27, 2025 | Apple Inc. | <https://s2.q4cdn.com/470004039/files/doc_financials/2025/ar/_10-K-2025-As-Filed.pdf> |

They remain the property of their issuers; they are redistributed here for
research and demonstration purposes.  The SHA-256 checksum of every document
is pinned in `data/seed_manifest.json`.
# Multi-Agent-Financial-Research-System

