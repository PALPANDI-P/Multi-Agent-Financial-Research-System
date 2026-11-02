"""Unit tests for :mod:`app.services.export_service`."""

from __future__ import annotations

import csv
import io
import json

import pytest

from app.services import export_service as es


def test_export_result_fields() -> None:
    result = es.ExportResult(filename="a.csv", content_type="text/csv", bytes=b"x")
    assert result.filename == "a.csv"
    assert result.content_type == "text/csv"
    assert result.bytes == b"x"


def test_sanitize_cell_formula() -> None:
    assert es.sanitize_cell("=SUM(1,2)") == "'=SUM(1,2)"
    assert es.sanitize_cell("+cmd") == "'+cmd"
    assert es.sanitize_cell("-cmd") == "'-cmd"
    assert es.sanitize_cell("@cmd") == "'@cmd"
    assert es.sanitize_cell("\tcmd") == "'\tcmd"
    assert es.sanitize_cell("safe") == "safe"
    assert es.sanitize_cell(42) == 42
    assert es.sanitize_cell(None) is None


def test_safe_filename() -> None:
    assert es.safe_filename("../secret.csv") == "secret.csv"
    assert es.safe_filename("a b/c.txt") == "a_b_c.txt"
    assert es.safe_filename("") == "export"
    assert es.safe_filename(None) == "export"


def test_export_csv_basic() -> None:
    rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    result = es.export_csv(rows, ["name", "age"])
    assert result.filename == "export.csv"
    assert result.content_type == "text/csv"
    text = result.bytes.decode("utf-8")
    reader = list(csv.reader(io.StringIO(text)))
    assert reader[0] == ["name", "age"]
    assert reader[1] == ["Alice", "30"]
    assert reader[2] == ["Bob", "25"]


def test_export_csv_formula_sanitized() -> None:
    rows = [{"v": "=1+1"}]
    result = es.export_csv(rows, ["v"])
    assert b"'=1+1" in result.bytes


def test_export_csv_derives_columns() -> None:
    rows = [{"b": 2, "a": 1}]
    result = es.export_csv(rows)
    text = result.bytes.decode("utf-8")
    assert text.splitlines()[0] == "b,a"


def test_export_csv_custom_filename() -> None:
    result = es.export_csv([], ["x"], filename="out.csv")
    assert result.filename == "out.csv"


def test_export_json_basic() -> None:
    result = es.export_json({"a": [1, 2], "b": "x"})
    assert result.filename == "export.json"
    assert result.content_type == "application/json"
    parsed = json.loads(result.bytes.decode("utf-8"))
    assert parsed == {"a": [1, 2], "b": "x"}


def test_export_json_datetime() -> None:
    from datetime import datetime

    result = es.export_json({"d": datetime(2024, 1, 1)})
    parsed = json.loads(result.bytes.decode("utf-8"))
    assert parsed["d"] == "2024-01-01T00:00:00"


def test_export_json_custom_filename() -> None:
    result = es.export_json(1, filename="data.json")
    assert result.filename == "data.json"


@pytest.mark.skipif(not es.OPENPYXL_AVAILABLE, reason="openpyxl not installed")
def test_export_xlsx_basic() -> None:
    pytest.importorskip("openpyxl")
    result = es.export_xlsx({"Sheet1": [{"a": 1, "b": "=x"}]})
    assert result is not None
    assert result.filename == "export.xlsx"
    assert result.content_type.startswith("application/vnd.openxmlformats")
    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(result.bytes))
    assert wb.sheetnames == ["Sheet1"]
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("a", "b")
    assert rows[1] == (1, "'=x")


@pytest.mark.skipif(not es.OPENPYXL_AVAILABLE, reason="openpyxl not installed")
def test_export_xlsx_tuple_columns() -> None:
    pytest.importorskip("openpyxl")
    result = es.export_xlsx({"S": (["x", "y"], [[1, 2], [3, 4]])})
    assert result is not None
    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(result.bytes))
    ws = wb["S"]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("x", "y")
    assert rows[1] == (1, 2)


@pytest.mark.skipif(not es.OPENPYXL_AVAILABLE, reason="openpyxl not installed")
def test_export_xlsx_columnar() -> None:
    pytest.importorskip("openpyxl")
    result = es.export_xlsx({"S": {"a": [1, 2], "b": [3, 4]}})
    assert result is not None


def test_export_xlsx_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(es, "OPENPYXL_AVAILABLE", False)
    assert es.export_xlsx({"S": [{"a": 1}]}) is None


@pytest.mark.skipif(not es.REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_export_pdf_basic() -> None:
    pytest.importorskip("reportlab")
    result = es.export_pdf("Title", [{"title": "S1", "content": "hello", "items": ["a"]}])
    assert result is not None
    assert result.filename == "export.pdf"
    assert result.content_type == "application/pdf"
    assert result.bytes.startswith(b"%PDF")


def test_export_pdf_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(es, "REPORTLAB_AVAILABLE", False)
    assert es.export_pdf("Title", []) is None


def test_import_hygiene() -> None:
    import importlib

    importlib.import_module("app.services.export_service")
