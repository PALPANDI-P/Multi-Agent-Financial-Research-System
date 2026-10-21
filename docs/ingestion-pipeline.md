# The ingestion pipeline

The ingestion pipeline turns a stored PDF into indexed, searchable chunks.  It
is implemented in `backend/app/ingestion/pipeline.py` and is orchestrated by
the `DocumentAgent` (`backend/app/agents/document_agent.py`).

---

## 1. The eight stages

The pipeline reports the state of the document after **every** stage, so that
the API (and a human) always sees where the processing stands.

| # | `processing_status` | `processing_stage` | What happens | Implemented by | What can fail |
| --- | --- | --- | --- | --- | --- |
| 1 | `validating` | `validating` | The stored bytes are read back and **re-validated** against the upload rules (the file system is outside the trust boundary of the application). The SHA-256 of the bytes is compared with the recorded `content_hash`; a mismatch is recorded as a warning, not as an error. | `FileValidator` (`backend/app/ingestion/validators.py`) | The file is missing (`storage_not_found`), unreadable (`storage_read_failed`), not a PDF any more (`invalid_stored_document`), encrypted (`pdf_encrypted`), too large, too many pages or a scan without OCR. |
| 2 | `extracting` | `pdf_text` | The text layer of every page is read with PyMuPDF, the headings are detected and the pages with (almost) no text are flagged. | `PyMuPdfTextExtractor` (`backend/app/ingestion/extractors/pdf_text.py`) | The PDF cannot be opened (`pdf_unreadable`), it is password protected (`pdf_encrypted`). A single broken page is a warning, not an error. |
| 3 | `extracting` | `pdf_tables` | The tables of the PDF are read with pdfplumber and attached to the page they belong to. | `PdfPlumberTableExtractor` (`backend/app/ingestion/extractors/pdf_tables.py`) | **Best effort**: every failure is logged and swallowed, the pipeline continues with the text layer. A missing pdfplumber is a warning as well. |
| 4 | `extracting` | `ocr` | The pages whose text layer holds fewer than `MIN_TEXT_CHARS_PER_PAGE` characters are routed to the OCR extractor. | `OcrExtractor` (`backend/app/ingestion/extractors/ocr.py`) | When OCR is not available the page is left untouched and a warning is recorded - the text is **never** fabricated. |
| 5 | `chunking` | `chunking` | The extracted document is split into chunks and the metadata of the document is detected. | `TokenAwareChunker` (`backend/app/ingestion/chunking.py`), `build_document_metadata()` (`backend/app/ingestion/metadata.py`) | An invalid configuration of the chunker (`ValueError`). A document without any text produces zero chunks - that is not an error. |
| 6 | `embedding` | `embedding` | The chunks are embedded. The vectors that were already computed for the same content **and** the same embedding configuration are reused. | `EmbeddingService` (`backend/app/embeddings/service.py`) | A transient provider failure is retried; a validation failure is not. The final error is an `EmbeddingError` (`embedding_provider_error`, `embedding_count_mismatch`, `embedding_dimension_mismatch`, `embedding_non_finite_value`, `embedding_degenerate_vector`, `embedding_timeout`). |
| 7 | `indexing` | `indexing` | The chunks of the document are deleted and written again with an idempotent upsert. | `PgVectorStore` (`backend/app/vectorstore/pgvector_store.py`) | A wrong dimension (`embedding_dimension_mismatch`), a non finite value (`embedding_not_finite`), an unknown chunk type (`invalid_chunk_type`), metadata that is not JSON serialisable (`invalid_metadata`) or a database error. |
| 8 | `completed` | `completed` | Everything is done; `processed_at` is stamped. | `DocumentRepository.set_status()` | – |

**A failure never leaves a document in a non-terminal state.**  Every
exception is reported as `failed` (with an error code and a concise, secret
free message) before it is re-raised.

---

## 2. Supported formats

| Format | Status | Notes |
| --- | --- | --- |
| PDF with a text layer | **Supported and verified** | The four seed documents (Walmart FY2026 10-K, JPMorgan Chase FY2025 audited financial statements, Netflix FY2025 10-K, Apple FY2025 10-K) were extracted, chunked, embedded and indexed with this path. |
| PDF whose pages are scans | **Detected, not extracted** | See below. |

`ALLOWED_DOCUMENT_EXTENSIONS` and `ALLOWED_MIME_TYPES` restrict the uploads to
`.pdf` / `application/pdf`.  The **content** of the file decides whether it is
a PDF at all: the `%PDF-` marker has to appear in the first kilobyte and
PyMuPDF has to be able to open the document.  The announced MIME type is only
a corroborating signal - a mismatch is reported as an issue, it never
overrules the sniffed content.

