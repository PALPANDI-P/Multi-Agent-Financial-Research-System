# E2E Test Report

- Base URL: http://localhost:8000/api/v1
- Started: 2026-11-04T17:14:36Z
- Finished: 2026-11-04T17:17:13Z

- User: e2e_285313d4bc@example.com
- Workspace ID: 288f6bec-9d53-4834-a2c0-eb82483f382b
- Document ID: d29e77d7-0fc9-4021-acc4-e486bb5d8712
- Document status: completed

## register

- Method: POST
- Path: /auth/register
- Elapsed: 2145.94 ms
- Status: 201

```json
{
  "id": "0b7e5152-62d7-47dd-a7a9-95265dd6c79c",
  "email": "e2e_285313d4bc@example.com",
  "full_name": "E2E Test User",
  "role": "analyst",
  "scenario_key": null,
  "created_at": "2026-11-04T22:44:38.989534+05:30",
  "last_login_at": null
}
```

## login

- Method: POST
- Path: /auth/login
- Elapsed: 100.69 ms
- Status: 200

```json
{
  "user": {
    "id": "0b7e5152-62d7-47dd-a7a9-95265dd6c79c",
    "email": "e2e_285313d4bc@example.com",
    "full_name": "E2E Test User",
    "role": "analyst",
    "scenario_key": null
  },
  "expires_at": "2026-11-05T17:14:39.178358Z"
}
```

## create_workspace

- Method: POST
- Path: /workspaces
- Elapsed: 12.67 ms
- Status: 201

```json
{
  "id": "288f6bec-9d53-4834-a2c0-eb82483f382b",
  "name": "E2E Test",
  "description": null,
  "owner_id": "0b7e5152-62d7-47dd-a7a9-95265dd6c79c",
  "document_count": 0,
  "created_at": "2026-11-04T22:44:39.194637+05:30",
  "updated_at": "2026-11-04T22:44:39.194637+05:30"
}
```

## upload_document

- Method: POST
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/documents
- Elapsed: 369.83 ms
- Status: 201

```json
{
  "document_id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
  "processing_status": "queued",
  "processing_stage": null,
  "content_hash": "fff3692cded4ca4cdb377210a8d772c37ac946e16223b4ebbb558c6a57d95e08",
  "duplicate": false
}
```

## poll_document_status

- Method: GET
- Path: /documents/d29e77d7-0fc9-4021-acc4-e486bb5d8712
- Elapsed: 153551.34 ms
- Status: 200

```json
{
  "id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
  "workspace_id": "288f6bec-9d53-4834-a2c0-eb82483f382b",
  "original_filename": "jpmorgan_chase_fy2025_audited_financial_statements.pdf",
  "content_hash": "fff3692cded4ca4cdb377210a8d772c37ac946e16223b4ebbb558c6a57d95e08",
  "file_size_bytes": 1145396,
  "mime_type": "application/pdf",
  "company_name": "Management of JPMorgan Chase & Co.",
  "document_title": "5Ac287e332bf4db6893f653df944ea55",
  "document_type": "form_10k",
  "fiscal_period": "FY2025",
  "source_url": null,
  "page_count": 167,
  "processing_status": "completed",
  "processing_stage": "completed",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-04T22:44:39.561091+05:30",
  "updated_at": "2026-11-04T22:47:11.686704+05:30",
  "processed_at": "2026-11-04T22:47:11.646653+05:30",
  "chunk_count": 869
}
```

## search

- Method: POST
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/search
- Elapsed: 27.32 ms
- Status: 200

