# API reference

The HTTP API of the Multi-Agent Financial Research System.

* **Base URL (development):** `http://localhost:8000/api/v1`
* **Interactive documentation:** <http://localhost:8000/docs> (Swagger UI)
* **OpenAPI document:** <http://localhost:8000/openapi.json>
* **Authentication:** **none.**  The API is currently unauthenticated - see
  [section 8](#8-authentication).

---

## 1. Endpoint overview

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `GET` | `/` | A tiny index of the API (name, version, entry points). Not under `/api/v1`. | `200` |
| `GET` | `/api/v1/health` | The health of the service and of its dependencies. | `200` |
| `POST` | `/api/v1/workspaces` | Create a workspace. | `201` |
| `GET` | `/api/v1/workspaces` | List the workspaces. | `200` |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Return a single workspace. | `200` |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | Update a workspace. | `200` |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | Delete a workspace and everything it owns. | `204` |
| `POST` | `/api/v1/workspaces/{workspace_id}/documents` | Upload a PDF into a workspace. | `201` |
| `GET` | `/api/v1/workspaces/{workspace_id}/documents` | List the documents of a workspace. | `200` |
| `GET` | `/api/v1/documents/{document_id}` | Return a single document. | `200` |
| `POST` | `/api/v1/documents/{document_id}/retry` | Retry the processing of a failed document. | `202` |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete a document and its chunks. | `204` |
| `POST` | `/api/v1/workspaces/{workspace_id}/search` | Search the chunks of a workspace. | `200` |

---

## 2. The error envelope

Every non 2xx response has the same shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "the workspace 6f9b... does not exist",
    "details": {"workspace_id": "6f9b..."},
    "request_id": "1d0c3a9f5b6e4d8fa1c2b3d4e5f60718"
  }
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `error.code` | string | Stable, machine readable. It is part of the public contract and never changes between releases. |
| `error.message` | string | Human readable. It may change at any time. |
| `error.details` | object | JSON serialisable diagnostic context. Never a secret, never an internal path. |
| `error.request_id` | string | The id of the request. The same id is written into the log records of the request, so a user can report it and an operator can find the request in the log. |

### The standard error codes

| Code | HTTP | Raised when |
| --- | --- | --- |
| `configuration_error` | 500 | The configuration is invalid or unsafe (the application refuses to start). |
| `validation_error` | 422 | A domain level rule rejected the request. |
| `request_validation_error` | 422 | The request does not satisfy the schema (a missing field, a wrong type, an unknown field). |
| `not_found` | 404 | The resource does not exist. |
| `conflict` | 409 | The request conflicts with the current state of the resource (for example the retry of a document that is not `failed`). |
| `storage_error` | 500 | The document storage backend failed. |
| `extraction_error` | 422 | The text or the tables could not be extracted. |
| `chunking_error` | 422 | The document could not be split into chunks. |
| `embedding_error` | 502 | The embedding provider failed to produce a vector. |
| `vector_store_error` | 500 | The vector store could not serve or persist a query. |
| `processing_error` | 500 | The ingestion pipeline failed. |
| `payload_too_large` | 413 | The request body exceeds `MAX_UPLOAD_SIZE_BYTES`. |
| `http_error` | 4xx / 5xx | The framework itself raised the error (for example an unknown path). |
| `internal_error` | 500 | An unexpected error. The message is the generic `An unexpected error occurred.`; the stack trace stays in the log. |

### The more specific codes

The same envelope carries a finer grained code for the individual failures:

| Code | Where it appears |
| --- | --- |
| `invalid_workspace_name` | The workspace name is empty or longer than 255 characters. |
| `invalid_upload` | The upload was rejected; `details.issues` lists every issue code (see `backend/app/ingestion/validators.py`: `file_too_large`, `file_empty`, `extension_not_allowed`, `not_a_pdf`, `mime_type_not_allowed`, `mime_type_mismatch`, `pdf_unreadable`, `pdf_encrypted`, `no_pages`, `too_many_pages`, `scanned_document_ocr_unavailable`). |
| `invalid_document_metadata` | The metadata of the upload was rejected by the schema. |
| `document_not_failed` | The retry was requested for a document that is not in the state `failed`. |
| `invalid_search_query` | The query is empty or longer than 1000 characters. |
| `invalid_search_limit` | The limit is smaller than 1. |
| `unsupported_storage_provider` | `STORAGE_PROVIDER` is not `local`. |
| `storage_path_escape` / `invalid_extension` / `storage_not_found` / `storage_write_failed` / `storage_read_failed` / `storage_delete_failed` / `invalid_payload` | The storage backend. |
| `ocr_unavailable` / `ocr_failed` / `pdf_unreadable` / `pdf_encrypted` / `page_out_of_range` | The extractors. They are recorded in `documents.error_code` and `processing_jobs.error_code`. |
| `embedding_provider_error` / `embedding_count_mismatch` / `embedding_dimension_mismatch` / `embedding_invalid_vector` / `embedding_non_finite_value` / `embedding_degenerate_vector` / `embedding_timeout` | The embedding service. |
| `invalid_limit` / `invalid_chunk_type` / `invalid_metadata` / `embedding_not_finite` | The vector store. |
| `missing_workspace_id` / `invalid_stored_document` | The pipeline. |

---

## 3. Pagination conventions

The list endpoints use the same three query parameters:

| Parameter | Type | Default | Range |
| --- | --- | --- | --- |
| `limit` | integer | `20` for the workspaces, `50` for the documents | `1 .. 100` (`MAX_PAGE_SIZE`). A value outside the range is rejected with `422`. |
| `offset` | integer | `0` | `>= 0`. |

The response is always the same envelope:

```json
{
  "items": [ ... ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

`total` is the number of rows that match the **filter**, not the size of the
returned page.

The search endpoint does not paginate: it returns the `limit` best hits
(`limit` defaults to 10 and is clamped to `RETRIEVAL_MAX_TOP_K`, 100 by
default).  A limit above the maximum is **clamped**, not rejected; a limit
below 1 is rejected with `422`.

---

## 4. `GET /api/v1/health`

Reports the state of the service and of its dependencies.  The response is
**always** `200`: a failing dependency is reported as `status="degraded"`
instead of as an error, because the process is alive and can still answer.

**Request:** no parameters.

**Response `200`:**

```json
{
  "status": "ok",
  "app": "Multi-Agent Financial Research System",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-21T08:14:03.512847+00:00",
  "checks": {
    "database": "ok (2 ms)",
    "pgvector": "0.8.6",
    "embeddings": "BAAI/bge-small-en-v1.5 (dimension 384)",
    "storage": "ok"
  }
}
```

A degraded dependency is reported with a message that starts with
`unavailable`, for example
`unavailable: the database is not reachable`,
`unavailable: the pgvector extension is not installed`,
`unavailable: the storage root does not exist` or
`unavailable: the storage root is not writable`.

The endpoint never leaks a secret: the connection string, the password and
the internal paths of the server are not part of the response.

**Status codes:** `200` (always).

**curl:**

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
```

---

## 5. Workspaces

### 5.1 `POST /api/v1/workspaces` - create a workspace

**Request body (JSON):**

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | yes | 1 .. 255 characters. It is stripped of the surrounding whitespace. |
| `description` | string \| null | no | At most 2000 characters. |

**Response `201`** (`WorkspaceRead`):

```json
{
  "id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "name": "Seed Documents",
  "description": "Seed corpus of the Multi-Agent Financial Research System.",
  "owner_id": null,
  "document_count": 4,
  "created_at": "2026-10-21T07:02:11.184920+00:00",
  "updated_at": "2026-10-21T07:02:11.184920+00:00"
}
```

