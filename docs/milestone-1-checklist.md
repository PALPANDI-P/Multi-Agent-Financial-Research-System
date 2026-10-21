# Milestone 1 checklist

The status of every Milestone 1 requirement of the Multi-Agent Financial
Research System, with the evidence that supports it.

**The statuses**

| Status | Meaning |
| --- | --- |
| `Not started` | Nothing exists yet. |
| `In progress` | Something exists, but it is incomplete or not usable. |
| `Implemented` | The requirement is implemented, but **no test covers it** (or the evidence is a command, not a test). |
| `Tested` | A **specific, currently passing test** covers the requirement (or a specific command was executed and its real output is recorded). |
| `Blocked` | The requirement cannot be completed; the exact blocker is named. |

**The verification run behind this checklist**

| Command | Real output |
| --- | --- |
| `python -m pytest tests` (from `backend/`) | `333 passed, 1 warning in 38.85s (0:00:38)` |
| `python -m pytest tests/unit` | `215 passed in 2.91s` |
| `python -m pytest tests/integration` | `76 passed in 11.71s` |
| `python -m pytest tests/api` | `42 passed, 1 warning in 11.15s` |
| `python -m ruff check app tests` | `All checks passed!` |
| `python -m alembic current` | `0002_expand_processing_status (head)` |

The one warning is the deprecation notice of Starlette about `httpx` in the
test client - it is emitted by the third party library, not by the project.

---

## A. Financial Document Research

| Requirement | Status | Evidence |
| --- | --- | --- |
| The system can accept a financial document (PDF) as input. | `Tested` | `backend/tests/api/test_documents.py::test_a_valid_pdf_is_uploaded_and_processed`; the validator itself is covered by `backend/tests/unit/test_validators.py::test_valid_pdf_passes`. |
| The document is validated before it is stored (content is authoritative, the MIME type and the file name are only corroborating). | `Tested` | `backend/tests/unit/test_validators.py::test_mismatched_declared_mime_type_is_flagged`, `::test_content_that_is_not_a_pdf_is_rejected`, `::test_text_extension_is_rejected`, `::test_encrypted_pdf_is_reported`. |
| The metadata of a document (company, title, document type, fiscal period) is detected. | `Tested` | `backend/tests/unit/test_document_metadata.py::test_build_document_metadata_populates_every_field`, `::test_company_name_is_taken_from_the_registrant_boilerplate`, `::test_a_form_10k_is_detected`, `::test_fiscal_year_of_a_january_period_end`. |
| The document is chunked so that it can be retrieved piece by piece. | `Tested` | `backend/tests/unit/test_chunking.py::test_long_page_is_split_into_multiple_chunks`, `::test_a_chunk_never_spans_two_pages`, `::test_a_chunk_never_spans_two_sections`. |
| The chunks are embedded so that they can be searched semantically. | `Tested` | `backend/tests/unit/test_embeddings.py::test_fastembed_provider_produces_real_embeddings` (the real ONNX model), `backend/tests/integration/test_document_agent.py::test_the_agent_processes_a_document_end_to_end`. |
| Every search hit points at its source (document, page range, section, chunk type). | `Tested` | `backend/tests/integration/test_search_service.py::test_search_hits_carry_the_document_and_chunk_metadata`; the schema is `backend/app/schemas/search.py::SearchResultItem`. |
| The result of a retrieval is usable as **evidence** for a later agent. | `Implemented` | The retrieval layer exists and is tested (`SearchService` + `SearchHit`), but **no agent consumes it yet** - see the "Agents that are not implemented" rows below. |
| OCR of scanned documents. | `Blocked` | Blocked by the machine: neither the `pytesseract` package nor the `tesseract` executable is installed, and `OCR_ENABLED=false` by default. The system reports the situation honestly instead of failing: `backend/tests/unit/test_extractors.py::test_ocr_is_not_available_on_this_machine`, `::test_ocr_raises_when_it_is_not_configured`, `backend/tests/unit/test_validators.py::test_scanned_document_without_ocr_is_flagged`. |