```json
{
  "query": "revenue",
  "workspace_id": "288f6bec-9d53-4834-a2c0-eb82483f382b",
  "total": 10,
  "results": [
    {
      "chunk_id": "a436a5fb-395e-4617-be92-ca301bd94e2a",
      "document_id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
      "document_title": "5Ac287e332bf4db6893f653df944ea55",
      "company_name": "Management of JPMorgan Chase & Co.",
      "document_type": "form_10k",
      "fiscal_period": "FY2025",
      "page_start": 115,
      "page_end": 115,
      "section_heading": "revenue:",
      "chunk_type": "text",
      "content": "revenue:\n\nOperating revenue:\n\nLoan servicing revenue\n\n1,651\n\n1,659\n\n1,634\nChanges in MSR asset fair\nvalue due to collection/\nrealization of expected cash\nflows\n (1,065)  (1,067)\n(1,011)\nTotal operating revenue\n\n586\n\n592\n\n623\nRisk management:\n\nChanges in MSR asset fair\nvalue due to market interest\nrates and other(a)\n\n48\n\n670\n\n424\nOther changes in MSR asset\nfair value due to other inputs\nand assumptions in model(b)\n—\n\n92\n\n43\nChange in derivative fair value\nand other\n\n70\n\n(603)\n(336)\nTotal risk management\n\n118\n\n159\n\n131\nTotal net mortgage servicing\nrevenue\n\n704\n\n751\n\n754",
      "score": 0.7286521630675903,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 115,
        "token_count": 124,
        "content_hash": "4926485419da129e3faf206054e3d79491c64b6067475686f78ffba772938270",
        "section_index": 11,
        "page_has_table": false,
        "section_heading": "revenue:",
        "embedding_config_hash": "f279eb2e4167e121db4f5ef7cb0645333467e536c2c3b8d07223200a396351a5",
        "merged_section_heading": "Total net mortgage servicing"
      }
    },
    {
      "chunk_id": "dfafa6a7-ef6e-40f4-9dca-aa9c2f440f8c",
      "document_id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
      "document_title": "5Ac287e332bf4db6893f653df944ea55",
      "company_name": "Management of JPMorgan Chase & Co.",
      "document_type": "form_10k",
      "fiscal_period": "FY2025",
      "page_start": 5,
      "page_end": 5,
      "section_heading": "Noninterest revenue",
      "chunk_type": "text",
      "content": "Noninterest revenue\n\n87,004\n\n84,973\n\n68,837\nInterest income\n\n193,341\n\n193,933\n\n170,588\nInterest expense\n\n97,898\n\n101,350\n\n81,321\nNet interest income\n\n95,443\n\n92,583\n\n89,267\nTotal net revenue\n\n182,447\n\n177,556\n\n158,104\nProvision for credit losses\n\n14,212\n\n10,678\n\n9,320",
      "score": 0.7182252621121786,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 5,
        "token_count": 70,
        "content_hash": "7ccd9d15dbee83a6ff29d4a17b48aa83d3d53b005f0568dec9925c44e305bd43",
        "section_index": 3,
        "page_has_table": false,
        "section_heading": "Noninterest revenue",
        "embedding_config_hash": "f279eb2e4167e121db4f5ef7cb0645333467e536c2c3b8d07223200a396351a5",
        "merged_section_heading": "Total net revenue"
      }
    },
    {
      "chunk_id": "74249abe-7d88-4689-8598-1100f842f3b3",
      "document_id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
      "document_title": "5Ac287e332bf4db6893f653df944ea55",
      "company_name": "Management of JPMorgan Chase & Co.",
      "document_type": "form_10k",
      "fiscal_period": "FY2025",
      "page_start": 149,
      "page_end": 149,
      "section_heading": "Total net revenue",
      "chunk_type": "text",
      "content": "Total net revenue\n\n7,025\n\n17,394\n\n8,038\n\n(3,134)\n(3,037)\n(4,262)\n\n182,447\n\n177,556\n\n158,104\nProvision for credit losses\n\n7\n\n10\n\n171\n—\n—\n—\n\n14,212\n\n10,678\n\n9,320\nTotal noninterest expense\n(d)\n\n1,825\n\n3,994\n(h)\n\n5,601\n\n—\n—\n—\n\n95,640\n\n91,797\n(h)\n\n87,172\nIncome/(loss) before income",
      "score": 0.7133708767073836,
      "metadata": {
        "source": "pdf_text",
        "has_table": false,
        "page_number": 149,
        "token_count": 95,
   
... (truncated)
```

## red_flag_analysis

- Method: POST
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/red-flags/analyze
- Elapsed: 14.6 ms
- Status: 200

