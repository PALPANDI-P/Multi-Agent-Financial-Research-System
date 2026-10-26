"""Seed the three demo accounts of the Multi-Agent Financial Research System.

Run the module to create the demo users, their personal workspaces and the
membership of the shared corpus::

    python -m scripts.seed_users

The script is **idempotent**: it can be run again and again.  An account
that exists is not created a second time, a personal workspace that exists
is not created a second time and a membership that exists is not inserted
a second time.

The script uses the real services - :class:`app.services.auth_service.AuthService`,
:class:`app.repositories.user_repository.UserRepository` and
:class:`app.services.workspace_service.WorkspaceService` - and never talks
to the database directly.

The database is the one of the application configuration (``DATABASE_URL``);
the development database therefore receives the demo accounts.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.session import SessionLocal
from app.repositories.user_repository import UserRepository
from app.services.auth_service import DEMO_PASSWORD, AuthService
from app.services.workspace_service import WorkspaceService

__all__ = ["DEMO_USERS", "main", "seed_users"]

#: The name of the workspace that holds the shared financial corpus.
SHARED_WORKSPACE_NAME = "Seed Documents"


@dataclass(frozen=True, slots=True)
class DemoUser:
    """One demo account and its personal workspace."""

    email: str
    full_name: str
    role: str
    scenario_key: str
    workspace_name: str
    workspace_description: str


#: The three demo accounts of the system.
DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        email="analyst@demo.local",
        full_name="Demo Equity Analyst",
        role="analyst",
        scenario_key="equity-analyst",
        workspace_name="Equity Analyst — Filings",
        workspace_description=(
            "The personal workspace of the equity analyst: the filings of the "
            "company, the revenue and the margin trends and the performance of "
            "every segment."
        ),
    ),
    DemoUser(
        email="credit@demo.local",
        full_name="Demo Credit Analyst",
        role="researcher",
        scenario_key="credit-analyst",
        workspace_name="Credit Analyst — Credit Review",
        workspace_description=(
            "The personal workspace of the credit analyst: the strength of the "
            "balance sheet, the liquidity and the funding and the credit risk."
        ),
    ),
    DemoUser(
        email="corpdev@demo.local",
        full_name="Demo Corporate Development Analyst",
        role="researcher",
        scenario_key="corporate-development",
        workspace_name="Corporate Development — Capital Allocation",
        workspace_description=(
            "The personal workspace of the corporate development analyst: the "
            "capital allocation, the acquisitions and the investments and the "
            "returns to the shareholders."
        ),
    ),
)


def _find_workspace(service: WorkspaceService, name: str) -> UUID | None:
    """Return the id of the workspace *name*, whoever owns it."""
    summaries, _ = service.list_workspaces(limit=100, name_contains=name)
    for summary in summaries:
        if summary.name == name:
            return summary.id
    return None


def _find_shared_workspace(service: WorkspaceService) -> UUID | None:
    """Return the id of the shared corpus workspace, if it exists."""
    summaries, _ = service.list_workspaces(limit=100, name_contains=SHARED_WORKSPACE_NAME)
    for summary in summaries:
        if summary.name == SHARED_WORKSPACE_NAME:
            return summary.id
    return None


def seed_users() -> int:
    """Create the demo accounts, their workspaces and the memberships.

    The function returns the number of accounts that were **created** (the
    accounts that already existed are not counted).
    """
    settings = get_settings()
    auth_service = AuthService(SessionLocal, settings=settings)
    workspace_service = WorkspaceService(SessionLocal)

    created = 0
    accounts: list[tuple[DemoUser, UUID]] = []

    print("== the demo accounts ==")
    for demo in DEMO_USERS:
        with SessionLocal() as session:
            existing = UserRepository(session).get_by_email(demo.email)
        if existing is not None:
            user_id = existing.id
            state = "already present"
        else:
            try:
                summary = auth_service.register(
                    email=demo.email,
                    full_name=demo.full_name,
                    password=DEMO_PASSWORD,
                    scenario_key=demo.scenario_key,
                )
            except ConflictError:
                with SessionLocal() as session:
                    existing = UserRepository(session).get_by_email(demo.email)
                if existing is None:  # pragma: no cover - defensive
                    raise
                user_id = existing.id
                state = "already present"
            else:
                user_id = summary.id
                state = "created"
                created += 1
        with SessionLocal() as session:
            repository = UserRepository(session)
            row = repository.get(user_id)
            if row is not None and row.role != demo.role:
                repository.set_role(user_id, demo.role)
                state = f"{state}, role={demo.role}"
        print(f"   {demo.email:<24} {state:<15} id={user_id}")
        accounts.append((demo, user_id))

    print()
    print("== the personal workspaces ==")
    workspace_ids: list[tuple[DemoUser, UUID, UUID]] = []
    for demo, user_id in accounts:
        existing_id = _find_workspace(workspace_service, demo.workspace_name)
        if existing_id is not None:
            workspace_id = existing_id
            # A workspace that lost its owner (a downgrade of the schema
            # for example) is adopted by the demo account.
            workspace_service.set_owner(workspace_id, user_id)
            workspace_service.add_member(workspace_id, user_id)
            state = "already present"
        else:
            summary = workspace_service.create_workspace(
                name=demo.workspace_name,
                description=demo.workspace_description,
                owner_id=user_id,
            )
            workspace_id = summary.id
            state = "created"
        print(f"   {demo.workspace_name:<44} {state:<15} id={workspace_id}")
        workspace_ids.append((demo, user_id, workspace_id))

    print()
    print("== the shared corpus ==")
    shared_id = _find_shared_workspace(workspace_service)
    if shared_id is None:
        print(
            f"   the workspace {SHARED_WORKSPACE_NAME!r} does not exist - the "
            "shared corpus is not visible to the demo accounts.  Run "
            "scripts/seed_documents.py to create it."
        )
    else:
        print(f"   {SHARED_WORKSPACE_NAME:<44} {'found':<15} id={shared_id}")
        for demo, user_id, _ in workspace_ids:
            added = workspace_service.add_member(shared_id, user_id)
            state = "member added" if added else "already a member"
            print(f"      {demo.email:<24} {state}")

    print()
    print("== summary ==")
    print(f"   accounts created this run : {created}")
    print(f"   personal workspaces        : {len(workspace_ids)}")
    print(
        "   shared corpus workspace   : "
        + (str(shared_id) if shared_id is not None else "not found")
    )
    print()
    print("== the demo credentials ==")
    print(f"   password of every account  : {DEMO_PASSWORD}")
    for demo, _user_id in accounts:
        print(f"   {demo.email:<24} role={demo.role:<12} scenario={demo.scenario_key}")
    print()
    print("== the workspace ids ==")
    for demo, _, workspace_id in workspace_ids:
        print(f"   {demo.workspace_name:<44} {workspace_id}")
    if shared_id is not None:
        print(f"   {SHARED_WORKSPACE_NAME:<44} {shared_id}")
    print()
    return created


def main() -> int:
    """Run the seeding and return the exit code of the process."""
    seed_users()
    return 0


if __name__ == "__main__":  # pragma: no cover - the module is the entry point
    sys.exit(main())