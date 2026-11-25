"""Application CRUD and archive: allowed, denied, cross-workspace and invalid-input cases."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import Role
from app.models import AuditLog, Workspace
from tests.conftest import SITE_ORIGIN, sign_in
from tests.factories import make_workspace, make_workspace_user

ORIGIN = {"Origin": SITE_ORIGIN}
BASE = "/api/v1/applications"


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "TaskFlow",
        "description": "Sample app",
        "repository_owner": "octo-org",
        "repository_name": f"taskflow-{uuid.uuid4().hex[:6]}",
    }
    body.update(overrides)
    return body


def _as(
    client: AsyncClient, db: Session, role: Role, workspace: Workspace | None = None
) -> Workspace:
    workspace = workspace or make_workspace(db)
    user = make_workspace_user(db, workspace, role)
    sign_in(client, db, user.id, workspace.id)
    return workspace


async def _create(client: AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post(BASE, json=_body(**overrides), headers=ORIGIN)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def _audit_actions(db: Session, target_id: str) -> list[str]:
    return list(
        db.scalars(
            select(AuditLog.action)
            .where(AuditLog.target_id == uuid.UUID(target_id))
            .order_by(AuditLog.created_at, AuditLog.action)
        ).all()
    )


# --- Create -------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_admin_and_developer_create_an_application_with_three_environments(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    _as(db_client, db, role)

    app = await _create(db_client, repository_id=123)
    environments = (await db_client.get(f"{BASE}/{app['id']}/environments")).json()

    assert app["status"] == "active"
    assert app["repository_id"] == 123
    assert app["default_branch"] == "main"
    assert app["deploy_workflow_path"] == ".github/workflows/deploy.yml"
    assert [env["environment_type"] for env in environments] == [
        "development",
        "staging",
        "production",
    ]
    dev, staging, prod = (env["policy"] for env in environments)
    assert dev["auto_deploy_on_release"] is True
    assert dev["requires_approval"] is False
    assert dev["promote_from_environment_id"] is None
    assert staging["auto_deploy_on_release"] is False
    assert staging["promote_from_environment_id"] == environments[0]["id"]
    assert prod["requires_approval"] is True
    assert prod["min_approvals"] == 1
    assert prod["promote_from_environment_id"] == environments[1]["id"]
    assert all(env["health_status"] == "unknown" for env in environments)
    assert _audit_actions(db, app["id"]) == ["application.created"]


@pytest.mark.parametrize("role", [Role.REVIEWER, Role.VIEWER])
async def test_reviewer_and_viewer_cannot_create(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    _as(db_client, db, role)

    response = await db_client.post(BASE, json=_body(), headers=ORIGIN)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_create_without_a_session_is_401(db_client: AsyncClient) -> None:
    response = await db_client.post(BASE, json=_body(), headers=ORIGIN)

    assert response.status_code == 401


async def test_create_from_a_foreign_origin_is_403(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)

    response = await db_client.post(BASE, json=_body(), headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_origin_mismatch"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "x" * 101},
        {"repository_owner": "-bad"},
        {"repository_owner": "has space"},
        {"repository_name": ".."},
        {"repository_name": "a/b"},
        {"repository_id": 0},
        {"default_branch": "bad branch"},
        {"deploy_workflow_path": "../../etc/passwd"},
        {"ci_workflow_path": ".github/workflows/ci.sh"},
        {"unexpected": "field"},
    ],
    ids=lambda o: next(iter(o)),
)
async def test_invalid_input_is_422(
    db_client: AsyncClient, db: Session, overrides: dict[str, Any]
) -> None:
    _as(db_client, db, Role.ADMIN)

    response = await db_client.post(BASE, json=_body(**overrides), headers=ORIGIN)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_a_repository_id_is_registered_once_per_workspace(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    await _create(db_client, repository_id=42)

    response = await db_client.post(BASE, json=_body(repository_id=42), headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "repository_already_registered"


# --- Read ---------------------------------------------------------------------------------


async def test_list_shows_only_the_callers_workspace(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)  # another workspace
    foreign = await _create(db_client, name="Foreign")
    _as(db_client, db, Role.ADMIN)  # the caller's own workspace (replaces the session cookie)
    own = await _create(db_client, name="Own")

    body = (await db_client.get(BASE)).json()

    assert [item["id"] for item in body["items"]] == [own["id"]]
    assert body["total"] == 1
    assert foreign["id"] not in str(body)


async def test_list_is_paginated(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    for i in range(3):
        await _create(db_client, name=f"App {i}")

    first = (await db_client.get(BASE, params={"page_size": 2})).json()
    second = (await db_client.get(BASE, params={"page_size": 2, "page": 2})).json()

    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert (await db_client.get(BASE, params={"page_size": 101})).status_code == 422


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_can_read(db_client: AsyncClient, db: Session, role: Role) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    app = await _create(db_client)
    _as(db_client, db, role, workspace)

    assert (await db_client.get(f"{BASE}/{app['id']}")).status_code == 200
    assert (await db_client.get(f"{BASE}/{app['id']}/environments")).status_code == 200


async def test_another_workspaces_application_is_404(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    foreign = await _create(db_client)
    _as(db_client, db, Role.ADMIN)  # now signed in to a different workspace

    for method, path in [
        ("GET", f"{BASE}/{foreign['id']}"),
        ("GET", f"{BASE}/{foreign['id']}/environments"),
        ("PATCH", f"{BASE}/{foreign['id']}"),
        ("POST", f"{BASE}/{foreign['id']}/archive"),
    ]:
        response = await db_client.request(method, path, json={"name": "x"}, headers=ORIGIN)
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "not_found"


async def test_unknown_and_malformed_ids(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.VIEWER)

    assert (await db_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404
    assert (await db_client.get(f"{BASE}/not-a-uuid")).status_code == 422


# --- Update -------------------------------------------------------------------------------


async def test_update_changes_only_sent_fields_and_audits_them(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.DEVELOPER)
    app = await _create(db_client, repository_id=7)

    response = await db_client.patch(
        f"{BASE}/{app['id']}",
        json={"description": "New text", "repository_id": None},
        headers=ORIGIN,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "New text"
    assert body["repository_id"] is None
    assert body["name"] == app["name"]
    (entry,) = db.scalars(select(AuditLog).where(AuditLog.action == "application.updated")).all()
    assert entry.details_json == {
        "changes": {
            "description": {"from": "Sample app", "to": "New text"},
            "repository_id": {"from": 7, "to": None},
        }
    }


async def test_update_refuses_null_for_required_fields(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    app = await _create(db_client)

    response = await db_client.patch(f"{BASE}/{app['id']}", json={"name": None}, headers=ORIGIN)

    assert response.status_code == 422


@pytest.mark.parametrize("role", [Role.REVIEWER, Role.VIEWER])
async def test_reviewer_and_viewer_cannot_edit_or_archive(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    app = await _create(db_client)
    _as(db_client, db, role, workspace)

    edit = await db_client.patch(f"{BASE}/{app['id']}", json={"name": "x"}, headers=ORIGIN)
    archive = await db_client.post(f"{BASE}/{app['id']}/archive", headers=ORIGIN)

    assert edit.status_code == archive.status_code == 403


# --- Archive ------------------------------------------------------------------------------


async def test_archive_hides_the_application_but_keeps_its_history(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    app = await _create(db_client)

    response = await db_client.post(f"{BASE}/{app['id']}/archive", headers=ORIGIN)
    again = await db_client.post(f"{BASE}/{app['id']}/archive", headers=ORIGIN)

    assert response.status_code == again.status_code == 200
    assert response.json()["status"] == "archived"
    assert response.json()["archived_at"] is not None
    assert (await db_client.get(BASE)).json()["items"] == []
    archived_list = (await db_client.get(BASE, params={"include_archived": True})).json()
    assert [item["id"] for item in archived_list["items"]] == [app["id"]]
    assert (await db_client.get(f"{BASE}/{app['id']}")).status_code == 200
    assert len((await db_client.get(f"{BASE}/{app['id']}/environments")).json()) == 3
    assert _audit_actions(db, app["id"]) == ["application.archived", "application.created"]


async def test_an_archived_application_cannot_be_edited(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    app = await _create(db_client)
    await db_client.post(f"{BASE}/{app['id']}/archive", headers=ORIGIN)

    response = await db_client.patch(f"{BASE}/{app['id']}", json={"name": "x"}, headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "application_archived"
