# Architecture

Milestone 1 of the Multi-Agent Financial Research System is a **modular
monolith**: one Python package (`backend/app`), one PostgreSQL database and
one React single page application.  The layers are separated by *contracts*
(protocols and frozen dataclasses), not by processes, so that a component can
be replaced without touching its callers.

---

## 1. Component responsibilities

### 1.1 API layer - `backend/app/api/`

| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | The application factory `create_app()`, the middleware stack (request id, CORS, maximum request size), the lifespan hook (creates the storage root, starts the background worker, recovers the queued documents) and the exception handlers. |
| `backend/app/api/router.py` | Collects the routers of the first API version under the prefix `/api/v1`. |
| `backend/app/api/v1/health.py` | `GET /health`. Reports the state of the database, of the pgvector extension, of the embedding provider and of the storage root. Always answers with `200`; a broken dependency is reported as `status="degraded"`. |
| `backend/app/api/v1/workspaces.py` | The CRUD endpoints of the workspaces. The handlers are thin: they translate the request into a call of `WorkspaceService` and the returned summary into the response schema. |
| `backend/app/api/v1/documents.py` | The upload, list, read, retry and delete endpoints of the documents. The upload reads the file in bounded chunks and reports the **real** status of the document. |
| `backend/app/api/v1/search.py` | `POST /workspaces/{id}/search`. Verifies the workspace, drops the document ids that belong to another workspace and delegates to `SearchService`. |
| `backend/app/api/deps.py` | The dependency providers. Every expensive component (engine, storage, embedding model, vector store, services, agent, job runner) is built once and cached under the *fingerprint* of the settings, so that the production settings and the settings of a test run live side by side. |
| `backend/app/api/errors.py` | The error envelope, the standard error codes and the exception handlers (domain error, request validation error, framework error, unexpected error). |

### 1.2 Schemas - `backend/app/schemas/`

Pydantic v2 models that define the contract of the HTTP API: the request
payloads (`WorkspaceCreate`, `WorkspaceUpdate`, `DocumentMetadata`,
`SearchRequest`) and the responses (`WorkspaceRead`, `DocumentRead`,
`DocumentUploadResponse`, `RetryResponse`, `SearchResponse`, `HealthResponse`,
`ErrorResponse`).  Every response model uses `extra="forbid"` (or
`from_attributes=True` for the read models), therefore an unknown field in a
request is rejected instead of being silently ignored.

### 1.3 Services - `backend/app/services/`

The business rules.  A service opens its own short lived session through the
injected `session_factory`, applies the rules that the repository may not
know, and returns a **frozen dataclass** - never an ORM object and never a
Pydantic schema.  The field names of the dataclasses match the response
schemas, so the API layer maps the result with a single `model_validate` call.

| Service | Owns |
| --- | --- |
| `WorkspaceService` | The validation of the name, the translation of a missing row into `NotFoundError`, the coordination of the database with the file system when a workspace is deleted. |
| `DocumentService` | The validation of an upload, the registration of a document (and of its job) in **one** transaction, the status bookkeeping (`report_status`, `apply_extraction_metadata`), the retry logic and the `DocumentProcessor` protocol. |
| `SearchService` | The validation of the query, the clamping of the limit and the composition of the embedding service with the vector store. |

### 1.4 Repositories - `backend/app/repositories/`

The persistence operations, one class per table: `WorkspaceRepository`,
`DocumentRepository`, `ChunkRepository`, `ProcessingJobRepository`.  A
repository never opens a transaction on its own behalf - the session it was
built with belongs to the caller.  The mutating methods that the service has
to compose into a single transaction accept a `commit=False` flag.

### 1.5 Ingestion - `backend/app/ingestion/`

