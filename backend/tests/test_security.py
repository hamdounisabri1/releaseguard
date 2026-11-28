"""Sprint 1 security sweeps (SCRUM-34) over **every** ``/api/v1`` route of the real app.

The routes come from the app's own route table, so a new endpoint is checked automatically:
it must refuse a foreign Origin, require a session, refuse a Viewer's write and hide another
workspace's resources, without writing anything. A deliberate exception goes in one of the
sets below, with a reason. The per-area tests (test_auth, test_rbac, test_applications,
test_environments, test_csrf, test_permissions) cover behavior in depth; append-only
``audit_logs`` (UPDATE, DELETE, TRUNCATE refused by the trigger) is in test_models.
"""

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings
from app.core.permissions import Role
from app.main import create_app
from app.models import Application, AuditLog, Environment, Integration, Job, Workspace
from app.models.enums import EnvironmentType, IntegrationStatus
from tests.conftest import SITE_ORIGIN, client_for, sign_in
from tests.factories import (
    make_application,
    make_environment,
    make_integration,
    make_workspace,
    make_workspace_user,
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
FOREIGN_ORIGIN = {"Origin": "https://evil.example"}
ORIGIN = {"Origin": SITE_ORIGIN}

# Routes that work without a session: login creates one, logout without one is a no-op.
PUBLIC = {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout")}
# Cookie-less endpoints authenticated by HMAC / OIDC instead (security.md); not built yet.
CSRF_EXEMPT = {("POST", "/api/v1/github/webhooks"), ("POST", "/api/v1/releases/ci")}

# A valid body for each write route, so the checks below hit permissions and scoping rather
# than a 422. A new write route without an entry fails test_every_write_route_has_a_body.
BODIES: dict[tuple[str, str], dict[str, Any] | None] = {
    ("POST", "/api/v1/auth/login"): {"email": "nobody@example.com", "password": "x"},
    ("POST", "/api/v1/auth/logout"): None,
    ("POST", "/api/v1/applications"): {
        "name": "Sweep",
        "repository_owner": "octo",
        "repository_name": "sweep",
    },
    ("PATCH", "/api/v1/applications/{application_id}"): {"name": "Tampered"},
    ("POST", "/api/v1/applications/{application_id}/archive"): None,
    ("PATCH", "/api/v1/environments/{environment_id}"): {"failure_threshold": 7},
    ("POST", "/api/v1/integrations/github/callback"): {"installation_id": 424242},
    ("DELETE", "/api/v1/integrations/{integration_id}"): None,
}


def _settings() -> Settings:
    return Settings(_env_file=None, env="local", site_origin=SITE_ORIGIN, cors_origins=[])


def _routes() -> list[tuple[str, str]]:
    # From the OpenAPI document: FastAPI 0.165 keeps included routers lazy, so `app.routes`
    # doesn't list them. Every API route is in the schema (only test-only routes opt out).
    paths: dict[str, dict[str, Any]] = create_app(_settings()).openapi()["paths"]
    routes = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/v1/")
        for method in operations
        if method.upper() in UNSAFE_METHODS | {"GET"}
    }
    return sorted(routes)


ROUTES = _routes()
WRITE_ROUTES = [r for r in ROUTES if r[0] in UNSAFE_METHODS]
SCOPED_ROUTES = [r for r in ROUTES if "{" in r[1]]
_PARAM = re.compile(r"\{(\w+)\}")


def _route_id(route: tuple[str, str]) -> str:
    return f"{route[0]} {route[1]}"


def _fill(path: str, ids: dict[str, uuid.UUID]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        assert name in ids, f"no test resource for path parameter {{{name}}}: add one to _ids()"
        return str(ids[name])

    return _PARAM.sub(replace, path)


def _ids(db: Session, workspace: Workspace) -> dict[str, uuid.UUID]:
    """One real resource per path parameter, in ``workspace``."""
    application = make_application(db, workspace)
    environment = make_environment(db, application, EnvironmentType.PRODUCTION)
    integration = make_integration(db, workspace, status=IntegrationStatus.ACTIVE)
    return {
        "application_id": application.id,
        "environment_id": environment.id,
        "integration_id": integration.id,
    }


# Tables a refused request must not add rows to.
_COUNTED = (AuditLog, Application, Integration, Job)


def _snapshot(db: Session) -> tuple[int, ...]:
    """Row counts a refused request must not change."""
    return tuple(db.scalar(select(func.count()).select_from(t)) or 0 for t in _COUNTED)


def _assert_untouched(db: Session, ids: dict[str, uuid.UUID], before: tuple[int, ...]) -> None:
    """Nothing was written: same counts, and the test resources still hold their values.

    Re-read from the database (``expire_all``), not from the session's identity map.
    """
    db.expire_all()
    assert _snapshot(db) == before
    application = db.get(Application, ids["application_id"])
    environment = db.get(Environment, ids["environment_id"])
    assert application is not None and environment is not None
    assert application.name == "TaskFlow" and application.archived_at is None
    assert environment.failure_threshold != 7  # the value BODIES tries to set
    integration = db.get(Integration, ids["integration_id"])
    assert integration is not None and integration.status == IntegrationStatus.ACTIVE.value


async def _send(
    client: AsyncClient, route: tuple[str, str], ids: dict[str, uuid.UUID], headers: dict[str, str]
) -> Any:
    method, template = route
    body = BODIES.get(route)
    return await client.request(
        method,
        _fill(template, ids),
        json=body if body is not None else None,
        headers=headers,
    )


@pytest.fixture
def sweep_app(db: Session) -> FastAPI:
    """The real app only (no test routes), with every request on the test's session."""
    app = create_app(_settings())
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
async def sweep_client(sweep_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(sweep_app) as c:
        yield c


# --- The route table itself ---------------------------------------------------------------


def test_the_sweep_sees_the_sprint_1_routes() -> None:
    assert ("GET", "/api/v1/auth/me") in ROUTES
    assert ("PATCH", "/api/v1/applications/{application_id}") in WRITE_ROUTES
    assert ("PATCH", "/api/v1/environments/{environment_id}") in WRITE_ROUTES


def test_every_write_route_has_a_body() -> None:
    missing = [_route_id(r) for r in WRITE_ROUTES if r not in BODIES]
    assert not missing, f"add a valid body to BODIES for {missing}"


def test_the_exception_lists_name_real_routes() -> None:
    # A typo here would silently exempt nothing (or the wrong thing).
    assert set(ROUTES) >= PUBLIC
    assert not (CSRF_EXEMPT & set(ROUTES)), "an exempt route exists now: sweep it with HMAC/OIDC"


# --- CSRF: a foreign Origin is refused on every write, even with a valid session ------------


@pytest.mark.parametrize("route", [r for r in WRITE_ROUTES if r not in CSRF_EXEMPT], ids=_route_id)
async def test_every_write_refuses_a_foreign_origin(
    sweep_client: AsyncClient, db: Session, route: tuple[str, str]
) -> None:
    workspace = make_workspace(db)
    admin = make_workspace_user(db, workspace, Role.ADMIN)
    sign_in(sweep_client, db, admin.id, workspace.id)
    ids = _ids(db, workspace)
    before = _snapshot(db)

    response = await _send(sweep_client, route, ids, FOREIGN_ORIGIN)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_origin_mismatch"
    _assert_untouched(db, ids, before)


# --- Authentication: everything but login/logout needs a session ----------------------------


@pytest.mark.parametrize("route", [r for r in ROUTES if r not in PUBLIC], ids=_route_id)
async def test_every_route_needs_a_session(
    sweep_client: AsyncClient, db: Session, route: tuple[str, str]
) -> None:
    ids = _ids(db, make_workspace(db))
    before = _snapshot(db)

    response = await _send(sweep_client, route, ids, ORIGIN)

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthorized"
    _assert_untouched(db, ids, before)


# --- RBAC: a Viewer can read but never write ----------------------------------------------


@pytest.mark.parametrize("route", [r for r in WRITE_ROUTES if r not in PUBLIC], ids=_route_id)
async def test_a_viewer_cannot_use_any_write_route(
    sweep_client: AsyncClient, db: Session, route: tuple[str, str]
) -> None:
    workspace = make_workspace(db)
    viewer = make_workspace_user(db, workspace, Role.VIEWER)
    sign_in(sweep_client, db, viewer.id, workspace.id)
    ids = _ids(db, workspace)
    before = _snapshot(db)

    response = await _send(sweep_client, route, ids, ORIGIN)

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"
    _assert_untouched(db, ids, before)


# --- Tenancy: another workspace's resources are 404 and untouched --------------------------


@pytest.mark.parametrize("route", SCOPED_ROUTES, ids=_route_id)
async def test_another_workspaces_resources_are_404_and_untouched(
    sweep_client: AsyncClient, db: Session, route: tuple[str, str]
) -> None:
    owner = make_workspace(db)
    ids = _ids(db, owner)
    intruder_workspace = make_workspace(db)
    intruder = make_workspace_user(db, intruder_workspace, Role.ADMIN)  # every capability
    sign_in(sweep_client, db, intruder.id, intruder_workspace.id)
    before = _snapshot(db)

    response = await _send(sweep_client, route, ids, ORIGIN)

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "not_found"
    _assert_untouched(db, ids, before)
