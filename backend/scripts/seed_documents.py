"""Seed the database with the documents of the seed corpus.

The loader reads a *manifest* - a JSON file that pins the URL, the SHA-256
checksum, the metadata and the retrieval probe of every seed document -
downloads the documents that are missing, registers them through the real
:class:`~app.services.document_service.DocumentService` and runs the real
ingestion pipeline through the
:class:`~app.agents.job_runner.InlineJobRunner`.

Run it from the ``backend/`` directory::

    python -m scripts.seed_documents --workspace "Seed Documents"

or from the repository root::

    python backend/scripts/seed_documents.py --workspace "Seed Documents"

Design rules
------------
* **The checksum is the contract.**  A file whose SHA-256 does not match the
  manifest is never ingested.
* **The loader never fabricates a document.**  A failed download is reported
  with its exact error and the remaining documents are still processed.
* **The loader is idempotent.**  A document that is already present in the
  workspace is reported as *already present* and is not ingested a second
  time (unless ``--force`` is given).
* **The loader heals the metadata of the corpus.**  The manifest is
  authoritative: the metadata of a document is reconciled with the
  manifest even when the document is not ingested again, therefore a
  document that was seeded with the old (buggy) behaviour is repaired by
  the next run of the loader.
* **Nothing runs in the background.**  The inline job runner finishes the
  ingestion before the script exits, therefore the summary the script prints
  is the state of the database.
* **The paths are anchored at the repository root.**  Every relative path is
  resolved against the root of the repository, which is computed from
  ``__file__``; the script therefore behaves identically no matter from which
  directory it was started.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
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

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.enums import DocumentType  # noqa: E402

__all__ = [
    "BACKEND_DIR",
    "DEFAULT_DATA_DIR",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_WORKSPACE_NAME",
    "MANIFEST_VERSION",
    "DownloadResult",
    "ManifestError",
    "SeedResult",
    "build_runtime",
    "download_document",
    "load_manifest",
    "main",
    "resolve_path",
    "validate_manifest",
]
#: Version of the manifest format this loader understands.
MANIFEST_VERSION = "1.0"

#: Default location of the manifest (relative to the repository root).
DEFAULT_MANIFEST_PATH: Path = REPO_ROOT / "data" / "seed_manifest.json"

#: Default directory the documents are downloaded into.
DEFAULT_DATA_DIR: Path = REPO_ROOT / "data" / "documents"

#: Name of the workspace the seed documents are registered in.
DEFAULT_WORKSPACE_NAME = "Seed Documents"

#: Description of the workspace the loader creates.
WORKSPACE_DESCRIPTION = "Seed corpus of the Multi-Agent Financial Research System."

#: Keys every manifest must carry.
REQUIRED_MANIFEST_KEYS: tuple[str, ...] = ("manifest_version", "generated_at", "documents")

#: Keys every document entry of a manifest must carry.
REQUIRED_DOCUMENT_KEYS: tuple[str, ...] = (
    "company",
    "title",
    "document_type",
    "fiscal_period",
    "period_end",
    "publication_date",
    "source_url",
    "filename",
    "sha256",
    "size_bytes",
    "page_count",
    "request_headers",
    "search_probe",
)

#: A safe local file name of a seed document.
FILENAME_PATTERN = r"^[a-z0-9_\-]+\.pdf$"

#: A SHA-256 checksum in lower case hexadecimal.
SHA256_PATTERN = r"^[0-9a-f]{64}$"

#: An ISO date (``YYYY-MM-DD``).
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

#: The magic bytes every PDF file starts with.
PDF_MAGIC = b"%PDF-"

#: The ``User-Agent`` that is sent when a document does not declare one.
DEFAULT_USER_AGENT = "FinancialResearchSeedLoader/1.0 (contact@example.com)"

#: Timeout of a single download request (seconds).
DOWNLOAD_TIMEOUT_SECONDS = 120

#: Number of bytes that are read at once while a document is downloaded.
DOWNLOAD_BLOCK_BYTES = 1 << 16

#: The valid values of ``document_type``.
VALID_DOCUMENT_TYPES: frozenset[str] = frozenset(member.value for member in DocumentType)


class ManifestError(Exception):
    """Raised when a manifest is missing, unreadable or invalid."""


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def _validate_document(document: Any, index: int) -> list[str]:
    """Return the problems of the document entry *index* of a manifest."""
    label = f"documents[{index}]"
    if not isinstance(document, dict):
        return [f"{label} must be a JSON object"]

    problems: list[str] = []
    for key in REQUIRED_DOCUMENT_KEYS:
        if key not in document:
            problems.append(f"{label} is missing the required key {key!r}")
    if problems:
        return problems

    for key in ("company", "title", "fiscal_period", "source_url", "filename", "search_probe"):
        value = document[key]
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label}.{key} must be a non-empty string")

    document_type = document["document_type"]
    if not isinstance(document_type, str) or document_type not in VALID_DOCUMENT_TYPES:
        problems.append(
            f"{label}.document_type must be one of {sorted(VALID_DOCUMENT_TYPES)}"
        )

    for key in ("period_end", "publication_date"):
        value = document[key]
        if not isinstance(value, str) or re.match(DATE_PATTERN, value) is None:
            problems.append(f"{label}.{key} must be an ISO date (YYYY-MM-DD)")

    source_url = document["source_url"]
    if isinstance(source_url, str) and not source_url.startswith("https://"):
        problems.append(f"{label}.source_url must start with 'https://'")

    filename = document["filename"]
    if isinstance(filename, str):
        if re.match(FILENAME_PATTERN, filename) is None:
            problems.append(f"{label}.filename must match {FILENAME_PATTERN}")
        if "/" in filename or "\\" in filename:
            problems.append(f"{label}.filename must not contain a path separator")

    checksum = document["sha256"]
    if not isinstance(checksum, str) or re.match(SHA256_PATTERN, checksum) is None:
        problems.append(f"{label}.sha256 must be 64 lower case hexadecimal characters")

    for key in ("size_bytes", "page_count"):
        value = document[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            problems.append(f"{label}.{key} must be a positive integer")

    headers = document["request_headers"]
    if not isinstance(headers, dict):
        problems.append(f"{label}.request_headers must be an object")
    else:
        for name, value in headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                problems.append(f"{label}.request_headers must map strings to strings")
                break

    return problems


def validate_manifest(manifest: Any) -> list[str]:
    """Return every problem of *manifest*.

    An empty list means that the manifest is valid.  The function never
    raises: a malformed manifest is reported as a list of human readable
    problems, therefore a caller can show all of them at once.
    """
    if not isinstance(manifest, dict):
        return ["the manifest must be a JSON object"]

    problems: list[str] = []
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            problems.append(f"the manifest is missing the required key {key!r}")
    if problems:
        return problems

    version = manifest["manifest_version"]
    if not isinstance(version, str) or not version.strip():
        problems.append("'manifest_version' must be a non-empty string")
    generated_at = manifest["generated_at"]
    if not isinstance(generated_at, str) or not generated_at.strip():
        problems.append("'generated_at' must be a non-empty string")

    documents = manifest["documents"]
    if not isinstance(documents, list):
        problems.append("'documents' must be a list")
        return problems
    if not documents:
        problems.append("'documents' must not be empty")

    for index, document in enumerate(documents):
        problems.extend(_validate_document(document, index))

    for key in ("company", "filename"):
        seen: dict[str, list[int]] = {}
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                continue
            value = document.get(key)
            if isinstance(value, str) and value:
                seen.setdefault(value, []).append(index)
        for value, indexes in seen.items():
            if len(indexes) > 1:
                problems.append(
                    f"the {key} {value!r} is used by more than one document "
                    f"(entries {indexes})"
                )

    return problems


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the manifest at *path* and return it.

    Raises
    ------
    ManifestError
        If the file is missing, is not valid JSON or does not satisfy
        :func:`validate_manifest`.
    """
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ManifestError(f"the manifest {manifest_path} does not exist")
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(
            f"the manifest {manifest_path} could not be read: {exc}"
        ) from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"the manifest {manifest_path} is not valid JSON: {exc}"
        ) from exc

    problems = validate_manifest(manifest)
    if problems:
        listed = "\n  - ".join(problems)
        raise ManifestError(f"the manifest {manifest_path} is invalid:\n  - {listed}")
    return manifest


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
def resolve_path(value: str | Path, *, base: Path = REPO_ROOT) -> Path:
    """Return *value* as an absolute path.

    A relative path is resolved against *base* (the root of the repository by
    default), therefore the script behaves identically no matter from which
    directory it was started.
    """
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def _resolved_settings(settings: Settings) -> Settings:
    """Return *settings* with the storage root anchored at the repository."""
    return settings.model_copy(
        update={"storage_root": resolve_path(settings.storage_root)}
    )
# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DownloadResult:
    """The outcome of a single download."""

    path: Path
    size_bytes: int
    sha256: str
    http_status: int | None


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(DOWNLOAD_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def download_document(
    url: str,
    destination: Path,
    *,
    request_headers: dict[str, str] | None = None,
    max_bytes: int,
) -> DownloadResult:
    """Download *url* into *destination* and return the outcome.

    The bytes are streamed into a ``.part`` file and are moved into place
    only after the whole body was received, therefore a half written file is
    never mistaken for a complete one.  The size cap is enforced while the
    body is read: the ``Content-Length`` header is never trusted, because
    some servers use a chunked transfer encoding and do not send it at all.

    Raises
    ------
    ManifestError
        If the download failed, exceeded the size cap or did not deliver a
        PDF.
    """
    headers = {str(name): str(value) for name, value in (request_headers or {}).items()}
    headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
    headers.setdefault("Accept", "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8")

    request = urllib.request.Request(url, headers=headers, method="GET")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")

    digest = hashlib.sha256()
    total = 0
    head = b""
    status: int | None = None
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 0) or response.getcode() or 0) or None
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    if int(declared) > max_bytes:
                        raise ManifestError(
                            f"the download of {url} announces {declared} bytes which "
                            f"exceeds the maximum of {max_bytes} bytes"
                        )
                except ValueError:
                    pass
            with partial.open("wb") as handle:
                while True:
                    block = response.read(DOWNLOAD_BLOCK_BYTES)
                    if not block:
                        break
                    if not head:
                        head = block[: len(PDF_MAGIC)]
                    total += len(block)
                    if total > max_bytes:
                        raise ManifestError(
                            f"the download of {url} exceeds the maximum of "
                            f"{max_bytes} bytes"
                        )
                    digest.update(block)
                    handle.write(block)
        if head != PDF_MAGIC:
            raise ManifestError(
                f"the download of {url} is not a PDF (the '%PDF-' marker is missing)"
            )
        os.replace(partial, destination)
    except urllib.error.HTTPError as exc:
        raise ManifestError(
            f"the download of {url} failed with HTTP {exc.code} {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ManifestError(f"the download of {url} failed: {exc.reason}") from exc
    except OSError as exc:
        raise ManifestError(f"the download of {url} failed: {exc}") from exc
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    return DownloadResult(
        path=destination,
        size_bytes=total,
        sha256=digest.hexdigest(),
        http_status=status,
    )


def verify_local_file(path: Path, expected_sha256: str) -> tuple[bool, str]:
    """Return whether the file at *path* matches *expected_sha256*."""
    if not path.is_file():
        return False, f"the file {path} does not exist"
    actual = _hash_file(path)
    if actual != expected_sha256:
        return (
            False,
            f"the SHA-256 of {Path(path).name} is {actual} but the manifest "
            f"pins {expected_sha256}",
        )
    return True, ""
# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Runtime:
    """The services the loader needs."""

    settings: Settings
    storage: Any
    document_service: Any
    workspace_service: Any
    agent: Any
    runner: Any
    session_factory: Any


def build_runtime(settings: Settings) -> Runtime:
    """Build the real services the loader drives."""
    from app.agents.document_agent import DocumentAgent
    from app.agents.job_runner import InlineJobRunner
    from app.core.storage import create_storage_backend
    from app.db.session import SessionLocal
    from app.embeddings.service import create_embedding_service
    from app.ingestion.chunking import ChunkerConfig, TokenAwareChunker
    from app.ingestion.extractors.ocr import OcrExtractor
    from app.ingestion.extractors.pdf_tables import PdfPlumberTableExtractor
    from app.ingestion.extractors.pdf_text import PyMuPdfTextExtractor
    from app.ingestion.pipeline import IngestionPipeline
    from app.ingestion.validators import FileValidator
    from app.services.document_service import DocumentService
    from app.services.workspace_service import WorkspaceService
    from app.vectorstore.pgvector_store import PgVectorStore

    storage = create_storage_backend(settings)
    embedding_service = create_embedding_service(settings)
    vector_store = PgVectorStore(
        SessionLocal,
        dimension=settings.embedding_dimension,
        embedding_config_hash=embedding_service.config_hash,
    )
    document_service = DocumentService(
        SessionLocal,
        storage=storage,
        validator=FileValidator(settings),
    )
    workspace_service = WorkspaceService(SessionLocal, storage=storage)
    chunker = TokenAwareChunker(
        ChunkerConfig(
            chunk_size_tokens=settings.chunk_size_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
            chunk_min_tokens=settings.chunk_min_tokens,
            chunk_max_tokens=settings.chunk_max_tokens,
        )
    )
    pipeline = IngestionPipeline(
        storage=storage,
        text_extractor=PyMuPdfTextExtractor(settings),
        table_extractor=PdfPlumberTableExtractor(settings),
        ocr_extractor=OcrExtractor(settings),
        chunker=chunker,
        embedding_service=embedding_service,
        vector_store=vector_store,
        reporter=document_service,
        embedding_source=vector_store,
        settings=settings,
    )
    agent = DocumentAgent(
        pipeline=pipeline,
        document_service=document_service,
        session_factory=SessionLocal,
    )
    return Runtime(
        settings=settings,
        storage=storage,
        document_service=document_service,
        workspace_service=workspace_service,
        agent=agent,
        runner=InlineJobRunner(agent),
        session_factory=SessionLocal,
    )


def resolve_workspace(workspace_service: Any, name: str) -> tuple[Any, bool]:
    """Return the workspace *name* and whether it was created."""
    page, _total = workspace_service.list_workspaces(limit=1000, name_contains=name)
    for summary in page:
        if summary.name == name:
            return summary, False
    summary = workspace_service.create_workspace(
        name=name,
        description=WORKSPACE_DESCRIPTION,
    )
    return summary, True
# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class SeedResult:
    """The outcome of a single document of the seed corpus."""

    company: str
    filename: str
    status: str
    pages: int | None = None
    chunks: int | None = None
    duration_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def failed(self) -> bool:
        """Return whether the document could not be seeded."""
        return self.status == "failed"


def _ensure_file(
    entry: dict[str, Any],
    destination: Path,
    *,
    skip_download: bool,
    max_bytes: int,
) -> tuple[Path | None, str | None]:
    """Return the local file of *entry* and an error message."""
    checksum = entry["sha256"]
    if destination.is_file():
        ok, problem = verify_local_file(destination, checksum)
        if ok:
            return destination, None
        print(f"  ! checksum mismatch: {problem}")
        if skip_download:
            return None, problem
        print("  -> re-downloading the document")
    else:
        if skip_download:
            return None, (
                f"the file {destination} is missing and --skip-download was given"
            )
        print("  -> downloading the document")

    url = entry["source_url"]
    try:
        result = download_document(
            url,
            destination,
            request_headers=entry.get("request_headers") or {},
            max_bytes=max_bytes,
        )
    except ManifestError as exc:
        return None, str(exc)
    print(
        f"  <- HTTP {result.http_status}, {result.size_bytes} bytes, "
        f"sha256 {result.sha256}"
    )
    if result.sha256 != checksum:
        destination.unlink(missing_ok=True)
        return None, (
            f"the SHA-256 of the downloaded file is {result.sha256} but the "
            f"manifest pins {checksum}; the file was removed and the document "
            f"was not ingested"
        )
    return destination, None


def _manifest_metadata(entry: dict[str, Any]) -> dict[str, str]:
    """Return the metadata of the manifest that belongs to *entry*."""
    return {
        "company_name": entry["company"],
        "document_title": entry["title"],
        "document_type": entry["document_type"],
        "fiscal_period": entry["fiscal_period"],
        "source_url": entry["source_url"],
    }


def _metadata_matches(entry: dict[str, Any], values: Any) -> bool:
    """Return whether *values* carries the metadata of the manifest.

    *values* is either a document summary or a document row: the names of
    the compared attributes are the same on both.
    """
    return all(
        getattr(values, name) == value
        for name, value in _manifest_metadata(entry).items()
    )


def _reconcile_manifest_metadata(
    runtime: Runtime,
    document_id: Any,
    entry: dict[str, Any],
) -> bool:
    """Write the metadata of the manifest onto the stored document.

    The manifest is authoritative for the seed corpus: every value is
    pinned and reviewed.  The write is therefore an unconditional UPDATE
    of the metadata columns, so that a document that carries a heuristic
    detection (or a value of an older manifest) is repaired.  The write is
    idempotent: a document that already carries the pinned values keeps
    them.

    The page count is the one exception: it is a fact that the extraction
    produced and it is only written when the document does not carry one
    yet.

    Returns
    -------
    bool
        Whether the stored metadata had to be repaired.
    """
    from app.repositories.document_repository import DocumentRepository

    with runtime.session_factory() as session:
        repository = DocumentRepository(session)
        document = repository.get(document_id)
        if document is None:
            raise ManifestError(f"the document {document_id} does not exist")

        repaired = not _metadata_matches(entry, document)
        fields: dict[str, Any] = dict(_manifest_metadata(entry))
        if document.page_count is None:
            fields["page_count"] = int(entry["page_count"])
        repository.update(document, **fields)
    return repaired


def _existing_document_id(runtime: Runtime, workspace_id: Any, content_hash: str) -> Any:
    """Return the id of the document of *workspace_id* with *content_hash*."""
    from app.repositories.document_repository import DocumentRepository

    with runtime.session_factory() as session:
        document = DocumentRepository(session).get_by_content_hash(
            workspace_id, content_hash
        )
        return None if document is None else document.id


def seed_document(
    runtime: Runtime,
    entry: dict[str, Any],
    *,
    workspace_id: Any,
    data_dir: Path,
    skip_download: bool,
    force: bool,
    process: bool,
) -> SeedResult:
    """Seed a single document of the manifest and return the outcome."""
    from app.schemas.document import DocumentMetadata

    started = time.perf_counter()
    company = entry["company"]
    filename = entry["filename"]
    destination = data_dir / filename

    path, error = _ensure_file(
        entry,
        destination,
        skip_download=skip_download,
        max_bytes=runtime.settings.max_upload_size_bytes,
    )
    if path is None:
        return SeedResult(
            company=company,
            filename=filename,
            status="failed",
            duration_seconds=time.perf_counter() - started,
            error=error,
        )

    if force:
        previous_id = _existing_document_id(runtime, workspace_id, entry["sha256"])
        if previous_id is not None:
            print("  -> removing the previous version of the document (--force)")
            runtime.document_service.delete_document(previous_id)

    metadata = DocumentMetadata(
        company_name=company,
        document_title=entry["title"],
        document_type=entry["document_type"],
        fiscal_period=entry["fiscal_period"],
        source_url=entry["source_url"],
    )
    payload = path.read_bytes()
    registration = runtime.document_service.register_upload(
        workspace_id=workspace_id,
        filename=filename,
        data=payload,
        declared_mime_type="application/pdf",
        metadata=metadata,
    )

    if registration.duplicate and not force:
        summary = runtime.document_service.get_document(registration.document_id)
        repaired = _reconcile_manifest_metadata(
            runtime, registration.document_id, entry
        )
        summary = runtime.document_service.get_document(registration.document_id)
        detail = (
            "the stored metadata was repaired"
            if repaired
            else "the stored metadata already matched the manifest"
        )
        print(
            f"  = already present (status {summary.processing_status}, "
            f"{summary.chunk_count} chunks, metadata reconciled: {detail})"
        )
        return SeedResult(
            company=company,
            filename=filename,
            status="already present (metadata reconciled)",
            pages=summary.page_count,
            chunks=summary.chunk_count,
            duration_seconds=time.perf_counter() - started,
        )

    if not process:
        print("  = registered (the ingestion was not run: --no-process)")
        return SeedResult(
            company=company,
            filename=filename,
            status="registered",
            duration_seconds=time.perf_counter() - started,
        )

    print("  -> running the ingestion pipeline")
    runtime.runner.submit(registration.document_id)
    summary = runtime.document_service.get_document(registration.document_id)
    job = runtime.document_service.get_job_summary(registration.document_id)
    duration = time.perf_counter() - started

    if summary.processing_status != "completed":
        return SeedResult(
            company=company,
            filename=filename,
            status="failed",
            pages=summary.page_count,
            chunks=summary.chunk_count,
            duration_seconds=duration,
            error=(
                f"the ingestion failed with status {summary.processing_status} "
                f"({summary.error_code}: {summary.error_message})"
            ),
        )

    if _metadata_matches(entry, summary):
        print("  -> the metadata of the manifest survived the ingestion")
    else:
        print(
            "  ! the metadata of the ingestion did not match the manifest; "
            "it was reconciled"
        )
        _reconcile_manifest_metadata(runtime, registration.document_id, entry)
        summary = runtime.document_service.get_document(registration.document_id)
    print(
        f"  = processed (status {summary.processing_status}, "
        f"{summary.page_count} pages, {summary.chunk_count} chunks, "
        f"job {job.status if job is not None else 'unknown'})"
    )
    return SeedResult(
        company=company,
        filename=filename,
        status="processed",
        pages=summary.page_count,
        chunks=summary.chunk_count,
        duration_seconds=duration,
    )


def _select_documents(
    manifest: dict[str, Any], only: Sequence[str] | None
) -> list[dict[str, Any]]:
    """Return the documents of *manifest* that were requested."""
    documents = list(manifest.get("documents") or [])
    if not only:
        return documents

    wanted = {name.strip().casefold() for name in only if name.strip()}
    known = {str(entry.get("company", "")).casefold() for entry in documents}
    unknown = sorted(name for name in wanted if name not in known)
    if unknown:
        raise ManifestError(
            "the manifest does not contain the company/corporation: " + ", ".join(unknown)
        )
    return [
        entry
        for entry in documents
        if str(entry.get("company", "")).casefold() in wanted
    ]


def _print_summary(results: Sequence[SeedResult]) -> None:
    """Print the summary table of the run."""
    headers = ("COMPANY", "STATUS", "PAGES", "CHUNKS", "DURATION", "WARNINGS")
    rows = [
        (
            result.company,
            result.status,
            "-" if result.pages is None else str(result.pages),
            "-" if result.chunks is None else str(result.chunks),
            f"{result.duration_seconds:.1f}s",
            "; ".join(result.warnings) if result.warnings else "",
        )
        for result in results
    ]
    widths = [
        max([len(headers[column])] + [len(row[column]) for row in rows])
        for column in range(len(headers))
    ]
    line = "  ".join(
        headers[column].ljust(widths[column]) for column in range(len(headers))
    )
    print()
    print("=" * len(line))
    print(line)
    print("-" * len(line))
    for row in rows:
        print(
            "  ".join(row[column].ljust(widths[column]) for column in range(len(headers)))
        )
    print("-" * len(line))


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line of the loader."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed_documents",
        description=(
            "Download the seed corpus, register it and run the real "
            "ingestion pipeline."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="path of the manifest (default: the SEED_MANIFEST_PATH setting)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="directory the documents are stored in (default: SEED_DOCUMENTS_DIR)",
    )
    parser.add_argument(
        "--workspace",
        default=DEFAULT_WORKSPACE_NAME,
        help=f"name of the workspace (default: {DEFAULT_WORKSPACE_NAME!r})",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="COMPANY",
        help="only seed this company (may be given more than once)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="only use the documents that are already in the data directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download and re-ingest the documents even if they are present",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run the index verification after the seeding",
    )
    parser.add_argument(
        "--no-process",
        action="store_true",
        help="register the documents but do not run the ingestion pipeline",
    )
    return parser.parse_args(argv)


def _redact(url: str) -> str:
    """Return *url* without its password component."""
    if "@" not in url or "//" not in url:
        return url
    scheme, _, remainder = url.partition("//")
    credentials, _, host = remainder.rpartition("@")
    if ":" not in credentials:
        return url
    user, _, _password = credentials.partition(":")
    return f"{scheme}//{user}:***@{host}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the loader and return the exit code."""
    args = _parse_args(argv)
    settings = _resolved_settings(get_settings())

    manifest_path = resolve_path(args.manifest or settings.seed_manifest_path)
    data_dir = resolve_path(args.data_dir or settings.seed_documents_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"manifest : {manifest_path}")
    print(f"data dir : {data_dir}")
    print(f"workspace: {args.workspace}")
    print(f"database : {_redact(settings.database_url)}")
    print()

    try:
        manifest = load_manifest(manifest_path)
        documents = _select_documents(manifest, args.only)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        runtime = build_runtime(settings)
    except Exception as exc:  # the runtime could not be built
        print(f"ERROR: the runtime could not be built: {exc}", file=sys.stderr)
        return 1

    try:
        workspace, created = resolve_workspace(runtime.workspace_service, args.workspace)
    except Exception as exc:
        print(f"ERROR: the workspace could not be resolved: {exc}", file=sys.stderr)
        return 1
    print(
        f"workspace '{workspace.name}' "
        f"({'created' if created else 'reused'}, id {workspace.id})"
    )
    print()

    results: list[SeedResult] = []
    for entry in documents:
        print(f"* {entry['company']} - {entry['title']}")
        try:
            result = seed_document(
                runtime,
                entry,
                workspace_id=workspace.id,
                data_dir=data_dir,
                skip_download=args.skip_download,
                force=args.force,
                process=not args.no_process,
            )
        except Exception as exc:  # a single document must not abort the run
            result = SeedResult(
                company=entry["company"],
                filename=entry["filename"],
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            print(f"  ! {result.error}")
        results.append(result)
        print()

    _print_summary(results)
    failed = [result for result in results if result.failed]
    print(
        f"{len(results) - len(failed)}/{len(results)} document(s) seeded, "
        f"{len(failed)} failed"
    )

    exit_code = 1 if failed else 0

    if args.verify:
        print()
        print("running the index verification")
        from scripts.verify_index import run_verification

        if not run_verification(workspace_name=args.workspace, settings=settings):
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())