| Module | Responsibility |
| --- | --- |
| `backend/app/ingestion/contracts.py` | The immutable hand-off contracts: `ExtractedDocument`, `ExtractedPage`, `ExtractedTable`, `DocumentExtractionMetadata`, `Chunk`. Every mapping field is a read-only `MappingProxyType`. |
| `backend/app/ingestion/validators.py` | The validation of an upload. The **content** of the file is authoritative, the announced MIME type is only a corroborating signal, the file name only contributes the extension. Every applicable problem is collected, so the answer lists *all* the reasons. |
| `backend/app/ingestion/extractors/` | The extraction strategies: `pdf_text.py` (PyMuPDF, text layer and heading detection), `pdf_tables.py` (pdfplumber, best effort), `ocr.py` (tesseract, with an explicit availability report). `base.py` holds the `DocumentExtractor` protocol. |
| `backend/app/ingestion/metadata.py` | The deterministic detection of the company name, the document title, the document type and the fiscal period. Pure functions, no I/O. |
| `backend/app/ingestion/chunking.py` | The token aware, page and section aware chunker (`TokenAwareChunker`) and the deterministic token counter `count_tokens`. |
| `backend/app/ingestion/pipeline.py` | The orchestration of the eight stages. The pipeline is a pure orchestrator: it imports neither `app.services` nor `app.repositories`, it only talks to the protocols that are injected into it. |

### 1.6 Embeddings - `backend/app/embeddings/`

| Module | Responsibility |
| --- | --- |
| `backend/app/embeddings/base.py` | The `EmbeddingProvider` protocol and the factory `build_embedding_error()`. |
| `backend/app/embeddings/provider.py` | `FastEmbedProvider`: a local ONNX model, lazily loaded, with a serialised inference call (the ONNX session is not guaranteed to be thread safe). |
| `backend/app/embeddings/service.py` | `EmbeddingService`: the validation (count, dimension, finiteness, non degeneracy), the reuse of already computed vectors and the retry policy (exponential backoff, only for transient failures). |
| `backend/app/embeddings/testing.py` | The **test only** deterministic hash provider. It is not re-exported by the package and the factory refuses it when `APP_ENV=production`. |

### 1.7 Vector store - `backend/app/vectorstore/`

| Module | Responsibility |
| --- | --- |
| `backend/app/vectorstore/base.py` | The `VectorStore` protocol and the immutable `VectorRecord` / `SearchHit` contracts. `workspace_id` is a **mandatory** search filter: a store must enforce it in the query itself. |
| `backend/app/vectorstore/pgvector_store.py` | `PgVectorStore`: the production implementation. The workspace isolation is enforced in SQL, every value is a bound parameter, the write is an idempotent `INSERT ... ON CONFLICT (document_id, chunk_index) DO UPDATE`. |
| `backend/app/vectorstore/in_memory_store.py` | The **test only** in-memory store (a dictionary plus NumPy). No persistence, no concurrency control. |

### 1.8 Agents - `backend/app/agents/`

| Module | Responsibility |
| --- | --- |
| `backend/app/agents/document_agent.py` | `DocumentAgent`: the owner of a single ingestion attempt. It loads the document, finds (or creates) the job, marks it as running (this counts the attempt), runs the pipeline and closes the job. A pipeline failure is **recorded, not raised**. |
| `backend/app/agents/job_runner.py` | The two job strategies: `InlineJobRunner` (synchronous, in the calling thread) and `BackgroundThreadJobRunner` (an in-process thread fed by a `queue.Queue`). `create_job_runner()` selects the strategy with `settings.processing_inline`. |

### 1.9 Core - `backend/app/core/`

| Module | Responsibility |
| --- | --- |
| `backend/app/core/config.py` | The `Settings` model (pydantic-settings, empty prefix, UPPER_SNAKE_CASE names), the cached accessor `get_settings()` and the startup validation `validate_runtime_settings()`. |
| `backend/app/core/exceptions.py` | The `AppError` hierarchy with the stable `code`, the human readable `message`, the JSON serialisable `details` and the finer grained `error_code`. Every exception carries its own `http_status`. |
| `backend/app/core/enums.py` | The single source of truth for the persisted values: `ProcessingStatus`, `ProcessingJobStatus`, `ChunkType`, `DocumentType`. |
| `backend/app/core/logging.py` | The structured logging (JSON by default), the request id context variable and the `bind_context` / `clear_context` helpers. Standard library only. |
| `backend/app/core/storage.py` | The `StorageBackend` protocol and the local file system implementation with the path traversal defence and the atomic writes. |

### 1.10 Scripts - `backend/scripts/`

