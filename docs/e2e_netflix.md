# E2E Test Report

- Base URL: http://localhost:8000/api/v1
- Started: 2026-11-04T17:17:26Z
- Finished: 2026-11-04T17:19:22Z

- User: e2e_f3b033a6b3@example.com
- Workspace ID: 693a4eaa-9b30-45df-8f60-a9d8d8c53bea
- Document ID: 3f760704-eef7-41fe-925e-621f345075e2
- Document status: completed

## register

- Method: POST
- Path: /auth/register
- Elapsed: 2204.57 ms
- Status: 201

```json
{
  "id": "1ab72584-bfbb-4d88-ae84-0585e703002c",
  "email": "e2e_f3b033a6b3@example.com",
  "full_name": "E2E Test User",
  "role": "analyst",
  "scenario_key": null,
  "created_at": "2026-11-04T22:47:28.709801+05:30",
  "last_login_at": null
}
```

## login

- Method: POST
- Path: /auth/login
- Elapsed: 84.49 ms
- Status: 200

```json
{
  "user": {
    "id": "1ab72584-bfbb-4d88-ae84-0585e703002c",
    "email": "e2e_f3b033a6b3@example.com",
    "full_name": "E2E Test User",
    "role": "analyst",
    "scenario_key": null
  },
  "expires_at": "2026-11-05T17:17:28.930066Z"
}
```

## create_workspace

- Method: POST
- Path: /workspaces
- Elapsed: 9.66 ms
- Status: 201

```json
{
  "id": "693a4eaa-9b30-45df-8f60-a9d8d8c53bea",
  "name": "E2E Test",
  "description": null,
  "owner_id": "1ab72584-bfbb-4d88-ae84-0585e703002c",
  "document_count": 0,
  "created_at": "2026-11-04T22:47:28.946182+05:30",
  "updated_at": "2026-11-04T22:47:28.946182+05:30"
}
```

## upload_document

- Method: POST
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/documents
- Elapsed: 404.09 ms
- Status: 201

```json
{
  "document_id": "3f760704-eef7-41fe-925e-621f345075e2",
  "processing_status": "queued",
  "processing_stage": null,
  "content_hash": "081fbe847afdee5ce4f522e4b89f2bf482c6a8992adfc509aec0c9106c31101f",
  "duplicate": false
}
```

## poll_document_status

- Method: GET
- Path: /documents/3f760704-eef7-41fe-925e-621f345075e2
- Elapsed: 113140.45 ms
- Status: 200

```json
{
  "id": "3f760704-eef7-41fe-925e-621f345075e2",
  "workspace_id": "693a4eaa-9b30-45df-8f60-a9d8d8c53bea",
  "original_filename": "netflix_fy2025_form_10k.pdf",
  "content_hash": "081fbe847afdee5ce4f522e4b89f2bf482c6a8992adfc509aec0c9106c31101f",
  "file_size_bytes": 1406925,
  "mime_type": "application/pdf",
  "company_name": "Netflix, Inc.",
  "document_title": "FORM 10-K",
  "document_type": "form_10k",
  "fiscal_period": "Q4 2025",
  "source_url": null,
  "page_count": 122,
  "processing_status": "completed",
  "processing_stage": "completed",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-04T22:47:29.339158+05:30",
  "updated_at": "2026-11-04T22:49:21.422441+05:30",
  "processed_at": "2026-11-04T22:49:21.410448+05:30",
  "chunk_count": 490
}
```

## search

- Method: POST
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/search
- Elapsed: 30.59 ms
- Status: 200

