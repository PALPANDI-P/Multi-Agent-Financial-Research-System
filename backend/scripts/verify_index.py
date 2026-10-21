"""Verify the seeded corpus against the real database.

The verification proves that the documents of the seed manifest really are
in the database, that every chunk they produced is intact (content, content
hash, page range, chunk type, embedding dimension, embedding configuration
hash) and that the retrieval of a document works: the search probe of the
manifest is executed against the real
:class:`~app.services.search_service.SearchService` and must return at least
one hit that points at a page.

Run it from the ``backend/`` directory::

    python -m scripts.verify_index --workspace "Seed Documents"

The exit code is ``0`` when every check passed and ``1`` otherwise; the
report names the check that failed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Directory that holds the ``app`` package.
BACKEND_DIR: Path = Path(__file__).resolve().parents[1]

#: Root of the repository (the parent of the ``backend`` directory).
REPO_ROOT: Path = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.enums import ChunkType  # noqa: E402


def _load_sibling_module(name: str, filename: str) -> Any:
    """Load the sibling module *filename* of this file under the name *name*.

    The module is loaded from its path instead of being imported as
    ``scripts.<name>`` because the repository root also carries a
    ``scripts`` directory: the file based loader therefore works no matter
    from which directory the script was started.
    """
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"the module {path} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


#: The seed loader; it owns the manifest, the paths and the services.
seed_documents = _load_sibling_module("frs_seed_documents", "seed_documents.py")

__all__ = [
    "Check",
    "DocumentReport",
    "main",
    "run_verification",
]

#: The chunk types a chunk may carry.
VALID_CHUNK_TYPES: frozenset[str] = frozenset(member.value for member in ChunkType)

#: Number of characters of the excerpt of the best hit.
EXCERPT_LENGTH = 160

#: The statement that reads the chunks of a document.
CHUNK_STATEMENT = """
    SELECT chunk_index,
           content,
           content_hash,
           page_start,
           page_end,
           chunk_type,
           vector_dims(embedding) AS embedding_dimension,
           embedding_config_hash
      FROM document_chunks
     WHERE document_id = :document_id
     ORDER BY chunk_index
"""

#: The statement that reads the documents of a workspace.
DOCUMENT_STATEMENT = """
    SELECT id,
           original_filename,
           company_name,
           document_title,
           document_type,
           fiscal_period,
           source_url,
           page_count,
           processing_status,
           processing_stage,
           error_code,
           error_message
      FROM documents
     WHERE workspace_id = :workspace_id
     ORDER BY created_at, id
