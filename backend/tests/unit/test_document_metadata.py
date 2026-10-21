"""Unit tests for the deterministic metadata detection."""

from __future__ import annotations

from app.core.enums import DocumentType
from app.ingestion.metadata import (
    build_document_metadata,
    detect_company_name,
    detect_document_title,
    detect_fiscal_period,
    infer_document_type,
)

TEN_K_COVER = (
    "UNITED STATES\n"
    "SECURITIES AND EXCHANGE COMMISSION\n"
    "Washington, D.C. 20549\n"
    "FORM 10-K\n"
    "Example Holdings Inc.\n"
    "(Exact name of registrant as specified in its charter)\n"
)


# ---------------------------------------------------------------------------
# fiscal period
# ---------------------------------------------------------------------------


def test_fiscal_year_of_a_january_period_end() -> None:
    label, evidence = detect_fiscal_period("For the fiscal year ended January 31, 2026")

    assert label == "FY2026"
    assert evidence is not None
    assert "January 31, 2026" in evidence


def test_fiscal_year_of_a_december_period_end() -> None:
    label, evidence = detect_fiscal_period("for the year ended December 31, 2025")

    assert label == "FY2025"
    assert evidence is not None
    assert "December 31, 2025" in evidence


def test_quarter_of_a_september_period_end() -> None:
    label, evidence = detect_fiscal_period("For the quarterly period ended September 30, 2025")

    assert label == "Q3 2025"
    assert evidence is not None
    assert "September 30, 2025" in evidence


def test_fiscal_year_of_an_uppercase_annual_report_title() -> None:
    label, _ = detect_fiscal_period(
        "ANNUAL REPORT ON FORM 10-K FOR THE FISCAL YEAR ENDED JANUARY 31, 2026"
    )

    assert label == "FY2026"


def test_plain_fiscal_year_label_is_recognised() -> None:
    label, evidence = detect_fiscal_period("The results for FY2025 are summarised in this report.")

    assert label == "FY2025"
    assert evidence == "FY2025"


def test_a_document_without_a_period_has_no_label() -> None:
    assert detect_fiscal_period("A document that does not talk about any period.") == (None, None)


def test_an_empty_text_has_no_label() -> None:
    assert detect_fiscal_period("") == (None, None)


# ---------------------------------------------------------------------------
# document type
# ---------------------------------------------------------------------------


def test_a_form_10k_is_detected() -> None:
    document_type = infer_document_type("report.pdf", "FORM 10-K\nAnnual report")

    assert document_type == DocumentType.FORM_10K
    assert document_type == "form_10k"


def test_a_form_10q_is_detected() -> None:
    document_type = infer_document_type("report.pdf", "FORM 10-Q\nQuarterly report")

    assert document_type == DocumentType.FORM_10Q


def test_an_annual_report_is_detected() -> None:
    document_type = infer_document_type("report.pdf", "Example Holdings plc Annual Report 2025")

    assert document_type == DocumentType.ANNUAL_REPORT


def test_an_earnings_release_is_detected() -> None:
    document_type = infer_document_type(
        "release.pdf",
        "Example Holdings reports record results for the fourth quarter.",
    )

    assert document_type == DocumentType.EARNINGS_RELEASE


def test_an_annual_letter_is_detected() -> None:
    document_type = infer_document_type("letter.pdf", "A Letter to Our Shareholders")

    assert document_type == DocumentType.ANNUAL_LETTER


def test_consolidated_financial_statements_are_detected() -> None:
    document_type = infer_document_type(
        "statements.pdf",
        "Consolidated Financial Statements for the years ended December 31, 2025",
    )

    assert document_type == DocumentType.FINANCIAL_STATEMENTS


def test_an_unknown_document_has_no_type() -> None:
    assert infer_document_type("notes.pdf", "A short note about the weather.") is None


# ---------------------------------------------------------------------------
# company name
# ---------------------------------------------------------------------------


def test_company_name_is_taken_from_the_registrant_boilerplate() -> None:
    company_name = detect_company_name(TEN_K_COVER)

    assert company_name == "Example Holdings Inc."


def test_company_name_falls_back_to_the_first_lines() -> None:
    company_name = detect_company_name("Example Holdings Inc.\nAnnual Report 2025\n")

    assert company_name == "Example Holdings Inc."


def test_a_section_heading_is_not_mistaken_for_a_company_name() -> None:
    assert detect_company_name("Item 1A. Risk Factors\n") is None
    assert detect_company_name("PART I\n") is None


def test_a_document_without_a_company_name_has_none() -> None:
    assert detect_company_name("Just a line of text.\n") is None


# ---------------------------------------------------------------------------
# document title
# ---------------------------------------------------------------------------


def test_an_explicit_title_line_wins_over_the_file_name() -> None:
    title = detect_document_title("ANNUAL REPORT\nSome body text\n", "example-10k-2026.pdf")

    assert title == "ANNUAL REPORT"


def test_the_file_name_is_used_as_a_fallback() -> None:
    title = detect_document_title("Some body text\n", "example_holdings_annual-report.pdf")

    assert title == "Example Holdings Annual Report"


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def test_build_document_metadata_populates_every_field() -> None:
    pages = [
        TEN_K_COVER + "ANNUAL REPORT\nFor the fiscal year ended January 31, 2026\n",
        "Item 1. Business\nThe company operates an office network.\n",
    ]

    metadata = build_document_metadata(pages, filename="example-10k-2026.pdf")

    assert metadata.page_count == 2
    assert metadata.fiscal_period == "FY2026"
    assert metadata.document_type == DocumentType.FORM_10K
    assert metadata.company_name == "Example Holdings Inc."
    assert metadata.document_title == "FORM 10-K"
    assert metadata.extra["fiscal_period_evidence"]
    assert metadata.extra["document_type_evidence"]
    assert metadata.extra["company_name_evidence"]
    assert all(isinstance(value, str) for value in metadata.extra.values())


def test_build_document_metadata_of_an_annual_report() -> None:
    pages = [
        "Example Holdings plc\nANNUAL REPORT\nFor the fiscal year ended January 31, 2026\n",
        "Item 1. Business\nThe company operates an office network.\n",
    ]

    metadata = build_document_metadata(pages, filename="example-annual-report-2026.pdf")

    assert metadata.fiscal_period == "FY2026"
    assert metadata.document_type == DocumentType.ANNUAL_REPORT
    assert metadata.company_name == "Example Holdings plc"
    assert metadata.document_title == "ANNUAL REPORT"


def test_build_document_metadata_of_an_empty_document() -> None:
    metadata = build_document_metadata([], filename=None)

    assert metadata.page_count == 0
    assert metadata.fiscal_period is None
    assert metadata.document_type is None
    assert metadata.company_name is None
    assert metadata.extra["fiscal_period_evidence"] == ""
    assert metadata.extra["document_type_evidence"] == ""
    assert metadata.extra["company_name_evidence"] == ""


def test_build_document_metadata_is_deterministic() -> None:
    pages = [TEN_K_COVER, "Item 1. Business\n"]

    first = build_document_metadata(pages, filename="example.pdf")
    second = build_document_metadata(pages, filename="example.pdf")

    assert first == second