`owner_id` is **always `null`** in this milestone (no authentication, no
multi-user isolation).

**Status codes:** `201`, `422` (`invalid_workspace_name` or
`request_validation_error`).

**curl:**

```bash
curl -s -X POST http://localhost:8000/api/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "Seed Documents", "description": "Seed corpus"}'
```

### 5.2 `GET /api/v1/workspaces` - list the workspaces

**Query parameters:** `limit` (default 20, 1..100), `offset` (default 0),
`name` (a case insensitive *contains* filter, at most 255 characters).

**Response `200`:** `{items: WorkspaceRead[], total, limit, offset}`.

**Status codes:** `200`.

**curl:**

```bash
curl -s "http://localhost:8000/api/v1/workspaces?limit=20&offset=0&name=Seed"
```

### 5.3 `GET /api/v1/workspaces/{workspace_id}` - read a workspace

**Response `200`:** a single `WorkspaceRead`.

**Status codes:** `200`, `404` (`not_found`).

**curl:**

```bash
curl -s http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0
```

### 5.4 `PATCH /api/v1/workspaces/{workspace_id}` - update a workspace

**Request body (JSON):** every field is optional.  A field that the client
does **not** send keeps its value; an explicit `null` clears the description.
The name of a workspace may never be cleared.

```json
{"name": "Seed corpus", "description": null}
```

**Response `200`:** the updated `WorkspaceRead`.

**Status codes:** `200`, `404`, `422`.

**curl:**

```bash
curl -s -X PATCH http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0 \
  -H "Content-Type: application/json" \
  -d '{"description": "A workspace"}'
```

### 5.5 `DELETE /api/v1/workspaces/{workspace_id}` - delete a workspace

Deletes the workspace, all of its documents, all of their chunks and all of
their processing jobs (the foreign key cascade of the schema).  The stored
files are removed from the storage backend afterwards.

**Response `204`:** no body.

**Status codes:** `204`, `404`.

**curl:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0
```

---

## 6. Documents

### 6.1 `POST /api/v1/workspaces/{workspace_id}/documents` - upload a document

**Request:** `multipart/form-data`.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `file` | file | yes | The PDF document. The content decides whether it is a PDF; the name and the announced MIME type are only corroborating signals. |
| `company_name` | string | no | At most 255 characters. |
| `document_title` | string | no | At most 512 characters. |
| `document_type` | string | no | At most 64 characters. |
| `fiscal_period` | string | no | At most 64 characters. |
| `source_url` | string | no | The URL the document came from. |

The response reports the **real** status of the document at the moment the
answer is written: with the inline runner the document was processed
completely, with the background runner it is still being processed.

**Response `201`** (`DocumentUploadResponse`):

```json
{
  "document_id": "b3a1c0de-1111-2222-3333-444455556666",
  "processing_status": "completed",
  "processing_stage": "completed",
  "content_hash": "550eaf563e00aa4862eb26f2a738b9c95968f3aa39e12f31e7076824e9ba9a8d",
  "duplicate": false
}
```

`duplicate: true` means that the same bytes were already registered in this
workspace; the existing document is reported and **no second file is
written** and no second processing run is started.

**Status codes:**

| Code | When |
| --- | --- |
| `201` | The document was registered. |
| `404` | The workspace does not exist. |
| `413` | The body exceeds `MAX_UPLOAD_SIZE_BYTES` (50 MiB by default). |
| `422` | The upload was rejected by the validation (`invalid_upload`); `details.issues` lists every reason. |

**curl:**

```bash
curl -s -X POST \
  http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/documents \
  -F "file=@data/documents/apple_fy2025_form_10k.pdf;type=application/pdf" \
  -F "company_name=Apple Inc." \
  -F "document_title=Apple Inc. Form 10-K for the fiscal year ended September 27, 2025" \
  -F "document_type=form_10k" \
  -F "fiscal_period=FY2025" \
  -F "source_url=https://s2.q4cdn.com/470004039/files/doc_financials/2025/ar/_10-K-2025-As-Filed.pdf"