### OCR is not available on the development machine

OCR needs **two** things: the Python package `pytesseract` and the
`tesseract` executable.  Neither is installed on the development machine, so
`OcrExtractor.is_available()` reports:

```
OCR is not available: the Python package 'pytesseract' is not installed;
the 'tesseract' executable was not found on PATH.
```

The consequences are honest and visible:

* A **document** whose every page has fewer than `MIN_TEXT_CHARS_PER_PAGE`
  characters of text is rejected by the validation with the issue code
  `scanned_document_ocr_unavailable` (`422`).
* A **single page** inside an otherwise readable document is not an error: the
  pipeline records the warning
  `page <n>: scanned content could not be extracted (ocr unavailable)` and
  continues.  The page keeps its (empty) text; **no text is ever
  fabricated**.
* `OcrExtractor.extract_page()` raises an `ExtractionError` with the stable
  code `ocr_unavailable` instead of returning an empty page, so a caller
  always knows whether the content was really read.
* `OCR_ENABLED=false` (the default) additionally switches the OCR off even
  when tesseract is installed.

---

## 3. Parsing behaviour

### 3.1 Text and heading detection (PyMuPDF)

`PyMuPdfTextExtractor` reads the text layer of every page with
`page.get_text("text")` and normalises the whitespace (trailing spaces are
removed, three or more consecutive newlines are collapsed into two).

A span is a **heading** when **either** of the two rules matches:

1. **The size rule.** The median font size of the page is computed and the
   threshold is `max(1.0, median_size * 1.15)`.  A span whose size exceeds
   the threshold is a heading.
2. **The bold rule.** The font name contains `bold`, `semibold` or `black`.

Additional rules for a candidate: at most 200 characters, not a pure number
(`1.234`, `$500` and `(42)` are rejected) and no duplicate (the comparison is
case insensitive).  At most 60 headings are reported per page.

**The outline merge.**  The bookmarks of the PDF (`document.get_toc()`) are
grouped by the page they start on and merged into the headings of that page.
A bookmark whose title is already a heading (case insensitive) is not added a
second time.  The result is therefore the union of the *typographic* headings
and the *structural* headings of the document.

### 3.2 Tables (pdfplumber)

`PdfPlumberTableExtractor` uses `page.find_tables()` and `table.extract()`.
The first row of a table is the header, the remaining rows are the body.  A
row whose cells are all empty is dropped, and the whitespace of every cell is
normalised.

Table extraction is **best effort**: a page whose tables cannot be read is
logged and skipped, a document that pdfplumber cannot open yields an empty
mapping.  The pipeline continues with the text layer of the document.

### 3.3 The per page low text threshold and the OCR routing

`MIN_TEXT_CHARS_PER_PAGE` (default 40) is the threshold that separates a
readable page from a scanned one.  It is used in three places:

* the **validator** flags a document whose *every* page is below the
  threshold as a scan that cannot be read (when OCR is unavailable),
* the **text extractor** adds the warning
  `page <n>: little or no extractable text (possible scanned page)` to every
  page below the threshold,
* the **pipeline** routes every page below the threshold to the OCR
  extractor.  When OCR is available the text of the page is replaced and the
  extraction method becomes `ocr`; when it is not, the page is left untouched
  and a warning is recorded.

---

## 4. Chunking strategy

### The token counter

`count_tokens(text)` counts the matches of `re.findall(r"\w+|[^\w\s]", text)`:
a token is either a maximal run of word characters or a single character that
is neither a word character nor whitespace.  It is an **approximation** of the
token count of a real language model, but it is deterministic, dependency free
and identical on every machine, which is what the reproducibility guarantees
of the chunker need.  The embedding model applies its own tokenizer
downstream.

### The budgets

| Setting | Default | Meaning |
| --- | --- | --- |
| `CHUNK_SIZE_TOKENS` | 512 | The maximum number of tokens of a window. |
| `CHUNK_OVERLAP_TOKENS` | 64 | The number of tokens two consecutive windows share. |
| `CHUNK_MIN_TOKENS` | 32 | Below this size a chunk is merged into its predecessor. |
| `CHUNK_MAX_TOKENS` | 1024 | The maximum size of a merged chunk. |

