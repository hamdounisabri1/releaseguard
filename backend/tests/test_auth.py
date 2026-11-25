"""Auth: argon2id, server-side sessions, login/logout/me, expiry and rotation."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.passwords import hash_password, needs_rehash, verify_password
from app.core.permissions import Role
from app.models import AuditLog, UserSession, Workspace
from app.services.auth_service import (
    ABSOLUTE_LIFETIME,
    IDLE_TIMEOUT,
    SESSION_COOKIE,
    hash_token,
)
from tests.conftest import SITE_ORIGIN, sign_in
from tests.factories import (
    DEFAULT_PASSWORD,
    make_member,
    make_user,
    make_workspace,
    make_workspace_user,
)

ORIGIN = {"Origin": SITE_ORIGIN}


async def _login(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> Response:
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}, headers=ORIGIN
    )


def _sessions(db: Session) -> list[UserSession]:
    return list(db.scalars(select(UserSession)).all())


# --- Passwords ----------------------------------------------------------------------------


def test_passwords_are_hashed_with_argon2id() -> None:
    password_hash = hash_password("s3cret!")

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "s3cret!")
    assert not verify_password(password_hash, "wrong")
    assert not needs_rehash(password_hash)


def test_a_malformed_hash_never_verifies() -> None:
    assert not verify_password("not-a-hash", "anything")


# --- Login --------------------------------------------------------------------------------


async def test_login_sets_a_hardened_session_cookie_and_returns_the_user(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.REVIEWER)

    response = await _login(db_client, user.email.upper())  # emails are case-insensitive

    assert response.status_code == 200
    assert response.json() == {
        "user": {"id": str(user.id), "email": user.email, "display_name": user.display_name},
        "workspace": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug},
        "role": "reviewer",
    }
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert attribute in cookie
    assert f"Max-Age={int(ABSOLUTE_LIFETIME.total_seconds())}" in cookie

    token = response.cookies[SESSION_COOKIE]
    (session,) = _sessions(db)
    assert session.token_hash == hash_token(token)  # only the hash is stored
    assert token.encode() != session.token_hash
    lifetime = session.expires_at - session.created_at
    assert abs(lifetime - ABSOLUTE_LIFETIME) < timedelta(minutes=1)


async def test_login_writes_an_audit_entry(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.VIEWER)

    await _login(db_client, user.email)

    actions = db.scalars(select(AuditLog.action).where(AuditLog.actor_id == user.id)).all()
    assert actions == ["auth.login"]


async def test_wrong_password_and_unknown_user_get_the_same_401(
    db_client: AsyncClient, db: Session
) -> None:
    user = make_workspace_user(db, make_workspace(db), Role.ADMIN)

    wrong_password = await _login(db_client, user.email, "not-the-password")
    unknown_user = await _login(db_client, "nobody@example.com")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert "set-cookie" not in wrong_password.headers
    assert _sessions(db) == []


async def test_disabled_user_cannot_log_in(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_user(db, status="disabled")
    make_member(db, workspace, user, Role.ADMIN)

    response = await _login(db_client, user.email)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_user_without_a_workspace_cannot_log_in(db_client: AsyncClient, db: Session) -> None:
    user = make_user(db)

    response = await _login(db_client, user.email)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_needs_the_site_origin(db_client: AsyncClient, db: Session) -> None:
    user = make_workspace_user(db, make_workspace(db), Role.ADMIN)

    response = await db_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": DEFAULT_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_origin_mismatch"


async def test_login_rotates_the_previous_session(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.ADMIN)
    old_token = sign_in(db_client, db, user.id, workspace.id)

    response = await _login(db_client, user.email)

    new_token = response.cookies[SESSION_COOKIE]
    assert new_token != old_token
    assert [s.token_hash for s in _sessions(db)] == [hash_token(new_token)]


# --- /me and session checks ---------------------------------------------------------------


async def test_me_returns_user_workspace_and_role(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.DEVELOPER)
    sign_in(db_client, db, user.id, workspace.id)

    response = await db_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == str(user.id)
    assert body["workspace"]["id"] == str(workspace.id)
    assert body["role"] == "developer"


@pytest.mark.parametrize("cookie", [None, "", "forged-token"])
async def test_me_without_a_valid_session_is_401(
    db_client: AsyncClient, cookie: str | None
) -> None:
    if cookie is not None:
        db_client.cookies.set(SESSION_COOKIE, cookie)

    response = await db_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    ("last_seen_ago", "expires_in"),
    [
        (IDLE_TIMEOUT + timedelta(minutes=1), timedelta(days=1)),  # idle-expired
        (timedelta(minutes=5), timedelta(seconds=-1)),  # absolute-expired
    ],
    ids=["idle", "absolute"],
)
async def test_an_expired_session_is_401_and_deleted(
    db_client: AsyncClient,
    db: Session,
    last_seen_ago: timedelta,
    expires_in: timedelta,
) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.ADMIN)
    sign_in(db_client, db, user.id, workspace.id)
    (session,) = _sessions(db)
    now = datetime.now(UTC)
    session.last_seen_at = now - last_seen_ago
    session.expires_at = now + expires_in
    db.flush()

    response = await db_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"
    assert _sessions(db) == []


async def test_activity_extends_the_idle_window(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.ADMIN)
    sign_in(db_client, db, user.id, workspace.id)
    (session,) = _sessions(db)
    session.last_seen_at = datetime.now(UTC) - timedelta(hours=11)
    db.flush()

    assert (await db_client.get("/api/v1/auth/me")).status_code == 200

    db.refresh(session)
    assert datetime.now(UTC) - session.last_seen_at < timedelta(minutes=1)


async def test_a_disabled_membership_ends_the_session(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_user(db)
    member = make_member(db, workspace, user, Role.ADMIN)
    sign_in(db_client, db, user.id, workspace.id)
    member.membership_status = "disabled"
    db.flush()

    response = await db_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert _sessions(db) == []


# --- Logout -------------------------------------------------------------------------------


async def test_logout_deletes_the_server_side_session(db_client: AsyncClient, db: Session) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.VIEWER)
    sign_in(db_client, db, user.id, workspace.id)

    response = await db_client.post("/api/v1/auth/logout", headers=ORIGIN)

    assert response.status_code == 204
    assert f'{SESSION_COOKIE}=""' in response.headers["set-cookie"]
    assert _sessions(db) == []
    actions = db.scalars(select(AuditLog.action).where(AuditLog.actor_id == user.id)).all()
    assert actions == ["auth.logout"]
    assert (await db_client.get("/api/v1/auth/me")).status_code == 401


async def test_logout_without_a_session_is_a_no_op(db_client: AsyncClient) -> None:
    response = await db_client.post("/api/v1/auth/logout", headers=ORIGIN)

    assert response.status_code == 204


async def test_sessions_are_tied_to_one_workspace(db_client: AsyncClient, db: Session) -> None:
    home, other = make_workspace(db), make_workspace(db)
    user = make_workspace_user(db, home, Role.ADMIN)
    make_member(db, other, user, Role.VIEWER)
    sign_in(db_client, db, user.id, other.id)

    body = (await db_client.get("/api/v1/auth/me")).json()

    assert body["workspace"]["id"] == str(other.id)
    assert body["role"] == "viewer"
    assert db.get(Workspace, home.id) is not None


async def test_logging_out_of_an_expired_session_writes_no_logout_entry(
    db_client: AsyncClient, db: Session
) -> None:
    workspace = make_workspace(db)
    user = make_workspace_user(db, workspace, Role.VIEWER)
    sign_in(db_client, db, user.id, workspace.id)
    (session,) = _sessions(db)
    session.last_seen_at = datetime.now(UTC) - IDLE_TIMEOUT - timedelta(minutes=1)
    db.flush()

    response = await db_client.post("/api/v1/auth/logout", headers=ORIGIN)

    assert response.status_code == 204
    assert _sessions(db) == []
    assert db.scalars(select(AuditLog).where(AuditLog.actor_id == user.id)).all() == []
