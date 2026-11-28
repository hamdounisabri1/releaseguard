"""Release registration (SCRUM-37): CI with a GitHub OIDC token (ADR-0006) and the manual
fallback. Every refused request is checked to write nothing.
"""

import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from jwt import PyJWK
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_oidc_verifier
from app.core.oidc import GITHUB_OIDC_ISSUER, OidcVerifier
from app.core.permissions import Role
from app.models import Application, AuditLog, Release, Workspace
from app.models.enums import ActorType, ApplicationStatus
from tests.conftest import SITE_ORIGIN, client_for, sign_in
from tests.factories import (
    digest,
    make_application,
    make_release,
    make_workspace,
    make_workspace_user,
)
from tests.oidc_keys import LocalKeys

AUDIENCE = "releaseguard-test"
CI = "/api/v1/releases/ci"
MANUAL = "/api/v1/releases"
ORIGIN = {"Origin": SITE_ORIGIN}
SHA = "3f786850e387550fdab836ed7e6dc881de23001b"
RUN_ID = 4242
KEYS = LocalKeys()


# --- Fixtures and builders ------------------------------------------------------------------


def _verifier(audience: str | None = AUDIENCE) -> OidcVerifier:
    return OidcVerifier(audience, KEYS)


@pytest.fixture
async def ci_client(db_app: FastAPI) -> AsyncIterator[AsyncClient]:
    db_app.dependency_overrides[get_oidc_verifier] = _verifier
    async with client_for(db_app) as client:
        yield client


def _app(db: Session, workspace: Workspace | None = None) -> Application:
    application = make_application(db, workspace or make_workspace(db))
    application.repository_id = uuid.uuid4().int % 10**9 + 1
    db.flush()
    return application


