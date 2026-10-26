"""Tests of the authentication endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.services.auth_service import AuthService
from app.services.workspace_service import WorkspaceService

pytestmark = pytest.mark.integration

#: The e-mail address of the account of the API tests.
TEST_USER_EMAIL = "api-test@frs.local"

#: The password of the account of the API tests.
TEST_USER_PASSWORD = "ApiTestPassword123!"


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------
def test_an_account_is_created(anonymous_client: TestClient) -> None:
    """A registration is answered with the new user."""
    response = anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newcomer@frs.local",
            "full_name": "New Comer",
            "password": "AnotherPassword123!",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["email"] == "newcomer@frs.local"
    assert body["full_name"] == "New Comer"
    assert body["role"] == "analyst"
    assert body["scenario_key"] is None
    assert body["created_at"]


def test_a_duplicate_address_is_a_conflict(anonymous_client: TestClient) -> None:
    """The same address cannot be registered twice."""
    payload = {
        "email": "twice@frs.local",
        "full_name": "Twice",
        "password": "AnotherPassword123!",
    }
    assert anonymous_client.post("/api/v1/auth/register", json=payload).status_code == 201

    response = anonymous_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "email_already_registered"
    assert body["error"]["request_id"]


def test_an_invalid_registration_is_rejected(anonymous_client: TestClient) -> None:
    """A payload that does not satisfy the rules is answered with 422."""
    response = anonymous_client.post(
        "/api/v1/auth/register",
        json={"email": "broken@frs.local", "full_name": "Broken"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["error"]["details"]["errors"]


def test_a_malformed_address_is_rejected(anonymous_client: TestClient) -> None:
    """An address that is not an address is answered with 422."""
    response = anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "full_name": "Broken",
            "password": "AnotherPassword123!",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_email"


# ----------------------------------------------------------------------
# login and logout
# ----------------------------------------------------------------------
def test_a_correct_credential_opens_a_session(client: TestClient) -> None:
    """The login answers with the user and sets the session cookie."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == TEST_USER_EMAIL
    assert body["user"]["full_name"]
    assert body["user"]["role"] == "analyst"
    assert body["user"]["scenario_key"] is None
    assert body["expires_at"]

    cookie = response.headers["set-cookie"]
    assert "frs_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.replace("SameSite=Lax", "SameSite=lax")
    assert "Path=/" in cookie


def test_a_wrong_password_is_a_generic_401(anonymous_client: TestClient) -> None:
    """A wrong password never reveals which field was wrong."""
    anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": "known@frs.local",
            "full_name": "Known User",
            "password": "AnotherPassword123!",
        },
    )

    wrong_password = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": "known@frs.local", "password": "WrongPassword123!"},
    )
    unknown_email = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@frs.local", "password": "AnotherPassword123!"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    wrong_body = wrong_password.json()
    unknown_body = unknown_email.json()
    # The two answers differ in nothing but the id of the request.
    assert wrong_body["error"]["code"] == unknown_body["error"]["code"]
    assert wrong_body["error"]["message"] == unknown_body["error"]["message"]
    assert wrong_body["error"]["details"] == unknown_body["error"]["details"]
    assert wrong_body["error"]["code"] == "invalid_credentials"
    # The message points at neither of the two fields.
    message = wrong_body["error"]["message"].lower()
    assert message == "invalid email or password."
    assert "not found" not in message
    assert "does not exist" not in message
    assert "unknown" not in message
    assert "wrong" not in message
    assert "known@frs.local" not in wrong_password.text
    assert "unknown@frs.local" not in unknown_email.text


def test_the_session_is_answered_by_me(client: TestClient) -> None:
    """The current user is answered with the session cookie."""
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_USER_EMAIL
    assert body["full_name"]
    assert body["role"] == "analyst"
    assert body["scenario_key"] is None
    assert body["created_at"]
    assert body["last_login_at"]


def test_without_a_session_there_is_no_current_user(
    anonymous_client: TestClient,
) -> None:
    """A request without a session is answered with 401."""
    response = anonymous_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_credentials"
    assert body["error"]["request_id"]


def test_the_logout_ends_the_session(client: TestClient) -> None:
    """The logout revokes the session and clears the cookie."""
    assert client.get("/api/v1/auth/me").status_code == 200

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert response.content == b""
    assert client.cookies.get("frs_session") is None
    assert client.get("/api/v1/auth/me").status_code == 401


# ----------------------------------------------------------------------
# the protected routes
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/workspaces"),
        ("get", "/api/v1/workspaces/{workspace_id}/documents"),
        ("get", "/api/v1/documents/{document_id}"),
        ("post", "/api/v1/workspaces/{workspace_id}/search"),
    ],
)
def test_the_protected_routes_need_a_session(
    anonymous_client: TestClient,
    method: str,
    path: str,
) -> None:
    """Every protected route answers a session-less request with 401."""
    target = path.format(
        workspace_id=uuid4(),
        document_id=uuid4(),
    )
    payload = {"query": "revenue"} if method == "post" else None

    response = anonymous_client.request(method, target, json=payload)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_the_health_endpoint_stays_reachable(anonymous_client: TestClient) -> None:
    """The health check needs no session."""
    response = anonymous_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_the_scenarios_are_public(anonymous_client: TestClient) -> None:
    """The scenarios are reachable before anybody signed in."""
    response = anonymous_client.get("/api/v1/auth/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert len(body["scenarios"]) == 3
    keys = [scenario["key"] for scenario in body["scenarios"]]
    assert keys == ["equity-analyst", "credit-analyst", "corporate-development"]
    for scenario in body["scenarios"]:
        assert scenario["title"]
        assert scenario["tagline"]
        assert scenario["description"]
        assert scenario["focus_areas"]
        assert scenario["suggested_queries"]
        assert scenario["demo_email"]
        assert scenario["demo_password"]


# ----------------------------------------------------------------------
# the ownership
# ----------------------------------------------------------------------
def test_a_user_sees_only_its_own_workspaces(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    api_settings: Settings,
) -> None:
    """The list carries the workspaces of the signed-in user only."""
    created = client.post(
        "/api/v1/workspaces",
        json={"name": "My workspace"},
    )
    assert created.status_code == 201

    service = AuthService(api_session_factory, settings=api_settings)
    stranger = service.register(
        email="stranger@frs.local",
        full_name="Stranger",
        password="AnotherPassword123!",
    )
    foreign = WorkspaceService(api_session_factory).create_workspace(
        name="Foreign workspace",
        owner_id=stranger.id,
    )

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [created.json()["id"]]

    # The workspace of somebody else is not disclosed.
    foreign_response = client.get(f"/api/v1/workspaces/{foreign.id}")
    assert foreign_response.status_code == 404
    assert foreign_response.json()["error"]["code"] == "not_found"