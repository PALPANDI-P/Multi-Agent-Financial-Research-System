# E2E Test Report

- Base URL: http://localhost:8000/api/v1
- Started: 2026-11-04T16:41:09Z
- Finished: 2026-11-04T16:42:18Z

- User: e2e_806b603ad0@example.com
- Workspace ID: f7cb71c5-e8f6-4796-85b8-e75c519619d4
- Document ID: eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820
- Document status: completed

## register

- Method: POST
- Path: /auth/register
- Elapsed: 2145.48 ms
- Status: 201

```json
{
  "id": "9cced56c-7eaa-4b44-9036-d0180318d73a",
  "email": "e2e_806b603ad0@example.com",
  "full_name": "E2E Test User",
  "role": "analyst",
  "scenario_key": null,
  "created_at": "2026-11-04T22:11:11.764345+05:30",
  "last_login_at": null
}
```

## login

- Method: POST
- Path: /auth/login
- Elapsed: 63.09 ms
- Status: 200

```json
{
  "user": {
    "id": "9cced56c-7eaa-4b44-9036-d0180318d73a",
    "email": "e2e_806b603ad0@example.com",
    "full_name": "E2E Test User",
    "role": "analyst",
    "scenario_key": null
  },
  "expires_at": "2026-11-05T16:41:11.884792Z"
}
```

## create_workspace

- Method: POST
- Path: /workspaces
- Elapsed: 15.98 ms
- Status: 201

```json
{
  "id": "f7cb71c5-e8f6-4796-85b8-e75c519619d4",
  "name": "E2E Test",
  "description": null,
  "owner_id": "9cced56c-7eaa-4b44-9036-d0180318d73a",
  "document_count": 0,
  "created_at": "2026-11-04T22:11:11.906542+05:30",
  "updated_at": "2026-11-04T22:11:11.906542+05:30"
}
```

## upload_document

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/documents
- Elapsed: 238.51 ms
- Status: 201

```json
{
  "document_id": "eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820",
  "processing_status": "queued",
  "processing_stage": null,
  "content_hash": "3eb270b22acb7d8d8e9c32a43dc221dec3345f8e4bca02755fdbc1ee16c823de",
  "duplicate": false
}
```

## poll_document_status

- Method: GET
- Path: /documents/eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820
- Elapsed: 65530.38 ms
- Status: 200

```json
{
  "id": "eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820",
  "workspace_id": "f7cb71c5-e8f6-4796-85b8-e75c519619d4",
  "original_filename": "apple_fy2025_form_10k.pdf",
  "content_hash": "3eb270b22acb7d8d8e9c32a43dc221dec3345f8e4bca02755fdbc1ee16c823de",
  "file_size_bytes": 1858048,
  "mime_type": "application/pdf",
  "company_name": "Apple Inc.",
  "document_title": "FORM 10-K",
  "document_type": "form_10k",
  "fiscal_period": "FY2025",
  "source_url": null,
  "page_count": 80,
  "processing_status": "completed",
  "processing_stage": "completed",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-04T22:11:12.141077+05:30",
  "updated_at": "2026-11-04T22:12:17.624144+05:30",
  "processed_at": "2026-11-04T22:12:17.611533+05:30",
  "chunk_count": 357
}
```

## search

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/search
- Elapsed: 83.5 ms
- Status: 200

