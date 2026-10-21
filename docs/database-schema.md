# Database schema

The schema of the Multi-Agent Financial Research System consists of four tables
plus the Alembic bookkeeping table.  It is created exclusively by the Alembic
migrations - `Base.metadata.create_all()` is never called by the application.

| Object | Owner module | Migration |
| --- | --- | --- |
| `workspaces` | `backend/app/db/models/workspace.py` | `backend/migrations/versions/0001_initial.py` |
| `documents` | `backend/app/db/models/document.py` | `backend/migrations/versions/0001_initial.py`, `0002_expand_processing_status.py` |
| `document_chunks` | `backend/app/db/models/chunk.py` | `backend/migrations/versions/0001_initial.py` |
| `processing_jobs` | `backend/app/db/models/job.py` | `backend/migrations/versions/0001_initial.py` |

The schema below was read from the live development database
(PostgreSQL 16.15 with pgvector 0.8.6) and matches the ORM models.

---

## 1. Entity relationship

```
workspaces (1) ──< (N) documents (1) ──< (N) document_chunks
                        │
                        └──< (N) processing_jobs
```

* **workspace -> document**: `documents.workspace_id -> workspaces.id`,
  `ON DELETE CASCADE`.
* **document -> document_chunk**: `document_chunks.document_id -> documents.id`,
  `ON DELETE CASCADE`.
* **document -> processing_job**: `processing_jobs.document_id -> documents.id`,
  `ON DELETE CASCADE`.

### Effect of a delete

| Deleting | Removes |
| --- | --- |
| a **workspace** | the workspace row, **every** document of that workspace, and with them every chunk and every processing job (the cascade is transitive). The stored PDF files are **not** removed by the database; `WorkspaceService.delete_workspace()` collects the storage keys *before* the delete, commits the delete and only then removes the files from the storage backend. A failure to remove a file is logged and never raised - the database is the source of truth. |
| a **document** | the document row, all of its chunks and all of its processing jobs. The stored file is removed afterwards by `DocumentService.delete_document()` (same compensating order as above). |
| a **processing job** | only the job row. The document and its chunks are untouched - a job is a *record of an attempt*, not the owner of the data. |

All primary keys are UUIDv4 values that are generated **client side** by
`UUIDPrimaryKeyMixin` (`uuid4`), therefore an insert never needs a round trip
to the server.

---

## 2. `workspaces`

A workspace is the top level container of a research project.  It scopes the
documents, the chunks and every search.

| Column | Type | Null | Default | Meaning |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | – | Primary key, generated client side (UUIDv4). |
| `name` | `varchar(255)` | NOT NULL | – | The name of the workspace. Stripped of surrounding whitespace by the service; must not be empty and must not be longer than 255 characters. |
| `description` | `text` | YES | `NULL` | Free text description. `PATCH` with an explicit `null` clears it. |
| `owner_id` | `uuid` | YES | `NULL` | **Reserved for a future multi-tenant owner.** Milestone 1 implements no authentication and therefore **no multi-user isolation**; this column is always `NULL`. |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Creation time (timezone aware). |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last modification time (timezone aware); refreshed by `onupdate=func.now()`. |

### Constraints and indexes

| Name | Kind | Definition |
| --- | --- | --- |
| `pk_workspaces` | PRIMARY KEY | `(id)` |
| `ix_workspaces_name` | btree index | `(name)` |

---

## 3. `documents`

A document is an uploaded file that was registered for processing.  It carries
both the provenance of the file (name, hash, size, MIME type, source URL) and
the state of its processing.

