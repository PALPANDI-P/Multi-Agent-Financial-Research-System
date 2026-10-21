"""Tests of the document endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import ProcessingStatus
from app.db.models.chunk import DocumentChunk
from app.repositories.document_repository import DocumentRepository

pytestmark = pytest.mark.integration

#: The statuses a document may have.
REAL_STATUSES = {status.value for status in ProcessingStatus}


def _workspace(client: TestClient, name: str = "Documents") -> str:
    """Create a workspace and return its id."""
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client: TestClient, workspace_id: str, content: bytes, filename: str = "acme.pdf"):
    """Upload a document and return the response."""
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, content, "application/pdf")},
    )


def _upload_pdf(client: TestClient, workspace_id: str, pdf_bytes: bytes) -> dict:
    """Upload a valid PDF and return the body of the answer."""
    response = _upload(client, workspace_id, pdf_bytes)
    assert response.status_code == 201, response.text
    return response.json()


def _force_failure(session_factory: sessionmaker[Session], document_id: str) -> None:
    """Move a document into the failed state."""
    with session_factory() as session:
        DocumentRepository(session).set_status(
            document_id,
            ProcessingStatus.FAILED,
            error_code="test_failure",
            error_message="the failure was forced by the test",
        )


def _chunk_count(session_factory: sessionmaker[Session], document_id: str) -> int:
    """Return the number of chunks of a document."""
    with session_factory() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
            ).scalar_one()
        )


def test_a_valid_pdf_is_uploaded_and_processed(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """The upload is registered, processed and reported with its real status."""
    workspace_id = _workspace(client)

    response = _upload(client, workspace_id, pdf_bytes)

    assert response.status_code == 201
    body = response.json()
    document_id = body["document_id"]
    assert UUID(document_id)
    assert body["processing_status"] in REAL_STATUSES
    assert body["processing_status"] == ProcessingStatus.COMPLETED.value
    assert body["processing_stage"]
    assert body["content_hash"]
    assert body["duplicate"] is False


def test_the_uploaded_document_is_retrievable(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """The document carries the page count and the chunk count."""
    workspace_id = _workspace(client)
    uploaded = _upload_pdf(client, workspace_id, pdf_bytes)

    response = client.get(f"/api/v1/documents/{uploaded['document_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == uploaded["document_id"]
    assert body["page_count"] == 2
    assert body["chunk_count"] >= 1
    assert body["processing_status"] == ProcessingStatus.COMPLETED.value
    assert body["workspace_id"] == workspace_id
    assert body["original_filename"] == "acme.pdf"


def test_the_same_document_twice_is_a_duplicate(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """The second upload of the same bytes reports the existing document."""
    workspace_id = _workspace(client)
    first = _upload_pdf(client, workspace_id, pdf_bytes)

    response = _upload(client, workspace_id, pdf_bytes)

    assert response.status_code == 201
    body = response.json()
    assert body["duplicate"] is True
    assert body["document_id"] == first["document_id"]
    assert body["content_hash"] == first["content_hash"]


def test_a_file_that_is_not_a_pdf_is_rejected(client: TestClient) -> None:
    """A file that is not a PDF is rejected with the collected issues."""
    workspace_id = _workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", b"this is not a pdf at all", "text/plain")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_upload"
    issues = body["error"]["details"]["issues"]
    assert "extension_not_allowed" in issues
    assert "not_a_pdf" in issues
    assert "mime_type_not_allowed" in issues


def test_an_empty_file_is_rejected(client: TestClient) -> None:
    """An empty file is rejected."""
    workspace_id = _workspace(client)

    response = _upload(client, workspace_id, b"", filename="empty.pdf")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_upload"
    assert "file_empty" in body["error"]["details"]["issues"]


def test_an_oversized_upload_is_rejected(
    client: TestClient,
    app,
    api_settings,
) -> None:
    """A file that is larger than the limit is rejected with 413."""
    from app.api.deps import get_settings_dep

    small = api_settings.model_copy(update={"max_upload_size_bytes": 1024 * 1024})
    app.dependency_overrides[get_settings_dep] = lambda: small
    workspace_id = _workspace(client)

    response = _upload(client, workspace_id, b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "payload_too_large"


def test_the_documents_of_a_workspace_are_listed(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """The list carries the documents and the total."""
    workspace_id = _workspace(client)
    _upload_pdf(client, workspace_id, pdf_bytes)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/documents")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["workspace_id"] == workspace_id


def test_the_documents_of_an_unknown_workspace_are_not_found(
    client: TestClient,
) -> None:
    """An unknown workspace is answered with 404."""
    response = client.get(f"/api/v1/workspaces/{uuid4()}/documents")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_the_documents_of_another_workspace_are_not_visible(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """A document of another workspace never shows up in the list."""
    first = _workspace(client, "First")
    second = _workspace(client, "Second")
    _upload_pdf(client, second, pdf_bytes)

    response = client.get(f"/api/v1/workspaces/{first}/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_an_unknown_document_is_not_found(client: TestClient) -> None:
    """An unknown document id is answered with 404."""
    response = client.get(f"/api/v1/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_completed_document_can_not_be_retried(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """Only a failed document may be retried."""
    workspace_id = _workspace(client)
    uploaded = _upload_pdf(client, workspace_id, pdf_bytes)

    response = client.post(f"/api/v1/documents/{uploaded['document_id']}/retry")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_failed"


def test_a_failed_document_is_retried(
    client: TestClient,
    pdf_bytes: bytes,
    session_factory: sessionmaker[Session],
) -> None:
    """A failed document is queued again."""
    workspace_id = _workspace(client)
    uploaded = _upload_pdf(client, workspace_id, pdf_bytes)
    _force_failure(session_factory, uploaded["document_id"])

    response = client.post(f"/api/v1/documents/{uploaded['document_id']}/retry")

    assert response.status_code == 202
    body = response.json()
    assert body["document_id"] == uploaded["document_id"]
    assert UUID(body["job_id"])
    assert body["attempt_count"] == 0
    assert body["processing_status"] == ProcessingStatus.QUEUED.value


def test_an_unknown_document_can_not_be_retried(client: TestClient) -> None:
    """Retrying an unknown document is answered with 404."""
    response = client.post(f"/api/v1/documents/{uuid4()}/retry")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_document_is_deleted_with_its_chunks(
    client: TestClient,
    pdf_bytes: bytes,
    session_factory: sessionmaker[Session],
) -> None:
    """The document and its chunks are gone after the deletion."""
    workspace_id = _workspace(client)
    uploaded = _upload_pdf(client, workspace_id, pdf_bytes)
    assert _chunk_count(session_factory, uploaded["document_id"]) >= 1

    response = client.delete(f"/api/v1/documents/{uploaded['document_id']}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/documents/{uploaded['document_id']}").status_code == 404
    assert _chunk_count(session_factory, uploaded["document_id"]) == 0


def test_deleting_an_unknown_document_is_not_found(client: TestClient) -> None:
    """Deleting an unknown document is answered with 404."""
    response = client.delete(f"/api/v1/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"