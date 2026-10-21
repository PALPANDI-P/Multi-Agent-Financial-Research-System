"""Tests of the workspace endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create(client: TestClient, name: str = "Research", description: str | None = None):
    """Create a workspace and return the response."""
    return client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": description},
    )


def test_a_workspace_is_created(client: TestClient) -> None:
    """A created workspace is returned with its fields."""
    response = _create(client, "Acme Research", "the workspace of the acme project")

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["name"] == "Acme Research"
    assert body["description"] == "the workspace of the acme project"
    assert body["document_count"] == 0
    assert body["created_at"]
    assert body["updated_at"]


def test_the_workspaces_are_listed(client: TestClient) -> None:
    """The list carries the items, the total and the pagination."""
    for index in range(3):
        _create(client, f"Workspace {index}")

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 3


def test_the_workspaces_are_paginated(client: TestClient) -> None:
    """The limit and the offset select the page."""
    for index in range(5):
        _create(client, f"Workspace {index}")

    first = client.get("/api/v1/workspaces", params={"limit": 2, "offset": 0})
    second = client.get("/api/v1/workspaces", params={"limit": 2, "offset": 2})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["total"] == 5
    assert second.json()["total"] == 5
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 2
    assert first.json()["limit"] == 2
    assert first.json()["offset"] == 0
    assert second.json()["offset"] == 2
    first_ids = {item["id"] for item in first.json()["items"]}
    second_ids = {item["id"] for item in second.json()["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_the_workspaces_can_be_filtered_by_name(client: TestClient) -> None:
    """The name filter only returns the matching workspaces."""
    _create(client, "Alpha Research")
    _create(client, "Beta Research")

    response = client.get("/api/v1/workspaces", params={"name": "Alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Alpha Research"


def test_a_single_workspace_is_returned(client: TestClient) -> None:
    """A workspace is returned by its id."""
    created = _create(client, "Acme Research").json()

    response = client.get(f"/api/v1/workspaces/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["name"] == "Acme Research"


def test_an_unknown_workspace_is_not_found(client: TestClient) -> None:
    """An unknown id is answered with 404."""
    response = client.get(f"/api/v1/workspaces/{uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]


def test_a_workspace_is_renamed(client: TestClient) -> None:
    """A patch changes the name of a workspace."""
    created = _create(client, "Old Name", "the description").json()

    response = client.patch(
        f"/api/v1/workspaces/{created['id']}",
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["description"] == "the description"


def test_a_patch_leaves_an_omitted_field_untouched(client: TestClient) -> None:
    """A field that the client did not send keeps its value."""
    created = _create(client, "Old Name", "the description").json()

    response = client.patch(
        f"/api/v1/workspaces/{created['id']}",
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "the description"


def test_a_patch_clears_the_description(client: TestClient) -> None:
    """An explicit null clears the description."""
    created = _create(client, "Old Name", "the description").json()

    response = client.patch(
        f"/api/v1/workspaces/{created['id']}",
        json={"description": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] is None
    assert body["name"] == "Old Name"


def test_a_workspace_is_deleted(client: TestClient) -> None:
    """A deleted workspace is gone."""
    created = _create(client, "Acme Research").json()

    response = client.delete(f"/api/v1/workspaces/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/v1/workspaces/{created['id']}").status_code == 404


def test_deleting_an_unknown_workspace_is_not_found(client: TestClient) -> None:
    """Deleting an unknown id is answered with 404."""
    response = client.delete(f"/api/v1/workspaces/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_workspace_without_a_name_is_rejected(client: TestClient) -> None:
    """An empty name is rejected by the schema."""
    response = client.post("/api/v1/workspaces", json={"name": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["error"]["details"]["errors"]