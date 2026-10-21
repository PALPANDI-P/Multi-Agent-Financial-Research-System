"""Import hygiene guarantees for the ``app`` package.

The tests in this module protect four properties of the package tree that
are easy to break when several teams work in parallel:

``test_every_app_module_imports``
    Every module below ``app`` must be importable on its own.  A module that
    genuinely needs a live database is tolerated only when it fails with a
    connection error, and such a module is reported explicitly.
``test_app_import_graph_is_acyclic``
    The intra-``app`` import graph must stay acyclic.  The offending cycle
    is reported in full (as a path) when one is found.
``test_importing_chunking_does_not_import_extractors``
    :mod:`app.ingestion.chunking` must stay independent of the heavy
    extraction stack (PyMuPDF, pdfplumber).  The check runs in a subprocess
    so that ``sys.modules`` is pristine.
``test_ingestion_public_api_is_importable``
    The public API of :mod:`app.ingestion` must keep exposing every
    documented name.
"""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import subprocess
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path

import app

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
APP_PACKAGE = "app"

#: Modules whose import failed because the database was unreachable.  The
#: list is filled by :func:`test_every_app_module_imports`; it is empty for a
#: healthy checkout.
DB_CONNECTION_FAILURES: list[str] = []

#: Exception classes that indicate "the database is not reachable".
_CONNECTION_ERROR_NAMES = frozenset(
    {
        "ConnectionError",
        "ConnectionRefusedError",
        "DatabaseError",
        "InterfaceError",
        "OperationalError",
    }
)

#: Substrings that identify a connection failure in an error message.
_CONNECTION_ERROR_HINTS = (
    "could not connect",
    "connection refused",
    "connection to server",
    "failed to establish a connection",
    "no pg_hba.conf entry",
    "database system is starting up",
    "server closed the connection unexpectedly",
)

#: Every public name that :mod:`app.ingestion` promises to expose.
INGESTION_PUBLIC_API = (
    "EXTRACTION_METHOD_EMPTY",
    "EXTRACTION_METHOD_OCR",
    "EXTRACTION_METHOD_TABLE",
    "EXTRACTION_METHOD_TEXT",
    "Chunk",
    "DocumentExtractionMetadata",
    "DocumentExtractor",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedTable",
    "FileValidator",
    "OcrAvailability",
    "OcrExtractor",
    "PdfPlumberTableExtractor",
    "PyMuPdfTextExtractor",
    "ValidationIssue",
    "ValidationResult",
    "build_document_metadata",
    "detect_company_name",
    "detect_document_title",
    "detect_fiscal_period",
    "infer_document_type",
    "ocr_pages_for_document",
    "validate_upload",
)


def _is_app_module(name: str) -> bool:
    """Return ``True`` when *name* refers to a module of the ``app`` package."""
    return name == APP_PACKAGE or name.startswith(f"{APP_PACKAGE}.")


def _app_module_names() -> list[str]:
    """Return the dotted name of every module below ``app``."""
    names = [APP_PACKAGE]
    for _, module_name, _ in pkgutil.walk_packages(
        app.__path__, prefix=f"{APP_PACKAGE}."
    ):
        names.append(module_name)
    return names


def _is_connection_error(exc: BaseException) -> bool:
    """Return ``True`` when *exc* means "the database is unreachable"."""
    if isinstance(exc, ConnectionError):
        return True
    if any(klass.__name__ in _CONNECTION_ERROR_NAMES for klass in type(exc).__mro__):
        return True
    message = str(exc).lower()
    return any(hint in message for hint in _CONNECTION_ERROR_HINTS)


def test_every_app_module_imports() -> None:
    """Every module of the ``app`` package must be importable on its own."""
    failures: list[str] = []
    db_failures: list[str] = []

    for module_name in _app_module_names():
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            entry = f"{module_name}: {type(exc).__name__}: {exc}"
            if _is_connection_error(exc):
                db_failures.append(entry)
            else:
                failures.append(entry)

    DB_CONNECTION_FAILURES[:] = [entry.split(":", 1)[0] for entry in db_failures]
    if db_failures:
        warnings.warn(
            "modules that require a live database: " + "; ".join(db_failures),
            stacklevel=2,
        )

    assert not failures, "modules failed to import:\n" + "\n".join(failures)