| Script | Responsibility |
| --- | --- |
| `backend/scripts/seed_documents.py` | Downloads the seed corpus (pinned by SHA-256 in the manifest), registers it through the **real** services and runs the **real** pipeline through the inline job runner. Idempotent. |
| `backend/scripts/verify_index.py` | Verifies the seeded corpus against the **real** database: the metadata, the page count, the integrity of every chunk (content, content hash, page range, chunk type, embedding dimension, embedding configuration hash) and the retrieval (the search probe of the manifest must return a hit that points at a page). |

---

## 2. Request flows

### 2.1 Upload -> validate -> register -> job -> pipeline

1. **Request.** `POST /api/v1/workspaces/{workspace_id}/documents` with a
   `multipart/form-data` body. The `MaxRequestSizeMiddleware` rejects a body
   whose `Content-Length` exceeds `MAX_UPLOAD_SIZE_BYTES` with `413` -
   **before** the body is read at all.
2. **Stream.** `_read_upload()` reads the file in 1 MiB chunks and aborts with
   `413` as soon as the payload exceeds the maximum, therefore a hostile
   upload can never exhaust the memory of the process.
3. **Validate.** `DocumentService.register_upload()` calls
   `FileValidator.validate()`. The `%PDF-` marker decides whether the payload
   is a PDF at all, PyMuPDF must be able to open it, the extension must be on
   the allow list and the announced MIME type must not contradict the sniffed
   one. Every issue is collected and reported in
   `details["issues"]` with the `422` status.
4. **Hash and duplicate check.** The SHA-256 of the bytes is computed and a
   document with the same `(workspace_id, content_hash)` is looked up. When it
   exists the upload is answered with `duplicate: true` and **no second file
   is written**.
5. **Store.** The bytes are written to the storage backend *before* the
   database is touched. The key is `YYYY/MM/<uuid4>.<ext>` - the caller's
   file name is never part of the path.
6. **Register.** The document row and the processing job row are inserted in
   **one transaction** and committed. The document row is therefore committed
   before any processing may start. When the database write fails, the stored
   file is removed again (compensating action) and the error is re-raised.
7. **Queue.** The API calls `JobRunner.submit(document_id)`. With the inline
   runner the document is processed completely before the answer is written;
   with the background runner it is queued for the worker thread. Either way
   the answer reports the **real** status of the document.
8. **Process.** The `DocumentAgent` marks the job as running (this increments
   `attempt_count`), runs the `IngestionPipeline` and closes the job. The
   pipeline reports the status after every stage.
9. **Answer.** `201` with `{document_id, processing_status, processing_stage,
   content_hash, duplicate}`.

### 2.2 Retrieval flow

1. **Request.** `POST /api/v1/workspaces/{workspace_id}/search` with
   `{query, limit, document_ids?, chunk_types?}`.
2. **Verify the workspace.** `WorkspaceService.get_workspace()` - an unknown
   workspace is answered with `404`.
3. **Scope the document ids.** Every id of `document_ids` is checked against
   the workspace; an id that does not exist or that belongs to another
   workspace is **dropped** (it is not an error).
4. **Validate.** `SearchService` rejects an empty query, a query longer than
   1000 characters and a limit below 1; a limit above
   `RETRIEVAL_MAX_TOP_K` is clamped.
5. **Embed.** `EmbeddingService.embed_query()` turns the query into a vector.
   The vector is validated (dimension, finiteness, non degeneracy).
6. **Search.** `PgVectorStore.search()` runs the similarity query. The
   workspace filter is part of the SQL `WHERE` clause
   (`documents.workspace_id = :workspace_id`), therefore a bug in the calling
   code cannot leak another workspace's data.
7. **Answer.** `200` with `{query, workspace_id, total, results[], took_ms}`.
   Every hit carries the chunk id, the document id, the document title, the
   company name, the document type, the fiscal period, the page range, the
   section heading, the chunk type, the content, the score and the metadata -
   i.e. the **source citation** of the hit.

---

## 3. System boundaries

