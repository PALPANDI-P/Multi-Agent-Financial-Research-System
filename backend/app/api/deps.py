"""Dependency providers of the HTTP API.

Every component the API needs is built here, from the settings alone.  The
providers are *singletons*: the database engine, the storage backend, the
embedding model and the vector store are expensive, therefore they are
created once and reused.

Caching
-------
The expensive components are cached with :func:`functools.lru_cache`.  The
cache key is the *fingerprint* of the settings (their JSON representation):
a :class:`~app.core.config.Settings` instance is not hashable, and the
fingerprint makes the cache work for **several** configurations at the same
time (the production settings and the settings of a test run live side by
side without ever sharing a component).

:func:`clear_dependency_cache` empties every cache and disposes the engines
that were created; the test suite calls it between two tests so that no
component of a previous test survives.

Wiring
------
The providers are plain functions, therefore they can be used in two ways:

* as a FastAPI dependency (``Depends(get_document_service)``), and
* directly (``get_document_service(settings)``), which the application
  factory uses for the lifespan hooks.

The session factory is the one component that is *not* built from scratch:
it hands out the sessions of :data:`app.db.session.SessionLocal`, bound to
the engine of the effective settings.  The global session factory is reused
when the effective settings are the global ones, so the production process
uses exactly one engine.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.agents.document_agent import DocumentAgent
from app.agents.job_runner import JobRunner, create_job_runner
from app.core.config import Settings, get_settings
from app.core.storage import StorageBackend, create_storage_backend
from app.db.session import SessionLocal, create_engine_from_settings
from app.embeddings.service import EmbeddingService, create_embedding_service
from app.ingestion.chunking import TokenAwareChunker
from app.ingestion.extractors.ocr import OcrExtractor
from app.ingestion.extractors.pdf_tables import PdfPlumberTableExtractor
from app.ingestion.extractors.pdf_text import PyMuPdfTextExtractor
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.validators import FileValidator
from app.repositories.chunk_repository import ChunkRepository
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.services.workspace_service import WorkspaceService
from app.vectorstore.pgvector_store import PgVectorStore

__all__ = [
    "SettingsDep",
    "clear_dependency_cache",
    "get_document_agent",
    "get_document_service",
    "get_embedding_service",
    "get_job_runner",
    "get_search_service",
    "get_session_factory",
    "get_settings_dep",
    "get_storage",
    "get_vector_store",
    "get_workspace_service",
]


# ---------------------------------------------------------------------------
# the settings registry
# ---------------------------------------------------------------------------
#: The settings that are known to the dependency cache, by their fingerprint.
_SETTINGS_BY_KEY: dict[str, Settings] = {}

#: The engines that were created by the dependency cache, by their fingerprint.
_ENGINES_BY_KEY: dict[str, Engine] = {}


def _settings_key(settings: Settings) -> str:
    """Return the cache key of *settings* and remember the instance.

    The key is the JSON representation of the settings: it is stable, it is
    hashable and it changes whenever a setting changes.
    """
    key = settings.model_dump_json()
    _SETTINGS_BY_KEY[key] = settings
    return key


def _settings_of(key: str) -> Settings:
    """Return the settings that belong to *key*."""
    return _SETTINGS_BY_KEY[key]


# ---------------------------------------------------------------------------
# the settings
# ---------------------------------------------------------------------------
def get_settings_dep() -> Settings:
    """Return the effective application settings.

    The provider is the single place the API reads the configuration from,
    therefore a test can replace the whole configuration by overriding this
    dependency.
    """
    return get_settings()


#: The settings of the current request.
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


# ---------------------------------------------------------------------------
# the infrastructure
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def _storage_for(key: str) -> StorageBackend:
    """Return the storage backend of the settings *key*."""
    return create_storage_backend(_settings_of(key))


def get_storage(settings: SettingsDep) -> StorageBackend:
    """Return the storage backend the documents are written to."""
    return _storage_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _session_factory_for(key: str) -> Callable[[], Session]:
    """Return the session factory of the settings *key*.

    The global session factory is reused when the settings are the global
    ones, so that the production process owns exactly one engine.  Every
    other configuration (a test run for example) gets its own engine, bound
    to the database of that configuration.
    """
    settings = _settings_of(key)
    if settings == get_settings():
        return SessionLocal

    engine = create_engine_from_settings(settings)
    _ENGINES_BY_KEY[key] = engine

    def factory() -> Session:
        return SessionLocal(bind=engine)

    return factory


def get_session_factory(settings: SettingsDep) -> Callable[[], Session]:
    """Return the factory that hands out the database sessions."""
    return _session_factory_for(_settings_key(settings))


# ---------------------------------------------------------------------------
# the services
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def _workspace_service_for(key: str) -> WorkspaceService:
    """Return the workspace service of the settings *key*."""
    return WorkspaceService(
        _session_factory_for(key),
        storage=_storage_for(key),
    )


def get_workspace_service(settings: SettingsDep) -> WorkspaceService:
    """Return the workspace service."""
    return _workspace_service_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _embedding_service_for(key: str) -> EmbeddingService:
    """Return the embedding service of the settings *key*."""
    return create_embedding_service(_settings_of(key))


def get_embedding_service(settings: SettingsDep) -> EmbeddingService:
    """Return the embedding service."""
    return _embedding_service_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _vector_store_for(key: str) -> PgVectorStore:
    """Return the vector store of the settings *key*."""
    settings = _settings_of(key)
    return PgVectorStore(
        session_factory=_session_factory_for(key),
        dimension=settings.embedding_dimension,
    )


def get_vector_store(settings: SettingsDep) -> PgVectorStore:
    """Return the vector store."""
    return _vector_store_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _document_service_for(key: str) -> DocumentService:
    """Return the document service of the settings *key*."""
    return DocumentService(
        _session_factory_for(key),
        storage=_storage_for(key),
        validator=FileValidator(_settings_of(key)),
    )


def get_document_service(settings: SettingsDep) -> DocumentService:
    """Return the document service."""
    return _document_service_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _search_service_for(key: str) -> SearchService:
    """Return the search service of the settings *key*."""
    return SearchService(
        vector_store=_vector_store_for(key),
        embedding_service=_embedding_service_for(key),
        settings=_settings_of(key),
    )


def get_search_service(settings: SettingsDep) -> SearchService:
    """Return the search service."""
    return _search_service_for(_settings_key(settings))


# ---------------------------------------------------------------------------
# the agents
# ---------------------------------------------------------------------------
class _ChunkEmbeddingSource:
    """Expose the chunk repository as an embedding source.

    The ingestion pipeline reuses the vectors that were already computed for
    a document.  The chunks live in the database, therefore the source of
    those vectors is the chunk repository - it is asked for the stored
    vectors of a document and it opens a short lived session for it.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Create the source for *session_factory*."""
        self._session_factory = session_factory

    def existing_embeddings(
        self,
        document_id: UUID,
    ) -> dict[str, tuple[str, list[float]]]:
        """Return ``{content_hash: (embedding_config_hash, embedding)}``."""
        with self._session_factory() as session:
            return ChunkRepository(session).existing_embeddings(document_id)


@lru_cache(maxsize=8)
def _document_agent_for(key: str) -> DocumentAgent:
    """Return the document agent of the settings *key*.

    The agent is wired with the **real** components: the real extractors,
    the real chunker (built from the chunk settings), the real embedding
    service, the real vector store and the real document service as the
    status reporter.
    """
    settings = _settings_of(key)
    session_factory = _session_factory_for(key)
    document_service = _document_service_for(key)
    vector_store = _vector_store_for(key)

    chunker = TokenAwareChunker(
        chunk_size_tokens=settings.chunk_size_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
        chunk_min_tokens=settings.chunk_min_tokens,
        chunk_max_tokens=settings.chunk_max_tokens,
    )

    pipeline = IngestionPipeline(
        storage=_storage_for(key),
        text_extractor=PyMuPdfTextExtractor(settings),
        table_extractor=PdfPlumberTableExtractor(settings),
        ocr_extractor=OcrExtractor(settings),
        chunker=chunker,
        embedding_service=_embedding_service_for(key),
        vector_store=vector_store,
        reporter=document_service,
        embedding_source=_ChunkEmbeddingSource(session_factory),
        settings=settings,
    )

    return DocumentAgent(
        pipeline=pipeline,
        document_service=document_service,
        session_factory=session_factory,
    )


def get_document_agent(settings: SettingsDep) -> DocumentAgent:
    """Return the document agent."""
    return _document_agent_for(_settings_key(settings))


@lru_cache(maxsize=8)
def _job_runner_for(key: str) -> JobRunner:
    """Return the job runner of the settings *key*.

    ``settings.processing_inline`` selects the strategy: the inline runner
    processes the document in the calling thread, the background runner
    processes it in a worker thread of the process.
    """
    return create_job_runner(_document_agent_for(key), _settings_of(key))


def get_job_runner(settings: SettingsDep) -> JobRunner:
    """Return the job runner."""
    return _job_runner_for(_settings_key(settings))


# ---------------------------------------------------------------------------
# the cache
# ---------------------------------------------------------------------------
def clear_dependency_cache() -> None:
    """Empty every dependency cache and dispose the created engines.

    The test suite calls the function before and after every test, so that
    no component of a previous test (and no open connection) survives.
    """
    for factory in (
        _storage_for,
        _session_factory_for,
        _workspace_service_for,
        _embedding_service_for,
        _vector_store_for,
        _document_service_for,
        _search_service_for,
        _document_agent_for,
        _job_runner_for,
    ):
        factory.cache_clear()

    for engine in _ENGINES_BY_KEY.values():
        engine.dispose()
    _ENGINES_BY_KEY.clear()
    _SETTINGS_BY_KEY.clear()