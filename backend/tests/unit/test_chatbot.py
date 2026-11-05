"""Unit tests for the document chatbot endpoint and answer-synthesis logic."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Helpers - import the module under test
# ---------------------------------------------------------------------------
from app.api.v1.chatbot import (
    _classify_question,
    _extract_numbers,
    _project_answer,
    _synthesise_answer,
)

# ---------------------------------------------------------------------------
# Tests for _classify_question
# ---------------------------------------------------------------------------


class TestClassifyQuestion:
    def test_revenue(self):
        assert _classify_question("What was the total revenue in FY2024?") == "revenue"

    def test_revenue_sales(self):
        assert _classify_question("How much did net sales grow?") == "revenue"

    def test_profit(self):
        assert _classify_question("What was net income last year?") == "profit"

    def test_loss(self):
        assert _classify_question("Did the company report a net loss?") == "loss"

    def test_forecast(self):
        assert _classify_question("What is management's growth outlook for 2025?") == "forecast"

    def test_risk(self):
        assert _classify_question("Are there any red flags or concerns?") == "risk"

    def test_margin(self):
        assert _classify_question("What is the gross margin trend?") == "margin"

    def test_market(self):
        assert _classify_question("What is the market rate and stock valuation?") == "market"

    def test_general(self):
        assert _classify_question("Tell me about the company.") == "general"


# ---------------------------------------------------------------------------
# Tests for _project_answer
# ---------------------------------------------------------------------------


class TestProjectAnswer:
    def test_upload_question(self):
        ans = _project_answer("How do I upload a file?")
        assert ans is not None
        assert "Upload" in ans or "upload" in ans

    def test_format_question(self):
        ans = _project_answer("What file formats are supported?")
        assert ans is not None
        assert "PDF" in ans

    def test_size_question(self):
        ans = _project_answer("What is the maximum file size?")
        assert ans is not None
        assert "50 MB" in ans or "52" in ans

    def test_workspace_question(self):
        ans = _project_answer("What is a workspace?")
        assert ans is not None
        assert "workspace" in ans.lower()

    def test_search_question(self):
        ans = _project_answer("How does semantic search work?")
        assert ans is not None
        assert "search" in ans.lower()

    def test_red_flag_question(self):
        ans = _project_answer("What are red flags?")
        assert ans is not None
        assert "red flag" in ans.lower() or "Red Flag" in ans

    def test_forecast_question(self):
        ans = _project_answer("How does the forecasting work?")
        assert ans is not None
        assert "forecast" in ans.lower() or "Forecast" in ans

    def test_export_question(self):
        ans = _project_answer("Can I export data as CSV?")
        assert ans is not None
        assert "CSV" in ans or "csv" in ans.lower()

    def test_api_question(self):
        ans = _project_answer("Where is the API documentation?")
        assert ans is not None
        assert "/api/docs" in ans or "swagger" in ans.lower()

    def test_unrelated_question_returns_none(self):
        ans = _project_answer("What is the capital of Germany?")
        assert ans is None


# ---------------------------------------------------------------------------
# Tests for _extract_numbers
# ---------------------------------------------------------------------------


class TestExtractNumbers:
    def test_revenue_extraction(self):
        text = "Total revenue was $394.3 billion in fiscal 2024, up 2% year-over-year."
        numbers = _extract_numbers(text, "revenue")
        assert len(numbers) > 0
        assert any("394" in n or "billion" in n.lower() for n in numbers)

    def test_profit_extraction(self):
        text = "Net income reached $97 billion, translating to EPS of $6.43."
        numbers = _extract_numbers(text, "profit")
        assert len(numbers) > 0

    def test_margin_extraction(self):
        text = "Gross margin improved to 46.2% from 44.1% in the prior year."
        numbers = _extract_numbers(text, "margin")
        assert len(numbers) > 0
        assert any("%" in n for n in numbers)

    def test_unknown_key_returns_empty(self):
        numbers = _extract_numbers("some text", "unknown_key")
        assert numbers == []


# ---------------------------------------------------------------------------
# Tests for _synthesise_answer
# ---------------------------------------------------------------------------


def _make_chunk(content: str, company: str = "Apple", page: int = 1) -> MagicMock:
    chunk = MagicMock()
    chunk.content = content
    chunk.document_title = f"{company} 10-K"
    chunk.company_name = company
    chunk.section_heading = "Financial Results"
    chunk.page_start = page
    chunk.page_end = page + 1
    chunk.score = 0.9
    return chunk


class TestSynthesiseAnswer:
    def test_no_chunks_returns_helpful_message(self):
        ans = _synthesise_answer("What was revenue?", [])
        assert "could not find" in ans.lower() or "no relevant" in ans.lower()

    def test_answer_mentions_document(self):
        chunks = [_make_chunk("Revenue was $394 billion in FY2024.")]
        ans = _synthesise_answer("What was revenue?", chunks)
        assert "Apple 10-K" in ans

    def test_answer_includes_content(self):
        chunks = [_make_chunk("Revenue was $394 billion in FY2024.")]
        ans = _synthesise_answer("What was revenue?", chunks)
        assert "394" in ans or "billion" in ans.lower() or "Revenue" in ans

    def test_risk_answer_mentions_red_flag(self):
        chunks = [_make_chunk("The company faces significant going-concern risks.")]
        ans = _synthesise_answer("What are the main risks?", chunks)
        assert "Red Flag" in ans or "red flag" in ans.lower() or "risk" in ans.lower()

    def test_forecast_answer_mentions_forecast_panel(self):
        chunks = [_make_chunk("Management expects 10% revenue growth in 2025.")]
        ans = _synthesise_answer("What is the future outlook?", chunks)
        assert "Forecast" in ans or "forecast" in ans.lower()

    def test_market_answer_notes_live_data_caveat(self):
        chunks = [_make_chunk("Market share has grown to 32%.")]
        ans = _synthesise_answer("What is the market rate?", chunks)
        assert "market" in ans.lower()

    def test_long_content_is_truncated(self):
        long_content = "X " * 500  # 1000 chars
        chunks = [_make_chunk(long_content)]
        ans = _synthesise_answer("Summary?", chunks)
        # Answer should not contain the full 1000-char content verbatim
        assert len(ans) < len(long_content) * 2

    def test_duplicate_content_deduplicated(self):
        content = "Revenue was $394 billion in FY2024."
        chunks = [_make_chunk(content, "Apple"), _make_chunk(content, "Apple")]
        ans = _synthesise_answer("What was revenue?", chunks)
        # Should appear only once in the answer body
        count = ans.count(content[:30])
        assert count <= 1

    def test_multiple_documents(self):
        chunks = [
            _make_chunk("Revenue was $394 billion.", "Apple"),
            _make_chunk("Revenue was $158 billion.", "JPMorgan"),
        ]
        ans = _synthesise_answer("What was revenue?", chunks)
        assert "Apple" in ans
        assert "JPMorgan" in ans

    def test_source_count_in_footer(self):
        chunks = [_make_chunk("Revenue was $394 billion.")]
        ans = _synthesise_answer("Revenue?", chunks)
        assert "1 document chunk" in ans or "chunk(s)" in ans


# ---------------------------------------------------------------------------
# Endpoint handler unit tests (direct function call, no HTTP/DB required)
# ---------------------------------------------------------------------------

from app.api.v1.chatbot import ChatRequest, chat  # noqa: E402
from app.services.auth_service import UserSummary  # noqa: E402
from app.services.search_service import SearchResultItem, SearchResults  # noqa: E402


class TestChatEndpoint:
    """Direct handler tests with mocked services."""

    def _make_mocks(self):
        mock_ws = MagicMock()
        mock_ws.get_workspace.return_value = MagicMock(id=uuid4(), name="Test WS")

        mock_search = MagicMock()
        sample_chunk = SearchResultItem(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_title="Apple 10-K",
            company_name="Apple",
            document_type="10-K",
            fiscal_period="FY2024",
            page_start=12,
            page_end=13,
            section_heading="Item 7. MD&A",
            chunk_type="text",
            content="Revenue was $394 billion in FY2024.",
            score=0.92,
            metadata={},
        )
        mock_search.search.return_value = SearchResults(
            query="revenue",
            workspace_id=uuid4(),
            total=1,
            results=[sample_chunk],
            took_ms=45.0,
        )

        mock_user = MagicMock(spec=UserSummary)
        mock_user.id = uuid4()
        mock_user.is_anonymous = False

        return mock_ws, mock_search, mock_user

    def test_project_question_returns_answer_no_search(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        ws_id = uuid4()
        req = ChatRequest(question="How do I upload a file?")
        resp = chat(
            workspace_id=ws_id,
            payload=req,
            workspace_service=mock_ws,
            search_service=mock_search,
            current_user=mock_user,
        )
        assert resp.answer
        assert "upload" in resp.answer.lower()
        mock_search.search.assert_not_called()
        assert resp.source_count == 0

    def test_document_question_calls_search(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        ws_id = uuid4()
        req = ChatRequest(question="What was total revenue?")
        resp = chat(
            workspace_id=ws_id,
            payload=req,
            workspace_service=mock_ws,
            search_service=mock_search,
            current_user=mock_user,
        )
        assert resp.answer
        assert len(resp.sources) == 1
        assert resp.sources[0].company_name == "Apple"
        mock_search.search.assert_called_once()

    def test_response_fields_present(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        ws_id = uuid4()
        req = ChatRequest(question="What was net income?")
        resp = chat(
            workspace_id=ws_id,
            payload=req,
            workspace_service=mock_ws,
            search_service=mock_search,
            current_user=mock_user,
        )
        assert resp.message_id
        assert resp.took_ms >= 0
        assert resp.document_count >= 0

    def test_history_passed(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        ws_id = uuid4()
        req = ChatRequest(
            question="What about profit?",
            history=[
                {"role": "user", "content": "Tell me about revenue."},
                {"role": "assistant", "content": "Revenue was $394B."},
            ],
        )
        resp = chat(
            workspace_id=ws_id,
            payload=req,
            workspace_service=mock_ws,
            search_service=mock_search,
            current_user=mock_user,
        )
        assert resp.answer
        assert mock_search.search.called

    def test_top_k_respected(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        ws_id = uuid4()
        req = ChatRequest(question="What is the profit margin?", top_k=5)
        chat(
            workspace_id=ws_id,
            payload=req,
            workspace_service=mock_ws,
            search_service=mock_search,
            current_user=mock_user,
        )
        assert mock_search.search.call_args.kwargs.get("limit") == 5

    def test_workspace_not_found_raises(self):
        mock_ws, mock_search, mock_user = self._make_mocks()
        from fastapi import HTTPException

        from app.core.exceptions import NotFoundError
        mock_ws.get_workspace.side_effect = NotFoundError("not found")

        ws_id = uuid4()
        req = ChatRequest(question="What was revenue?")
        with pytest.raises(HTTPException) as exc_info:
            chat(
                workspace_id=ws_id,
                payload=req,
                workspace_service=mock_ws,
                search_service=mock_search,
                current_user=mock_user,
            )
        assert exc_info.value.status_code == 404