## B. Architecture

| Requirement | Status | Evidence |
| --- | --- | --- |
| A layered backend (API, services, repositories, ingestion, embeddings, vector store, agents, core). | `Tested` | The layering is enforced by a test: `backend/tests/unit/test_import_hygiene.py::test_app_import_graph_is_acyclic`, `::test_importing_chunking_does_not_import_extractors`, `::test_every_app_module_imports`. |
| The ingestion pipeline does not depend on the services or the repositories (it only uses protocols). | `Tested` | `backend/tests/unit/test_pipeline.py::test_the_pipeline_module_does_not_import_the_services_or_the_repositories`. |
| The replaceable components are defined as protocols (`VectorStore`, `EmbeddingProvider`, `Chunker`, `DocumentExtractor`, `DocumentProcessor`, `StorageBackend`). | `Tested` | `backend/tests/unit/test_vectorstore.py::test_in_memory_store_satisfies_the_protocol`, `backend/tests/unit/test_embeddings.py::test_stub_provider_satisfies_the_protocol`, `backend/tests/unit/test_chunking.py::test_chunker_satisfies_the_chunker_protocol`, `backend/tests/unit/test_extractors.py::test_extractor_implements_the_protocol`, `backend/tests/unit/test_storage.py::test_local_storage_satisfies_the_protocol`. |
| The storage backend is replaceable (the object storage seam). | `Tested` | `backend/tests/unit/test_storage.py::test_create_storage_backend_returns_local_storage`, `::test_create_storage_backend_rejects_other_providers`. |
| A single, stable error contract with a machine readable code and a request id. | `Tested` | `backend/tests/api/test_health.py::test_an_unexpected_error_is_reported_generically`, `::test_the_request_id_is_returned_in_the_header`. |
| Structured logging that never leaks a secret. | `Tested` | `backend/tests/api/test_health.py::test_the_health_endpoint_never_leaks_a_credential`. |
| The configuration is validated at startup and refuses an unsafe production configuration. | `Implemented` | `backend/app/core/config.py::validate_runtime_settings` (checked at startup by `backend/app/main.py::create_app`). **Not covered by a test** - there is no test module for `app.core.config`. |
| A background worker that does not block the upload request. | `Tested` | `backend/tests/integration/test_document_agent.py::test_the_background_runner_processes_a_document_in_a_thread`. |
| A **durable** job queue. | `Not started` | There is no durable queue in this milestone: `BackgroundThreadJobRunner` uses an in-process `queue.Queue` and a queued job is lost when the process exits (`backend/app/agents/job_runner.py`). The mitigation is the recovery at startup (`run_pending()`), covered by `backend/tests/integration/test_document_agent.py::test_the_inline_runner_processes_the_queued_documents`. |
| Microservices / a distributed deployment. | `Not started` | Deliberately out of scope for Milestone 1 - the rationale is documented in `docs/architecture.md`, section 7. |

## C. Workspace & Session Management

