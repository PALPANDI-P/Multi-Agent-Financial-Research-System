"""Authentication request/response schemas.

The schemas are the **public contract** of the authentication endpoints;
the frontend is built against them:

* ``POST /api/v1/auth/register`` -> ``201`` :class:`UserRead`
* ``POST /api/v1/auth/login``    -> ``200`` :class:`LoginResponse`
* ``POST /api/v1/auth/logout``   -> ``204``
* ``GET  /api/v1/auth/me``       -> ``200`` :class:`UserRead`
* ``GET  /api/v1/auth/scenarios`` -> ``200`` :class:`ScenarioListResponse`
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "LoginUserRead",
    "RegisterRequest",
    "ScenarioListResponse",
    "ScenarioRead",
    "UserRead",
]


class RegisterRequest(BaseModel):
    """The payload of a registration.

    The length of the password is **not** checked here: the minimum length
    is a configuration value (``AUTH_PASSWORD_MIN_LENGTH``) and therefore
    the service layer owns the rule.
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    """The payload of a login.

    The endpoint accepts **JSON only** - a form encoded body is not
    supported.
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserRead(BaseModel):
    """A user as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: str
    scenario_key: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class LoginUserRead(BaseModel):
    """The user of a login answer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: str
    scenario_key: str | None = None


class LoginResponse(BaseModel):
    """The answer of a successful login."""

    model_config = ConfigDict(extra="forbid")

    user: LoginUserRead
    expires_at: datetime


class ScenarioRead(BaseModel):
    """One demo scenario of the system."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    tagline: str
    description: str
    focus_areas: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    demo_email: str | None = None
    demo_password: str | None = None


class ScenarioListResponse(BaseModel):
    """The list of the demo scenarios."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[ScenarioRead] = Field(default_factory=list)