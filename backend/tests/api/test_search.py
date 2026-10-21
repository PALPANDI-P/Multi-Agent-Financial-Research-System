"""Tests of the search endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _workspace(client: TestClient, name: str = "Search") -> str:
    """Create a workspace and return its id."""
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client: TestClient, workspace_id: str, pdf_bytes: bytes) -> str:
    """Upload a document and return its id."""
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("acme.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _search(client: TestClient, workspace_id: str, **payload) -> dict:
    """Run a search and return the body of the answer."""
    response = client.post(f"/api/v1/workspaces/{workspace_id}/search", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_search_without_documents_returns_no_hit(client: TestClient) -> None:
    """A workspace without documents is not an error, it is an empty result."""
    workspace_id = _workspace(client)

    body = _search(client, workspace_id, query="revenue")

    assert body["results"] == []
    assert body["total"] == 0
    assert body["workspace_id"] == workspace_id
    assert body["query"] == "revenue"


def test_a_search_finds_the_uploaded_document(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """The indexed chunks of the document are found."""
    workspace_id = _workspace(client)
    document_id = _upload(client, workspace_id, pdf_bytes)

    body = _search(client, workspace_id, query="how much did the revenue grow")

    assert body["total"] >= 1
    assert body["results"]
    hit = body["results"][0]
    assert hit["document_id"] == document_id
    assert hit["page_start"] is not None
    assert hit["score"] is not None
    assert hit["content"]


def test_the_limit_of_a_search_is_clamped(client: TestClient) -> None:
    """A limit above the maximum is clamped instead of rejected."""
    workspace_id = _workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        json={"query": "revenue", "limit": 999},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_a_blank_query_is_rejected(client: TestClient) -> None:
    """An empty query is rejected."""
    workspace_id = _workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        json={"query": ""},
    )

    assert response.status_code == 422


def test_a_too_long_query_is_rejected(client: TestClient) -> None:
    """A query of more than 1000 characters is rejected."""
    workspace_id = _workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        json={"query": "a" * 1001},
    )

    assert response.status_code == 422


def test_a_limit_below_one_is_rejected(client: TestClient) -> None:
    """A limit of zero is rejected."""
    workspace_id = _workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        json={"query": "revenue", "limit": 0},
    )

    assert response.status_code == 422


def test_a_document_of_another_workspace_is_never_returned(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """A document id of another workspace is dropped, not an error."""
    first = _workspace(client, "First")
    second = _workspace(client, "Second")
    foreign_id = _upload(client, second, pdf_bytes)

    body = _search(client, first, query="revenue", document_ids=[foreign_id])

    assert body["results"] == []
    assert body["total"] == 0


def test_a_document_of_the_workspace_is_returned(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    """A document id of the workspace narrows the search down."""
    workspace_id = _workspace(client)
    document_id = _upload(client, workspace_id, pdf_bytes)

    body = _search(client, workspace_id, query="revenue", document_ids=[document_id])

    assert body["total"] >= 1
    assert body["results"]
    assert {hit["document_id"] for hit in body["results"]} == {document_id}


def test_searching_an_unknown_workspace_is_not_found(client: TestClient) -> None:
    """An unknown workspace is answered with 404."""
    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/search",
        json={"query": "revenue"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"