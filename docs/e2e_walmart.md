# E2E Test Report

- Base URL: http://localhost:8000/api/v1
- Started: 2026-11-04T17:19:37Z
- Finished: 2026-11-04T17:21:06Z

- User: e2e_c4477eee49@example.com
- Workspace ID: 3ae3c8b6-1dc2-4d1a-b7c0-42979c848255
- Document ID: b256eb5d-e792-4a6d-b212-5356c1f180c3
- Document status: completed

## register

- Method: POST
- Path: /auth/register
- Elapsed: 2160.98 ms
- Status: 201

```json
{
  "id": "9c5cdf91-cd49-4c38-b46c-4cb88b6043b4",
  "email": "e2e_c4477eee49@example.com",
  "full_name": "E2E Test User",
  "role": "analyst",
  "scenario_key": null,
  "created_at": "2026-11-04T22:49:40.044448+05:30",
  "last_login_at": null
}
```

## login

- Method: POST
- Path: /auth/login
- Elapsed: 86.34 ms
- Status: 200

```json
{
  "user": {
    "id": "9c5cdf91-cd49-4c38-b46c-4cb88b6043b4",
    "email": "e2e_c4477eee49@example.com",
    "full_name": "E2E Test User",
    "role": "analyst",
    "scenario_key": null
  },
  "expires_at": "2026-11-05T17:19:40.224112Z"
}
```

## create_workspace

- Method: POST
- Path: /workspaces
- Elapsed: 8.34 ms
- Status: 201

```json
{
  "id": "3ae3c8b6-1dc2-4d1a-b7c0-42979c848255",
  "name": "E2E Test",
  "description": null,
  "owner_id": "9c5cdf91-cd49-4c38-b46c-4cb88b6043b4",
  "document_count": 0,
  "created_at": "2026-11-04T22:49:40.244760+05:30",
  "updated_at": "2026-11-04T22:49:40.244760+05:30"
}
```

## upload_document

- Method: POST
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/documents
- Elapsed: 812.9 ms
- Status: 201

```json
{
  "document_id": "b256eb5d-e792-4a6d-b212-5356c1f180c3",
  "processing_status": "queued",
  "processing_stage": null,
  "content_hash": "550eaf563e00aa4862eb26f2a738b9c95968f3aa39e12f31e7076824e9ba9a8d",
  "duplicate": false
}
```

## poll_document_status

- Method: GET
- Path: /documents/b256eb5d-e792-4a6d-b212-5356c1f180c3
- Elapsed: 84994.26 ms
- Status: 200

```json
{
  "id": "b256eb5d-e792-4a6d-b212-5356c1f180c3",
  "workspace_id": "3ae3c8b6-1dc2-4d1a-b7c0-42979c848255",
  "original_filename": "walmart_fy2026_form_10k.pdf",
  "content_hash": "550eaf563e00aa4862eb26f2a738b9c95968f3aa39e12f31e7076824e9ba9a8d",
  "file_size_bytes": 14805939,
  "mime_type": "application/pdf",
  "company_name": "WALMART INC.",
  "document_title": "Annual Report",
  "document_type": "form_10k",
  "fiscal_period": "Q1 2026",
  "source_url": null,
  "page_count": 100,
  "processing_status": "completed",
  "processing_stage": "completed",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-04T22:49:41.050410+05:30",
  "updated_at": "2026-11-04T22:51:04.638425+05:30",
  "processed_at": "2026-11-04T22:51:04.617873+05:30",
  "chunk_count": 445
}
```

## search

- Method: POST
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/search
- Elapsed: 30.03 ms
- Status: 200