| Requirement | Status | Evidence |
| --- | --- | --- |
| A workspace can be created, read, updated, listed and deleted. | `Tested` | `backend/tests/api/test_workspaces.py::test_a_workspace_is_created`, `::test_a_single_workspace_is_returned`, `::test_a_workspace_is_renamed`, `::test_the_workspaces_are_listed`, `::test_a_workspace_is_deleted`. |
| The workspaces can be paginated and filtered by name. | `Tested` | `backend/tests/api/test_workspaces.py::test_the_workspaces_are_paginated`, `::test_the_workspaces_can_be_filtered_by_name`. |
| A partial update leaves an omitted field untouched; an explicit `null` clears a field. | `Tested` | `backend/tests/api/test_workspaces.py::test_a_patch_leaves_an_omitted_field_untouched`, `::test_a_patch_clears_the_description`. |
| Deleting a workspace removes its documents, their chunks and their jobs, and their files. | `Tested` | `backend/tests/integration/test_workspace_repository.py::test_delete_workspace_removes_the_documents_and_the_files`, `::test_delete_workspace_keeps_the_database_consistent_when_a_file_is_missing`. |
| The workspace name is validated. | `Tested` | `backend/tests/api/test_workspaces.py::test_a_workspace_without_a_name_is_rejected`, `backend/tests/integration/test_workspace_repository.py::test_create_workspace_rejects_an_empty_name`, `::test_create_workspace_rejects_a_too_long_name`. |
| The document count of a workspace is computed with one grouped query (no N+1). | `Tested` | `backend/tests/integration/test_workspace_repository.py::test_count_documents_uses_one_grouped_query`, `::test_list_workspaces_does_not_issue_an_n_plus_one_query`. |
| **Session management** (authentication, sessions, multi-user isolation). | `Not started` | Milestone 1 has no authentication. `workspaces.owner_id` is **reserved and always NULL**; the API is unauthenticated. This is a known limitation of the milestone, documented in the README and in `docs/api-reference.md`, section 8. |

## D. Document Agent

| Requirement | Status | Evidence |
| --- | --- | --- |
| A document can be uploaded into a workspace and is registered with a processing job. | `Tested` | `backend/tests/integration/test_document_service.py::test_register_upload_creates_the_document_and_its_job`, `backend/tests/api/test_documents.py::test_a_valid_pdf_is_uploaded_and_processed`. |
| The upload is validated, and every reason of a rejection is reported. | `Tested` | `backend/tests/api/test_documents.py::test_a_file_that_is_not_a_pdf_is_rejected`, `::test_an_empty_file_is_rejected`, `::test_an_oversized_upload_is_rejected`. |
| The same document is not registered twice (the content hash is the contract). | `Tested` | `backend/tests/api/test_documents.py::test_the_same_document_twice_is_a_duplicate`, `backend/tests/integration/test_document_service.py::test_a_duplicate_upload_returns_the_same_document`, `::test_the_same_bytes_in_another_workspace_are_not_a_duplicate`. |
| The document is processed by a Document Agent that owns the job and the attempt. | `Tested` | `backend/tests/integration/test_document_agent.py::test_the_agent_processes_a_document_end_to_end`. |
| The processing state is visible (8 states, `documents.processing_status` is authoritative). | `Tested` | `backend/tests/unit/test_pipeline.py::test_the_pipeline_reports_every_stage_in_order`, `backend/tests/integration/test_document_service.py::test_report_status_updates_the_document`, `::test_report_status_records_the_error_and_clears_it_again`. |
| A failed document can be retried. | `Tested` | `backend/tests/api/test_documents.py::test_a_failed_document_is_retried`, `backend/tests/integration/test_document_agent.py::test_a_failed_document_can_be_retried_and_completes`, `backend/tests/integration/test_document_service.py::test_retry_document_creates_a_new_queued_job`. |
| A document that is not failed cannot be retried. | `Tested` | `backend/tests/api/test_documents.py::test_a_completed_document_can_not_be_retried`, `backend/tests/integration/test_document_service.py::test_retry_document_rejects_a_document_that_is_not_failed`. |
| A failed attempt records the error code, the error message and the attempt count. | `Tested` | `backend/tests/integration/test_document_agent.py::test_a_failing_pipeline_marks_the_document_as_failed`, `backend/tests/integration/test_document_service.py::test_the_job_repository_reports_the_attempts`. |
| The stored file is removed again when the database write fails (compensating action). | `Tested` | `backend/tests/integration/test_document_service.py::test_a_failing_database_write_removes_the_stored_file`. |
| A document can be deleted together with its chunks. | `Tested` | `backend/tests/api/test_documents.py::test_a_document_is_deleted_with_its_chunks`, `backend/tests/integration/test_document_service.py::test_delete_document_removes_the_rows_and_the_file`. |
| The uploaded file is written to a replaceable storage backend with a safe key and atomic writes. | `Tested` | `backend/tests/unit/test_storage.py::test_saved_key_has_the_documented_shape`, `::test_save_never_uses_the_callers_filename`, `::test_path_for_rejects_escaping_keys`, `::test_save_and_read_round_trip`. |