```json
{
  "query": "revenue",
  "workspace_id": "f7cb71c5-e8f6-4796-85b8-e75c519619d4",
  "total": 2,
  "results": [
    {
      "chunk_id": "32f2c8fe-c234-467c-a5b5-269f77aec64e",
      "document_id": "eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820",
      "document_title": "FORM 10-K",
      "company_name": "Apple Inc.",
      "document_type": "form_10k",
      "fiscal_period": "FY2025",
      "page_start": 38,
      "page_end": 38,
      "section_heading": "Note 2 – Revenue",
      "chunk_type": "text",
      "content": "Note 2 – Revenue\nThe Company recognizes revenue at the amount to which it expects to be entitled when control of products or services is\ntransferred to its customers. Control is generally transferred when the Company has a present right to payment and title and the\nsignificant risks and rewards of ownership of products or services are transferred to its customers. For most of the Company’s\nProducts net sales, control transfers when products are shipped. For the Company’s Services net sales, control transfers over\ntime as services are delivered. Payment for Products and Services net sales is collected within a short period following transfer\nof control or commencement of delivery of services, as applicable.\nThe Company records reductions to Products net sales related to future product returns, price protection and other customer\nincentive programs based on the Company’s expectations and historical experience.\nFor arrangements with multiple performance obligations, which represent promises within an arrangement that are distinct, the\nCompany allocates revenue to all distinct performance obligations based on their relative stand-alone selling prices (“SSPs”).\nWhen available, the Company uses observable prices to determine SSPs. When observable prices are not available, SSPs are\nestablished that reflect the Company’s best estimates of what the selling prices of the performance obligations would be if they\nwere sold regularly on a stand-alone basis. The Company’s process for estimating SSPs without observable prices considers\nmultiple factors that may vary depending upon the unique facts and circumstances related to each performance obligation\nincluding, where applicable, prices charged by the Company for similar offerings, market trends in the pricing for similar offerings,\nproduct-specific business objectives and the estimated cost to provide the performance obligation.\nThe Company has identified the performance obligations regularly included in arrangements involving the sale of iPhone, Mac\nand iPad. The first material performance obligation, which represents the substantial portion of the allocated sales price, is the\nhardware and bundled software delivered at the time of sale. The second material performance obligation is the right to receive\ncertain product-related bundled services, which include iCloud®, Siri® and Maps. The Company allocates revenue and any\nrelated discounts to all of its performance obligations based on their relative SSPs. Because the Company lacks observable\nprices for product-related bundled services, the allocation of revenue is based on the Company’s estimated SSPs. Revenue\nallocated to the delivered hardware and bundled software is recognized when control has transferred to the customer, which\ngenerally occurs when the product is shipped. Revenue allocated to product-related bundled services is deferred and recognized\non a straight-line basis over the estimated period they are expected to be provided.\nFor certain long-term service arrangements, the Company has",
      "score": 0.7319981615544474,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 38,
        "token_count": 512,
        "content_hash": "395976ae750ed55cc3e2d079d871bc0d5a567ea7c32207c9edb6ce3e5b89d08a",
        "section_index": 3,
        "page_has_table": false,
        "section_heading": "Note 2 – Revenue",
        "embedding_config_hash": "f279eb2e4167e12
... (truncated)
```

## red_flag_analysis

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/red-flags/analyze
- Elapsed: 209.69 ms
- Status: 200

```json
{
  "findings": [],
  "red_flags": [],
  "flags": [],
  "risks": [],
  "warnings": [],
  "errors": [],
  "workspace_id": "f7cb71c5-e8f6-4796-85b8-e75c519619d4",
  "document_id": "eb4607f2-0c87-4b97-a9ce-6b6cf7cd1820",
  "metrics_count": 0,
  "calculations_count": 0,
  "rules_evaluated": [
    "declining_revenue",
    "declining_margin",
    "rising_debt",
    "negative_cash_flow",
    "liquidity_issue"
  ],
  "summary": {
    "total": 0,
    "by_severity": {
      "low": 0,
      "medium": 0,
      "high": 0,
      "critical": 0
    }
  },
  "counts_by_severity": {
    "low": 0,
    "medium": 0,
    "high": 0,
    "critical": 0
  },
  "metadata": {
    "rules": [
      "declining_revenue",
      "declining_margin",
      "rising_debt",
      "negative_cash_flow",
      "liquidity_issue"
    ]
  }
}
```

## research

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/research
- Elapsed: 39.64 ms
- Status: 200

```json
{
  "question": "What was revenue?",
  "query": "What was revenue?",
  "research_question": "What was revenue?",
  "answer": "Research question: What was revenue?\n\nAnswer (grounded in retrieved evidence):\nFacts:\n- Note 2 – Revenue\nThe Company recognizes revenue at the amount to which it expects to be entitled when control of products or services is\ntransferred to its customers. Control is generally transferred when the Company has a present right to payment and title and the\nsignificant risks and rewards of ownership of products or services are transferred to its customers. For most of the Company’s\nProducts net sales, control transfers when products are shipped. For the Company’s Services net sales, control transfers over\ntime as services are delivered. Payment for Products and Services net sales is collected within a short period following transfer\nof control or commencement of delivery of services, as applicable.\nThe Company records reductions to Products net sales related to future product returns, price protection and other customer\nincentive programs based on the Company’s expectations and historical experience.\nFor arrangements with multiple performance obligations, which represent promises within an arrangement that are distinct, the\nCompany allocates revenue to all distinct performance obligations based on their relative stand-alone selling prices (“SSPs”).\nWhen available, the Company uses observable prices to determine SSPs. When observable prices are not available, SSPs are\nestablished that reflect the Company’s best estimates of what the selling prices of the performance obligations would be if they\nwere sold regularly on a stand-alone basis. The Company’s process for estimating SSPs without observable prices considers\nmultiple factors that may vary depending upon the unique facts and circumstances related to each performance obligation\nincluding, where applicable, prices charged by the Company for similar offerings, market trends in the pricing for similar offerings,\nproduct-specific business objectives and the estimated cost to provide the performance obligation.\nThe Company has identified the performance obligations regularly included in arrangements involving the sale of iPhone, Mac\nand iPad. The first material performance obligation, which represents the substantial portion of the allocated sales price, is the\nhardware and bundled software delivered at the time of sale. The second material performance obligation is the right to receive\ncertain product-related bundled services, which include iCloud®, Siri® and Maps. The Company allocates revenue and any\nrelated discounts to all of its performance obligations based on their relative SSPs. Because the Company lacks observable\nprices for product-related bundled services, the allocation of revenue is based on the Company’s estimated SSPs. Revenue\nallocated to the delivered hardware and bundled software is recognized when control has transferred to the customer, which\ngenerally occurs when the product is shipped. Revenue allocated to product-related bundled services is deferred and recognized\non a straight-line basis over the estimated period they are expected to be provided.\nFor certain long-term service arrangements, the Company has [1]\n- delivered hardware and bundled software is recognized when control has transferred to the customer, which\ngenerally occurs when the product is shipped. Revenue allocated to product-related bundled services is deferred and recognized\non a straight-line basis over the estimated period they are expected to be provided.\nFor certain long-term service arrangements, the Company has performance obligations for services it has not yet delivered. For\nthese arrangements, the Company does not have a right to bill for the undelivered services. The Company has determined that\nany unbilled consideration relates entirely to the value of the undelivered services. Accordingly, the Company has not recognized\nrev
... (truncated)
```

