"""Persistence operations for the ``documents`` table."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import ProcessingStatus
from app.db.base import utcnow
from app.db.models.document import Document
from app.db.models.workspace import Workspace, WorkspaceMember

__all__ = ["DocumentRepository"]


def _status_value(status: ProcessingStatus | str) -> str:
    """Return the persisted value of *status*."""
    return ProcessingStatus(status).value


def _accessible_workspace_ids(owner_id: UUID):
    """Return the query of the workspaces *owner_id* may reach.

    A workspace is reachable when the user owns it or when it is a member
    of it.  The condition is a single expression with a subquery, therefore
    the filter never costs an extra round trip.
    """
    return select(Workspace.id).where(
        or_(
            Workspace.owner_id == owner_id,
            Workspace.id.in_(
                select(WorkspaceMember.workspace_id).where(
                    WorkspaceMember.user_id == owner_id
                )
            ),
        )
    )


class DocumentRepository:
    """CRUD operations for :class:`~app.db.models.document.Document`.

    Every mutating method commits the session it was given.  The methods
    that the service layer has to compose into a single transaction accept a
    ``commit=False`` flag; in that case the change is only flushed and the
    caller decides when the transaction ends.
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to *session*."""
        self._session = session

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def create(
        self,
        *,
        workspace_id: UUID,
        original_filename: str,
        storage_key: str,
        content_hash: str,
        file_size_bytes: int,
        mime_type: str,
        company_name: str | None = None,
        document_title: str | None = None,
        document_type: str | None = None,
        fiscal_period: str | None = None,
        source_url: str | None = None,
        processing_status: ProcessingStatus | str = ProcessingStatus.QUEUED,
        commit: bool = True,
    ) -> Document:
        """Insert a document and return it."""
        document = Document(
            workspace_id=workspace_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_hash=content_hash,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            company_name=company_name,
            document_title=document_title,
            document_type=document_type,
            fiscal_period=fiscal_period,
            source_url=source_url,
            processing_status=_status_value(processing_status),
        )
        self._session.add(document)
        if commit:
            self._session.commit()
            self._session.refresh(document)
        else:
            self._session.flush()
        return document

    def update(self, document: Document, **fields: object) -> Document:
        """Update *document* with *fields* and return it.

        Only known columns are accepted; an unknown field name is rejected
        with a :class:`ValueError` instead of silently creating an
        attribute on the ORM object.
        """
        for name, value in fields.items():
            if name not in _UPDATABLE_COLUMNS:
                raise ValueError(f"unknown document column {name!r}")
            setattr(document, name, value)
        self._session.commit()
        self._session.refresh(document)
        return document

    def set_status(
        self,
        document_id: UUID,
        status: ProcessingStatus | str,
        *,
        stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        processed_at: datetime | None = None,
        commit: bool = True,
    ) -> Document | None:
        """Move the document *document_id* into *status* and return it.

        The status **and** the supplementary ``processing_stage`` are
        written.  The error fields are cleared whenever the new status is
        not ``FAILED`` and ``processed_at`` is stamped when the document
        reaches ``COMPLETED``.  ``None`` is returned when the document does
        not exist.
        """
        document = self.get(document_id)
        if document is None:
            return None

        new_status = ProcessingStatus(status)
        document.processing_status = new_status.value
        document.processing_stage = stage
        if new_status == ProcessingStatus.FAILED:
            document.error_code = error_code
            document.error_message = error_message
        else:
            document.error_code = None
            document.error_message = None
        if new_status == ProcessingStatus.COMPLETED:
            document.processed_at = processed_at or utcnow()

        if commit:
            self._session.commit()
            self._session.refresh(document)
        else:
            self._session.flush()
        return document

    def set_metadata(
        self,
        document_id: UUID,
        *,
        company_name: str | None = None,
        document_title: str | None = None,
        document_type: str | None = None,
        fiscal_period: str | None = None,
        page_count: int | None = None,
        commit: bool = True,
    ) -> Document | None:
        """Write the metadata of a document and return it.

        Only the values that are **not** ``None`` are assigned, therefore a
        partial update never wipes an existing value.  ``None`` is returned
        when the document does not exist.
        """
        document = self.get(document_id)
        if document is None:
            return None

        if company_name is not None:
            document.company_name = company_name
        if document_title is not None:
            document.document_title = document_title
        if document_type is not None:
            document.document_type = document_type
        if fiscal_period is not None:
            document.fiscal_period = fiscal_period
        if page_count is not None:
            document.page_count = page_count

        if commit:
            self._session.commit()
            self._session.refresh(document)
        else:
            self._session.flush()
        return document

    def delete(self, document_id: UUID) -> bool:
        """Delete the document *document_id*; return whether it existed.

        The chunks and the jobs of the document are removed by the foreign
        key cascade of the schema.
        """
        document = self.get(document_id)
        if document is None:
            return False
        self._session.delete(document)
        self._session.commit()
        return True

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get(self, document_id: UUID, *, owner_id: UUID | None = None) -> Document | None:
        """Return the document *document_id* or ``None``.

        ``owner_id`` restricts the lookup to the documents of the
        workspaces the user may reach.  ``None`` means *no filtering*.
        """
        if owner_id is None:
            return self._session.get(Document, document_id)
        statement = select(Document).where(
            Document.id == document_id,
            Document.workspace_id.in_(_accessible_workspace_ids(owner_id)),
        )
        return self._session.execute(statement).scalars().first()

    def get_by_content_hash(self, workspace_id: UUID, content_hash: str) -> Document | None:
        """Return the document with *content_hash* of *workspace_id*."""
        statement = (
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.content_hash == content_hash,
            )
            .limit(1)
        )
        return self._session.execute(statement).scalars().first()

    def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        limit: int,
        offset: int,
        status: ProcessingStatus | str | None = None,
        document_type: str | None = None,
        company_name: str | None = None,
        owner_id: UUID | None = None,
    ) -> tuple[list[Document], int]:
        """Return a page of documents of a workspace and the **total** count.

        The second element of the tuple is the number of documents that
        match the filters - not the size of the returned page.

        ``owner_id`` restricts the page to the documents of the workspaces
        the user may reach.  ``None`` means *no filtering*.
        """
        filters = [Document.workspace_id == workspace_id]
        if owner_id is not None:
            filters.append(
                Document.workspace_id.in_(_accessible_workspace_ids(owner_id))
            )
        if status is not None:
            filters.append(Document.processing_status == _status_value(status))
        if document_type is not None:
            filters.append(Document.document_type == document_type)
        if company_name is not None:
            filters.append(Document.company_name == company_name)

        count_statement = select(func.count()).select_from(Document).where(*filters)
        page_statement = select(Document).where(*filters)

        total = int(self._session.execute(count_statement).scalar_one())
        page = list(
            self._session.execute(
                page_statement.order_by(Document.created_at.asc(), Document.id.asc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return page, total

    def list_by_ids(self, document_ids: Sequence[UUID]) -> list[Document]:
        """Return the documents of *document_ids* (an empty list when empty)."""
        identifiers = list(document_ids)
        if not identifiers:
            return []
        statement = select(Document).where(Document.id.in_(identifiers))
        return list(self._session.execute(statement).scalars().all())

    def count_by_workspace(self, workspace_id: UUID) -> int:
        """Return the number of documents of *workspace_id*."""
        statement = (
            select(func.count())
            .select_from(Document)
            .where(Document.workspace_id == workspace_id)
        )
        return int(self._session.execute(statement).scalar_one())

    def list_storage_keys(self, workspace_id: UUID) -> list[str]:
        """Return the storage keys of every document of *workspace_id*.

        The keys are collected *before* the workspace is deleted, because
        the deletion removes the documents and with them the keys.
        """
        statement = select(Document.storage_key).where(Document.workspace_id == workspace_id)
        return [str(row[0]) for row in self._session.execute(statement).all()]


#: Columns that :meth:`DocumentRepository.update` accepts.
_UPDATABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "original_filename",
        "storage_key",
        "content_hash",
        "file_size_bytes",
        "mime_type",
        "company_name",
        "document_title",
        "document_type",
        "fiscal_period",
        "source_url",
        "page_count",
        "processing_status",
        "processing_stage",
        "error_code",
        "error_message",
        "processed_at",
    }
)