"""Application settings for the Multi-Agent Financial Research System.

Contract for later waves
------------------------
* :func:`get_settings` returns a cached :class:`Settings` instance built from
  the process environment and the ``backend/.env`` file.  The cache can be
  cleared with ``get_settings.cache_clear()`` (useful in tests).
* :func:`settings` is the module level convenience accessor.  It is a
  *function* and not a module level mutable object so that a reloaded
  configuration can never be silently ignored by an importing module.
* :func:`load_settings` is the startup helper: it resolves the settings and
  runs :func:`validate_runtime_settings`.  The FastAPI application factory
  (Wave 5) MUST call ``load_settings()`` during startup so that an invalid or
  unsafe configuration fails fast instead of at the first request.
* :func:`validate_runtime_settings` raises
  :class:`app.core.exceptions.ConfigurationError` when the configuration is
  self-contradictory or unsafe for the selected environment.

Environment variable naming
---------------------------
Every field is overridable from the environment using the UPPER_SNAKE_CASE
name of the field, because ``env_prefix`` is empty.  List valued settings
(``ALLOWED_DOCUMENT_EXTENSIONS``, ``ALLOWED_MIME_TYPES``, ``CORS_ORIGINS``)
are parsed by pydantic-settings as JSON arrays, e.g.::

    CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

The ``.env`` file is resolved relative to the ``backend/`` directory, so the
application behaves identically no matter which working directory it is
started from.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError

__all__ = [
    "BACKEND_DIR",
    "ENV_FILE",
    "Settings",
    "get_settings",
    "load_settings",
    "settings",
    "validate_runtime_settings",
]

BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
ENV_FILE: Path = BACKEND_DIR / ".env"

#: Values that must never survive into a production deployment.
_DEV_PASSWORD_MARKER = "frs_dev_password"
_DEV_HOST_MARKER = "127.0.0.1:55432"

#: Smallest accepted upload size (1 MiB) - anything smaller is a mistake.
MIN_UPLOAD_SIZE_BYTES = 1_048_576


class Settings(BaseSettings):
    """Strongly typed runtime configuration for the whole backend."""

    model_config = SettingsConfigDict(
        env_file=(ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )

    # ---- application metadata -------------------------------------------------
    app_name: str = "Multi-Agent Financial Research System"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    # ---- database -------------------------------------------------------------
    database_url: str = (
        "postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research"
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_echo: bool = False

    # ---- document storage -----------------------------------------------------
    storage_provider: Literal["local"] = "local"
    storage_root: Path = Path("data/storage")
    max_upload_size_bytes: int = 52_428_800
    allowed_document_extensions: list[str] = [".pdf"]
    allowed_mime_types: list[str] = ["application/pdf"]
    max_pdf_pages: int = 2000
    min_text_chars_per_page: int = 40

    # ---- embeddings -----------------------------------------------------------
    embedding_provider: Literal["fastembed"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    embedding_batch_size: int = 32
    embedding_max_retries: int = 3
    embedding_timeout_seconds: float = 60.0

    # ---- chunking -------------------------------------------------------------
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    chunk_min_tokens: int = 32
    chunk_max_tokens: int = 1024

    # ---- retrieval ------------------------------------------------------------
    retrieval_top_k: int = 10
    retrieval_max_top_k: int = 100

    # ---- processing pipeline --------------------------------------------------
    processing_max_attempts: int = 3
    # Strategy: the processing pipeline runs in a background thread of the
    # API process, never inline in the request that uploaded the document.
    # A request therefore never blocks on the extraction of a document.  The
    # inline runner exists for the scripts and the tests, which set the
    # flag explicitly.
    processing_inline: bool = False
    table_extraction_enabled: bool = True
    ocr_enabled: bool = False
    ocr_language: str = "eng"

    # ---- http -----------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ---- seed corpus ----------------------------------------------------------
    seed_manifest_path: Path = Path("data/seed_manifest.json")
    seed_documents_dir: Path = Path("data/documents")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


def settings() -> Settings:
    """Return the cached application settings (convenience accessor)."""
    return get_settings()


def validate_runtime_settings(config: Settings | None = None) -> None:
    """Validate the effective configuration.

    Raises
    ------
    app.core.exceptions.ConfigurationError
        If the configuration is self-contradictory, or if a ``production``
        deployment still uses development credentials or an open CORS policy.
    """
    config = config or get_settings()

    if config.app_env == "production":
        if (
            _DEV_PASSWORD_MARKER in config.database_url
            or _DEV_HOST_MARKER in config.database_url
        ):
            raise ConfigurationError(
                "DATABASE_URL still points at the development database; "
                "override it before running in production",
                details={"database_url_host": _redact_url(config.database_url)},
            )
        if config.debug:
            raise ConfigurationError(
                "DEBUG must be disabled when APP_ENV=production",
                details={"debug": config.debug},
            )
        if "*" in config.cors_origins:
            raise ConfigurationError(
                "CORS_ORIGINS must not contain '*' when APP_ENV=production",
                details={"cors_origins": config.cors_origins},
            )

    if not 1 <= config.embedding_dimension <= 4096:
        raise ConfigurationError(
            "EMBEDDING_DIMENSION must be between 1 and 4096",
            details={"embedding_dimension": config.embedding_dimension},
        )

    if config.chunk_overlap_tokens >= config.chunk_size_tokens:
        raise ConfigurationError(
            "CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS",
            details={
                "chunk_overlap_tokens": config.chunk_overlap_tokens,
                "chunk_size_tokens": config.chunk_size_tokens,
            },
        )

    if config.chunk_min_tokens > config.chunk_size_tokens:
        raise ConfigurationError(
            "CHUNK_MIN_TOKENS must not exceed CHUNK_SIZE_TOKENS",
            details={
                "chunk_min_tokens": config.chunk_min_tokens,
                "chunk_size_tokens": config.chunk_size_tokens,
            },
        )

    if config.chunk_max_tokens < config.chunk_size_tokens:
        raise ConfigurationError(
            "CHUNK_MAX_TOKENS must not be smaller than CHUNK_SIZE_TOKENS",
            details={
                "chunk_max_tokens": config.chunk_max_tokens,
                "chunk_size_tokens": config.chunk_size_tokens,
            },
        )

    if config.embedding_batch_size < 1:
        raise ConfigurationError(
            "EMBEDDING_BATCH_SIZE must be at least 1",
            details={"embedding_batch_size": config.embedding_batch_size},
        )

    if config.retrieval_top_k > config.retrieval_max_top_k:
        raise ConfigurationError(
            "RETRIEVAL_TOP_K must not exceed RETRIEVAL_MAX_TOP_K",
            details={
                "retrieval_top_k": config.retrieval_top_k,
                "retrieval_max_top_k": config.retrieval_max_top_k,
            },
        )

    if config.max_upload_size_bytes < MIN_UPLOAD_SIZE_BYTES:
        raise ConfigurationError(
            "MAX_UPLOAD_SIZE_BYTES must be at least 1 MiB",
            details={"max_upload_size_bytes": config.max_upload_size_bytes},
        )


def load_settings() -> Settings:
    """Return validated settings; used by the application startup hook."""
    config = get_settings()
    validate_runtime_settings(config)
    return config


def _redact_url(url: str) -> str:
    """Return ``url`` without its password component."""
    if "@" not in url or "//" not in url:
        return url
    scheme, _, remainder = url.partition("//")
    credentials, _, host = remainder.rpartition("@")
    if ":" not in credentials:
        return url
    user, _, _password = credentials.partition(":")
    return f"{scheme}//{user}:***@{host}"