def _claims(application: Application, **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    repository = f"{application.repository_owner}/{application.repository_name}"
    claims: dict[str, Any] = {
        "iss": GITHUB_OIDC_ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "repository": repository,
        "repository_id": str(application.repository_id),  # GitHub sends ids as strings
        "workflow_ref": f"{repository}/.github/workflows/ci.yml@refs/heads/main",
        "ref": "refs/heads/main",
        "sha": SHA,
        "run_id": str(RUN_ID),
        "actor": "octocat",
        "event_name": "push",
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "version": "1.4.0",
        "commit_sha": SHA,
        "branch": "main",
        "image_repository": "ghcr.io/octo-org/taskflow",
        "image_tag": "1.4.0",
        "image_digest": digest("1.4.0"),
        "workflow_run_id": RUN_ID,
    }
    body.update(overrides)
    return body


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _post_ci(
    client: AsyncClient,
    application: Application,
    *,
    claims: dict[str, Any] | None = None,
    **body: Any,
) -> Any:
    token = KEYS.sign(claims if claims is not None else _claims(application))
    return await client.post(CI, json=_body(**body), headers=_bearer(token))


def _counts(db: Session) -> tuple[int, int]:
    return (
        db.scalar(select(func.count()).select_from(Release)) or 0,
        db.scalar(select(func.count()).select_from(AuditLog)) or 0,
    )


# --- CI: success, replay, conflicts ---------------------------------------------------------


async def test_a_valid_token_registers_the_release(ci_client: AsyncClient, db: Session) -> None:
    application = _app(db)

    response = await _post_ci(ci_client, application)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["application_id"] == str(application.id)
    assert (body["version"], body["commit_sha"]) == ("1.4.0", SHA)
    assert body["image_digest"] == digest("1.4.0")
    assert body["source"] == "ci"
    assert body["created_by"] is None
    assert body["workflow_run_id"] == RUN_ID
    repository = f"{application.repository_owner}/{application.repository_name}"
    assert body["workflow_url"] == f"https://github.com/{repository}/actions/runs/{RUN_ID}"

    audit = db.scalars(select(AuditLog).where(AuditLog.target_id == uuid.UUID(body["id"]))).one()
    assert (audit.action, audit.actor_type, audit.actor_id) == (
        "release.registered",
        ActorType.CI.value,
        None,
    )
    assert audit.workspace_id == application.workspace_id
    assert audit.details_json["github_actor"] == "octocat"
    assert audit.details_json["workflow_run_id"] == RUN_ID


async def test_a_release_from_a_tag_is_accepted(ci_client: AsyncClient, db: Session) -> None:
    application = _app(db)
    repository = f"{application.repository_owner}/{application.repository_name}"
    claims = _claims(
        application, workflow_ref=f"{repository}/.github/workflows/ci.yml@refs/tags/v1.4.0"
    )

    response = await _post_ci(ci_client, application, claims=claims)

    assert response.status_code == 201, response.text


async def test_a_ci_retry_of_the_same_build_returns_the_release(
    ci_client: AsyncClient, db: Session
) -> None:
    application = _app(db)
    first = await _post_ci(ci_client, application)
    before = _counts(db)

    again = await _post_ci(ci_client, application)

    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert _counts(db) == before  # no second row, no second audit entry


async def test_the_same_version_with_another_digest_is_409(
    ci_client: AsyncClient, db: Session
) -> None:
    application = _app(db)
    await _post_ci(ci_client, application)
    before = _counts(db)

    response = await _post_ci(ci_client, application, image_digest=digest("rebuilt"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "release_version_exists"
    assert _counts(db) == before


# --- CI: the token itself (401) -------------------------------------------------------------


def _expired(application: Application) -> str:
    now = int(time.time())
    return KEYS.sign(_claims(application, iat=now - 900, nbf=now - 900, exp=now - 120))


TOKENS: dict[str, Callable[[Application], str]] = {
    "expired": _expired,
    "wrong_audience": lambda a: KEYS.sign(_claims(a, aud="another-service")),
    "wrong_issuer": lambda a: KEYS.sign(_claims(a, iss="https://evil.example")),
    "foreign_signature": lambda a: KEYS.sign(_claims(a), other_key=True),
    "unknown_key_id": lambda a: KEYS.sign(_claims(a), kid="rotated-away"),
    "missing_repository_id": lambda a: KEYS.sign(_claims(a, repository_id=None)),
    "missing_exp": lambda a: KEYS.sign(_claims(a, exp=None)),
    "not_a_jwt": lambda a: "not.a.jwt",
}


@pytest.mark.parametrize("case", sorted(TOKENS))
async def test_a_bad_token_is_401_and_writes_nothing(
    ci_client: AsyncClient, db: Session, case: str
) -> None:
    application = _app(db)
    before = _counts(db)

    response = await ci_client.post(CI, json=_body(), headers=_bearer(TOKENS[case](application)))

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "invalid_oidc_token"
    assert response.headers["www-authenticate"] == "Bearer"
    assert _counts(db) == before


async def test_no_token_is_401_before_the_body_is_looked_at(
    ci_client: AsyncClient, db: Session
) -> None:
    response = await ci_client.post(CI, json={"anything": True})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_oidc_token"


async def test_without_a_configured_audience_every_token_is_refused(
    db_app: FastAPI, db: Session
) -> None:
    db_app.dependency_overrides[get_oidc_verifier] = lambda: _verifier(audience=None)
    application = _app(db)
    async with client_for(db_app) as client:
        response = await _post_ci(client, application)

    assert response.status_code == 401
    assert _counts(db)[0] == 0


async def test_an_unreachable_jwks_is_503(db_app: FastAPI, db: Session) -> None:
    class Unreachable:
        def get_signing_key_from_jwt(self, token: str) -> PyJWK:
            raise PyJWKClientConnectionError("Fail to fetch data from the url")

    db_app.dependency_overrides[get_oidc_verifier] = lambda: OidcVerifier(AUDIENCE, Unreachable())
    application = _app(db)
    async with client_for(db_app) as client:
        response = await _post_ci(client, application)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "oidc_unavailable"


# --- CI: binding the claims to the application (403) ----------------------------------------


def _binding_cases(application: Application) -> dict[str, dict[str, Any]]:
    repository = f"{application.repository_owner}/{application.repository_name}"
    workflow = f"{repository}/.github/workflows"
    return {
        "unknown_repository": {"repository_id": "999999999999"},
        "other_workflow_file": {"workflow_ref": f"{workflow}/release.yml@refs/heads/main"},
        "pull_request_ref": {"workflow_ref": f"{workflow}/ci.yml@refs/pull/7/merge"},
        "feature_branch": {"workflow_ref": f"{workflow}/ci.yml@refs/heads/feature"},
        "workflow_of_another_repository": {
            "workflow_ref": "evil/fork/.github/workflows/ci.yml@refs/heads/main"
        },
        "sha_mismatch": {"sha": "0" * 40},
        "run_id_mismatch": {"run_id": "1"},
    }


@pytest.mark.parametrize(
    "case",
    [
        "unknown_repository",
        "other_workflow_file",
        "pull_request_ref",
        "feature_branch",
        "workflow_of_another_repository",
        "sha_mismatch",
        "run_id_mismatch",
    ],
)
async def test_a_token_bound_to_something_else_is_403_and_writes_nothing(
    ci_client: AsyncClient, db: Session, case: str
) -> None:
    application = _app(db)
    claims = _claims(application, **_binding_cases(application)[case])
    before = _counts(db)

    response = await _post_ci(ci_client, application, claims=claims)

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "oidc_binding_mismatch"
    assert _counts(db) == before


async def test_an_archived_application_gets_no_ci_releases(
    ci_client: AsyncClient, db: Session
) -> None:
    application = _app(db)
    claims = _claims(application)
    application.status = ApplicationStatus.ARCHIVED.value
    db.flush()

    response = await _post_ci(ci_client, application, claims=claims)

    assert response.status_code == 403


async def test_a_repository_bound_in_two_workspaces_is_ambiguous(
    ci_client: AsyncClient, db: Session
) -> None:
    application = _app(db)
    twin = make_application(db, make_workspace(db))
    twin.repository_id = application.repository_id
    db.flush()
    before = _counts(db)

    response = await _post_ci(ci_client, application)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "repository_ambiguous"
    assert _counts(db) == before


# --- CI: body validation (422) --------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"image_digest": "ghcr.io/octo-org/taskflow:latest"},
        {"image_digest": "latest"},
        {"image_digest": "sha256:" + "A" * 64},
        {"image_digest": "sha256:" + "a" * 63},
        {"commit_sha": "abc123"},
        {"version": "../../etc"},
        {"image_repository": "GHCR.io/Octo/TaskFlow"},
        {"image_tag": "bad tag"},
        {"workflow_run_id": 0},
        {"source": "manual"},
    ],
)
async def test_a_malformed_ci_body_is_422(
    ci_client: AsyncClient, db: Session, override: dict[str, Any]
) -> None:
    application = _app(db)
    before = _counts(db)

    response = await _post_ci(ci_client, application, **override)

    assert response.status_code == 422, response.text
    assert _counts(db) == before


# --- Manual registration --------------------------------------------------------------------


def _as(client: AsyncClient, db: Session, role: Role, workspace: Workspace) -> uuid.UUID:
    user = make_workspace_user(db, workspace, role)
    sign_in(client, db, user.id, workspace.id)
    return user.id


def _manual_body(application: Application, **overrides: Any) -> dict[str, Any]:
    body = _body(application_id=str(application.id), release_notes="First cut")
    del body["workflow_run_id"]
    body.update(overrides)
    return body


@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_admin_or_developer_registers_a_release_manually(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    workspace = make_workspace(db)
    user_id = _as(db_client, db, role, workspace)
    application = make_application(db, workspace)

    response = await db_client.post(MANUAL, json=_manual_body(application), headers=ORIGIN)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["source"], body["created_by"]) == ("manual", str(user_id))
    assert body["workflow_url"] is None
    audit = db.scalars(select(AuditLog).where(AuditLog.target_id == uuid.UUID(body["id"]))).one()
    assert (audit.action, audit.actor_id) == ("release.registered", user_id)


@pytest.mark.parametrize("role", [Role.REVIEWER, Role.VIEWER])
async def test_reviewer_or_viewer_cannot_register_a_release(
    db_client: AsyncClient, db: Session, role: Role
) -> None:
    workspace = make_workspace(db)
    _as(db_client, db, role, workspace)
    application = make_application(db, workspace)
    before = _counts(db)

    response = await db_client.post(MANUAL, json=_manual_body(application), headers=ORIGIN)

    assert response.status_code == 403
    assert _counts(db) == before


async def test_another_workspaces_application_is_404(db_client: AsyncClient, db: Session) -> None:
    _as(db_client, db, Role.ADMIN, make_workspace(db))
    foreign = make_application(db, make_workspace(db))
    before = _counts(db)

    response = await db_client.post(MANUAL, json=_manual_body(foreign), headers=ORIGIN)

    assert response.status_code == 404
    assert _counts(db) == before


async def test_an_archived_application_is_409(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    _as(db_client, db, Role.DEVELOPER, workspace)
    application = make_application(db, workspace)
    application.status = ApplicationStatus.ARCHIVED.value
    db.flush()

    response = await db_client.post(MANUAL, json=_manual_body(application), headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "application_archived"


async def test_a_duplicate_manual_version_is_409(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    _as(db_client, db, Role.DEVELOPER, workspace)
    application = make_application(db, workspace)
    existing = make_release(db, application, version="2.0.0")
    before = _counts(db)

    response = await db_client.post(
        MANUAL,
        json=_manual_body(application, version="2.0.0", image_digest=existing.image_digest),
        headers=ORIGIN,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "release_version_exists"
    assert _counts(db) == before


async def test_a_manual_release_needs_a_digest(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    _as(db_client, db, Role.DEVELOPER, workspace)
    application = make_application(db, workspace)

    response = await db_client.post(
        MANUAL, json=_manual_body(application, image_digest="taskflow:latest"), headers=ORIGIN
    )

    assert response.status_code == 422
