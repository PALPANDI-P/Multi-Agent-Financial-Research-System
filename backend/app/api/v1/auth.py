"""The authentication endpoints of the API.

Endpoints
---------
``POST /api/v1/auth/register``
    Create an account.  Answered with ``201`` and the new user, with
    ``403`` when the registration is switched off and with ``409`` when the
    address is already registered.
``POST /api/v1/auth/login``
    Verify a credential and open a session.  Answered with ``200``, the
    user and the moment the session expires.  The session token is written
    into an **httpOnly** cookie (``SameSite=Lax``); the request may
    alternatively carry the token in the ``Authorization: Bearer <token>``
    header.
``POST /api/v1/auth/logout``
    Revoke the session and clear the cookie.  Answered with ``204``.
``GET /api/v1/auth/me``
    Return the user of the current session.  Answered with ``401`` when
    there is no valid session.
``GET /api/v1/auth/scenarios``
    Return the demo scenarios.  The endpoint is **public**: it is the
    landing page of the frontend that needs it before anybody signed in.

Security notes
--------------
* The login answers with the **same** message for an unknown address, an
  inactive account and a wrong password: the endpoint does not allow the
  enumeration of the accounts.
* The password is never logged and never returned; only its Argon2id hash
  is stored.
* The raw session token is delivered **once** - in the cookie of the login
  answer.  The database only ever sees its SHA-256 hash.

Known limitations
-----------------
* There is **no rate limit** on the login endpoint.  A brute force against
  the passwords of a known address is therefore possible; the protection
  has to be added in front of the service (a reverse proxy) before the
  system is exposed to the internet.
* The login accepts a **JSON body only**; a form encoded body is not
  supported.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    AuthServiceDep,
    CurrentUserDep,
    SettingsDep,
    extract_session_token,
)
from app.api.errors import error_response
from app.core.exceptions import AppError, AuthenticationError
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LoginUserRead,
    RegisterRequest,
    ScenarioListResponse,
    ScenarioRead,
    UserRead,
)

__all__ = ["authentication_error_handler", "router"]

router = APIRouter(prefix="/auth", tags=["auth"])

#: The challenge the answer of a ``401`` carries.
WWW_AUTHENTICATE_CHALLENGE = 'Bearer realm="frs", error="invalid_token"'


async def authentication_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Translate an authentication error into the error envelope.

    The answer carries the standard envelope of the API and a
    ``WWW-Authenticate`` header, therefore a client that speaks HTTP knows
    that it has to authenticate itself.
    """
    assert isinstance(exc, AuthenticationError)
    scope_request_id = request.scope.get("request_id")
    response = error_response(
        exc.code,
        exc.message,
        status_code=exc.http_status,
        details=exc.details,
        request_id=scope_request_id if isinstance(scope_request_id, str) else None,
    )
    response.headers["WWW-Authenticate"] = WWW_AUTHENTICATE_CHALLENGE
    return response


def _client_ip(request: Request) -> str | None:
    """Return the address of the client of *request*.

    Only the address of the socket is used: a forwarded header would be
    under the control of the client and must therefore never be trusted.
    """
    client = request.client
    return client.host if client is not None else None


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def register(
    payload: RegisterRequest,
    settings: SettingsDep,
    service: AuthServiceDep,
) -> UserRead:
    """Create an account and return it.

    Raises
    ------
    app.core.exceptions.AppError
        With the code ``registration_disabled`` and the status ``403`` when
        the registration is switched off.
    app.core.exceptions.ConflictError
        With the status ``409`` when the address is already registered.
    app.core.exceptions.ValidationError
        With the status ``422`` when the payload does not satisfy the rules.
    """
    if not settings.auth_registration_enabled:
        raise AppError(
            "the registration is disabled",
            code="registration_disabled",
            http_status=status.HTTP_403_FORBIDDEN,
        )

    summary = service.register(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
    )
    return UserRead.model_validate(summary)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in and open a session",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
) -> LoginResponse:
    """Verify the credential and open a session.

    The session token is written into the httpOnly cookie
    ``AUTH_COOKIE_NAME``.  The body carries the user and the moment the
    session expires - never the token itself.

    Raises
    ------
    app.core.exceptions.AuthenticationError
        With the status ``401`` and the generic message
        ``Invalid email or password.`` when the credential is not valid.
    """
    authenticated = service.authenticate(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=authenticated.token,
        httponly=True,
        samesite="lax",
        secure=settings.auth_cookie_secure,
        path="/",
        max_age=int(settings.auth_session_ttl_hours) * 3600,
    )

    return LoginResponse(
        user=LoginUserRead.model_validate(authenticated.user),
        expires_at=authenticated.expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="End the session",
)
def logout(
    request: Request,
    settings: SettingsDep,
    service: AuthServiceDep,
) -> Response:
    """Revoke the session of the request and clear the cookie.

    The endpoint is idempotent: a request without a session is answered
    with ``204`` as well, because the session the client wanted to end is
    gone either way.
    """
    token = extract_session_token(request, settings)
    service.logout(token)

    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    result.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.auth_cookie_secure,
    )
    return result


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the user of the current session",
)
def me(current_user: CurrentUserDep) -> UserRead:
    """Return the user of the current session.

    Raises
    ------
    app.core.exceptions.AuthenticationError
        With the status ``401`` when there is no valid session.
    """
    return UserRead.model_validate(current_user)


@router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    summary="Return the demo scenarios",
)
def scenarios(service: AuthServiceDep) -> ScenarioListResponse:
    """Return the demo scenarios of the system.

    The endpoint is public: the landing page of the frontend shows the
    scenarios before anybody signed in.  The demo credentials are only part
    of the answer when ``AUTH_DEMO_SCENARIOS_ENABLED`` is true.
    """
    return ScenarioListResponse(
        scenarios=[
            ScenarioRead.model_validate(scenario)
            for scenario in service.list_scenarios()
        ]
    )
# The router carries the two public endpoints of the authentication and the
# two endpoints that need a session; the guard of the protected routers
# lives in :mod:`app.api.deps`.