```json
{
  "query": "revenue",
  "workspace_id": "693a4eaa-9b30-45df-8f60-a9d8d8c53bea",
  "total": 10,
  "results": [
    {
      "chunk_id": "4a9b88a1-54f3-4918-9008-55f81128693d",
      "document_id": "3f760704-eef7-41fe-925e-621f345075e2",
      "document_title": "FORM 10-K",
      "company_name": "Netflix, Inc.",
      "document_type": "form_10k",
      "fiscal_period": "Q4 2025",
      "page_start": 72,
      "page_end": 72,
      "section_heading": "(in thousands)",
      "chunk_type": "text",
      "content": "(in thousands)\nRevenues\n$\n45,183,036\n$\n39,000,966\n$\n33,723,297\nLess:\nContent amortization\n16,422,166\n15,301,517\n14,197,437\nOther cost of revenues\n6,853,163\n5,736,947\n5,517,931\nSales and marketing\n3,301,306\n2,917,554\n2,657,883\nTechnology and development\n3,391,390\n2,925,295\n2,675,758\nGeneral and administrative\n1,888,408\n1,702,039\n1,720,285\nOperating income\n13,326,603\n10,417,614\n6,954,003\nOperating margin\n29.5 %\n26.7 %\n20.6 %\nOther income (expense)\nInterest expense\n(776,510)\n(718,733)\n(699,826)\nInterest and other income (expense)\n172,459\n266,776\n(48,772)\nIncome before income taxes\n12,722,552\n9,965,657\n6,205,405\nProvision for income taxes\n(1,741,351)\n(1,254,026)\n(797,415)\nNet income\n$\n10,981,201\n$\n8,711,631\n$\n5,407,990\n(1) Includes interest income of $295 million, $294 million and $281 million for the years ended December 31, 2025, 2024 and 2023, respectively.\nSee the consolidated financial statements for other financial information regarding the Company’s operating segment.\nTotal U.S. revenues were $18.5 billion, $16.1 billion and $13.8 billion for the years ended December 31, 2025, 2024 and 2023, respectively. See Note 2\nRevenue Recognition for additional information about streaming revenue by region.\n   The Company's long-lived tangible assets, as well as the Company's operating lease right-of-use assets recognized on the Consolidated Balance Sheets were\nlocated as follows:",
      "score": 0.7680673232098619,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 72,
        "token_count": 387,
        "content_hash": "b9fb1e17821c037eeea9b2b84e707e7608f1f4e1560a38f6aa24adc4d8ad3874",
        "section_index": 2,
        "page_has_table": true,
        "section_heading": "(in thousands)",
        "embedding_config_hash": "f279eb2e4167e121db4f5ef7cb0645333467e536c2c3b8d07223200a396351a5"
      }
    },
    {
      "chunk_id": "3e71e408-d814-4292-845c-ad612142d65f",
      "document_id": "3f760704-eef7-41fe-925e-621f345075e2",
      "document_title": "FORM 10-K",
      "company_name": "Netflix, Inc.",
      "document_type": "form_10k",
      "fiscal_period": "Q4 2025",
      "page_start": 49,
      "page_end": 49,
      "section_heading": "Revenue Recognition",
      "chunk_type": "text",
      "content": "Revenue Recognition\nThe Company's primary source of revenues is from monthly membership fees. Members are billed in advance of the start of their monthly membership\nand revenues are recognized ratably over each monthly membership period. Revenues are presented net of the taxes that are collected from members and\nremitted to governmental authorities. The Company is the principal in all its relationships where partners, including consumer electronics (“CE”)\nmanufacturers, multichannel video programming distributors (“MVPDs”), mobile operators and internet service providers (“ISPs”), provide access to the\nservice as the Company retains control over service delivery to its members. In circumstances in which the price that the member pays is established by a\npartner and there is no standalone price for the Netflix service (for instance, in a bundle), the net amount collected from the partner is recognized as revenue.\nThe Company also earns revenue from advertisements presented on its streaming service, consumer products, live experiences and various other sources.\nRevenues earned from sources other than month
... (truncated)
```

## red_flag_analysis

- Method: POST
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/red-flags/analyze
- Elapsed: 13.33 ms
- Status: 200

