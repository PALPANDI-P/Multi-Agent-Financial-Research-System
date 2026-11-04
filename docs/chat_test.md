# Chat Test Results

Workspace: `cfcbb76a-4112-49ee-b7c8-e7986c5bcf8f`
Document: Apple FY2025 10-K (`9326c1ea-4302-4d22-bda2-d5c93315f5be`), status: `completed`

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

Answer (grounded in retrieved evidence):
Facts:
- Note 2 – Revenue
The Company recognizes revenue at the amount to which it expects to be entitled when control of products or services is
transferred to its customers. Control is generally transferred when the Company has a present right to payment and title and the
significant risks and rewards of ownership of products or services are transferred to its customers. For most of the Company’s
Products net sales, control transfers when products are shipped. For the Company’s Services net sales, control transfers over
time as services are delivered. Payment for Products and Services net sales is collected within a short period following transfer
of control or commencement of delivery of services, as applicab
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

## Errors

None encountered.
