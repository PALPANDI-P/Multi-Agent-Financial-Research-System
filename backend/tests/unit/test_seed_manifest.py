"""Unit tests of the seed manifest and of its validation.

The tests are completely offline: they read the manifest that ships with the
repository and they never touch the database or the network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.core.enums import DocumentType
from scripts.seed_documents import (
    DEFAULT_MANIFEST_PATH,
    ManifestError,
    load_manifest,
    validate_manifest,
)

#: The manifest of the repository.
MANIFEST_PATH: Path = DEFAULT_MANIFEST_PATH

#: The file name of a seed document must be a safe local name.
FILENAME_PATTERN = re.compile(r"^[a-z0-9_\-]+\.pdf$")

#: A SHA-256 checksum in lower case hexadecimal.
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: The companies the seed corpus must contain.
EXPECTED_COMPANIES: set[str] = {
    "Walmart Inc.",
    "JPMorgan Chase & Co.",
    "Netflix, Inc.",
    "Apple Inc.",
}

#: The keys every document entry of a manifest must carry.
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


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the manifest of the repository."""
    return load_manifest(MANIFEST_PATH)


@pytest.fixture(scope="module")
def documents(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the document entries of the manifest."""
    return list(manifest["documents"])


def test_the_manifest_file_exists() -> None:
    """The manifest ships with the repository."""
    assert MANIFEST_PATH.is_file()
    assert MANIFEST_PATH.name == "seed_manifest.json"
    assert MANIFEST_PATH.parent.name == "data"


def test_the_manifest_parses_as_json_and_has_the_required_keys(
    manifest: dict[str, Any],
) -> None:
    """The manifest is a JSON object with the three top level keys."""
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    for key in ("manifest_version", "generated_at", "documents"):
        assert key in raw
    assert isinstance(manifest["manifest_version"], str)
    assert manifest["manifest_version"].strip()
    assert isinstance(manifest["generated_at"], str)
    assert manifest["generated_at"].strip()
    assert isinstance(manifest["documents"], list)
    assert manifest["documents"]


def test_every_document_entry_has_all_required_fields(
    documents: list[dict[str, Any]],
) -> None:
    """Every document entry carries every required key with the right type."""
    for entry in documents:
        for key in REQUIRED_DOCUMENT_KEYS:
            assert key in entry, f"{entry.get('company')!r} is missing {key!r}"
        assert isinstance(entry["company"], str)
        assert isinstance(entry["title"], str)
        assert isinstance(entry["document_type"], str)
        assert isinstance(entry["fiscal_period"], str)
        assert isinstance(entry["period_end"], str)
        assert isinstance(entry["publication_date"], str)
        assert isinstance(entry["source_url"], str)
        assert isinstance(entry["filename"], str)
        assert isinstance(entry["sha256"], str)
        assert isinstance(entry["size_bytes"], int)
        assert isinstance(entry["page_count"], int)
        assert isinstance(entry["request_headers"], dict)
        assert isinstance(entry["search_probe"], str)


def test_the_document_type_is_a_valid_document_type(
    documents: list[dict[str, Any]],
) -> None:
    """Every document type is one of the values of ``DocumentType``."""
    allowed = {member.value for member in DocumentType}
    for entry in documents:
        assert entry["document_type"] in allowed


def test_the_filename_is_a_safe_local_name(
    documents: list[dict[str, Any]],
) -> None:
    """Every file name is a lower case local name without a path separator."""
    for entry in documents:
        filename = entry["filename"]
        assert FILENAME_PATTERN.match(filename), filename
        assert "/" not in filename
        assert "\\" not in filename
        assert ".." not in filename
        assert filename == filename.lower()
        assert filename.endswith(".pdf")


def test_the_source_url_uses_https(documents: list[dict[str, Any]]) -> None:
    """Every source url is an absolute https url."""
    for entry in documents:
        assert entry["source_url"].startswith("https://")
        assert " " not in entry["source_url"]


def test_the_sha256_is_64_hexadecimal_characters(
    documents: list[dict[str, Any]],
) -> None:
    """Every checksum is a SHA-256 hex digest."""
    for entry in documents:
        assert SHA256_PATTERN.match(entry["sha256"]), entry["sha256"]
        assert len(entry["sha256"]) == 64


def test_the_size_and_the_page_count_are_positive(
    documents: list[dict[str, Any]],
) -> None:
    """Every document has a size and a page count that are greater than zero."""
    for entry in documents:
        assert entry["size_bytes"] > 0
        assert entry["page_count"] > 0


def test_the_search_probe_is_not_empty(documents: list[dict[str, Any]]) -> None:
    """Every document declares the query the verification uses."""
    for entry in documents:
        assert entry["search_probe"].strip()
        assert len(entry["search_probe"]) >= 3


def test_the_four_expected_companies_are_present(
    documents: list[dict[str, Any]],
) -> None:
    """The seed corpus holds the four expected companies."""
    companies = {entry["company"] for entry in documents}
    assert companies >= EXPECTED_COMPANIES


def test_the_company_names_are_unique(documents: list[dict[str, Any]]) -> None:
    """No company is used by two documents."""
    companies = [entry["company"] for entry in documents]
    assert len(companies) == len(set(companies))


def test_the_filenames_are_unique(documents: list[dict[str, Any]]) -> None:
    """No file name is used by two documents."""
    filenames = [entry["filename"] for entry in documents]
    assert len(filenames) == len(set(filenames))


def test_the_real_manifest_passes_the_validation(
    manifest: dict[str, Any],
) -> None:
    """The manifest of the repository has no problem at all."""
    assert validate_manifest(manifest) == []


def _valid_document() -> dict[str, Any]:
    """Return a document entry that satisfies every rule of the manifest."""
    return {
        "company": "Example Inc.",
        "title": "Example Inc. Form 10-K for the fiscal year ended December 31, 2025",
        "document_type": "form_10k",
        "fiscal_period": "FY2025",
        "period_end": "2025-12-31",
        "publication_date": "2026-01-23",
        "source_url": "https://www.sec.gov/Archives/edgar/example.pdf",
        "filename": "example_fy2025_form_10k.pdf",
        "sha256": "a" * 64,
        "size_bytes": 1234,
        "page_count": 42,
        "request_headers": {"User-Agent": "FinancialResearchSeedLoader/1.0"},
        "search_probe": "net sales consolidated statements of income",
    }


def _valid_manifest() -> dict[str, Any]:
    """Return a manifest that satisfies every rule of the manifest."""
    return {
        "manifest_version": "1.0",
        "generated_at": "2026-01-23T00:00:00+00:00",
        "documents": [_valid_document()],
    }


def test_a_valid_manifest_has_no_problems() -> None:
    """The reference manifest is accepted."""
    assert validate_manifest(_valid_manifest()) == []


@pytest.mark.parametrize(
    ("description", "mutate"),
    [
        ("not an object", lambda m: m.clear()),
        ("documents is not a list", lambda m: m.update(documents={})),
        ("documents is empty", lambda m: m.update(documents=[])),
        (
            "the version is missing",
            lambda m: m.pop("manifest_version"),
        ),
        (
            "the generated_at is missing",
            lambda m: m.pop("generated_at"),
        ),
        (
            "the document type is unknown",
            lambda m: m["documents"][0].update(document_type="balance_sheet"),
        ),
        (
            "the file name has a path separator",
            lambda m: m["documents"][0].update(filename="sub/dir/example.pdf"),
        ),
        (
            "the file name is not lower case",
            lambda m: m["documents"][0].update(filename="Example_FY2025.pdf"),
        ),
        (
            "the source url is not https",
            lambda m: m["documents"][0].update(source_url="http://example.com/a.pdf"),
        ),
        (
            "the checksum is too short",
            lambda m: m["documents"][0].update(sha256="abc"),
        ),
        (
            "the size is zero",
            lambda m: m["documents"][0].update(size_bytes=0),
        ),
        (
            "the page count is zero",
            lambda m: m["documents"][0].update(page_count=0),
        ),
        (
            "the search probe is empty",
            lambda m: m["documents"][0].update(search_probe="   "),
        ),
        (
            "a required key is missing",
            lambda m: m["documents"][0].pop("request_headers"),
        ),
        (
            "the request headers are not strings",
            lambda m: m["documents"][0].update(request_headers={"User-Agent": 42}),
        ),
        (
            "the company is used twice",
            lambda m: m["documents"].append(dict(m["documents"][0])),
        ),
        (
            "the file name is used twice",
            lambda m: m["documents"].append(dict(m["documents"][0], company="Other Inc.")),
        ),
    ],
)
def test_a_malformed_manifest_is_rejected(
    description: str, mutate: Any
) -> None:
    """Every malformed manifest is reported by the validation function."""
    manifest = _valid_manifest()
    mutate(manifest)
    problems = validate_manifest(manifest)
    assert problems, f"the malformed manifest {description!r} was not rejected"
    assert all(isinstance(problem, str) and problem for problem in problems)


def test_a_manifest_that_is_not_an_object_is_rejected() -> None:
    """A manifest that is not a JSON object is reported as such."""
    assert validate_manifest(["not", "a", "manifest"]) == [
        "the manifest must be a JSON object"
    ]


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    """The loader reports a manifest that does not exist."""
    with pytest.raises(ManifestError) as error:
        load_manifest(tmp_path / "does_not_exist.json")
    assert "does not exist" in str(error.value)


def test_a_manifest_that_is_not_json_is_reported(tmp_path: Path) -> None:
    """The loader reports a manifest that is not valid JSON."""
    broken = tmp_path / "seed_manifest.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError) as error:
        load_manifest(broken)
    assert "not valid JSON" in str(error.value)


def test_an_invalid_manifest_is_reported(tmp_path: Path) -> None:
    """The loader reports every problem of an invalid manifest."""
    invalid = tmp_path / "seed_manifest.json"
    invalid.write_text(json.dumps({"manifest_version": "1.0"}), encoding="utf-8")
    with pytest.raises(ManifestError) as error:
        load_manifest(invalid)
    assert "is invalid" in str(error.value)