```json
{
  "findings": [],
  "red_flags": [],
  "flags": [],
  "risks": [],
  "warnings": [],
  "errors": [],
  "workspace_id": "693a4eaa-9b30-45df-8f60-a9d8d8c53bea",
  "document_id": "3f760704-eef7-41fe-925e-621f345075e2",
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
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/research
- Elapsed: 29.79 ms
- Status: 200

```json
{
  "question": "What was revenue?",
  "query": "What was revenue?",
  "research_question": "What was revenue?",
  "answer": "Research question: What was revenue?\n\nAnswer (grounded in retrieved evidence):\nFacts:\n- (in thousands)\nRevenues\n$\n45,183,036\n$\n39,000,966\n$\n33,723,297\nLess:\nContent amortization\n16,422,166\n15,301,517\n14,197,437\nOther cost of revenues\n6,853,163\n5,736,947\n5,517,931\nSales and marketing\n3,301,306\n2,917,554\n2,657,883\nTechnology and development\n3,391,390\n2,925,295\n2,675,758\nGeneral and administrative\n1,888,408\n1,702,039\n1,720,285\nOperating income\n13,326,603\n10,417,614\n6,954,003\nOperating margin\n29.5 %\n26.7 %\n20.6 %\nOther income (expense)\nInterest expense\n(776,510)\n(718,733)\n(699,826)\nInterest and other income (expense)\n172,459\n266,776\n(48,772)\nIncome before income taxes\n12,722,552\n9,965,657\n6,205,405\nProvision for income taxes\n(1,741,351)\n(1,254,026)\n(797,415)\nNet income\n$\n10,981,201\n$\n8,711,631\n$\n5,407,990\n(1) Includes interest income of $295 million, $294 million and $281 million for the years ended December 31, 2025, 2024 and 2023, respectively.\nSee the consolidated financial statements for other financial information regarding the Company’s operating segment.\nTotal U.S. revenues were $18.5 billion, $16.1 billion and $13.8 billion for the years ended December 31, 2025, 2024 and 2023, respectively. See Note 2\nRevenue Recognition for additional information about streaming revenue by region.\n   The Company's long-lived tangible assets, as well as the Company's operating lease right-of-use assets recognized on the Consolidated Balance Sheets were\nlocated as follows: [1]\n- Cost of Revenues\nCost of revenues primarily consists of the amortization of content assets. Other costs of revenues include expenses associated with the acquisition,\nlicensing and production of content, streaming delivery costs, and other operating costs.\nExpenses related to the acquisition, licensing and production of content not included in content amortization may include payroll, stock-based\ncompensation, facilities, and other personnel-related expenses, costs associated with obtaining rights to music included in our content, overall deals with talent,\nmiscellaneous production-related costs and participations and residuals. Streaming delivery costs are primarily related to our global content delivery network\n(“Open Connect”). We have built our own Open Connect network to help us efficiently stream a high volume of content to our members over the internet.\nDelivery expenses, therefore, include equipment costs related to Open Connect, payroll and related personnel expenses and all third-party costs, such as cloud\ncomputing costs, associated with delivering content over the internet. Other operating costs include customer service and payment processing fees, including\nthose we pay to our integrated payment partners, as well as other costs incurred in making our content available to members.\nYear Ended December 31,\nChange\n\n2025\n2024\n2023\n2025 vs. 2024 [2]\n- Table of Contents\nYear Ended December 31,\n2025\nRevenues\nCost of Revenues\nInterest and other\nincome (expense)\nProvision for\nIncome Taxes\nTotal\nReclassifications\n(in thousands) [3]\n- Revenue Recognition\nThe Company's primary source of revenues is from monthly membership fees. Members are billed in advance of the start of their monthly membership\nand revenues are recognized ratably over each monthly membership period. Revenues are presented net of the taxes that are collected from members and\nremitted to governmental authorities. The Company is the principal in all its relationships where partners, including consumer electronics (“CE”)\nmanufacturers, multichannel video programming distributors (“MVPDs”), mobile operators and internet service providers (“ISPs”), provide access to the\nservice as the Company retains control over service delivery to its members. In circumstances in which the p
... (truncated)
```

## forecast

- Method: POST
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/forecasts
- Elapsed: 12.31 ms
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
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/exports
- Elapsed: 12.92 ms
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
- Path: /workspaces/693a4eaa-9b30-45df-8f60-a9d8d8c53bea/exports
- Elapsed: 12.25 ms
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