```

### 6.2 `GET /api/v1/workspaces/{workspace_id}/documents` - list the documents

**Query parameters:**

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `limit` | integer | `50` | 1 .. 100. |
| `offset` | integer | `0` | `>= 0`. |
| `status` | string | – | Filters on `processing_status` (for example `completed`, `failed`). |
| `document_type` | string | – | Filters on `document_type`; at most 64 characters. |
| `company_name` | string | – | Filters on `company_name`; at most 255 characters. |

**Response `200`:** `{items: DocumentRead[], total, limit, offset}`.

A `DocumentRead` carries the provenance (`original_filename`, `content_hash`,
`file_size_bytes`, `mime_type`, `company_name`, `document_title`,
`document_type`, `fiscal_period`, `source_url`, `page_count`), the processing
state (`processing_status`, `processing_stage`, `error_code`, `error_message`,
`processed_at`) and the counters (`chunk_count`).

**Status codes:** `200`, `404` (the workspace does not exist).

**curl:**

```bash
curl -s "http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/documents?limit=50&status=completed"
```

### 6.3 `GET /api/v1/documents/{document_id}` - read a document

**Response `200`:** a single `DocumentRead`.

**Status codes:** `200`, `404`.

**curl:**

```bash
curl -s http://localhost:8000/api/v1/documents/b3a1c0de-1111-2222-3333-444455556666
```

### 6.4 `POST /api/v1/documents/{document_id}/retry` - retry a failed document

Queues a new processing attempt.  The document must be in the state `failed`.

**Request:** no body.

**Response `202`** (`RetryResponse`):

```json
{
  "document_id": "b3a1c0de-1111-2222-3333-444455556666",
  "job_id": "9c8b7a65-4321-4321-8765-0a1b2c3d4e5f",
  "attempt_count": 0,
  "processing_status": "queued"
}
```

**Status codes:**

| Code | When |
| --- | --- |
| `202` | The new attempt was queued. |
| `404` | The document does not exist. |
| `409` | The document is not in the state `failed` (`document_not_failed`). |

**curl:**

```bash
curl -s -X POST http://localhost:8000/api/v1/documents/b3a1c0de-1111-2222-3333-444455556666/retry
```

### 6.5 `DELETE /api/v1/documents/{document_id}` - delete a document

Deletes the document row, its chunks and its processing jobs, and removes the
stored file afterwards.

**Response `204`:** no body.

**Status codes:** `204`, `404`.

**curl:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  http://localhost:8000/api/v1/documents/b3a1c0de-1111-2222-3333-444455556666
```

---

## 7. Search

### `POST /api/v1/workspaces/{workspace_id}/search`

**Request body (JSON):**

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `query` | string | yes | 1 .. 1000 characters. A blank query is rejected. |
| `limit` | integer | no | `>= 1`, default 10. A value above the server maximum is clamped, not rejected. |
| `document_ids` | array of UUID | no | Restricts the search to these documents. An id of another workspace is **dropped**. |
| `chunk_types` | array of string | no | `text` and/or `table`. |

**Response `200`** (`SearchResponse`):

```json
{
  "query": "net sales consolidated statements of income",
  "workspace_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "total": 10,
  "results": [
    {
      "chunk_id": "1a2b3c4d-5e6f-7081-9203-a4b5c6d7e8f9",
      "document_id": "b3a1c0de-1111-2222-3333-444455556666",
      "document_title": "Walmart Inc. Form 10-K for the fiscal year ended January 31, 2026",
      "company_name": "Walmart Inc.",
      "document_type": "form_10k",
      "fiscal_period": "FY2026",
      "page_start": 42,
      "page_end": 42,
      "section_heading": "Consolidated Statements of Income",
      "chunk_type": "text",
      "content": "...",
      "score": 0.8123,
      "metadata": {"source": "pdf_text", "page_number": 42, "section_heading": "..."}
    }
  ],
  "took_ms": 41.2
}
```