```json
{
  "query": "revenue",
  "workspace_id": "3ae3c8b6-1dc2-4d1a-b7c0-42979c848255",
  "total": 7,
  "results": [
    {
      "chunk_id": "68c4755b-b555-4e94-a4cb-1a1d8278909c",
      "document_id": "b256eb5d-e792-4a6d-b212-5356c1f180c3",
      "document_title": "Annual Report",
      "company_name": "WALMART INC.",
      "document_type": "form_10k",
      "fiscal_period": "Q1 2026",
      "page_start": 64,
      "page_end": 64,
      "section_heading": "Revenue Recognition",
      "chunk_type": "text",
      "content": "Revenue Recognition\nNet Sales\nThe Company recognizes sales revenue, net of sales taxes and estimated sales returns, at the time it sells merchandise or\nprovides services to the customer. eCommerce sales include shipping revenue and are recorded upon delivery to the customer.\nEstimated sales returns are calculated based on expected returns.\nFinancial, Advertising and Other Services\nThe Company recognizes revenue from service transactions at the time the service is performed. Generally, revenue from\nservices is classified as a component of net sales in the Company's Consolidated Statements of Income.\nMembership and Other Income\nMembership and other income primarily includes membership fee revenue associated with the Company's various membership\nofferings for customers and members across each reportable segment. Membership fee revenue is recognized over the term of\nthe membership, which are generally one year, although certain offerings are month-to month. Membership fee revenue was\n$4.4 billion, $3.8 billion and $3.1 billion for fiscal 2026, 2025 and 2024, respectively. Deferred membership fee revenue is\nincluded in accrued liabilities in the Company's Consolidated Balance Sheets. Additionally, membership and other income\nincludes items such as rental and tenant income, recycling income, and gift card breakage income.\nGift Cards\nCustomer purchases of gift cards are not recognized as sales until the card is redeemed and the customer purchases merchandise\nusing the gift card, thus a liability for deferred gift card revenue is recorded within accrued liabilities in the Consolidated\nBalance Sheets. Refer to Note 4. Gift cards in the U.S. and some countries do not carry an expiration date; therefore, customers\nand members can redeem their gift cards for merchandise and services indefinitely. Gift cards in some countries where the\nCompany does business have expiration dates. While gift cards are generally redeemed within 12 months, a certain number of\ngift cards, both with and without expiration dates, will not be fully redeemed. Management estimates unredeemed balances and\nrecognizes gift card breakage income for these amounts in membership and other income in the Company's Consolidated\nStatements of Income over the expected redemption period.",
      "score": 0.7415628587268093,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 64,
        "token_count": 393,
        "content_hash": "7724892b9c0c19a850d1398841f8e30c76db48cc04f56e82c2f866bf8538b19a",
        "section_index": 1,
        "page_has_table": false,
        "section_heading": "Revenue Recognition",
        "embedding_config_hash": "f279eb2e4167e121db4f5ef7cb0645333467e536c2c3b8d07223200a396351a5"
      }
    },
    {
      "chunk_id": "d0714910-efe5-4c21-bb8b-8cd71def7a24",
      "document_id": "b256eb5d-e792-4a6d-b212-5356c1f180c3",
      "document_title": "Annual Report",
      "company_name": "WALMART INC.",
      "document_type": "form_10k",
      "fiscal_period": "Q1 2026",
      "page_start": 54,
      "page_end": 54,
      "section_heading": "Revenues:",
      "chunk_type": "text",
      "content": "Revenues:\nNet sales\n$\n706,413\n$\n674,538\n$\n642,637\nMembership and other income\n\n6,750\n\n6,447\n\n5,488\nTotal revenues\n\n713,163\n\n680,985\n\n648,125",
      "score": 0.7271752682715387,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        
... (truncated)
```

## red_flag_analysis

- Method: POST
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/red-flags/analyze
- Elapsed: 11.31 ms
- Status: 200