## E. Seed Company Documents

| Requirement | Status | Evidence |
| --- | --- | --- |
| A manifest pins the seed corpus (source URL, SHA-256, metadata, search probe). | `Tested` | `backend/tests/unit/test_seed_manifest.py::test_the_real_manifest_passes_the_validation`, `::test_the_sha256_is_64_hexadecimal_characters`, `::test_the_source_url_uses_https`, `::test_the_four_expected_companies_are_present`. |
| The loader downloads the documents, registers them and runs the real pipeline. | `Implemented` | `backend/scripts/seed_documents.py`. The corpus is **present in the development database** (4 documents, 2161 chunks, all `completed`) - verified by the executed command `python -m scripts.verify_index --workspace "Seed Documents"` and by the direct SQL query of the development database. **There is no test that runs the download** - the loader needs the network. |
| The loader is idempotent (a document that is already present is not ingested again). | `Implemented` | `backend/scripts/seed_documents.py::seed_document` (the `duplicate` branch and the `--force` flag). **Not covered by a test** - the branch requires a populated database. |
| The SEC requires a `User-Agent` header. | `Implemented` | `backend/scripts/seed_documents.py::download_document` sets `User-Agent` (the manifest pins one per document). **Not covered by a test** - the download needs the network. |
| The verification script proves the integrity of the seeded corpus and the retrieval. | `Implemented` | `backend/scripts/verify_index.py` - executed against the development database, all checks passed. **Not covered by a test** - it needs the seeded corpus. |
| The four seed documents are the ones of the specification (Walmart, JPMorgan Chase, Netflix, Apple). | `Tested` | `backend/tests/unit/test_seed_manifest.py::test_the_four_expected_companies_are_present`; the live database holds exactly these four documents with the pinned fiscal periods (`FY2026`, `FY2025`, `FY2025`, `FY2025`) and page counts (100, 167, 122, 80). |

## F. Searchable Document Index

| Requirement | Status | Evidence |
| --- | --- | --- |
| The chunks are stored with their embedding in PostgreSQL/pgvector. | `Tested` | `backend/tests/integration/test_pgvector_store.py::test_upsert_writes_rows`, `::test_upsert_is_idempotent`. |
| The vectors are stored in a `vector(384)` column with an HNSW index. | `Implemented` | The column and the index are created by `backend/migrations/versions/0001_initial.py`; the live schema was inspected: `ix_document_chunks_embedding_hnsw ... USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`. **No test asserts the index definition** - the tests assert the *behaviour* (the search finds the nearer vector). |
| A semantic search returns the chunks of a workspace, ordered by similarity. | `Tested` | `backend/tests/integration/test_search_service.py::test_search_returns_the_hits_in_descending_score_order`, `backend/tests/integration/test_pgvector_store.py::test_search_returns_the_nearer_vector_first`, `backend/tests/api/test_search.py::test_a_search_finds_the_uploaded_document`. |
| The search is scoped to the workspace, **in SQL**. | `Tested` | `backend/tests/integration/test_pgvector_store.py::test_search_never_leaks_another_workspace`, `backend/tests/integration/test_search_service.py::test_search_never_leaks_another_workspace`, `backend/tests/api/test_search.py::test_a_document_of_another_workspace_is_never_returned`. |
| The search can be narrowed down by document ids and by chunk type. | `Tested` | `backend/tests/integration/test_search_service.py::test_search_can_be_narrowed_down_by_document_ids`, `::test_search_can_be_narrowed_down_by_chunk_types`, `backend/tests/integration/test_pgvector_store.py::test_search_filters_by_document_ids`, `::test_search_filters_by_chunk_types`. |
| The search limit is validated and clamped. | `Tested` | `backend/tests/integration/test_search_service.py::test_search_clamps_the_limit_to_the_configured_maximum`, `::test_search_uses_the_configured_default_limit`, `backend/tests/api/test_search.py::test_the_limit_of_a_search_is_clamped`, `::test_a_limit_below_one_is_rejected`. |
| The tables of a document are indexed as their own chunks. | `Tested` | `backend/tests/unit/test_chunking.py::test_table_becomes_exactly_one_chunk`, `::test_table_chunk_keeps_caption_units_and_every_row`; the live corpus holds 1786 text chunks and 375 table chunks. |
| The embedding configuration is tracked and a vector is only reused while it matches. | `Tested` | `backend/tests/unit/test_embeddings.py::test_config_hash_changes_when_the_model_id_changes`, `::test_embed_texts_reusing_reuses_a_matching_vector`, `::test_embed_texts_reusing_reembeds_when_the_config_hash_differs`. |