"""
# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Check:
    """The outcome of a single verification check."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class DocumentReport:
    """The verification report of a single document."""

    company: str
    filename: str
    document_id: str | None = None
    status: str = "missing"
    pages_expected: int = 0
    pages_actual: int | None = None
    chunks: int = 0
    text_chunks: int = 0
    table_chunks: int = 0
    best_score: float | None = None
    best_page: int | None = None
    excerpt: str = ""
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return whether every check of the document passed."""
        return bool(self.checks) and all(check.passed for check in self.checks)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        """Record the outcome of a check."""
        self.checks.append(Check(name=name, passed=passed, detail=detail))


def _excerpt(text: str) -> str:
    """Return a short, single line excerpt of *text*."""
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= EXCERPT_LENGTH:
        return collapsed
    return collapsed[: EXCERPT_LENGTH - 3] + "..."


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
def _find_document(rows: Sequence[Any], entry: dict[str, Any]) -> Any:
    """Return the row of the document of *entry*."""
    for row in rows:
        if row["source_url"] and row["source_url"] == entry["source_url"]:
            return row
    for row in rows:
        if row["original_filename"] == entry["filename"]:
            return row
    for row in rows:
        if row["company_name"] and row["company_name"] == entry["company"]:
            return row
    return None


def _verify_chunks(
    report: DocumentReport,
    rows: Sequence[Any],
    *,
    page_count: int,
    expected_dimension: int,
    expected_config_hash: str,
) -> None:
    """Verify every chunk of a document."""
    report.chunks = len(rows)
    empty = [row["chunk_index"] for row in rows if not (row["content"] or "").strip()]
    report.add(
        "every chunk has a non-empty content",
        not empty,
        "" if not empty else f"the chunks {empty[:10]} are empty",
    )

    bad_hash = [
        row["chunk_index"]
        for row in rows
        if row["content_hash"] != hashlib.sha256((row["content"] or "").encode("utf-8")).hexdigest()
    ]
    report.add(
        "every content_hash matches the SHA-256 of the content",
        not bad_hash,
        "" if not bad_hash else f"the chunks {bad_hash[:10]} carry a wrong content_hash",
    )

    bad_pages = [
        row["chunk_index"]
        for row in rows
        if row["page_start"] is None
        or row["page_end"] is None
        or row["page_start"] < 1
        or row["page_end"] < row["page_start"]
        or row["page_end"] > page_count
    ]
    report.add(
        "every page range is inside the page range of the document",
        not bad_pages,
        ""
        if not bad_pages
        else f"the chunks {bad_pages[:10]} carry an invalid page range "
        f"(the document has {page_count} pages)",
    )

    bad_type = [row["chunk_index"] for row in rows if row["chunk_type"] not in VALID_CHUNK_TYPES]
    report.add(
        "every chunk_type is 'text' or 'table'",
        not bad_type,
        "" if not bad_type else f"the chunks {bad_type[:10]} carry an unknown chunk_type",
    )

    bad_dimension = [
        (row["chunk_index"], row["embedding_dimension"])
        for row in rows
        if row["embedding_dimension"] != expected_dimension
    ]
    report.add(
        f"every embedding has {expected_dimension} dimensions (vector_dims)",
        not bad_dimension,
        ""
        if not bad_dimension
        else f"the chunks {bad_dimension[:10]} carry a wrong dimension",
    )

    bad_config = [
        row["chunk_index"]
        for row in rows
        if row["embedding_config_hash"] != expected_config_hash
    ]
    report.add(
        "every embedding_config_hash matches the current embedding configuration",
        not bad_config,
        ""
        if not bad_config
        else f"the chunks {bad_config[:10]} were embedded with another configuration",
    )

    report.text_chunks = sum(1 for row in rows if row["chunk_type"] == ChunkType.TEXT.value)
    report.table_chunks = sum(1 for row in rows if row["chunk_type"] == ChunkType.TABLE.value)
def _verify_document(
    entry: dict[str, Any],
    *,
    document_row: Any,
    chunk_rows: Sequence[Any],
    workspace_id: Any,
    embedding_service: Any,
    search_service: Any,
    expected_dimension: int,
    expected_config_hash: str,
) -> DocumentReport:
    """Verify a single document of the manifest and return its report."""
    report = DocumentReport(
        company=entry["company"],
        filename=entry["filename"],
        pages_expected=int(entry["page_count"]),
    )

    if document_row is None:
        report.add("the document exists in the workspace", False, "no document row was found")
        return report

    report.document_id = str(document_row["id"])
    report.status = str(document_row["processing_status"])
    report.pages_actual = document_row["page_count"]
    report.add("the document exists in the workspace", True)

    mismatches: list[str] = []
    if document_row["company_name"] != entry["company"]:
        mismatches.append(
            f"company_name {document_row["company_name"]!r} != {entry['company']!r}"
        )
    if document_row["document_title"] != entry["title"]:
        mismatches.append(
            f"document_title {document_row["document_title"]!r} != {entry['title']!r}"
        )
    if document_row["fiscal_period"] != entry["fiscal_period"]:
        mismatches.append(
            f"fiscal_period {document_row["fiscal_period"]!r} != {entry['fiscal_period']!r}"
        )
    if document_row["source_url"] != entry["source_url"]:
        mismatches.append(
            f"source_url {document_row["source_url"]!r} != {entry['source_url']!r}"
        )
    if document_row["document_type"] != entry["document_type"]:
        mismatches.append(
            f"document_type {document_row['document_type']!r} != {entry['document_type']!r}"
        )
    report.add(
        "company, title, document type, fiscal period and source url match the manifest",
        not mismatches,
        "; ".join(mismatches),
    )

    report.add(
        "the processing status is 'completed'",
        report.status == "completed",
        ""
        if report.status == "completed"
        else f"the status is {report.status!r}"
        + (
            f" ({document_row["error_code"]}: {document_row["error_message"]})"
            if document_row["error_code"]
            else ""
        ),
    )

    report.add(
        "the page count matches the manifest",
        document_row["page_count"] == int(entry["page_count"]),
        f"the document has {document_row["page_count"]} pages, "
        f"the manifest pins {entry['page_count']}",
    )

    report.add(
        "the document has at least one chunk",
        len(chunk_rows) > 0,
        f"{len(chunk_rows)} chunks",
    )

    page_count = int(document_row["page_count"] or entry["page_count"])
    _verify_chunks(
        report,
        chunk_rows,
        page_count=page_count,
        expected_dimension=expected_dimension,
        expected_config_hash=expected_config_hash,
    )

    probe = str(entry["search_probe"])
    results = search_service.search(
        workspace_id=workspace_id,
        query=probe,
        limit=10,
        document_ids=[document_row["id"]],
    )
    hits = [item for item in results.results if item.page_start is not None]
    report.add(
        "the search probe returns a hit that points at a page",
        bool(hits),
        ""
        if hits
        else f"the probe {probe!r} returned {len(results.results)} hit(s), "
        f"none of them carries a page",
    )
    if results.results:
        best = max(results.results, key=lambda item: item.score)
        report.best_score = float(best.score)
        report.best_page = best.page_start
        report.excerpt = _excerpt(best.content)

    return report


def _print_report(report: DocumentReport) -> None:
    """Print the report of a single document."""
    print(f"* {report.company} ({report.filename})")
    print(
        f"    status   : {report.status}"
        f" | pages: {report.pages_actual}/{report.pages_expected}"
        f" | chunks: {report.chunks}"
        f" (text {report.text_chunks}, table {report.table_chunks})"
    )
    if report.best_score is not None:
        print(
            f"    best hit : score {report.best_score:.4f}"
            f" | page {report.best_page}"
        )
        print(f"    excerpt  : {report.excerpt}")
    for check in report.checks:
        marker = "ok  " if check.passed else "FAIL"
        detail = f" - {check.detail}" if check.detail else ""
        print(f"    [{marker}] {check.name}{detail}")


def run_verification(
    *,
    workspace_name: str = seed_documents.DEFAULT_WORKSPACE_NAME,
    settings: Any = None,
    manifest_path: Path | None = None,
) -> bool:
    """Verify the seeded corpus and return whether every check passed."""
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.embeddings.service import create_embedding_service
    from app.repositories.workspace_repository import WorkspaceRepository
    from app.services.search_service import SearchService
    from app.vectorstore.pgvector_store import PgVectorStore

    config = settings if settings is not None else get_settings()
    resolved_manifest = seed_documents.resolve_path(
        manifest_path or config.seed_manifest_path
    )
    print(f"manifest  : {resolved_manifest}")
    print(f"workspace : {workspace_name}")

    try:
        manifest = seed_documents.load_manifest(resolved_manifest)
    except seed_documents.ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return False

    embedding_service = create_embedding_service(config)
    vector_store = PgVectorStore(
        SessionLocal,
        dimension=config.embedding_dimension,
        embedding_config_hash=embedding_service.config_hash,
    )
    search_service = SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        settings=config,
    )

    with SessionLocal() as session:
        workspace = None
        for candidate in WorkspaceRepository(session).list(
            limit=1000, offset=0, name_contains=workspace_name
        )[0]:
            if candidate.name == workspace_name:
                workspace = candidate
                break
        if workspace is None:
            print(
                f"ERROR: the workspace {workspace_name!r} does not exist",
                file=sys.stderr,
            )
            return False

        workspace_id = workspace.id
        document_rows = session.execute(
            text(DOCUMENT_STATEMENT), {"workspace_id": workspace_id}
        ).mappings().all()
        document_rows = [dict(row) for row in document_rows]

    reports: list[DocumentReport] = []
    for entry in manifest["documents"]:
        row = _find_document(document_rows, entry)
        with SessionLocal() as session:
            chunk_rows: list[Any] = []
            if row is not None:
                chunk_rows = [
                    dict(chunk)
                    for chunk in session.execute(
                        text(CHUNK_STATEMENT), {"document_id": row["id"]}
                    ).mappings().all()
                ]
        report = _verify_document(
            entry,
            document_row=row,
            chunk_rows=chunk_rows,
            workspace_id=workspace_id,
            embedding_service=embedding_service,
            search_service=search_service,
            expected_dimension=int(config.embedding_dimension),
            expected_config_hash=embedding_service.config_hash,
        )
        reports.append(report)
        _print_report(report)
        print()

    failed = [report for report in reports if not report.passed]
    print("=" * 72)
    for report in failed:
        for check in report.checks:
            if not check.passed:
                print(f"FAILED: {report.company} - {check.name}: {check.detail}")
    if failed:
        print(
            f"FAIL: {len(failed)}/{len(reports)} document(s) failed the verification"
        )
        return False
    print(f"PASS: all {len(reports)} document(s) passed the verification")
    return True


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line of the verification."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.verify_index",
        description="Verify the seeded corpus against the real database.",
    )
    parser.add_argument(
        "--workspace",
        default=seed_documents.DEFAULT_WORKSPACE_NAME,
        help=(
            "name of the workspace that holds the seed documents "
            f"(default: {seed_documents.DEFAULT_WORKSPACE_NAME!r})"
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="path of the manifest (default: the SEED_MANIFEST_PATH setting)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the verification and return the exit code."""
    args = _parse_args(argv)
    manifest_path = (
        seed_documents.resolve_path(args.manifest)
        if args.manifest
        else None
    )
    try:
        passed = run_verification(
            workspace_name=args.workspace,
            manifest_path=manifest_path,
        )
    except Exception as exc:
        print(f"ERROR: the verification could not be run: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    return 0 if passed else 1


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())