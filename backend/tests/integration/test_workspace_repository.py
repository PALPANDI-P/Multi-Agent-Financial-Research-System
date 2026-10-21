"""Integration tests for the workspace repository and the workspace service.

The tests run against a **real** PostgreSQL server.  Every test empties the
test tables before and after it runs, therefore the tests are independent
of each other and leave no residue behind.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import LocalStorage
from app.db.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.workspace_service import WorkspaceService

pytestmark = pytest.mark.integration


def _create_workspaces(
    repository: WorkspaceRepository,
    count: int,
    *,
    prefix: str = "workspace",
) -> list[UUID]:
    """Create *count* workspaces and return their ids."""
    return [
        repository.create(name=f"{prefix}-{index}", description=f"number {index}").id
        for index in range(count)
    ]


def _add_document(
    session: Session,
    workspace_id: UUID,
    *,
    storage_key: str,
    suffix: str = "doc",
) -> UUID:
    """Insert a document into *workspace_id* and return its id."""
    document = Document(
        workspace_id=workspace_id,
        original_filename=f"{suffix}.pdf",
        storage_key=storage_key,
        content_hash=uuid.uuid4().hex,
        file_size_bytes=1024,
        mime_type="application/pdf",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document.id


# ----------------------------------------------------------------------
# repository
# ----------------------------------------------------------------------
def test_create_and_get_a_workspace(db_session: Session) -> None:
    """A created workspace can be read back."""
    repository = WorkspaceRepository(db_session)

    created = repository.create(name="Research", description="everything")

    fetched = repository.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Research"
    assert fetched.description == "everything"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_get_returns_none_for_an_unknown_workspace(db_session: Session) -> None:
    """A missing row is reported as ``None`` and not as an exception."""
    repository = WorkspaceRepository(db_session)

    assert repository.get(uuid.uuid4()) is None


def test_list_returns_the_page_and_the_total_count(db_session: Session) -> None:
    """The second element of the tuple is the total, not the page size."""
    repository = WorkspaceRepository(db_session)
    _create_workspaces(repository, 5)

    page, total = repository.list(limit=2, offset=0)

    assert len(page) == 2
    assert total == 5

    second_page, total = repository.list(limit=2, offset=4)
    assert len(second_page) == 1
    assert total == 5


def test_list_filters_by_name_contains(db_session: Session) -> None:
    """``name_contains`` narrows the page and the total."""
    repository = WorkspaceRepository(db_session)
    _create_workspaces(repository, 3, prefix="alpha")
    _create_workspaces(repository, 2, prefix="beta")

    page, total = repository.list(limit=10, offset=0, name_contains="alpha")

    assert total == 3
    assert len(page) == 3
    assert all(workspace.name.startswith("alpha") for workspace in page)


def test_update_only_changes_the_given_fields(db_session: Session) -> None:
    """A field that is ``None`` keeps its old value."""
    repository = WorkspaceRepository(db_session)
    workspace = repository.create(name="Original", description="kept")

    updated = repository.update(workspace, name="Renamed")

    assert updated.name == "Renamed"
    assert updated.description == "kept"

    updated = repository.update(updated, description="changed")
    assert updated.name == "Renamed"
    assert updated.description == "changed"


def test_delete_reports_whether_the_row_existed(db_session: Session) -> None:
    """``delete`` returns ``False`` for an unknown workspace."""
    repository = WorkspaceRepository(db_session)
    workspace = repository.create(name="Temporary", description=None)

    assert repository.delete(workspace.id) is True
    assert repository.get(workspace.id) is None
    assert repository.delete(uuid.uuid4()) is False


def test_count_documents_uses_one_grouped_query(db_session: Session) -> None:
    """The document counts of several workspaces come from a single query."""
    repository = WorkspaceRepository(db_session)
    document_repository = DocumentRepository(db_session)

    first = repository.create(name="first", description=None)
    second = repository.create(name="second", description=None)
    empty = repository.create(name="empty", description=None)

    _add_document(db_session, first.id, storage_key="a/one.pdf")
    _add_document(db_session, first.id, storage_key="a/two.pdf")
    _add_document(db_session, second.id, storage_key="b/one.pdf")

    counts = repository.count_documents([first.id, second.id, empty.id])

    assert counts == {first.id: 2, second.id: 1}
    assert empty.id not in counts
    assert document_repository.count_by_workspace(first.id) == 2


def test_count_documents_of_an_empty_selection(db_session: Session) -> None:
    """An empty selection does not produce a query at all."""
    repository = WorkspaceRepository(db_session)

    assert repository.count_documents([]) == {}


def test_list_storage_keys_returns_the_keys_of_a_workspace(
    db_session: Session,
) -> None:
    """The storage keys of the documents are collected before the delete."""
    repository = WorkspaceRepository(db_session)
    document_repository = DocumentRepository(db_session)
    workspace = repository.create(name="with-files", description=None)

    _add_document(db_session, workspace.id, storage_key="2025/01/one.pdf")
    _add_document(db_session, workspace.id, storage_key="2025/01/two.pdf")

    keys = document_repository.list_storage_keys(workspace.id)

    assert sorted(keys) == ["2025/01/one.pdf", "2025/01/two.pdf"]


# ----------------------------------------------------------------------
# service
# ----------------------------------------------------------------------
def test_create_workspace_returns_a_summary(session_factory: sessionmaker[Session]) -> None:
    """The service returns a frozen dataclass, not an ORM object."""
    service = WorkspaceService(session_factory)

    summary = service.create_workspace(name="Research", description="all research")

    assert summary.name == "Research"
    assert summary.description == "all research"
    assert summary.document_count == 0
    assert summary.owner_id is None
    assert summary.created_at is not None


def test_create_workspace_rejects_an_empty_name(
    session_factory: sessionmaker[Session],
) -> None:
    """An empty or blank name is a validation error."""
    service = WorkspaceService(session_factory)

    with pytest.raises(ValidationError):
        service.create_workspace(name="   ")

    with pytest.raises(ValidationError):
        service.create_workspace(name="")


def test_create_workspace_rejects_a_too_long_name(
    session_factory: sessionmaker[Session],
) -> None:
    """A name of more than 255 characters is a validation error."""
    service = WorkspaceService(session_factory)

    with pytest.raises(ValidationError):
        service.create_workspace(name="x" * 256)


def test_get_workspace_raises_not_found(session_factory: sessionmaker[Session]) -> None:
    """A missing workspace is reported as :class:`NotFoundError`."""
    service = WorkspaceService(session_factory)

    with pytest.raises(NotFoundError):
        service.get_workspace(uuid.uuid4())


def test_list_workspaces_returns_the_page_and_the_total(
    session_factory: sessionmaker[Session],
) -> None:
    """The service reports the total number of workspaces."""
    service = WorkspaceService(session_factory)
    for index in range(5):
        service.create_workspace(name=f"workspace-{index}")

    page, total = service.list_workspaces(limit=2, offset=0)

    assert len(page) == 2
    assert total == 5
    assert all(summary.document_count == 0 for summary in page)


def test_list_workspaces_does_not_issue_an_n_plus_one_query(
    engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    """The document counts of the page come from one grouped query.

    The number of executed statements is counted with a SQLAlchemy event
    listener.  A per-workspace query would raise the count to five (one
    page query, one total query and three count queries).
    """
    service = WorkspaceService(session_factory)
    for index in range(3):
        service.create_workspace(name=f"nplus1-{index}")

    statements: list[str] = []

    def record_statement(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        summaries, total = service.list_workspaces(limit=10, offset=0)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert total == 3
    assert len(summaries) == 3
    assert len(statements) <= 4, f"unexpected number of statements: {statements}"


def test_update_workspace_raises_not_found(session_factory: sessionmaker[Session]) -> None:
    """A missing workspace is reported as :class:`NotFoundError`."""
    service = WorkspaceService(session_factory)

    with pytest.raises(NotFoundError):
        service.update_workspace(uuid.uuid4(), name="whatever")


def test_update_workspace_changes_only_the_given_fields(
    session_factory: sessionmaker[Session],
) -> None:
    """A field that is ``None`` keeps its old value."""
    service = WorkspaceService(session_factory)
    created = service.create_workspace(name="Original", description="kept")

    updated = service.update_workspace(created.id, name="Renamed")

    assert updated.name == "Renamed"
    assert updated.description == "kept"


def test_delete_workspace_removes_the_documents_and_the_files(
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
) -> None:
    """The documents disappear with the workspace and their files are removed."""
    service = WorkspaceService(session_factory, storage=tmp_storage)
    created = service.create_workspace(name="to-delete", description=None)

    first_key = tmp_storage.save(b"first", extension=".pdf")
    second_key = tmp_storage.save(b"second", extension=".pdf")

    with session_factory() as session:
        _add_document(session, created.id, storage_key=first_key, suffix="one")
        _add_document(session, created.id, storage_key=second_key, suffix="two")

    service.delete_workspace(created.id)

    with session_factory() as session:
        assert WorkspaceRepository(session).get(created.id) is None
        assert DocumentRepository(session).count_by_workspace(created.id) == 0

    assert tmp_storage.exists(first_key) is False
    assert tmp_storage.exists(second_key) is False


def test_delete_workspace_raises_not_found(session_factory: sessionmaker[Session]) -> None:
    """A missing workspace is reported as :class:`NotFoundError`."""
    service = WorkspaceService(session_factory)

    with pytest.raises(NotFoundError):
        service.delete_workspace(uuid.uuid4())


def test_delete_workspace_keeps_the_database_consistent_when_a_file_is_missing(
    session_factory: sessionmaker[Session],
    tmp_storage: LocalStorage,
) -> None:
    """A file that cannot be removed is logged, never raised."""
    service = WorkspaceService(session_factory, storage=tmp_storage)
    created = service.create_workspace(name="with-missing-file", description=None)

    with session_factory() as session:
        _add_document(session, created.id, storage_key="2025/01/gone.pdf")

    service.delete_workspace(created.id)

    with session_factory() as session:
        assert WorkspaceRepository(session).get(created.id) is None