Every hit carries its **source citation**: the document, the page range, the
section heading and the chunk type.  `score` is the cosine similarity
(`1 - cosine_distance`), `1.0` is a perfect match.

**Status codes:**

| Code | When |
| --- | --- |
| `200` | The search ran. An empty result list is a normal answer, not an error. |
| `404` | The workspace does not exist. |
| `422` | The query is empty, too long, or the limit is below 1 (`invalid_search_query`, `invalid_search_limit`). |

**curl:**

```bash
curl -s -X POST http://localhost:8000/api/v1/workspaces/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/search \
  -H "Content-Type: application/json" \
  -d '{"query": "net sales consolidated statements of income", "limit": 5, "chunk_types": ["text", "table"]}'
```

---

## 8. Authentication

**The API is currently unauthenticated.**  Milestone 1 implements no
authentication, no authorisation and therefore **no multi-user isolation**:
every client that can reach the API can read, create and delete every
workspace and every document.  The `workspaces.owner_id` column exists but is
reserved and always `NULL`.

What *does* exist is a **data** isolation: a search never returns a chunk of
another workspace, and the document ids of a search request are verified
against the workspace before the query runs.  This is a correctness property,
not a security boundary - see [section 9](#9-workspace-isolation).

---

## 9. Workspace isolation

The workspace of the path is the **only** scope of a search, and the scope is
enforced **in SQL, not by the client**:

```sql
SELECT ...
  FROM document_chunks
  JOIN documents ON documents.id = document_chunks.document_id
 WHERE documents.workspace_id = :workspace_id
 ORDER BY document_chunks.embedding <=> CAST(:query_embedding AS vector)
 LIMIT :limit
```

`PgVectorStore.search()` takes `workspace_id` as a mandatory argument and adds
it to the `WHERE` clause; there is no code path that filters in Python
afterwards.  A bug in the calling code therefore cannot leak another
workspace's data.

In addition, the API layer drops every document id of a search request that
does not belong to the workspace of the path - an unknown id and an id of
another workspace are both silently removed, because a search must never leave
the scope of its request.

---

## 10. The request size limit and the `X-Request-ID` header

### The size limit

`MAX_UPLOAD_SIZE_BYTES` (default 52 428 800 = 50 MiB) is enforced **twice**:

1. `MaxRequestSizeMiddleware` compares the `Content-Length` header with the
   maximum and answers with `413` and the code `payload_too_large` -
   **before the body is read at all**.
2. The upload endpoint reads the file in 1 MiB chunks and aborts with the
   same `413` as soon as the payload exceeds the maximum, because a client
   may lie about the length of the body.

### The `X-Request-ID` header

`RequestIdMiddleware` reads the `X-Request-ID` header of the request, or
generates a UUID4 hex string when the header is absent.  The id is

* written into the response header `X-Request-ID`,
* bound to the logging context, so that every log record of the request
  carries it,
* written into the `request_id` field of the error envelope.

A client can therefore correlate its own request with the log of the server.

**curl:**

```bash
curl -s -D - -o /dev/null -H "X-Request-ID: my-correlation-id" \
  http://localhost:8000/api/v1/health
```

---

## 11. The multipart upload field names

The upload endpoint expects exactly these form fields:

| Field | Type | Required |
| --- | --- | --- |
| `file` | the PDF file | yes |
| `company_name` | text | no |
| `document_title` | text | no |
| `document_type` | text | no |
| `fiscal_period` | text | no |
| `source_url` | text | no |

The frontend sends exactly these names
(`frontend/src/api/documents.ts`); the `Content-Type` header must **not** be
set by the client, because the browser has to generate the multipart boundary
itself.
