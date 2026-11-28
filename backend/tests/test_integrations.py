"""GitHub integration connect, verify and disconnect (SCRUM-43): allowed, denied,
cross-workspace and refused-installation cases, plus the worker's verification job.
"""

import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import Role
from app.models import AuditLog, Integration, Job, Workspace
from app.models.enums import IntegrationStatus, JobStatus
from app.repositories import integrations as integration_repository
from app.schemas.jobs import JobKind
from app.services.integration_service import InstallationInfo
from app.worker.handlers.github_installation import verify_installation_spec
from app.worker.runner import Worker, WorkerConfig
from tests.conftest import SITE_ORIGIN, sign_in
from tests.factories import make_integration, make_workspace, make_workspace_user

ORIGIN = {"Origin": SITE_ORIGIN}
BASE = "/api/v1/integrations"
CALLBACK = f"{BASE}/github/callback"


def _as(
    client: AsyncClient, db: Session, role: Role, workspace: Workspace | None = None
) -> Workspace:
    workspace = workspace or make_workspace(db)
    user = make_workspace_user(db, workspace, role)
    sign_in(client, db, user.id, workspace.id)
    return workspace


def _installation_id() -> int:
    return uuid.uuid4().int % 10**9 + 1


def _audit_actions(db: Session, target_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(AuditLog.action)
            .where(AuditLog.target_id == target_id)
            .order_by(AuditLog.created_at, AuditLog.action)
        ).all()
    )


def _verify_jobs(db: Session, workspace: Workspace) -> list[Job]:
    return list(
        db.scalars(
            select(Job).where(
                Job.workspace_id == workspace.id,
                Job.kind == JobKind.VERIFY_GITHUB_INSTALLATION.value,
            )
        ).all()
    )


def _counts(db: Session) -> tuple[int, int, int]:
    return (
        db.scalar(select(func.count()).select_from(Integration)) or 0,
        db.scalar(select(func.count()).select_from(Job)) or 0,
        db.scalar(select(func.count()).select_from(AuditLog)) or 0,
    )


# --- Connect --------------------------------------------------------------------------------


