"""require_role / require_capability against the guide §3.1 matrix, and the service-side checks."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_capability, require_role
from app.core.errors import ForbiddenError, NotFoundError
from app.core.permissions import ROLE_CAPABILITIES, Capability, Role, roles_with
from app.services.auth_service import Principal
from app.services.authz import ensure_can, found
from tests.conftest import build_app, client_for, sign_in
from tests.factories import make_workspace, make_workspace_user


def _rbac_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/_rbac")
    for capability in Capability:
        router.add_api_route(
            f"/capability/{capability.value}",
            lambda: {"ok": True},
            dependencies=[Depends(require_capability(capability))],
        )
    router.add_api_route(
        "/admin-or-reviewer",
        lambda: {"ok": True},
        dependencies=[Depends(require_role(Role.ADMIN, Role.REVIEWER))],
    )
    return router


@pytest.fixture
async def rbac_client(db: Session) -> AsyncIterator[AsyncClient]:
    app: FastAPI = build_app()
    app.include_router(_rbac_router())
    app.dependency_overrides[get_db] = lambda: db
    async with client_for(app) as client:
        yield client


async def _as(client: AsyncClient, db: Session, role: Role) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, role)
    sign_in(client, db, user.id, workspace.id)


@pytest.mark.parametrize("role", list(Role))
async def test_require_capability_follows_the_role_matrix(
    rbac_client: AsyncClient, db: Session, role: Role
) -> None:
    await _as(rbac_client, db, role)

    for capability in Capability:
        response = await rbac_client.get(f"/api/v1/_rbac/capability/{capability.value}")

        expected = 200 if capability in ROLE_CAPABILITIES[role] else 403
        assert response.status_code == expected, (role, capability)
        if expected == 403:
            assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.ADMIN, 200), (Role.REVIEWER, 200), (Role.DEVELOPER, 403), (Role.VIEWER, 403)],
)
async def test_require_role_allows_only_the_listed_roles(
    rbac_client: AsyncClient, db: Session, role: Role, expected: int
) -> None:
    await _as(rbac_client, db, role)

    response = await rbac_client.get("/api/v1/_rbac/admin-or-reviewer")

    assert response.status_code == expected


async def test_role_checks_need_a_session_first(rbac_client: AsyncClient) -> None:
    response = await rbac_client.get("/api/v1/_rbac/capability/view")

    assert response.status_code == 401


def test_roles_with_is_derived_from_the_matrix() -> None:
    assert roles_with(Capability.DECIDE_APPROVALS) == {Role.ADMIN, Role.REVIEWER}
    assert roles_with(Capability.VIEW) == set(Role)


def _principal(role: Role) -> Principal:
    return Principal(uuid.uuid4(), uuid.uuid4(), role, uuid.uuid4())


def test_ensure_can_raises_403_for_a_missing_capability() -> None:
    ensure_can(_principal(Role.DEVELOPER), Capability.MANAGE_APPLICATIONS)

    with pytest.raises(ForbiddenError):
        ensure_can(_principal(Role.VIEWER), Capability.MANAGE_APPLICATIONS)


def test_found_turns_a_scoped_miss_into_404() -> None:
    assert found("x") == "x"

    with pytest.raises(NotFoundError):
        found(None)