def _module_name(path: Path) -> str:
    """Return the dotted module name of the file at *path*."""
    parts = path.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _app_modules() -> dict[str, Path]:
    """Return every module of the ``app`` package mapped to its file."""
    return {_module_name(path): path for path in sorted(APP_ROOT.rglob("*.py"))}


def _import_edges(path: Path, modules: dict[str, Path]) -> set[str]:
    """Return the intra-``app`` modules that the file at *path* imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    edges: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_app_module(alias.name):
                    edges.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or not node.module or not _is_app_module(node.module):
                continue
            edges.add(node.module)
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                if candidate in modules:
                    edges.add(candidate)
    return {edge for edge in edges if edge in modules}


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """Return the path of a cycle in *graph*, or ``None`` when it is acyclic."""
    white, grey, black = 0, 1, 2
    colour = dict.fromkeys(graph, white)

    for start in sorted(graph):
        if colour[start] != white:
            continue
        colour[start] = grey
        path = [start]
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(sorted(graph[start])))]
        while stack:
            node, children = stack[-1]
            for child in children:
                if colour[child] == grey:
                    return [*path[path.index(child) :], child]
                if colour[child] == white:
                    colour[child] = grey
                    path.append(child)
                    stack.append((child, iter(sorted(graph[child]))))
                    break
            else:
                colour[node] = black
                stack.pop()
                path.pop()
    return None


def test_app_import_graph_is_acyclic() -> None:
    """The intra-``app`` import graph must not contain a cycle."""
    modules = _app_modules()
    graph = {name: _import_edges(path, modules) for name, path in modules.items()}
    cycle = _find_cycle(graph)
    assert cycle is None, "import cycle detected: " + " -> ".join(cycle)


def test_importing_chunking_does_not_import_extractors() -> None:
    """``app.ingestion.chunking`` must not drag in the extraction stack."""
    code = (
        "import sys, app.ingestion.chunking; "
        "print([m for m in sys.modules if 'extractors' in m])"
    )
    env = dict(os.environ)
    python_path = [str(BACKEND_ROOT)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
        env=env,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    loaded = ast.literal_eval(result.stdout.strip())
    assert loaded == [], f"importing app.ingestion.chunking pulled in {loaded}"


def test_ingestion_public_api_is_importable() -> None:
    """Every documented name of :mod:`app.ingestion` must be importable."""
    import app.ingestion as ingestion
    from app.ingestion import (
        EXTRACTION_METHOD_EMPTY,
        EXTRACTION_METHOD_OCR,
        EXTRACTION_METHOD_TABLE,
        EXTRACTION_METHOD_TEXT,
        Chunk,
        DocumentExtractionMetadata,
        DocumentExtractor,
        ExtractedDocument,
        ExtractedPage,
        ExtractedTable,
        FileValidator,
        OcrAvailability,
        OcrExtractor,
        PdfPlumberTableExtractor,
        PyMuPdfTextExtractor,
        ValidationIssue,
        ValidationResult,
        build_document_metadata,
        detect_company_name,
        detect_document_title,
        detect_fiscal_period,
        infer_document_type,
        ocr_pages_for_document,
        validate_upload,
    )

    resolved = [
        EXTRACTION_METHOD_EMPTY,
        EXTRACTION_METHOD_OCR,
        EXTRACTION_METHOD_TABLE,
        EXTRACTION_METHOD_TEXT,
        Chunk,
        DocumentExtractionMetadata,
        DocumentExtractor,
        ExtractedDocument,
        ExtractedPage,
        ExtractedTable,
        FileValidator,
        OcrAvailability,
        OcrExtractor,
        PdfPlumberTableExtractor,
        PyMuPdfTextExtractor,
        ValidationIssue,
        ValidationResult,
        build_document_metadata,
        detect_company_name,
        detect_document_title,
        detect_fiscal_period,
        infer_document_type,
        ocr_pages_for_document,
        validate_upload,
    ]
    assert all(value is not None for value in resolved)
    for name, value in zip(INGESTION_PUBLIC_API, resolved, strict=True):
        assert value is getattr(ingestion, name), f"{name} is not exported by app.ingestion"

    assert set(ingestion.__all__) == set(INGESTION_PUBLIC_API)