| Column | Type | Null | Default | Meaning |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | – | Primary key (UUIDv4, client side). |
| `workspace_id` | `uuid` | NOT NULL | – | FK to `workspaces.id`, `ON DELETE CASCADE`. |
| `original_filename` | `varchar(512)` | NOT NULL | – | The file name the client sent. It is **never** used to build a file system path. |
| `storage_key` | `varchar(512)` | NOT NULL | – | The key of the file in the storage backend, e.g. `2026/10/<uuid>.pdf`. Unique over the whole table. |
| `content_hash` | `varchar(64)` | NOT NULL | – | The SHA-256 hex digest of the uploaded bytes. |
| `file_size_bytes` | `bigint` | NOT NULL | – | The size of the uploaded file in bytes. |
| `mime_type` | `varchar(128)` | NOT NULL | – | The MIME type that was **detected** from the content of the file (`application/pdf` today). |
| `company_name` | `varchar(255)` | YES | `NULL` | The detected (or supplied) issuer of the document. |
| `document_title` | `varchar(512)` | YES | `NULL` | The detected (or supplied) title. |
| `document_type` | `varchar(64)` | YES | `NULL` | One of the `DocumentType` values: `annual_report`, `form_10k`, `form_10q`, `earnings_release`, `annual_letter`, `financial_statements`, `other`. |
| `fiscal_period` | `varchar(64)` | YES | `NULL` | Normalised label of the period, e.g. `FY2025` or `Q3 2025`. |
| `source_url` | `text` | YES | `NULL` | The URL the document was downloaded from (the seed corpus pins it in the manifest). |
| `page_count` | `integer` | YES | `NULL` | The number of pages that were really read. |
| `processing_status` | `varchar(32)` | NOT NULL | `'queued'` | The **authoritative** processing state - see section 7. |
| `processing_stage` | `varchar(64)` | YES | `NULL` | Supplementary sub-stage detail (`validating`, `pdf_text`, `pdf_tables`, `ocr`, `chunking`, `embedding`, `indexing`, `completed`). **Not** a second state machine. |
| `error_code` | `varchar(64)` | YES | `NULL` | The stable, fine grained diagnosis of the last failure. |
| `error_message` | `text` | YES | `NULL` | A concise, single line, secret free description of the last failure (truncated to 500 characters by the pipeline). |
| `processed_at` | `timestamptz` | YES | `NULL` | The moment the document reached `completed`. Stamped by `DocumentRepository.set_status()`. |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Registration time (timezone aware). |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last modification time (timezone aware). |

### Constraints and indexes

| Name | Kind | Definition |
| --- | --- | --- |
| `pk_documents` | PRIMARY KEY | `(id)` |
| `fk_documents_workspace_id_workspaces` | FOREIGN KEY | `workspace_id -> workspaces.id ON DELETE CASCADE` |
| `uq_documents_workspace_content_hash` | UNIQUE | `(workspace_id, content_hash)` - the same bytes may only be registered once per workspace (the duplicate detection of the upload). |
| `uq_documents_storage_key` | UNIQUE | `(storage_key)` - two documents may never share a storage key. |
| `ck_documents_processing_status` | CHECK | `processing_status IN ('queued','validating','extracting','chunking','embedding','indexing','completed','failed')` |
| `ix_documents_workspace_id` | btree index | `(workspace_id)` |
| `ix_documents_workspace_id_processing_status` | btree index | `(workspace_id, processing_status)` - the filter of the document list. |
| `ix_documents_content_hash` | btree index | `(content_hash)` |

---

## 4. `document_chunks`

A chunk is a retrievable slice of a document.  It carries the text, the
provenance (page range, section heading, chunk type), the provenance metadata
as JSON and the pgvector embedding.

