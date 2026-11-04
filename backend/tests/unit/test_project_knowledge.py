from __future__ import annotations

from app.services.project_knowledge import project_answer


def test_returns_none_for_unrelated_question() -> None:
    assert project_answer("What is the weather today?") is None


def test_returns_none_for_empty_input() -> None:
    assert project_answer("") is None
    assert project_answer("   ") is None


def test_returns_none_for_non_string() -> None:
    assert project_answer(None) is None  # type: ignore[arg-type]


def test_case_insensitive_matching() -> None:
    answer = project_answer("WHAT FILE FORMATS ARE SUPPORTED?")
    assert isinstance(answer, str)
    assert "PDF" in answer


def test_file_formats_answer() -> None:
    answer = project_answer("supported file formats")
    assert answer is not None
    assert ".pdf" in answer
    assert "application/pdf" in answer


def test_file_size_answer_mentions_setting() -> None:
    answer = project_answer("max upload size limit")
    assert answer is not None
    assert "MAX_UPLOAD_SIZE_BYTES" in answer


def test_upload_flow_answer() -> None:
    answer = project_answer("how does upload work")
    assert answer is not None
    assert "multipart/form-data" in answer
    assert "retry" in answer.lower()


def test_processing_stages_answer() -> None:
    answer = project_answer("processing stages")
    assert answer is not None
    for stage in (
        "queued",
        "validating",
        "extracting",
        "chunking",
        "embedding",
        "indexing",
        "completed",
        "failed",
    ):
        assert stage in answer


def test_workspaces_answer() -> None:
    answer = project_answer("workspaces")
    assert answer is not None
    assert "255" in answer


def test_search_answer() -> None:
    answer = project_answer("semantic search")
    assert answer is not None
    assert "pgvector" in answer


def test_auth_answer() -> None:
    answer = project_answer("authentication login")
    assert answer is not None
    assert "DemoAnalyst2024!" in answer


def test_forecasting_answer() -> None:
    answer = project_answer("forecasting methods")
    assert answer is not None
    assert "naive" in answer
    assert "linear" in answer


def test_exports_answer() -> None:
    answer = project_answer("export formats")
    assert answer is not None
    for fmt in ("CSV", "JSON", "XLSX", "PDF"):
        assert fmt in answer


def test_agents_answer() -> None:
    answer = project_answer("agents")
    assert answer is not None
    assert "DocumentAgent" in answer


def test_troubleshooting_answer() -> None:
    answer = project_answer("troubleshooting an error")
    assert answer is not None
    assert "403" in answer


def test_how_to_run_answer() -> None:
    answer = project_answer("how to run the project")
    assert answer is not None
    assert "uvicorn" in answer
    assert "npm run dev" in answer