`ChunkerConfig` validates the combination at construction time: the size must
be positive, the overlap must be smaller than the size, the minimum must not
exceed the size and the maximum must not be smaller than the size.

### The boundaries

* **Page boundaries are sacred.**  A chunk never spans two pages, therefore
  `page_start == page_end == page_number` always holds.
* **Section boundaries are sacred.**  A chunk never mixes the content of two
  sections and every chunk carries the `section_heading` of its section
  (`NULL` for the leading, un-headed part of a page).  The headings are
  located case insensitively in the text of the page; a heading that cannot be
  located is ignored.
* **Tables are never shredded.**  Every extracted table becomes exactly one
  `table` chunk.  Table chunks are never merged and never dropped.

### The algorithm

For every page of the document, in document order:

1. The page text is split into sections at the page's headings.  The text
   before the first heading becomes a leading section with
   `section_heading = NULL`.
2. Every section is split into token windows of at most `CHUNK_SIZE_TOKENS`
   tokens that overlap by `CHUNK_OVERLAP_TOKENS` tokens.
3. Windows that are shorter than `CHUNK_MIN_TOKENS` are merged into the
   previous chunk of the same page when the merged result still fits into
   `CHUNK_MAX_TOKENS`; otherwise the short chunk is kept as-is, so that no
   content is lost.  The merged chunk keeps the heading of the predecessor and
   records the absorbed one in `metadata["merged_section_heading"]`.
4. The text chunks of the page are emitted first, followed by the table chunks
   of the page.  `chunk_index` is a global, 0-based counter over the whole
   document.

### The rendering of a table chunk

`render_table_chunk()` produces a verbose, self-contained text:

```
Table on page 42
Section: Consolidated Statements of Income
Caption: Net sales by segment
Units: Millions of US dollars
Columns: Segment | 2025 | 2024 | Change
Total revenue: 1234 | 1100 | 12.3%
```

* The header row becomes the **label of every cell**, so that a reader can map
  every value to its label without seeing the original page.
* An empty header cell falls back to the positional label `Column <n>`
  (1-based).
* The cell values are kept **verbatim** - numbers are never reformatted.
* The caption and the units are rendered when they exist.

The metadata of a table chunk carries `table_index` and `column_count` in
addition to the common keys.

---

## 5. Embedding configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | `fastembed` | The adapter. `test-hash` exists for the unit tests and is refused when `APP_ENV=production`. |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | The ONNX model that runs **locally** in the process. |
| `EMBEDDING_DIMENSION` | `384` | The expected length of every vector. It must match the dimension of the model - the factory rejects a mismatch with a `ConfigurationError`. |
| `EMBEDDING_BATCH_SIZE` | 32 | The number of texts that are handed to the model in one inference call. |
| `EMBEDDING_MAX_RETRIES` | 3 | The number of retries **after** the first attempt. |
| `EMBEDDING_TIMEOUT_SECONDS` | 60.0 | The total budget of the retry loop. |

### The validation rules

Every vector that leaves `EmbeddingService` has been checked:

| Rule | Error code |
| --- | --- |
| The number of vectors equals the number of texts. | `embedding_count_mismatch` |
| Every component is numeric. | `embedding_invalid_vector` |
| Every vector has exactly `EMBEDDING_DIMENSION` components. | `embedding_dimension_mismatch` |
| Every component is finite (no `NaN`, no `inf`). | `embedding_non_finite_value` |
| No vector is degenerate (its L2 norm is not zero). | `embedding_degenerate_vector` |

### The retry policy

Only **transient** provider failures are retried: an error whose code is
`embedding_provider_error`, `embedding_error` or unset.  The backoff is
exponential (0.5 s, 1 s, 2 s, ...) and has to fit into the remaining
`EMBEDDING_TIMEOUT_SECONDS` budget; when the budget is exhausted the error
`embedding_timeout` is raised.  A **validation** failure is never retried - a
wrong dimension will not fix itself.

### The reuse rule

A stored vector is reused only when **both** hashes match:

* the **content hash** - the SHA-256 of the text of the chunk, and
* the **configuration hash** - the SHA-256 of `"{model_id}|{dimension}"`,
  stored in `document_chunks.embedding_config_hash`.

The configuration hash therefore changes exactly when the previously stored
vectors become unusable (a different model or a different dimension).  The
pipeline reads the stored vectors of the document through the
`ExistingEmbeddingSource` protocol (`ChunkRepository.existing_embeddings()`)
and calls `embed_texts_reusing()`, which embeds only the missing texts - in
**one** call.

---

## 6. Indexing behaviour