| Component | Where it runs | Notes |
| --- | --- | --- |
| The HTTP API | In the API process (uvicorn) | FastAPI, one worker process in development. |
| The React SPA | In the browser | Talks to the API over HTTP; in the container stack through the nginx reverse proxy. |
| The ingestion pipeline | **In the API process** - either in the request thread (inline) or in the worker thread of the background runner | There is **no durable queue** in this milestone. A queued job is lost when the process exits. |
| The embedding model | **In the API process**, locally | `fastembed` runs the ONNX model in-process; the model files are downloaded once into the `fastembed` cache. There is **no** call to a hosted embedding API. |
| The database | **External** - a PostgreSQL 16 server with the pgvector extension | The only durable store of the metadata and of the vectors. |
| The documents | **External** - the local file system behind the `StorageBackend` protocol | The `LocalStorage` implementation writes below `STORAGE_ROOT`. |

The consequence of running the model in-process: the first embedding call
pays the model load (a few seconds), the health endpoint therefore uses the
**cheap** readiness check of the provider and never loads the model.

---

## 4. Storage design

The ingestion pipeline never touches the file system directly: it asks a
`StorageBackend` for a key, writes the bytes and later reads them back.

### Key format

```
YYYY/MM/<uuid4>.<ext>
```

for example `2026/10/14fa589300104a3691f84f5fd3b362db.pdf`.

The key is generated by the backend and carries **no information from the
caller's file name**, therefore a hostile name such as `../../etc/passwd`
cannot influence where the bytes land.  The extension is normalised
(`normalise_extension()`): lower case, a single leading dot, at most 16
characters and only `A-Z a-z 0-9 . _ -`.

### Atomic writes

`LocalStorage.save()` writes the bytes to a temporary file
(`.<name>.<uuid>.tmp`) in the target directory, flushes it, calls
`os.fsync()` and then moves it into place with `os.replace()`.  A reader
therefore never sees a half written document, and a crash leaves either the
old file or the new one - never a truncated document.

### Path traversal defence

`LocalStorage.path_for()` resolves the requested key and asserts that the
result stays inside the storage root.  The following are rejected with a
`StorageError` whose code is `storage_path_escape`:

* a key that is empty or not a string,
* a key that contains a backslash,
* a key that starts with a Windows drive letter (`C:`),
* a key that is an absolute path (`/...`),
* a key that contains a `..` segment,
* a key that resolves to the root itself or outside of it.

### The object storage seam

`create_storage_backend(settings)` is the documented seam: it returns the
`LocalStorage` for `STORAGE_PROVIDER=local` and raises a `ConfigurationError`
for every other provider.  An S3 / Azure Blob / ADLS backend only has to
implement the five methods of the `StorageBackend` protocol
(`save`, `read`, `delete`, `exists`, `path_for`); neither the pipeline, the
services nor the schema have to change.  The `path_for` method is the one
that is specific to a local file system - a remote backend would return the
local cache path of the document or raise.

---

## 5. Error handling

### The hierarchy

```
AppError (code, message, details, error_code, http_status)
├── ConfigurationError   configuration_error    500
├── ValidationError      validation_error       422
├── NotFoundError        not_found              404
├── ConflictError        conflict               409
├── StorageError         storage_error          500
├── ExtractionError      extraction_error       422
├── ChunkingError        chunking_error         422
├── EmbeddingError       embedding_error        502
├── VectorStoreError     vector_store_error     500
└── ProcessingError      processing_error       500
```

`PayloadTooLargeError` (`backend/app/api/errors.py`) is an `AppError` with the
code `payload_too_large` and the status `413`.

### The envelope

