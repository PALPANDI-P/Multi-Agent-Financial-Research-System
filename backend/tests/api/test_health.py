"""Tests of the health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_settings_dep
from app.main import create_app

pytestmark = pytest.mark.integration


def test_the_health_endpoint_reports_the_state_of_the_service(
    client: TestClient,
) -> None:
    """The endpoint answers with the state of the service and its checks."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "status",
        "app",
        "version",
        "environment",
        "timestamp",
        "checks",
    }
    assert body["status"] in {"ok", "degraded"}
    assert body["app"]
    assert body["version"]
    assert body["environment"] == "test"
    assert body["timestamp"]
    assert body["checks"]["database"].startswith("ok")


def test_the_health_endpoint_checks_every_dependency(client: TestClient) -> None:
    """Every dependency of the service is part of the checks."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    checks = response.json()["checks"]
    assert set(checks) == {"database", "pgvector", "embeddings", "storage"}
    assert all(isinstance(value, str) and value for value in checks.values())


def test_the_health_endpoint_never_leaks_a_credential(
    client: TestClient,
) -> None:
    """The response carries neither the password nor the connection string."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    text = response.text
    assert "frs_dev_password" not in text
    assert "postgresql+psycopg" not in text
    assert "financial_research_test" not in text
    assert "://" not in text


def test_the_index_of_the_api_is_served(client: TestClient) -> None:
    """The root of the API is a tiny index, not a landing page."""
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["app"]
    assert body["version"]
    assert body["docs"] == "/docs"
    assert body["api"] == "/api/v1"


def test_the_request_id_is_returned_in_the_header(client: TestClient) -> None:
    """Every response carries the id of the request."""
    response = client.get("/api/v1/health")
    assert response.headers["X-Request-ID"]

    response = client.get("/api/v1/health", headers={"X-Request-ID": "client-supplied-id"})
    assert response.headers["X-Request-ID"] == "client-supplied-id"


def test_an_unexpected_error_is_reported_generically(api_settings) -> None:
    """An unexpected error never reaches the client in detail."""
    application = create_app(api_settings)
    application.dependency_overrides[get_settings_dep] = lambda: api_settings

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("the secret of the internal path C:\\secret\\file")

    with TestClient(application, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "An unexpected error occurred."
    assert body["error"]["details"] == {}
    assert body["error"]["request_id"]
    assert "secret" not in response.text
    assert "Traceback" not in response.text