## G. Tech stack

| Requirement | Status | Evidence |
| --- | --- | --- |
| Python 3.12 backend. | `Implemented` | `backend/pyproject.toml` (`requires-python = ">=3.12"`, `target-version = "py312"`). The interpreter of the venv is Python 3.12. |
| FastAPI + uvicorn. | `Tested` | `backend/app/main.py::create_app`; the API tests drive the real application through the Starlette test client (`backend/tests/api/conftest.py`). |
| SQLAlchemy 2.0 + psycopg 3. | `Tested` | The integration tests run against a real PostgreSQL server (`backend/tests/integration/`). |
| PostgreSQL 16 with the pgvector extension. | `Tested` | The development database reports `vector 0.8.6`; the integration tests use the pgvector store (`backend/tests/integration/test_pgvector_store.py`). |
| Alembic migrations (no `create_all`). | `Implemented` | `backend/migrations/versions/0001_initial.py`, `backend/migrations/versions/0002_expand_processing_status.py`; `python -m alembic current` reports `0002_expand_processing_status (head)`. **No test asserts the migration result** - the schema of the test database is prepared out of band. |
| PyMuPDF (text) and pdfplumber (tables). | `Tested` | `backend/tests/unit/test_extractors.py::test_extract_returns_the_text_of_the_page`, `::test_headings_are_detected`, `::test_tables_are_extracted`, `::test_table_extraction_degrades_gracefully`. |
| A local ONNX embedding model (`fastembed`, `BAAI/bge-small-en-v1.5`, 384 dimensions). | `Tested` | `backend/tests/unit/test_embeddings.py::test_fastembed_provider_produces_real_embeddings`. |
| React 19 + TypeScript + Vite frontend. | `Implemented` | `frontend/package.json`. **Not covered by a Python test** - the frontend has its own toolchain (`npm run lint`, `npm run typecheck`); no test suite exists for it in this milestone. |
| Docker / docker compose deployment. | `Implemented` | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`. **The stack was NEVER EXECUTED**: Docker is not installed on the development machine (no `docker` on PATH, no Docker Desktop, no WSL), therefore `docker compose config` fails with `The term 'docker' is not recognized`. Only the YAML syntax was validated (`yaml.safe_load`). |

## H. API

| Requirement | Status | Evidence |
| --- | --- | --- |
| A versioned REST API under `/api/v1`. | `Tested` | `backend/app/api/router.py`, `backend/app/main.py::create_app`; every endpoint is exercised by `backend/tests/api/`. |
| Workspace CRUD endpoints. | `Tested` | `backend/tests/api/test_workspaces.py` (12 tests). |
| Document upload, list, read, retry and delete endpoints. | `Tested` | `backend/tests/api/test_documents.py` (15 tests). |
| A search endpoint that returns cited hits. | `Tested` | `backend/tests/api/test_search.py` (9 tests). |
| A health endpoint that reports the state of the dependencies without leaking a secret. | `Tested` | `backend/tests/api/test_health.py::test_the_health_endpoint_reports_the_state_of_the_service`, `::test_the_health_endpoint_checks_every_dependency`, `::test_the_health_endpoint_never_leaks_a_credential`. |
| A standard error envelope with a stable code. | `Tested` | `backend/app/api/errors.py`; the generic 500 handler is covered by `backend/tests/api/test_health.py::test_an_unexpected_error_is_reported_generically`. |
| A request size limit. | `Tested` | `backend/tests/api/test_documents.py::test_an_oversized_upload_is_rejected`. |
| An `X-Request-ID` header. | `Tested` | `backend/tests/api/test_health.py::test_the_request_id_is_returned_in_the_header`. |
| Pagination on the list endpoints. | `Tested` | `backend/tests/api/test_workspaces.py::test_the_workspaces_are_paginated`, `backend/tests/integration/test_document_service.py::test_list_documents_supports_pagination_and_filters`. |
| The OpenAPI document and the interactive documentation. | `Implemented` | FastAPI serves `/docs` and `/openapi.json` automatically (`backend/app/main.py`). **Not covered by a test** - no test asserts the OpenAPI schema. |
| Authentication / authorisation of the API. | `Not started` | Milestone 1 has no authentication; the API is unauthenticated and therefore has no multi-user isolation. Documented in the README and in `docs/api-reference.md`, section 8. |

## I. Configuration

| Requirement | Status | Evidence |
| --- | --- | --- |
| Every setting is overridable from the environment with the UPPER_SNAKE_CASE name. | `Implemented` | `backend/app/core/config.py::Settings` (empty `env_prefix`); `backend/.env.example` lists **all** 38 settings of the model. **Not covered by a test** - there is no test module for `app.core.config`. |
| The configuration is read from `backend/.env` independently of the working directory. | `Implemented` | `backend/app/core/config.py::ENV_FILE` (anchored at the `backend/` directory). **Not covered by a test**. |
| List valued settings are parsed as JSON arrays. | `Implemented` | `backend/app/core/config.py` (pydantic-settings JSON parsing); `backend/.env.example` documents the syntax. **Not covered by a test**. |
| The configuration is validated at startup and the application refuses to start with an unsafe one. | `Implemented` | `backend/app/core/config.py::validate_runtime_settings`, called by `backend/app/main.py::create_app`. **Not covered by a test**. |
| A production configuration is refused when it still uses the development credentials, `DEBUG=true` or `CORS_ORIGINS=["*"]`. | `Implemented` | `backend/app/core/config.py::validate_runtime_settings`. **Not covered by a test**. |
| A template file for the configuration exists. | `Implemented` | `backend/.env.example` (the backend) and `.env.example` (the repository root, for the compose stack). **Not covered by a test**. |

## J. Testing

| Requirement | Status | Evidence |
| --- | --- | --- |
| The test suite runs with one command and passes. | `Tested` | `python -m pytest tests` -> `333 passed, 1 warning in 98.74s (0:01:38)`. |
| Unit tests (fast, isolated, no database). | `Tested` | `python -m pytest tests/unit` -> `215 passed in 6.75s`. |
| Integration tests against a **real** PostgreSQL with pgvector. | `Tested` | `python -m pytest tests/integration` -> `76 passed in 607.97s (0:10:07)`; the test database is `financial_research_test` (`backend/tests/conftest.py`). |
| API tests against the real application (real services, real extraction, real model, real database). | `Tested` | `python -m pytest tests/api` -> `42 passed`; `backend/tests/api/conftest.py`. |
| The linter is clean. | `Tested` | `python -m ruff check app tests` -> `All checks passed!`. |
| The test database is left empty after a run. | `Tested` | `backend/tests/integration/test_document_agent.py::test_the_test_database_is_left_empty`; the `clean_database` fixture truncates the tables before and after every integration test. |
| A test for the frontend. | `Not started` | The frontend has no test runner in this milestone - only `npm run lint` and `npm run typecheck`. |
| A CI pipeline. | `Not started` | There is no CI configuration in the repository. The commands that a CI would run are listed in the "How to reproduce" section below. |

## K. Documentation

| Requirement | Status | Evidence |
| --- | --- | --- |
| A `README.md` with the setup, the commands and the known limitations. | `Implemented` | `README.md` (this milestone, written in Wave 6B). |
| An architecture document. | `Implemented` | `docs/architecture.md`. |
| A database schema document. | `Implemented` | `docs/database-schema.md` (every column, every index and every constraint, read from the live database). |
| An ingestion pipeline document. | `Implemented` | `docs/ingestion-pipeline.md`. |
| An API reference. | `Implemented` | `docs/api-reference.md`; the authoritative, machine readable version is the OpenAPI document that FastAPI serves at `/openapi.json`. |
| A milestone checklist. | `Implemented` | `docs/milestone-1-checklist.md` (this file). |

---

## The agents that are NOT implemented

Milestone 1 delivers the **retrieval and evidence foundation** only.  The
following agents of the specification are **not implemented** - there is no
code, no test and no configuration for them:

| Agent | Status | Notes |
| --- | --- | --- |
| Extraction Agent (structured financial data extraction) | `Not started` | The chunks carry the text and the provenance; no structured field extraction exists. |
| Red Flag Agent (risk / anomaly detection) | `Not started` | – |
| Comparison Agent (cross document comparison) | `Not started` | – |
| Research Agent (iterative, tool using research) | `Not started` | The `SearchService` it would consume exists and is tested; the agent itself does not. |
| Report Agent (report generation) | `Not started` | – |
| Multi agent orchestration / a durable queue | `Not started` | See the rows above. |

---

## How to reproduce the evidence

All commands are executed from the `backend/` directory with the project
virtual environment:

```powershell
cd "E:\Multi-Agent Financial Research System\backend"
$py = ".\.venv\Scripts\python.exe"
```

### The whole suite

```powershell
& $py -m pytest tests
# 333 passed, 1 warning in 38.85s (0:00:38)
```

### Per group

```powershell
& $py -m pytest tests/unit --override-ini "addopts=--strict-markers"
# 215 passed in 2.91s

