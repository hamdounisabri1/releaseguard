"""Environment read and update: Admin-only edits, policy validation, cross-workspace 404."""

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


def _as(
    client: AsyncClient, db: Session, role: Role, workspace: Workspace | None = None
) -> Workspace:
    workspace = workspace or make_workspace(db)
    user = make_workspace_user(db, workspace, role)
    sign_in(client, db, user.id, workspace.id)
    return workspace


async def _environments(client: AsyncClient) -> list[dict[str, Any]]:
    """Create an application and return its three environments (dev, staging, prod)."""
    created = await client.post(
        "/api/v1/applications",
        json={
            "name": "TaskFlow",
            "repository_owner": "octo",
            "repository_name": f"r-{uuid.uuid4().hex[:6]}",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    response = await client.get(f"/api/v1/applications/{created.json()['id']}/environments")
    environments: list[dict[str, Any]] = response.json()
    return environments


async def _patch(client: AsyncClient, environment_id: str, body: dict[str, Any]) -> Any:
    return await client.patch(f"/api/v1/environments/{environment_id}", json=body, headers=ORIGIN)


async def test_admin_updates_timing_and_merges_policy_fields(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    _, _, prod = await _environments(db_client)

    response = await _patch(
        db_client,
        prod["id"],
        {"failure_threshold": 5, "policy": {"min_approvals": 2, "require_comment": True}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["failure_threshold"] == 5
    assert body["policy"]["min_approvals"] == 2
    assert body["policy"]["require_comment"] is True
    assert body["policy"]["requires_approval"] is True  # untouched fields keep their value
    assert (
        body["policy"]["promote_from_environment_id"]
        == prod["policy"]["promote_from_environment_id"]
    )
    (entry,) = db.scalars(select(AuditLog).where(AuditLog.action == "environment.updated")).all()
    assert entry.target_id == uuid.UUID(prod["id"])
    assert entry.details_json["changes"] == {
        "failure_threshold": {"from": 3, "to": 5},
        "policy": {
            "min_approvals": {"from": 1, "to": 2},
            "require_comment": {"from": False, "to": True},
        },
    }
    fetched = (await db_client.get(f"/api/v1/environments/{prod['id']}")).json()
    assert fetched == body


async def test_an_unchanged_update_writes_no_audit_entry(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, _, _ = await _environments(db_client)

    response = await _patch(db_client, dev["id"], {"failure_threshold": 3})

    assert response.status_code == 200
    assert db.scalars(select(AuditLog).where(AuditLog.action == "environment.updated")).all() == []


@pytest.mark.parametrize("role", [Role.DEVELOPER, Role.REVIEWER, Role.VIEWER])
async def test_only_admins_configure_environments(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    dev, _, _ = await _environments(db_client)
    _as(db_client, db, role, workspace)

    response = await _patch(db_client, dev["id"], {"failure_threshold": 4})

    assert response.status_code == 403
    assert (await db_client.get(f"/api/v1/environments/{dev['id']}")).status_code == 200


async def test_another_workspaces_environment_is_404(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, _, _ = await _environments(db_client)
    _as(db_client, db, Role.ADMIN)

    assert (await db_client.get(f"/api/v1/environments/{dev['id']}")).status_code == 404
    assert (await _patch(db_client, dev["id"], {"failure_threshold": 4})).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"health_url": "http://169.254.169.254/"},  # arrives in S4 with the SSRF guard
        {"failure_threshold": 0},
        {"timeout_ms": 99},
        {"expected_status": 600},
        {"policy": {"min_approvals": 0}},
        {"policy": {"approval_ttl_hours": 1000}},
        {"policy": {"unknown": True}},
    ],
    ids=lambda b: str(b),
)
async def test_invalid_input_is_422(
    db_client: AsyncClient, db: Session, body: dict[str, Any]
) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, _, _ = await _environments(db_client)

    response = await _patch(db_client, dev["id"], body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_promote_from_must_be_a_sibling_environment(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, staging, _ = await _environments(db_client)
    other_dev, _, _ = await _environments(db_client)

    for source in (staging["id"], other_dev["id"], str(uuid.uuid4())):
        target = staging if source == staging["id"] else dev
        response = await _patch(
            db_client, target["id"], {"policy": {"promote_from_environment_id": source}}
        )
        assert response.status_code == 422, source
        assert response.json()["error"]["code"] == "invalid_policy"


async def test_promotion_cycles_are_refused(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, _, prod = await _environments(db_client)

    # prod <- staging <- dev already; dev <- prod would close the loop.
    response = await _patch(
        db_client, dev["id"], {"policy": {"promote_from_environment_id": prod["id"]}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_policy"


async def test_environments_of_an_archived_application_cannot_be_edited(
    db_client: AsyncClient, db: Session
) -> None:
    _as(db_client, db, Role.ADMIN)
    dev, _, _ = await _environments(db_client)
    await db_client.post(f"/api/v1/applications/{dev['application_id']}/archive", headers=ORIGIN)

    response = await _patch(db_client, dev["id"], {"failure_threshold": 4})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"policy": {"min_approvals": None}},
        {"policy": {"requires_approval": None}},
        {"failure_threshold": None},
        {"policy": None},
    ],
    ids=lambda b: str(b),
)
async def test_explicit_nulls_are_422_not_500(
    db_client: AsyncClient, db: Session, body: dict[str, Any]
) -> None:
    _as(db_client, db, Role.ADMIN)
    _, _, prod = await _environments(db_client)

    response = await _patch(db_client, prod["id"], body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_promote_from_can_be_cleared(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN)
    _, staging, _ = await _environments(db_client)

    response = await _patch(
        db_client, staging["id"], {"policy": {"promote_from_environment_id": None}}
    )

    assert response.status_code == 200
    assert response.json()["policy"]["promote_from_environment_id"] is None