Every non 2xx response has the same shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "the workspace 0f1e... does not exist",
    "details": {"workspace_id": "0f1e..."},
    "request_id": "b4c0e1..."
  }
}
```

* `code` is stable and machine readable; it never changes between releases.
* `message` is human readable and may change at any time.
* `details` is JSON serialisable diagnostic context.  It never carries a
  secret and never carries an internal file system path.
* `request_id` is the id of the request, taken from the `X-Request-ID` header
  of the request or generated.  It is the same id that is written into the
  log records of the request.

### The policy for unexpected errors

`_handle_unexpected_error()` logs the exception **with its stack trace** and
answers with a generic envelope:

```json
{"error": {"code": "internal_error", "message": "An unexpected error occurred.", "details": {}, "request_id": "..."}}
```

The stack trace, the text of the exception, the credentials and the internal
paths never reach the client.  The handler also re-attaches the
`X-Request-ID` response header, because it runs outside of the request id
middleware.

---

## 6. Extension points for the future agents

The foundation of Milestone 1 is the **retrieval and evidence layer**.  The
agents that will consume it (Extraction, Red Flag, Comparison, Research,
Report) are *not* implemented yet.  The seams they will use already exist:

| Seam | Where | What a future agent gets |
| --- | --- | --- |
| `VectorStore` | `backend/app/vectorstore/base.py` | `search(embedding, workspace_id, limit=..., document_ids=..., chunk_types=...)` - the workspace isolation is enforced by the store itself. |
| `EmbeddingProvider` | `backend/app/embeddings/base.py` | `embed(texts)`, `model_id`, `dimension`, `health()`, `probe()` - a different model (or a hosted API) is one more adapter. |
| `Chunker` | `backend/app/ingestion/chunking.py` | `chunk(document) -> list[Chunk]` - a different splitting strategy (for example a layout aware one) is one more implementation. |
| `DocumentExtractor` | `backend/app/ingestion/extractors/base.py` | `supports(file_path)`, `extract(file_path) -> ExtractedDocument` - a new format (DOCX, XLSX, HTML) is one more extractor. |
| `DocumentProcessor` | `backend/app/services/document_service.py` | `process(document_id) -> None` - the contract the `DocumentAgent` implements and that a dedicated worker will call. |
| `SearchService` | `backend/app/services/search_service.py` | `search(workspace_id=..., query=..., limit=..., document_ids=..., chunk_types=...)` - the entry point of the Research Agent: it returns the chunks with their citations. |
| `ProcessingStatusReporter` | `backend/app/ingestion/pipeline.py` | `report_status(document_id, status, stage=..., error_code=..., error_message=...)` - how a future agent reports its progress. |
| `StorageBackend` | `backend/app/core/storage.py` | `save` / `read` / `delete` / `exists` - how the corpus is persisted, independent of the file system. |

The `ExtractedDocument` / `Chunk` / `SearchHit` contracts are frozen
dataclasses with read-only mappings, so a new agent can rely on them without
having to defend against a mutation.

---

## 7. Why the key decisions

### Modular monolith, not microservices

Milestone 1 has four tables, one ingestion pipeline and nine endpoints.  A
microservice split would add a network hop, a distributed transaction and a
deployment artefact per service without removing a single bottleneck.  The
layers are already separated by protocols, therefore the *code* boundaries
that a split would need already exist - and they can be turned into real
services later without rewriting the business rules.

### No durable queue yet

The requirement is "the upload must not block on the extraction".  An
in-process worker thread satisfies that today and costs nothing.  The price is
that a queued job is lost when the process exits - and the mitigation is
`BackgroundThreadJobRunner.run_pending()`, which rescans the database for the
documents that are still `queued` and processes them again at startup.  A
real queue (Celery, RQ, Arq) becomes necessary when the corpus is processed
faster than one process can, and it can replace the runner without touching
the pipeline: the runner only has to call `DocumentAgent.process()`.

### Protocol seams instead of an interface hierarchy

The extractors, the chunker, the embedding provider and the vector store are
`typing.Protocol` classes with `runtime_checkable`.  A protocol needs no
inheritance, no registration and no factory, and the production wiring stays
a plain constructor call in `backend/app/api/deps.py`.  The unit tests
therefore inject small fakes (`FakeChunker`, `FakeEmbeddingService`,
`FakeVectorStore`) without a mocking framework - see
`backend/tests/unit/test_pipeline.py`.

### No authentication in Milestone 1

Authentication, authorisation and multi-user isolation are explicitly out of
scope for this milestone.  The `workspaces.owner_id` column is **reserved and
always NULL**, and the API is therefore **unauthenticated**.  The workspace
isolation that *does* exist is a *data* isolation (a search never leaves the
workspace of its path), not a *security* isolation - anybody who can reach
the API can read every workspace.  This is stated in the README as a known
limitation and must not be forgotten before the system is exposed.

### Deterministic where it can be

The token counter, the chunker, the metadata detection and the manifest
validation are deterministic pure functions.  Determinism is what makes the
pipeline reproducible, the tests meaningful and the chunk hashes comparable
across runs.