```json
{
  "findings": [],
  "red_flags": [],
  "flags": [],
  "risks": [],
  "warnings": [],
  "errors": [],
  "workspace_id": "3ae3c8b6-1dc2-4d1a-b7c0-42979c848255",
  "document_id": "b256eb5d-e792-4a6d-b212-5356c1f180c3",
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
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/research
- Elapsed: 41.61 ms
- Status: 200

```json
{
  "question": "What was revenue?",
  "query": "What was revenue?",
  "research_question": "What was revenue?",
  "answer": "Research question: What was revenue?\n\nAnswer (grounded in retrieved evidence):\nFacts:\n- Our total revenues increased $32.2 billion or 4.7% and $32.9 billion or 5.1% for fiscal 2026 and 2025, respectively, when\ncompared to the previous fiscal year. These increases in revenues were primarily due to increases in net sales, which increased [1]\n- Revenues:\nNet sales\n$\n706,413\n$\n674,538\n$\n642,637\nMembership and other income\n\n6,750\n\n6,447\n\n5,488\nTotal revenues\n\n713,163\n\n680,985\n\n648,125 [2]\n- Revenue Recognition\nNet Sales\nThe Company recognizes sales revenue, net of sales taxes and estimated sales returns, at the time it sells merchandise or\nprovides services to the customer. eCommerce sales include shipping revenue and are recorded upon delivery to the customer.\nEstimated sales returns are calculated based on expected returns.\nFinancial, Advertising and Other Services\nThe Company recognizes revenue from service transactions at the time the service is performed. Generally, revenue from\nservices is classified as a component of net sales in the Company's Consolidated Statements of Income.\nMembership and Other Income\nMembership and other income primarily includes membership fee revenue associated with the Company's various membership\nofferings for customers and members across each reportable segment. Membership fee revenue is recognized over the term of\nthe membership, which are generally one year, although certain offerings are month-to month. Membership fee revenue was\n$4.4 billion, $3.8 billion and $3.1 billion for fiscal 2026, 2025 and 2024, respectively. Deferred membership fee revenue is\nincluded in accrued liabilities in the Company's Consolidated Balance Sheets. Additionally, membership and other income\nincludes items such as rental and tenant income, recycling income, and gift card breakage income.\nGift Cards\nCustomer purchases of gift cards are not recognized as sales until the card is redeemed and the customer purchases merchandise\nusing the gift card, thus a liability for deferred gift card revenue is recorded within accrued liabilities in the Consolidated\nBalance Sheets. Refer to Note 4. Gift cards in the U.S. and some countries do not carry an expiration date; therefore, customers\nand members can redeem their gift cards for merchandise and services indefinitely. Gift cards in some countries where the\nCompany does business have expiration dates. While gift cards are generally redeemed within 12 months, a certain number of\ngift cards, both with and without expiration dates, will not be fully redeemed. Management estimates unredeemed balances and\nrecognizes gift card breakage income for these amounts in membership and other income in the Company's Consolidated\nStatements of Income over the expected redemption period. [3]\n- Table on page 80\nSection: Total assets, depreciation and amortization, and capital expenditures for the Company's segments, as well as for Corporate and\nColumns: Revenues\nRevenues: U.S. operations $ 581,175 $ 557,622 $ 532,076\nRevenues: Non-U.S. operations 131,988 123,363 116,049\nRevenues: Total revenues $ 713,163 $ 680,985 $ 648,125\nRevenues: Long-lived assets\nRevenues: U.S. operations $ 128,366 $ 115,250 $ 104,480\nRevenues: Non-U.S. operations 28,590 24,455 25,858\nRevenues: Total long-lived assets $ 156,956 $ 139,705 $ 130,338 [4]\n- Fiscal Years Ended January 31,\n(Dollar amounts and retail square feet in millions)\n2026\n2025\n2024\nNet sales\n$\n706,413\n$\n674,538\n$\n642,637\nPercentage change from comparable period\n 4.7 %\n 5.0 %\n 6.1 %\nMembership and other income(1)\n\n6,750\n\n6,447\n\n5,488\nTotal revenues\n\n713,163\n\n680,985\n\n648,125\nPercentage change from comparable period\n 4.7 %\n 5.1 %\n 6.0 %\nGross profit(2)\n\n171,018\n\n162,785\n\n152,495\nOperating expenses(2)\n\n147,943\n\n139,884\n\n130,971\nO
... (truncated)
```

## forecast

- Method: POST
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/forecasts
- Elapsed: 10.86 ms
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
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/exports
- Elapsed: 13.55 ms
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
- Path: /workspaces/3ae3c8b6-1dc2-4d1a-b7c0-42979c848255/exports
- Elapsed: 12.88 ms
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