async def test_admin_links_an_installation_as_pending_and_enqueues_verification(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    installation_id = _installation_id()

    response = await db_client.post(
        CALLBACK,
        json={"installation_id": installation_id, "setup_action": "install"},
        headers=ORIGIN,
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["installation_id"] == installation_id
    assert body["account_login"] is None
    jobs = _verify_jobs(db, workspace)
    assert len(jobs) == 1
    assert jobs[0].payload == {"integration_id": body["id"]}
    assert _audit_actions(db, uuid.UUID(body["id"])) == ["integration.requested"]
    # Not usable for dispatches until the worker verifies it.
    assert integration_repository.get_active_github(db, workspace.id) is None


async def test_the_same_installation_again_returns_the_existing_link(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    installation_id = _installation_id()
    first = await db_client.post(
        CALLBACK, json={"installation_id": installation_id}, headers=ORIGIN
    )

    again = await db_client.post(
        CALLBACK,
        json={"installation_id": installation_id, "setup_action": "update"},
        headers=ORIGIN,
    )

    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(_verify_jobs(db, workspace)) == 1


async def test_an_installation_linked_to_another_workspace_is_refused(
    db_client: AsyncClient, db: Session
) -> None:
    owner = make_workspace(db)
    taken = make_integration(db, owner, status=IntegrationStatus.ACTIVE)
    _as(db_client, db, Role.ADMIN)
    before = _counts(db)

    response = await db_client.post(
        CALLBACK, json={"installation_id": taken.installation_id}, headers=ORIGIN
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "installation_unavailable"
    assert str(owner.id) not in response.text
    assert _counts(db) == before  # nothing written: no integration, job or audit row


async def test_a_disconnected_installation_can_be_linked_again(
    db_client: AsyncClient, db: Session
) -> None:
    old = make_integration(db, make_workspace(db), status=IntegrationStatus.DISCONNECTED)
    _as(db_client, db, Role.ADMIN)

    response = await db_client.post(
        CALLBACK, json={"installation_id": old.installation_id}, headers=ORIGIN
    )

    assert response.status_code == 202


async def test_a_second_installation_in_one_workspace_is_refused(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    make_integration(db, workspace, status=IntegrationStatus.ACTIVE)
    before = _counts(db)

    response = await db_client.post(
        CALLBACK, json={"installation_id": _installation_id()}, headers=ORIGIN
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "integration_exists"
    assert _counts(db) == before


@pytest.mark.parametrize(
    "body",
    [
        {"installation_id": 0},
        {"installation_id": -5},
        {"installation_id": "12; DROP TABLE"},
        {"installation_id": 2**63},
        {"installation_id": 1, "setup_action": "delete"},
        {"installation_id": 1, "workspace_id": str(uuid.uuid4())},
        {},
    ],
)
async def test_a_malformed_callback_is_422(
    db_client: AsyncClient, db: Session, body: dict[str, object]
) -> None:
    _as(db_client, db, Role.ADMIN)

    response = await db_client.post(CALLBACK, json=body, headers=ORIGIN)

    assert response.status_code == 422


@pytest.mark.parametrize("role", [Role.DEVELOPER, Role.REVIEWER, Role.VIEWER])
async def test_only_an_admin_can_connect_list_or_disconnect(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    workspace = _as(db_client, db, role)
    integration = make_integration(db, workspace)
    before = _counts(db)

    connect = await db_client.post(
        CALLBACK, json={"installation_id": _installation_id()}, headers=ORIGIN
    )
    listing = await db_client.get(BASE)
    remove = await db_client.delete(f"{BASE}/{integration.id}", headers=ORIGIN)

    assert (connect.status_code, listing.status_code, remove.status_code) == (403, 403, 403)
    assert _counts(db) == before
    db.refresh(integration)
    assert integration.status == IntegrationStatus.ACTIVE.value


# --- List and disconnect --------------------------------------------------------------------


async def test_admin_lists_only_their_workspaces_integrations(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    own = make_integration(db, workspace, status=IntegrationStatus.DISCONNECTED)
    make_integration(db, make_workspace(db))

    response = await db_client.get(BASE)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(own.id)]


async def test_disconnect_stops_dispatches_and_is_audited(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = _as(db_client, db, Role.ADMIN)
    integration = make_integration(db, workspace, status=IntegrationStatus.ACTIVE)
    assert integration_repository.get_active_github(db, workspace.id) is not None

    response = await db_client.delete(f"{BASE}/{integration.id}", headers=ORIGIN)
    again = await db_client.delete(f"{BASE}/{integration.id}", headers=ORIGIN)

    assert (response.status_code, again.status_code) == (204, 204)
    assert integration_repository.get_active_github(db, workspace.id) is None
    db.refresh(integration)
    assert integration.status == IntegrationStatus.DISCONNECTED.value
    assert integration.disconnected_at is not None
    assert _audit_actions(db, integration.id) == ["integration.disconnected"]  # once


async def test_another_workspaces_integration_is_404_and_untouched(
    db_client: AsyncClient, db: Session
) -> None:
    foreign = make_integration(db, make_workspace(db))
    _as(db_client, db, Role.ADMIN)

    response = await db_client.delete(f"{BASE}/{foreign.id}", headers=ORIGIN)

    assert response.status_code == 404
    db.refresh(foreign)
    assert foreign.status == IntegrationStatus.ACTIVE.value


# --- The worker's verification job ----------------------------------------------------------


class FakeGitHub:
    def __init__(self, installations: dict[int, InstallationInfo], *, down: bool = False) -> None:
        self.installations = installations
        self.down = down
        self.calls: list[int] = []

    async def get_installation(self, installation_id: int) -> InstallationInfo | None:
        self.calls.append(installation_id)
        if self.down:
            raise ConnectionError("api.github.com unreachable")
        return self.installations.get(installation_id)


INFO = InstallationInfo(
    account_login="octo-org", permissions={"actions": "write", "contents": "read"}
)


def _verifier(db: Session, github: FakeGitHub) -> Worker:
    return Worker(
        session=lambda: nullcontext(db),
        jobs={JobKind.VERIFY_GITHUB_INSTALLATION.value: verify_installation_spec(github)},
        config=WorkerConfig(backoff_base_seconds=1),
        clock=lambda: datetime.now(UTC) + timedelta(hours=1),
    )


async def _connect(client: AsyncClient, db: Session) -> tuple[Workspace, uuid.UUID, int]:
    workspace = _as(client, db, Role.ADMIN)
    installation_id = _installation_id()
    response = await client.post(
        CALLBACK, json={"installation_id": installation_id}, headers=ORIGIN
    )
    assert response.status_code == 202
    return workspace, uuid.UUID(response.json()["id"]), installation_id


async def test_a_known_installation_becomes_active(db_client: AsyncClient, db: Session) -> None:
    workspace, integration_id, installation_id = await _connect(db_client, db)
    github = FakeGitHub({installation_id: INFO})

    assert await _verifier(db, github).run_once() == 1

    active = integration_repository.get_active_github(db, workspace.id)
    assert active is not None and active.id == integration_id
    assert active.account_login == "octo-org"
    assert active.permissions_summary == {"actions": "write", "contents": "read"}
    assert active.connected_at is not None
    # Same transaction in tests, so the same created_at: compare as sorted lists.
    assert _audit_actions(db, integration_id) == ["integration.connected", "integration.requested"]
    listing = await db_client.get(BASE)
    assert listing.json()[0]["status"] == "active"


async def test_an_unknown_installation_is_refused(db_client: AsyncClient, db: Session) -> None:
    workspace, integration_id, installation_id = await _connect(db_client, db)
    github = FakeGitHub({})  # GitHub answers 404: not an installation of our App

    await _verifier(db, github).run_once()

    assert github.calls == [installation_id]
    assert integration_repository.get_active_github(db, workspace.id) is None
    integration = db.get(Integration, integration_id)
    assert integration is not None and integration.status == IntegrationStatus.INVALID.value
    assert "integration.verification_failed" in _audit_actions(db, integration_id)


async def test_a_link_disconnected_before_verification_stays_disconnected(
    db_client: AsyncClient, db: Session
) -> None:
    workspace, integration_id, installation_id = await _connect(db_client, db)
    await db_client.delete(f"{BASE}/{integration_id}", headers=ORIGIN)
    github = FakeGitHub({installation_id: INFO})

    await _verifier(db, github).run_once()

    assert github.calls == []  # nothing left to verify
    assert integration_repository.get_active_github(db, workspace.id) is None


async def test_github_unreachable_retries_then_marks_the_link_invalid(
    db_client: AsyncClient, db: Session
) -> None:
    workspace, integration_id, _ = await _connect(db_client, db)
    github = FakeGitHub({}, down=True)
    job = _verify_jobs(db, workspace)[0]
    job.max_attempts = 2
    db.commit()
    clock = [datetime.now(UTC) + timedelta(hours=1)]
    worker = _verifier(db, github)
    worker.clock = lambda: clock[0]

    await worker.run_once()  # attempt 1: retried
    db.refresh(job)
    assert job.status == JobStatus.PENDING.value
    clock[0] += timedelta(minutes=5)
    await worker.run_once()  # attempt 2: dead → on_dead marks it invalid

    db.refresh(job)
    assert job.status == JobStatus.DEAD.value
    integration = db.get(Integration, integration_id)
    db.refresh(integration)
    assert integration is not None and integration.status == IntegrationStatus.INVALID.value