| Column | Type | Null | Default | Meaning |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | – | Primary key (UUIDv4, client side). |
| `document_id` | `uuid` | NOT NULL | – | FK to `documents.id`, `ON DELETE CASCADE`. |
| `chunk_index` | `integer` | NOT NULL | – | The 0-based position of the chunk inside its document. Unique per document. |
| `content` | `text` | NOT NULL | – | The text of the chunk (for a table chunk: the rendered table). |
| `content_hash` | `varchar(64)` | NOT NULL | – | The SHA-256 hex digest of `content`. |
| `page_start` | `integer` | YES | `NULL` | The first page of the chunk (1-based). |
| `page_end` | `integer` | YES | `NULL` | The last page of the chunk (1-based). A chunk never spans two pages, therefore `page_start == page_end`. |
| `section_heading` | `varchar(512)` | YES | `NULL` | The heading of the section the chunk came from; `NULL` for the leading, un-headed part of a page. |
| `chunk_type` | `varchar(32)` | NOT NULL | `'text'` | `text` or `table`. |
| `token_count` | `integer` | YES | `NULL` | The number of tokens of the chunk, counted with the deterministic counter of the chunker. |
| `metadata_json` | `jsonb` | NOT NULL | `'{}'::jsonb` | Flat, JSON serialisable provenance metadata (`source`, `page_number`, `section_heading`, `has_table`, `page_has_table`, `section_index`, `table_index`, `column_count`, `content_hash`, `embedding_config_hash`, `token_count`). |
| `embedding` | `vector(384)` | NOT NULL | – | The embedding vector - see section 6. |
| `embedding_config_hash` | `varchar(64)` | NOT NULL | – | The SHA-256 of `"{model_id}\|{dimension}"`. A stored vector may only be reused while this hash still matches the current configuration. |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Insertion time (timezone aware). The chunk table has **no** `updated_at`: a chunk is immutable, a re-indexing replaces the rows. |

### Constraints and indexes

| Name | Kind | Definition |
| --- | --- | --- |
| `pk_document_chunks` | PRIMARY KEY | `(id)` |
| `fk_document_chunks_document_id_documents` | FOREIGN KEY | `document_id -> documents.id ON DELETE CASCADE` |
| `uq_document_chunks_document_chunk_index` | UNIQUE | `(document_id, chunk_index)` - the guarantee that a re-run of the pipeline cannot create duplicates. |
| `ck_document_chunks_chunk_type` | CHECK | `chunk_type IN ('text','table')` |
| `ix_document_chunks_document_id` | btree index | `(document_id)` |
| `ix_document_chunks_metadata_json` | **GIN** index | `(metadata_json)` - supports containment queries on the provenance metadata. |
| `ix_document_chunks_embedding_hnsw` | **HNSW** index | `(embedding) USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')` - the approximate nearest neighbour index that the similarity search uses. |

The `vector_cosine_ops` operator class matches the cosine distance that
`PgVectorStore.search()` computes (`embedding <=> query`); the score that is
returned to the client is `1 - cosine_distance`.

---

## 5. `processing_jobs`

A processing job records **one attempt** of the ingestion pipeline for a
document.

| Column | Type | Null | Default | Meaning |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | – | Primary key (UUIDv4, client side). |
| `document_id` | `uuid` | NOT NULL | – | FK to `documents.id`, `ON DELETE CASCADE`. |
| `status` | `varchar(32)` | NOT NULL | `'queued'` | `queued`, `running`, `completed` or `failed`. |
| `attempt_count` | `integer` | NOT NULL | `0` | Incremented every time the job starts (`mark_running`), therefore it is the number of attempts the document needed. |
| `started_at` | `timestamptz` | YES | `NULL` | When the attempt started. |
| `completed_at` | `timestamptz` | YES | `NULL` | When the attempt ended (successfully or not). |
| `error_code` | `varchar(64)` | YES | `NULL` | The stable diagnosis of the failure of this attempt. |
| `error_message` | `text` | YES | `NULL` | A concise, secret free description of the failure. |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Creation time (timezone aware). |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last modification time (timezone aware). |

### Constraints and indexes

| Name | Kind | Definition |
| --- | --- | --- |
| `pk_processing_jobs` | PRIMARY KEY | `(id)` |
| `fk_processing_jobs_document_id_documents` | FOREIGN KEY | `document_id -> documents.id ON DELETE CASCADE` |
| `ck_processing_jobs_status` | CHECK | `status IN ('queued','running','completed','failed')` |
| `ix_processing_jobs_document_id` | btree index | `(document_id)` |
| `ix_processing_jobs_document_id_attempt_count` | btree index | `(document_id, attempt_count)` |