1. `PgVectorStore.delete_document_chunks(document_id)` removes the chunks of
   the document.
2. `PgVectorStore.upsert_chunks(records)` writes the new chunks with

   ```sql
   INSERT INTO document_chunks (...) VALUES (...)
   ON CONFLICT (document_id, chunk_index) DO UPDATE SET ...
   ```

The **delete-then-upsert** order is what guarantees that a re-run of the
pipeline leaves exactly one chunk per `(document_id, chunk_index)`:

* the upsert alone is already idempotent, because the conflict target is the
  unique constraint `uq_document_chunks_document_chunk_index` - a re-run
  updates the existing rows instead of creating new ones,
* the delete before the upsert removes the chunks of a **previous** run that
  the current run does not produce any more (for example when the document
  shrank), so that no orphan chunk survives.

Every value of the statement is a bound parameter; nothing is interpolated
into the SQL text.  The optional `IN` lists use `bindparam(..., expanding=True)`.

The similarity search uses the HNSW index `ix_document_chunks_embedding_hnsw`
(`USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)`)
that the migration creates.  The workspace filter is part of the `WHERE`
clause, not a post filter:

```sql
SELECT ...
  FROM document_chunks
  JOIN documents ON documents.id = document_chunks.document_id
 WHERE documents.workspace_id = :workspace_id
 ORDER BY document_chunks.embedding <=> CAST(:query_embedding AS vector)
 LIMIT :limit
```

---

## 7. Retry and failure handling

### What is recorded

| Where | What |
| --- | --- |
| `documents.processing_status` | The authoritative state (`failed`). |
| `documents.processing_stage` | The stage that was running when the failure happened. |
| `documents.error_code` | The stable, fine grained diagnosis (for example `ocr_unavailable`, `embedding_dimension_mismatch`, `invalid_stored_document`). |
| `documents.error_message` | A concise, single line, secret free message. The pipeline collapses the whitespace and truncates it to 500 characters. |
| `processing_jobs.status` | `failed`. |
| `processing_jobs.error_code` / `error_message` | The same diagnosis on the job row. |
| `processing_jobs.attempt_count` | The number of attempts the document needed (incremented by `mark_running`). |
| `processing_jobs.started_at` / `completed_at` | The boundaries of the attempt. |
| The log | The full exception **with its stack trace** (`logger.exception`). |

The error code is derived by `error_code_of()`: the `error_code` attribute
wins (the fine grained diagnosis), then the `code` attribute (the stable
envelope code) and finally the name of the exception class.

### How a failed job is retried

`POST /api/v1/documents/{document_id}/retry`:

1. the document must exist (`404` otherwise) and must be in the state
   `failed` - any other state is rejected with `409` and the code
   `document_not_failed`,
2. a **new** job row is created with the status `queued` (its
   `attempt_count` starts at 0); the previous job row stays as the record of
   the failed attempt,
3. the document goes back to `queued` and its `error_code` /
   `error_message` are cleared (the repository clears them for every status
   that is not `failed`),
4. the job runner submits the document again.

The answer is `202` with `{document_id, job_id, attempt_count,
processing_status}`.

### The idempotency guarantees

* **Uploading the same bytes twice** into the same workspace returns the
  existing document with `duplicate: true`; no second file is written and no
  second job is created (the unique constraint
  `uq_documents_workspace_content_hash` is the last line of defence).
* **Running the pipeline twice** leaves exactly one chunk per
  `(document_id, chunk_index)`.
* **The status transitions are idempotent**: reporting the same status twice
  writes the same values.
* **A crash during the extraction** leaves the document in a non-terminal
  state, but the background runner recovers it: `run_pending()` rescans the
  database for the documents that are still `queued` and processes them
  again.

---

## 8. There is no durable queue

The background runner is an **in-process thread** that is fed by a
`queue.Queue`:

* a job that is queued is **lost when the process exits**,
* the queue lives in the memory of the process that created it,
* there is exactly one worker thread, therefore the documents are processed
  one after the other.

The mitigation is the recovery at startup (`run_pending()`), which finds the
documents that are still `queued` and processes them again.

A durable queue (Celery, RQ, Arq) becomes necessary when the corpus is
processed faster than one process can.  It can replace the runner without
touching the pipeline: the runner only has to call
`DocumentAgent.process(document_id)`.

`settings.processing_inline` selects the strategy: `true` processes the
document in the calling thread (the strategy of the scripts and of the
tests), `false` uses the background thread (the default of the setting).