## forecast

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/forecasts
- Elapsed: 9.85 ms
- Status: 200

```json
{
  "method": "linear",
  "historical": [
    {
      "period": "2022",
      "value": 100.0
    },
    {
      "period": "2023",
      "value": 120.0
    },
    {
      "period": "2024",
      "value": 145.0
    }
  ],
  "forecast": [
    {
      "period": "2025",
      "value": 166.66666666666669,
      "lower": 161.50161315505835,
      "upper": 171.83172017827502
    },
    {
      "period": "2026",
      "value": 189.16666666666669,
      "lower": 182.3339431166384,
      "upper": 195.99939021669496
    }
  ],
  "historical_periods": [
    "2022",
    "2023",
    "2024"
  ],
  "historical_values": [
    100.0,
    120.0,
    145.0
  ],
  "forecast_periods": [
    "2025",
    "2026"
  ],
  "forecast_values": [
    166.66666666666669,
    189.16666666666669
  ],
  "periods": [
    "2025",
    "2026"
  ],
  "values": [
    166.66666666666669,
    189.16666666666669
  ],
  "assumptions": [
    "Observations are ordered chronologically by period.",
    "Values are numeric and finite.",
    "A linear trend fitted by ordinary least squares continues.",
    "Residuals are approximately normal for interval coverage."
  ],
  "limitations": [
    "The forecast extrapolates historical patterns and ignores external drivers.",
    "Sensitive to outliers and assumes a constant slope.",
    "Confidence intervals are residual-based approximations.",
    "Insufficient data for chronological holdout evaluation."
  ],
  "evaluation": null,
  "confidence_intervals": [
    [
      161.50161315505835,
      171.83172017827502
    ],
    [
      182.3339431166384,
      195.99939021669496
    ]
  ],
  "confidence_interval": [
    [
      161.50161315505835,
      171.83172017827502
    ],
    [
      182.3339431166384,
      195.99939021669496
    ]
  ],
  "ci": [
    [
      161.50161315505835,
      171.83172017827502
    ],
    [
      182.3339431166384,
      195.99939021669496
    ]
  ],
  "metric": "financial_metric",
  "source_count": 3,
  "metadata": {
    "metric": "financial_metric",
    "source_count": 3,
    "limitations": [
      "The forecast extrapolates historical patterns and ignores external drivers.",
      "Sensitive to outliers and assumes a constant slope.",
      "Confidence intervals are residual-based approximations.",
      "Insufficient data for chronological holdout evaluation."
    ]
  }
}
```

## export_csv

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/exports
- Elapsed: 11.76 ms
- Status: 200

```json
{
  "saved_to": "E:\\Multi-Agent Financial Research System\\var\\e2e\\e2e_metrics.csv",
  "bytes": 207,
  "content_type": "text/csv; charset=utf-8"
}
```

## export_json

- Method: POST
- Path: /workspaces/f7cb71c5-e8f6-4796-85b8-e75c519619d4/exports
- Elapsed: 9.78 ms
- Status: 200

```json
{
  "saved_to": "E:\\Multi-Agent Financial Research System\\var\\e2e\\e2e_metrics.json",
  "bytes": 2,
  "content_type": "application/json"
}
```

## Artifacts

- E:\Multi-Agent Financial Research System\var\e2e\e2e_metrics.csv
- E:\Multi-Agent Financial Research System\var\e2e\e2e_metrics.json
