"""Unit tests for the local storage backend."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import ConfigurationError, StorageError
from app.core.storage import LocalStorage, StorageBackend, create_storage_backend

pytestmark = pytest.mark.unit

KEY_PATTERN = re.compile(r"^\d{4}/\d{2}/[0-9a-f]{32}\.[a-z0-9._-]+$")


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    """Return a local storage backend rooted in a temporary directory."""
    return LocalStorage(tmp_path / "storage")


def test_local_storage_satisfies_the_protocol(storage: LocalStorage) -> None:
    """The local backend implements the whole StorageBackend protocol."""
    assert isinstance(storage, StorageBackend)


def test_save_and_read_round_trip(storage: LocalStorage) -> None:
    """Bytes written with ``save`` come back unchanged from ``read``."""
    payload = b"%PDF-1.7 fake document content"

    key = storage.save(payload, extension=".pdf")

    assert storage.read(key) == payload
    assert storage.exists(key) is True


def test_save_creates_the_root_directory(tmp_path: Path) -> None:
    """The storage root is created on demand."""
    root = tmp_path / "deeply" / "nested" / "storage"
    storage = LocalStorage(root)

    storage.save(b"payload", extension=".pdf")

    assert root.is_dir()


def test_saved_key_has_the_documented_shape(storage: LocalStorage) -> None:
    """The key is ``YYYY/MM/<uuid4>.<ext>``."""
    key = storage.save(b"payload", extension=".pdf")

    assert KEY_PATTERN.match(key)
    assert key.endswith(".pdf")


def test_save_never_uses_the_callers_filename(storage: LocalStorage) -> None:
    """A hostile filename cannot influence the generated path."""
    hostile_filename = "../../etc/passwd"

    key = storage.save(b"payload", extension=".pdf")

    assert "passwd" not in key
    assert ".." not in key
    assert hostile_filename not in key
    assert "etc" not in storage.path_for(key).parts


def test_extension_is_normalised_to_lowercase(storage: LocalStorage) -> None:
    """The extension is lowercased and gets exactly one leading dot."""
    assert storage.save(b"a", extension="PDF").endswith(".pdf")
    assert storage.save(b"b", extension=".pdf").endswith(".pdf")
    assert storage.save(b"c", extension=" .Pdf ").endswith(".pdf")


@pytest.mark.parametrize("extension", ["", "  ", "pd f", "pdf/../x", "a" * 17, "..", "pdf\x00"])
def test_invalid_extension_is_rejected(storage: LocalStorage, extension: str) -> None:
    """Only short, alphanumeric-ish extensions are accepted."""
    with pytest.raises(StorageError) as excinfo:
        storage.save(b"payload", extension=extension)

    assert excinfo.value.code == "invalid_extension"


@pytest.mark.parametrize(
    "storage_key",
    [
        "../escape",
        "../../escape.txt",
        "2026/10/../../escape",
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
        "c:\\Windows\\System32",
        "\\\\server\\share\\file.pdf",
        "",
    ],
)
def test_path_for_rejects_escaping_keys(storage: LocalStorage, storage_key: str) -> None:
    """Every attempt to leave the storage root is refused."""
    with pytest.raises(StorageError) as excinfo:
        storage.path_for(storage_key)

    assert excinfo.value.code == "storage_path_escape"


def test_path_for_returns_a_path_inside_the_root(storage: LocalStorage) -> None:
    """A valid key resolves to a path below the root."""
    key = storage.save(b"payload", extension=".pdf")

    path = storage.path_for(key)

    assert path.is_file()
    assert path.is_relative_to(storage.root.resolve())


def test_read_of_a_missing_key_raises(storage: LocalStorage) -> None:
    """Reading an unknown key is a domain error, not an OS error."""
    with pytest.raises(StorageError) as excinfo:
        storage.read("2026/10/does-not-exist.pdf")

    assert excinfo.value.code == "storage_not_found"


def test_delete_is_idempotent(storage: LocalStorage) -> None:
    """Deleting a document twice is not an error."""
    key = storage.save(b"payload", extension=".pdf")

    storage.delete(key)

    assert storage.exists(key) is False
    storage.delete(key)
    assert storage.exists(key) is False


def test_exists_reports_missing_documents(storage: LocalStorage) -> None:
    """``exists`` is ``False`` for a key that was never written."""
    assert storage.exists("2026/10/never-written.pdf") is False


def test_create_storage_backend_returns_local_storage(tmp_path: Path) -> None:
    """The ``local`` provider maps to :class:`LocalStorage`."""
    settings = Settings(storage_provider="local", storage_root=tmp_path / "storage")

    backend = create_storage_backend(settings)

    assert isinstance(backend, LocalStorage)
    assert backend.root == tmp_path / "storage"


def test_create_storage_backend_rejects_other_providers(tmp_path: Path) -> None:
    """An unknown provider fails fast with a configuration error."""
    settings = Settings.model_construct(
        storage_provider="s3",
        storage_root=tmp_path / "storage",
    )

    with pytest.raises(ConfigurationError) as excinfo:
        create_storage_backend(settings)

    assert excinfo.value.code == "unsupported_storage_provider"
