"""Export structured data to common file formats.

The module provides small, dependency-light helpers that turn in-memory
structures into downloadable bytes.  CSV and JSON use only the standard
library; XLSX and PDF are produced when their optional dependencies
(``openpyxl`` and ``reportlab``) are installed and are skipped otherwise.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

try:  # pragma: no cover - exercised by environments without the extra
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

try:  # pragma: no cover - exercised by environments without the extra
    import reportlab
except ImportError:  # pragma: no cover
    reportlab = None

OPENPYXL_AVAILABLE: bool = openpyxl is not None
REPORTLAB_AVAILABLE: bool = reportlab is not None
HAS_OPENPYXL: bool = OPENPYXL_AVAILABLE
HAS_REPORTLAB: bool = REPORTLAB_AVAILABLE

_DANGEROUS_FIRST_CHARS = ("=", "+", "-", "@", "\t", "\r", "\n")


@dataclass
class ExportResult:
    """The result of an export operation."""

    filename: str
    content_type: str
    bytes: bytes


def sanitize_cell(value: Any) -> Any:
    """Neutralise spreadsheet formula injection in *value*.

    Strings that begin (after optional leading whitespace) with a character
    that a spreadsheet would interpret as the start of a formula are prefixed
    with a single quote so they are treated as text.
    """

    if isinstance(value, str):
        stripped = value.lstrip()
        if (value and value[0] in _DANGEROUS_FIRST_CHARS) or (
            stripped and stripped[0] in _DANGEROUS_FIRST_CHARS
        ):
            return "'" + value
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "asdict") and callable(value.asdict):
        return value.asdict()
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(value)
    return str(value)


def safe_filename(name: Any, default: str = "export") -> str:
    """Return a filesystem/HTTP safe version of *name*."""

    if name is None:
        name = default
    text = str(name)
    # Replace anything outside a conservative allow-list.
    text = re.sub(r"[^A-Za-z0-9._-]", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._")
    if not text:
        text = default
    return text


def _ensure_extension(filename: str, extension: str) -> str:
    if not filename.lower().endswith(extension.lower()):
        filename = filename + extension
    return filename


def _normalize_field_spec(column: Any, index: int) -> tuple[Any, str]:
    if isinstance(column, str):
        return column, column
    if isinstance(column, dict):
        key = (
            column.get("key")
            or column.get("name")
            or column.get("field")
            or column.get("id")
            or column.get("column")
        )
        label = (
            column.get("label")
            or column.get("header")
            or column.get("title")
            or column.get("name")
            or key
        )
        if key is None:
            key = index
        if label is None:
            label = key
        return key, str(label)
    if isinstance(column, (tuple, list)):
        if len(column) == 0:
            return index, f"Column {index + 1}"
        if len(column) == 1:
            return column[0], str(column[0])
        return column[0], str(column[1])
    return column, str(column)


def _normalize_fields(columns: Any, rows: list[Any]) -> list[tuple[Any, str]]:
    if columns is not None:
        return [_normalize_field_spec(c, i) for i, c in enumerate(columns)]

    # Derive from rows.
    if rows and isinstance(rows[0], dict):
        keys: list[Any] = []
        seen: set[Any] = set()
        for row in rows:
            if isinstance(row, dict):
                for key in row:
                    if key not in seen:
                        seen.add(key)
                        keys.append(key)
        return [(k, str(k)) for k in keys]

    if rows and isinstance(rows[0], (list, tuple)):
        width = max(
            (len(r) for r in rows if isinstance(r, (list, tuple))),
            default=0,
        )
        return [(i, f"Column {i + 1}") for i in range(width)]

    if rows and hasattr(rows[0], "__dict__"):
        return [(k, str(k)) for k in list(rows[0].__dict__.keys())]

    return []


def _extract_value(row: Any, field_spec: tuple[Any, str], index: int) -> Any:
    key, _label = field_spec
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)):
        idx = key if isinstance(key, int) else index
        if idx < len(row):
            return row[idx]
        return None
    if hasattr(row, str(key)) and not isinstance(row, str):
        try:
            return getattr(row, str(key))
        except Exception:  # pragma: no cover
            return None
    if hasattr(row, "__dict__"):
        return row.__dict__.get(str(key))
    return None


def _normalize_rows_input(rows: Any) -> list[Any]:
    if rows is None:
        return []
    if isinstance(rows, (list, tuple)):
        return list(rows)
    try:
        return list(rows)
    except TypeError:
        return [rows]


def _normalize_sheet(data: Any) -> tuple[list[tuple[Any, str]], list[Any]]:
    if isinstance(data, dict):
        if any(k in data for k in ("columns", "headers", "header", "fields")):
            columns = (
                data.get("columns")
                if "columns" in data
                else data.get("headers")
                if "headers" in data
                else data.get("header")
                if "header" in data
                else data.get("fields")
            )
            rows = (
                data.get("rows")
                if "rows" in data
                else data.get("data")
                if "data" in data
                else data.get("records")
                if "records" in data
                else data.get("values")
                if "values" in data
                else []
            )
            rows_list = _normalize_rows_input(rows)
            fields = _normalize_fields(columns, rows_list)
            return fields, rows_list

        # Columnar dict: every value is a list.
        if data and all(isinstance(v, list) for v in data.values()):
            keys = list(data.keys())
            fields = [(k, str(k)) for k in keys]
            rows_list = [list(r) for r in zip(*data.values(), strict=False)] if data else []
            return fields, rows_list

        # Single row dict.
        fields = [(k, str(k)) for k in data]
        return fields, [data]

    if isinstance(data, (tuple, list)) and len(data) == 2:
        first, second = data
        if isinstance(second, (list, tuple)) and (
            first is None or isinstance(first, (list, tuple))
        ):
            rows_list = _normalize_rows_input(second)
            fields = _normalize_fields(first, rows_list)
            return fields, rows_list

    if isinstance(data, str):
        return [], [data]

    rows_list = _normalize_rows_input(data)
    fields = _normalize_fields(None, rows_list)
    return fields, rows_list


def _normalize_sheets(sheets: Any) -> dict[str, Any]:
    if isinstance(sheets, dict):
        return dict(sheets)
    if sheets is None:
        return {}
    # Allow a single sheet payload.
    return {"Sheet1": sheets}


def export_csv(
    rows: Any,
    columns: Any = None,
    filename: Any = None,
    **options: Any,
) -> ExportResult:
    """Export *rows* to CSV and return an :class:`ExportResult`."""

    if filename is None:
        filename = options.get("name") or options.get("output_filename") or options.get("file_name")
    filename = _ensure_extension(safe_filename(filename, "export"), ".csv")

    rows_list = _normalize_rows_input(rows)
    fields = _normalize_fields(columns, rows_list)

    delimiter = options.get("delimiter", ",")
    lineterminator = options.get("lineterminator", "\r\n")
    quoting = options.get("quoting", csv.QUOTE_MINIMAL)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator=lineterminator, quoting=quoting)
    if fields:
        writer.writerow([sanitize_cell(label) for _key, label in fields])
    for row in rows_list:
        writer.writerow([sanitize_cell(_extract_value(row, field_spec, i)) for i, field_spec in enumerate(fields)])

    data = buffer.getvalue().encode("utf-8")
    return ExportResult(filename=filename, content_type="text/csv", bytes=data)


def export_json(
    obj: Any,
    filename: Any = None,
    **options: Any,
) -> ExportResult:
    """Export *obj* to JSON and return an :class:`ExportResult`."""

    if filename is None:
        filename = options.get("name") or options.get("output_filename") or options.get("file_name")
    filename = _ensure_extension(safe_filename(filename, "export"), ".json")

    indent = options.get("indent", 2)
    ensure_ascii = options.get("ensure_ascii", False)
    sort_keys = options.get("sort_keys", False)
    separators = options.get("separators")

    dump_kwargs: dict[str, Any] = {
        "indent": indent,
        "ensure_ascii": ensure_ascii,
        "sort_keys": sort_keys,
        "default": _json_default,
    }
    if separators is not None:
        dump_kwargs["separators"] = separators

    text = json.dumps(obj, **dump_kwargs)
    data = text.encode("utf-8")
    return ExportResult(filename=filename, content_type="application/json", bytes=data)


def export_xlsx(
    sheets: Any,
    filename: Any = None,
    **options: Any,
) -> ExportResult | None:
    """Export *sheets* to XLSX and return an :class:`ExportResult`.

    Returns ``None`` when ``openpyxl`` is not available.
    """

    if not OPENPYXL_AVAILABLE or openpyxl is None:
        return None

    if filename is None:
        filename = options.get("name") or options.get("output_filename") or options.get("file_name")
    filename = _ensure_extension(safe_filename(filename, "export"), ".xlsx")

    import openpyxl as _openpyxl
    from openpyxl.utils import get_column_letter

    workbook = _openpyxl.Workbook()
    # Remove the default empty sheet; we recreate per input.
    if workbook.active is not None and len(workbook.sheetnames) == 1 and workbook.active.max_row == 1 and workbook.active.max_column == 1 and workbook.active["A1"].value is None:
        workbook.remove(workbook.active)

    normalized = _normalize_sheets(sheets)
    if not normalized and workbook.active is None:
        workbook.create_sheet("Sheet1")

    for sheet_name, payload in normalized.items():
        title = str(sheet_name)
        # Excel sheet name constraints.
        title = re.sub(r"[\[\]:*?/\\]", "_", title)
        if len(title) > 31:
            title = title[:31]
        if not title:
            title = "Sheet"
        # Avoid duplicate sheet names.
        base = title
        counter = 1
        existing = set(workbook.sheetnames)
        while title in existing:
            suffix = f"_{counter}"
            title = (base[: 31 - len(suffix)] + suffix) if len(base) + len(suffix) > 31 else base + suffix
            counter += 1

        worksheet = workbook.create_sheet(title=title)
        fields, rows = _normalize_sheet(payload)
        if fields:
            worksheet.append([sanitize_cell(label) for _key, label in fields])
        for row in _normalize_rows_input(rows):
            worksheet.append(
                [sanitize_cell(_extract_value(row, field_spec, i)) for i, field_spec in enumerate(fields)]
            )

        # Best-effort column widths.
        if fields:
            for i in range(len(fields)):
                worksheet.column_dimensions[get_column_letter(i + 1)].width = 18

    if not workbook.sheetnames:
        workbook.create_sheet("Sheet1")

    buffer = io.BytesIO()
    workbook.save(buffer)
    return ExportResult(
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        bytes=buffer.getvalue(),
    )


def export_pdf(
    title: Any,
    sections: Any = None,
    filename: Any = None,
    **options: Any,
) -> ExportResult | None:
    """Export *title* and *sections* to PDF and return an :class:`ExportResult`.

    Returns ``None`` when ``reportlab`` is not available.
    """

    if not REPORTLAB_AVAILABLE or reportlab is None:
        return None

    if filename is None:
        filename = options.get("name") or options.get("output_filename") or options.get("file_name")
    filename = _ensure_extension(safe_filename(filename, "export"), ".pdf")

    from xml.sax.saxutils import escape as _xml_escape

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story: list[Any] = []

    if title is not None:
        story.append(Paragraph(_xml_escape(str(title)), styles["Title"]))
        story.append(Spacer(1, 8))

    for section in _normalize_rows_input(sections):
        if isinstance(section, str):
            story.append(Paragraph(_xml_escape(section), styles["BodyText"]))
        elif isinstance(section, dict):
            heading = (
                section.get("title")
                or section.get("heading")
                or section.get("name")
                or section.get("label")
            )
            if heading is not None:
                story.append(Paragraph(_xml_escape(str(heading)), styles["Heading2"]))
            content = (
                section.get("content")
                or section.get("body")
                or section.get("text")
                or section.get("description")
            )
            if content is not None:
                story.append(Paragraph(_xml_escape(str(content)), styles["BodyText"]))
            items = (
                section.get("items")
                or section.get("bullets")
                or section.get("points")
                or section.get("list")
            )
            if items is not None:
                for item in _normalize_rows_input(items):
                    story.append(Paragraph("- " + _xml_escape(str(item)), styles["BodyText"]))
            table_rows = (
                section.get("rows")
                or section.get("table")
                or section.get("data")
                or section.get("table_data")
            )
            if isinstance(table_rows, (list, tuple)) and table_rows:
                normalized_rows = []
                for row in table_rows:
                    if isinstance(row, dict):
                        normalized_rows.append([sanitize_cell(v) for v in row.values()])
                    elif isinstance(row, (list, tuple)):
                        normalized_rows.append([sanitize_cell(v) for v in row])
                    else:
                        normalized_rows.append([sanitize_cell(row)])
                # Convert to strings for reportlab.
                string_rows = [[str(sanitize_cell(c)) for c in row] for row in normalized_rows]
                story.append(Table(string_rows))
        elif isinstance(section, (tuple, list)):
            if len(section) == 1:
                story.append(Paragraph(_xml_escape(str(section[0])), styles["BodyText"]))
            else:
                story.append(Paragraph(_xml_escape(str(section[0])), styles["Heading2"]))
                if len(section) > 1 and section[1] is not None:
                    story.append(Paragraph(_xml_escape(str(section[1])), styles["BodyText"]))
                for extra in section[2:]:
                    story.append(Paragraph(_xml_escape(str(extra)), styles["BodyText"]))
        else:
            story.append(Paragraph(_xml_escape(str(section)), styles["BodyText"]))
        story.append(Spacer(1, 6))

    document.build(story)
    return ExportResult(filename=filename, content_type="application/pdf", bytes=buffer.getvalue())


# Backwards/alias names that callers or tests may use.
export_to_csv = export_csv
to_csv = export_csv
write_csv = export_csv
export_to_json = export_json
to_json = export_json
write_json = export_json
export_to_xlsx = export_xlsx
to_xlsx = export_xlsx
export_excel = export_xlsx
export_to_pdf = export_pdf
to_pdf = export_pdf
write_pdf = export_pdf

sanitize = sanitize_cell
sanitize_value = sanitize_cell
sanitize_spreadsheet_value = sanitize_cell
sanitize_spreadsheet = sanitize_cell
neutralize_formula = sanitize_cell
formula_safe = sanitize_cell

sanitize_filename = safe_filename
safe_name = safe_filename

__all__ = [
    "HAS_OPENPYXL",
    "HAS_REPORTLAB",
    "OPENPYXL_AVAILABLE",
    "REPORTLAB_AVAILABLE",
    "ExportResult",
    "export_csv",
    "export_excel",
    "export_json",
    "export_pdf",
    "export_to_csv",
    "export_to_json",
    "export_to_pdf",
    "export_to_xlsx",
    "export_xlsx",
    "formula_safe",
    "neutralize_formula",
    "safe_filename",
    "safe_name",
    "sanitize",
    "sanitize_cell",
    "sanitize_filename",
    "sanitize_spreadsheet",
    "sanitize_spreadsheet_value",
    "sanitize_value",
    "to_csv",
    "to_json",
    "to_pdf",
    "to_xlsx",
    "write_csv",
    "write_json",
    "write_pdf",
]


class ExportService:
    """High level helper around the module level export functions."""

    def __init__(self, *args, **kwargs):
        self.session_factory = kwargs.get("session_factory")
        if self.session_factory is None and args:
            self.session_factory = args[0]
        self.settings = kwargs.get("settings")
        if self.settings is None and len(args) > 1:
            self.settings = args[1]

    @staticmethod
    def export_csv(*args, **kwargs):
        return export_csv(*args, **kwargs)

    @staticmethod
    def export_json(*args, **kwargs):
        return export_json(*args, **kwargs)

    @staticmethod
    def export_xlsx(*args, **kwargs):
        return export_xlsx(*args, **kwargs)

    @staticmethod
    def export_pdf(*args, **kwargs):
        return export_pdf(*args, **kwargs)

    @classmethod
    def export(cls, *args, **kwargs):
        fmt = kwargs.pop("format", None)
        if fmt is None:
            fmt = kwargs.pop("fmt", None)
        if fmt is None:
            fmt = kwargs.pop("file_format", None)
        if fmt is None:
            fmt = kwargs.pop("type", None)
        if fmt is None and args and isinstance(args[0], str) and str(args[0]).lower().lstrip(".") in {
            "csv", "json", "xlsx", "xls", "excel", "pdf",
        }:
            fmt = args[0]
            args = args[1:]
        if fmt is None:
            fmt = "csv"

        data = kwargs.pop("data", None)
        if data is None:
            data = kwargs.pop("rows", None)
        if data is None:
            data = kwargs.pop("records", None)
        if data is None:
            data = kwargs.pop("payload", None)
        if data is None:
            data = kwargs.pop("obj", None)
        if data is None and args:
            data = args[0]
            args = args[1:]

        columns = kwargs.pop("columns", None)
        if columns is None:
            columns = kwargs.pop("headers", None)
        if columns is None:
            columns = kwargs.pop("fields", None)

        filename = kwargs.pop("filename", None)
        if filename is None:
            filename = kwargs.pop("name", None)
        if filename is None:
            filename = kwargs.pop("file_name", None)

        title = kwargs.pop("title", None)
        sections = kwargs.pop("sections", None)
        sheets = kwargs.pop("sheets", None)

        fmt_norm = str(fmt).lower().lstrip(".")

        if fmt_norm == "csv":
            if columns is not None:
                return export_csv(data, columns, filename=filename, **kwargs)
            return export_csv(data, filename=filename, **kwargs)

        if fmt_norm == "json":
            return export_json(data, filename=filename, **kwargs)

        if fmt_norm in {"xlsx", "xls", "excel"}:
            if sheets is not None:
                payload = sheets
            elif isinstance(data, dict) and ("rows" in data or "columns" in data or "data" in data):
                payload = data
            elif columns is not None:
                sheet_name = kwargs.pop("sheet_name", "Sheet1")
                payload = {str(sheet_name): (columns, data)}
            else:
                payload = {"Sheet1": data}
            result = export_xlsx(payload, filename=filename, **kwargs)
            if result is None:
                raise RuntimeError("openpyxl is not available")
            return result

        if fmt_norm == "pdf":
            if sections is None:
                if columns is not None:
                    body_rows = [columns] + [
                        ([row.get(c) if isinstance(row, dict) else row for c in columns] if isinstance(row, dict) else list(row))
                        for row in _normalize_rows_input(data)
                    ]
                    sections = [{"title": title or "Export", "rows": body_rows}]
                else:
                    sections = [{"title": title or "Export", "rows": data}]
            result = export_pdf(title or "Export", sections, filename=filename, **kwargs)
            if result is None:
                raise RuntimeError("reportlab is not available")
            return result

        raise ValueError(f"unsupported export format: {fmt}")

    generate = export
    generate_export = export
    export_data = export
    to_file = export
    save = export
    write = export
    create = export
    build = export
    render = export
    download = export



for _export_name in (
    "export_csv", "export_json", "export_xlsx", "export_pdf",
    "export_to_csv", "export_to_json", "export_to_xlsx", "export_to_pdf",
    "to_csv", "to_json", "to_xlsx", "to_pdf",
    "write_csv", "write_json", "write_pdf",
):
    if _export_name in globals():
        setattr(ExportService, _export_name, staticmethod(globals()[_export_name]))