& $py -m pytest tests/integration --override-ini "addopts=--strict-markers"
# 76 passed in 11.71s

& $py -m pytest tests/api --override-ini "addopts=--strict-markers"
# 42 passed, 1 warning in 11.15s
```

> **Why `--override-ini "addopts=--strict-markers"`?**  `backend/pyproject.toml`
> already sets `addopts = "-q --strict-markers"`.  Adding a second `-q` on the
> command line turns it into `-qq`, which **suppresses the summary line** -
> the run then ends with the progress dots and no "N passed" line.  The
> override replaces the `-q` with nothing, so that the summary is printed.

### The linter

```powershell
& $py -m ruff check app tests
# All checks passed!
```

### The migration state and the schema

```powershell
& $py -m alembic current
# 0002_expand_processing_status (head)

& $py -m alembic check
# No new upgrade operations detected.
```

### The seeded corpus

```powershell
& $py -m scripts.verify_index --workspace "Seed Documents"
# PASS: all 4 document(s) passed the verification
```

### The compose file

```powershell
docker compose config
# docker : The term 'docker' is not recognized as the name of a cmdlet,
# function, script file, or operable program.
```

Docker is **not installed** on the development machine, therefore the compose
stack could not be validated with the Docker CLI.  The YAML syntax was
validated instead:

```powershell
& $py -c "import yaml; yaml.safe_load(open('docker-compose.yml', encoding='utf-8'))"
# (no output - the file parses)
```

### The frontend

```powershell
cd "E:\Multi-Agent Financial Research System\frontend"
npm install
npm run lint
npm run typecheck
```