A retry creates a **new** job row (its `attempt_count` starts at 0) and moves
the document back to `queued`; the previous job row stays as the record of the
failed attempt.

---

## 6. The `vector(384)` column

`document_chunks.embedding` is declared as `vector(384)`.

* **Why 384?** 384 is the native output dimension of
  `BAAI/bge-small-en-v1.5`, the model the default configuration embeds with
  (`EMBEDDING_MODEL`).  It is the smallest of the three known models
  (`bge-small` 384 / `bge-base` 768 / `bge-large` 1024) and therefore the
  cheapest to compute locally.  The mapping is fixed in
  `backend/app/embeddings/service.py` (`KNOWN_MODEL_DIMENSIONS`).
* **How it relates to the settings.**  The dimension is a *configuration* value,
  not a constant.  `backend/app/db/models/chunk.py` reads
  `settings.embedding_dimension` at import time
  (`EMBEDDING_DIMENSION = get_settings().embedding_dimension`), and the
  migration `0001_initial` reads `os.getenv("EMBEDDING_DIMENSION", "384")`.
  `backend/migrations/env.py` exports the configured value into the
  environment before the migration runs, so the model and the migration always
  agree.
* **Changing the dimension requires a migration.**  The column type is
  `vector(384)` in the database; a different dimension needs a new Alembic
  revision that changes the column, **and** every existing vector has to be
  re-embedded, because the stored vectors of the old dimension are
  meaningless for the new model.  The `embedding_config_hash` column exists
  for exactly that reason: a vector is only reused when its configuration
  hash still matches the current one.

---

## 7. The processing status state machine

`documents.processing_status` is the **authoritative** state of a document.
It has exactly eight values (`ProcessingStatus` in
`backend/app/core/enums.py`):

```
queued ──> validating ──> extracting ──> chunking ──> embedding ──> indexing ──> completed
   │            │             │             │            │             │
   └────────────┴─────────────┴─────────────┴────────────┴─────────────┴──────> failed
```

| State | Meaning | Terminal |
| --- | --- | --- |
| `queued` | The document is registered and waiting for a worker. | no |
| `validating` | The stored bytes are re-validated against the upload rules. | no |
| `extracting` | The text layer, the tables and (if available) the OCR of the pages are read. | no |
| `chunking` | The extracted document is split into chunks. | no |
| `embedding` | The chunks are embedded (already computed vectors are reused). | no |
| `indexing` | The chunks are written into the vector store. | no |
| `completed` | The document is fully processed and searchable. | **yes** |
| `failed` | The processing failed; `error_code` and `error_message` carry the diagnosis. | **yes** |

`TERMINAL_PROCESSING_STATUSES = {completed, failed}` and
`ACTIVE_PROCESSING_STATUSES = {queued, validating, extracting, chunking,
embedding, indexing}` are defined in the same module; `is_terminal()` treats an
unknown value as *not* terminal.

### `processing_stage` is not a status

`documents.processing_stage` carries **supplementary detail only** - the
sub-stage of the extraction (`pdf_text`, `pdf_tables`, `ocr`) or the name of
the stage that is currently running.  It is not a second state machine and it
must never be branched on.  The database comment on the column says exactly
that, and the migration `0002_expand_processing_status` writes the comment.

### How the status is updated

* Every update goes through `DocumentRepository.set_status()`, which writes
  the status **and** the stage in one statement, clears `error_code` /
  `error_message` whenever the new status is not `failed`, and stamps
  `processed_at` when the document reaches `completed`.
* The call is transactional: the repository either commits (`commit=True`) or
  only flushes (`commit=False`), so the service can compose the document row
  and the job row into a single transaction.
