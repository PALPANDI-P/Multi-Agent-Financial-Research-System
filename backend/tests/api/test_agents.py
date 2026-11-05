"""Tests of the agent HTTP endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _workspace(client: TestClient, name: str = "Agents") -> str:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client: TestClient, workspace_id: str, pdf_bytes: bytes) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("acme.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text


def test_red_flag_analysis_empty_workspace(client: TestClient) -> None:
    workspace_id = _workspace(client)
    response = client.post(f"/api/v1/workspaces/{workspace_id}/red-flag-analysis")
    assert response.status_code == 200, response.text
    body = response.json()
    findings = body.get("findings", body.get("red_flags", []))
    assert isinstance(findings, list)


def test_red_flag_analysis_after_upload(client: TestClient, pdf_bytes: bytes) -> None:
    workspace_id = _workspace(client)
    _upload(client, workspace_id, pdf_bytes)
    response = client.post(f"/api/v1/workspaces/{workspace_id}/red-flag-analysis")
    assert response.status_code == 200, response.text


def test_research_revenue_question(client: TestClient, pdf_bytes: bytes) -> None:
    workspace_id = _workspace(client)
    _upload(client, workspace_id, pdf_bytes)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/research",
        json={"question": "What was total revenue?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    text = str(body).lower()
    assert "1.2" in text or "revenue" in text


def test_research_empty_question(client: TestClient) -> None:
    workspace_id = _workspace(client)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/research",
        json={"question": ""},
    )
    assert response.status_code in (200, 422), response.text


def test_comparison_endpoint(client: TestClient, pdf_bytes: bytes) -> None:
    workspace_id = _workspace(client)
    _upload(client, workspace_id, pdf_bytes)
    response = client.post(f"/api/v1/workspaces/{workspace_id}/compare", json={})
    assert response.status_code == 200, response.text


def test_report_generation(client: TestClient, pdf_bytes: bytes) -> None:
    workspace_id = _workspace(client)
    _upload(client, workspace_id, pdf_bytes)
    response = client.post(f"/api/v1/workspaces/{workspace_id}/reports", json={})
    assert response.status_code == 201, response.text


def test_red_flag_invalid_workspace(client: TestClient) -> None:
    response = client.post(f"/api/v1/workspaces/{uuid4()}/red-flag-analysis")
    assert response.status_code == 404


def test_research_invalid_workspace(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/research",
        json={"question": "What was total revenue?"},
    )
    assert response.status_code == 404
