# Chat Test Results

Workspace: `90044e1b-5fa2-42f3-b86a-4b06cd9744f0`
Document: Apple FY2025 10-K (`03566384-4f8c-44db-b8c0-19a113b273a9`), status: `embedding`

## Q: What file formats are supported?

```
File formats
-----------
Only PDF documents are supported. The allow list is `.pdf` / `application/pdf` (see `allowed_document_extensions` and `allowed_mime_types` in `app/core/config.py`).
- The content of the file is authoritative: the `%PDF-` magic bytes decide whether the payload is a PDF at all; the client MIME type only corroborates it and a mismatch is reported as an issue.
- The file name only contributes the extension, which is checked against the allow list; it is never used to decide that a file is a PDF.
- A PDF is rejected when it cannot be opened, is encrypted, has no pages, or exceeds `max_pdf_pages` (default 2000).
- DOCX, XLSX and HTML are not implemented; the `DocumentExtractor` protocol is the seam they would be plugged into.

```

## Q: What is the maximum file size?

```
File size limits
----------------
The maximum upload size is configured by the `MAX_UPLOAD_SIZE_BYTES` setting/environment variable (default 52428800 bytes (~50MB / about 50 MB), in `app/core/config.py`).
- The request body is read in bounded chunks; a payload that is too large is rejected with HTTP 413 before it is fully buffered.
- The validator also enforces `max_pdf_pages` (default 2000) on the number of pages.
- An empty file is rejected with the `file_empty` issue.

```

## Q: Explain the processing flow.

```
Processing stages
-----------------
The pipeline moves through the explicit states
queued -> validating -> extracting -> chunking -> embedding -> indexing -> completed
and may end in `failed`.
Supplementary sub-stages recorded in `processing_stage` include `pdf_text`, `pdf_tables` and `ocr`.
- validating: file and PDF checks.
- extracting: PyMuPDF text + headings, pdfplumber tables, OCR for scanned pages (OCR is unavailable in this environment).
- chunking: section/table aware chunks, one chunk per table.
- embedding: fastembed `BAAI/bge-small-en-v1.5` (384 dimensions).
- indexing: pgvector upsert with HNSW index.
- completed/failed: terminal states; failures carry a stable error code and message.

```

## Q: What was revenue?

```
Research question: What was revenue?

Answer: The available indexed documents do not contain enough information to answer this question.

Missing information:
- No retrieved evidence found for: What was revenue?
- Financial metrics/calculations were not available to support numeric conclusions.
- Insufficient information in the indexed documents to answer the question.
```

## Q: Forecast revenue for next 2 periods

```
Forecasting
-----------
Implemented in `app/services/forecasting_service.py`.
- Methods: `naive`, `mean`, `linear`.
- Validates observations and reports issues before computing.
- Returns historical/forecast periods and values, assumptions, limitations, evaluation metrics and confidence intervals.
- Scenario analysis applies adjustments to a base forecast.

```