* The pipeline reports the status after **every** stage through the
  `ProcessingStatusReporter` protocol.  The reporter of the production
  wiring is `DocumentService.report_status()`, which opens its own short
  lived session and commits immediately - the status is therefore durable as
  soon as it is reported, and no transaction is held open across the slow
  extraction or embedding work.
* A failure is reported as `failed` **before** the exception is re-raised, so
  a document never stays in a non-terminal state.

---

## 8. Timestamps

Every timestamp column is `TIMESTAMP WITH TIME ZONE` (`timestamptz`):

* the server default is `now()`, which is the transaction timestamp of
  PostgreSQL;
* `updated_at` is refreshed by `onupdate=func.now()` on every ORM update;
* `utcnow()` in `backend/app/db/base.py` returns a timezone aware UTC
  `datetime` and is used for the timestamps that the application writes
  itself (`started_at`, `completed_at`, `processed_at`);
* the API serialises them as ISO 8601 strings with an explicit offset, e.g.
  `2026-10-21T08:14:03.512847+00:00`.

Storing the timestamps with a time zone (and not as `timestamp without time
zone`) is what makes them comparable across the machines of a deployment.

---

## 9. Migration strategy

* **Alembic** is the only way the schema is created or changed.
  `Base.metadata.create_all()` is never called by the application, by the
  scripts or by the tests.
* `backend/migrations/env.py` takes the database URL from the application
  settings (so that the migrations always run against the same database the
  application uses) and imports the ORM models, therefore `alembic revision
  --autogenerate` and `alembic check` see the complete schema.
* The migration `0001_initial` creates the `vector` extension
  (`CREATE EXTENSION IF NOT EXISTS vector`) and the four tables with their
  indexes.  **pgvector must be installed server side**, otherwise the
  migration fails with `could not find extension "vector"`.  The extension is
  shared with the other databases of the cluster and is therefore never
  dropped in `downgrade()`.
* The migration `0002_expand_processing_status` replaces the coarse
  `processing` value of `documents.processing_status` with the eight explicit
  states.  Rows that carry the old value are mapped back to `queued` first, so
  that no row is lost and the new CHECK constraint can be applied without a
  validation error.  The allowed values are imported from
  `app.core.enums`, therefore the migration and the ORM model can never drift
  apart.
* `alembic check` compares the metadata with the database and fails when they
  differ - it belongs into the CI pipeline.
* The current revision of the development database is
  `0002_expand_processing_status (head)`.

Useful commands (run from `backend/`):

```powershell
python -m alembic upgrade head      # apply every migration
python -m alembic downgrade -1       # undo the last migration
python -m alembic current            # show the applied revision
python -m alembic check              # assert that the schema matches the models
```

---

## 10. Why the binaries are not stored in PostgreSQL

The PDF files are **not** stored in the database.  Only their metadata, their
SHA-256 hash and their storage key live in PostgreSQL; the bytes live in the
storage backend (the local file system today, behind the `StorageBackend`
protocol).

The reasons:

1. **Size.**  The seed corpus alone is about 19 MB of PDF; a real research
   corpus is measured in gigabytes.  `bytea` columns would bloat the heap,
   the WAL and every backup of the database.
2. **TOAST and backups.**  Large binary values are stored out of line in the
   TOAST tables, which makes the row statistics and the vacuum behaviour of
   the table much harder to reason about.
3. **Streaming.**  The extractor reads the file from the file system
   (PyMuPDF and pdfplumber both work on a path), and the upload endpoint
   streams the request body in 1 MiB chunks instead of buffering it.
4. **The seam.**  Because the bytes live behind the `StorageBackend` protocol,
   an S3 / Azure Blob / ADLS backend can replace the local file system
   without a change in the pipeline, the services or the schema.  The column
   `documents.storage_key` is the only thing that has to survive the move.
5. **The database stays the source of truth for the *metadata*.**  The rows
   describe the corpus, they do not carry it.