```json
{
  "findings": [],
  "red_flags": [],
  "flags": [],
  "risks": [],
  "warnings": [],
  "errors": [],
  "workspace_id": "288f6bec-9d53-4834-a2c0-eb82483f382b",
  "document_id": "d29e77d7-0fc9-4021-acc4-e486bb5d8712",
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
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/research
- Elapsed: 28.88 ms
- Status: 200

```json
{
  "question": "What was revenue?",
  "query": "What was revenue?",
  "research_question": "What was revenue?",
  "answer": "Research question: What was revenue?\n\nAnswer (grounded in retrieved evidence):\nFacts:\n- revenue:\n\nOperating revenue:\n\nLoan servicing revenue\n\n1,651\n\n1,659\n\n1,634\nChanges in MSR asset fair\nvalue due to collection/\nrealization of expected cash\nflows\n (1,065)  (1,067)\n(1,011)\nTotal operating revenue\n\n586\n\n592\n\n623\nRisk management:\n\nChanges in MSR asset fair\nvalue due to market interest\nrates and other(a)\n\n48\n\n670\n\n424\nOther changes in MSR asset\nfair value due to other inputs\nand assumptions in model(b)\n—\n\n92\n\n43\nChange in derivative fair value\nand other\n\n70\n\n(603)\n(336)\nTotal risk management\n\n118\n\n159\n\n131\nTotal net mortgage servicing\nrevenue\n\n704\n\n751\n\n754 [1]\n- Expense categories:\n• Volume- and/or revenue-related expenses generally\ncorrelate with changes in the related business/\ntransaction volume or revenue. Examples include\ncommissions and incentive compensation within the\nLOBs, depreciation expense related to operating\nlease assets, and brokerage expense related to\ntrading transaction volume.\n• Investments in the business include expenses\nassociated with supporting medium- to longer-term\nGlossary of Terms and Acronyms\nJPMorgan Chase & Co./2025 Form 10-K\n321 [2]\n- (Table continued from previous page)\nAs of or for the year ended\nDecember 31,\n(in millions, except ratios)\nCorporate\nReconciling Items\n(a)\nTotal\n2025\n2024\n2023\n2025\n2024\n2023\n2025\n2024\n2023\nNoninterest revenue\n$\n911\n$\n7,608 [3]\n- Production revenue: Includes fees and income\nrecognized as earned on mortgage loans originated\nwith the intent to sell, and the impact of risk\nmanagement activities associated with the mortgage\npipeline and warehouse loans. Production revenue\nalso includes gains and losses on sales and lower of\ncost or fair value adjustments on mortgage loans held-\nfor-sale (excluding certain repurchased loans insured\nby U.S. government agencies), and changes in the fair\nvalue of financial instruments measured under the fair\nvalue option.\nGlossary of Terms and Acronyms\nJPMorgan Chase & Co./2025 Form 10-K\n325 [4]\n- Noninterest revenue\n\n87,004\n\n84,973\n\n68,837\nInterest income\n\n193,341\n\n193,933\n\n170,588\nInterest expense\n\n97,898\n\n101,350\n\n81,321\nNet interest income\n\n95,443\n\n92,583\n\n89,267\nTotal net revenue\n\n182,447\n\n177,556\n\n158,104\nProvision for credit losses\n\n14,212\n\n10,678\n\n9,320 [5]\n- Total net revenue\n\n7,025\n\n17,394\n\n8,038\n\n(3,134)\n(3,037)\n(4,262)\n\n182,447\n\n177,556\n\n158,104\nProvision for credit losses\n\n7\n\n10\n\n171\n—\n—\n—\n\n14,212\n\n10,678\n\n9,320\nTotal noninterest expense\n(d)\n\n1,825\n\n3,994\n(h)\n\n5,601\n\n—\n—\n—\n\n95,640\n\n91,797\n(h)\n\n87,172\nIncome/(loss) before income [6]\n- income and the related depreciation expense on the\nConsolidated statements of income.\nYear ended December 31,\n(in millions)\n2025\n2024\n2023\nOperating lease income\n$\n3,803 $\n2,795 $\n2,843\nDepreciation expense\n\n2,418\n1,685\n1,778\nThe following table presents future receipts under [7]\nInterpretations:\n- The answer is based on the retrieved document passages cited below; no facts beyond those passages and the supplied financial data are asserted.\n\nSources:\n[1] 5Ac287e332bf4db6893f653df944ea55 | Management of JPMorgan Chase & Co. | FY2025 | p.115 | revenue:\n[2] 5Ac287e332bf4db6893f653df944ea55 | Management of JPMorgan Chase & Co. | FY2025 | p.161 | Expense categories:\n[3] 5Ac287e332bf4db6893f653df944ea55 | Management of JPMorgan Chase & Co. | FY2025 | p.149 | (Table continued from previous page)\n[4] 5Ac287e332bf4db6893f653df944ea55 | Management of JPMorgan Chase & Co. | FY2025 | p.165 | Production revenue:\n[5] 5Ac287e332bf4db6893f653df944ea55 | Management of JPMorgan Chase & Co. | FY2025 | p.5 | Noninterest revenue\n[6] 5Ac287e332bf4db6893f653df9
... (truncated)
```

## forecast

- Method: POST
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/forecasts
- Elapsed: 15.2 ms
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
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/exports
- Elapsed: 14.72 ms
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
- Path: /workspaces/288f6bec-9d53-4834-a2c0-eb82483f382b/exports
- Elapsed: 15.15 ms
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
