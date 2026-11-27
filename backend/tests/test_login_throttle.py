"""Login throttling (SCRUM-110): per (email, IP) and per IP caps, stored in Postgres."""

import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.permissions import Role
from app.main import create_app
from app.models import AuditLog, LoginAttempt
from app.repositories import identity
from app.services.auth_service import client_key
from tests.conftest import SITE_ORIGIN, build_app
from tests.factories import DEFAULT_PASSWORD, make_workspace, make_workspace_user

ORIGIN = {"Origin": SITE_ORIGIN}
USER_IP = "203.0.113.10"
ATTACKER_IP = "198.51.100.66"
WRONG = "not-the-password"


def _client(db: Session, *, peer: str = USER_IP, **overrides: Any) -> AsyncClient:
    """A client whose socket peer is ``peer``, on an app built with ``overrides``."""
    app = build_app(**overrides)
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app, raise_app_exceptions=False, client=(peer, 50_000))
    return AsyncClient(transport=transport, base_url=SITE_ORIGIN)


async def _login(
    client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD, **headers: str
) -> Response:
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={**ORIGIN, **headers},
    )


async def _fail(client: AsyncClient, email: str, times: int) -> None:
    for _ in range(times):
        assert (await _login(client, email, WRONG)).status_code == 401


def _attempts(db: Session) -> list[LoginAttempt]:
    return list(db.scalars(select(LoginAttempt).order_by(LoginAttempt.created_at)).all())


def _user_email(db: Session) -> str:
    return make_workspace_user(db, make_workspace(db), Role.DEVELOPER).email


def _assert_throttled(response: Response) -> int:
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_attempts"
    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= 900
    return retry_after


# --- Per (email, IP) ----------------------------------------------------------------------


async def test_the_sixth_failure_is_throttled_even_with_the_right_password(db: Session) -> None:
    email = _user_email(db)
    async with _client(db) as client:
        await _fail(client, email, 5)

        response = await _login(client, email)  # correct password

    _assert_throttled(response)
    assert "rg_session" not in response.cookies
    # A refused attempt isn't recorded, so hammering doesn't push the unlock time further out.
    assert len(_attempts(db)) == 5


async def test_an_unknown_email_is_throttled_exactly_like_a_known_one(db: Session) -> None:
    known = _user_email(db)
    async with _client(db) as client:
        await _fail(client, known, 5)
        await _fail(client, "nobody@example.com", 5)
        for_known = await _login(client, known, WRONG)
        for_unknown = await _login(client, "nobody@example.com", WRONG)

    _assert_throttled(for_known)
    _assert_throttled(for_unknown)
    assert for_known.json() == for_unknown.json()


async def test_emails_are_normalized_before_counting(db: Session) -> None:
    email = _user_email(db)
    async with _client(db) as client:
        await _fail(client, email.upper(), 3)
        await _fail(client, f"  {email}  ", 2)

        _assert_throttled(await _login(client, email))


async def test_a_successful_login_resets_the_count_for_that_email_and_ip(db: Session) -> None:
    email = _user_email(db)
    async with _client(db) as client:
        await _fail(client, email, 4)
        assert (await _login(client, email)).status_code == 200

        await _fail(client, email, 5)  # a fresh budget of five
        _assert_throttled(await _login(client, email))


async def test_a_successful_login_does_not_refund_the_per_ip_budget(db: Session) -> None:
    own = _user_email(db)  # the attacker's own account, at the attacker's IP
    async with _client(db, peer=ATTACKER_IP, login_max_failures_per_ip=5) as attacker:
        await _fail(attacker, own, 2)
        await _fail(attacker, "victim@example.com", 2)
        assert (await _login(attacker, own)).status_code == 200
        await _fail(attacker, "victim@example.com", 1)  # 5 failures from this IP

        _assert_throttled(await _login(attacker, "victim@example.com", WRONG))


async def test_an_email_that_grows_when_lowercased_is_refused_without_a_500(
    db: Session,
) -> None:
    # "İ" lowercases to two code points: 254 of them pass a raw length check but not storage.
    async with _client(db) as client:
        response = await _login(client, "İ" * 254, WRONG)

    assert response.status_code == 422
    assert "İ" not in response.text
    assert _attempts(db) == []


async def test_failures_from_another_ip_dont_lock_the_user_out(db: Session) -> None:
    email = _user_email(db)
    async with _client(db, peer=ATTACKER_IP) as attacker:
        await _fail(attacker, email, 5)
        _assert_throttled(await _login(attacker, email))

    async with _client(db, peer=USER_IP) as user:
        assert (await _login(user, email)).status_code == 200


async def test_retry_after_counts_from_the_oldest_failure_in_the_window(db: Session) -> None:
    email = _user_email(db)
    ten_minutes_ago = datetime.now(UTC) - timedelta(minutes=10)
    for _ in range(5):
        identity.add_login_attempt(
            db, email=email, client_ip=USER_IP, succeeded=False, at=ten_minutes_ago
        )
    async with _client(db) as client:
        retry_after = _assert_throttled(await _login(client, email))

    assert 290 <= retry_after <= 300  # the window is 15 min, the failures 10 min old


async def test_failures_outside_the_window_are_not_counted(db: Session) -> None:
    email = _user_email(db)
    sixteen_minutes_ago = datetime.now(UTC) - timedelta(minutes=16)
    for _ in range(5):
        identity.add_login_attempt(
            db, email=email, client_ip=USER_IP, succeeded=False, at=sixteen_minutes_ago
        )
    async with _client(db) as client:
        assert (await _login(client, email)).status_code == 200


async def test_attempts_older_than_a_day_are_purged_on_login(db: Session) -> None:
    identity.add_login_attempt(
        db,
        email="old@example.com",
        client_ip=ATTACKER_IP,
        succeeded=False,
        at=datetime.now(UTC) - timedelta(hours=25),
    )
    async with _client(db) as client:
        await _login(client, "someone@example.com", WRONG)

    assert [a.email for a in _attempts(db)] == ["someone@example.com"]


# --- Per IP -------------------------------------------------------------------------------


async def test_the_per_ip_cap_applies_across_many_emails(db: Session) -> None:
    async with _client(db, peer=ATTACKER_IP, login_max_failures_per_ip=3) as attacker:
        for n in range(3):
            await _fail(attacker, f"victim-{n}@example.com", 1)

        _assert_throttled(await _login(attacker, "victim-99@example.com", WRONG))

    async with _client(db, peer=USER_IP, login_max_failures_per_ip=3) as other:
        assert (await _login(other, "victim-99@example.com", WRONG)).status_code == 401


async def test_when_both_caps_are_hit_retry_after_is_the_longer_wait(db: Session) -> None:
    email = _user_email(db)
    now = datetime.now(UTC)
    # Per IP: failures 2 min old (13 min left). Per account: failures 10 min old (5 min left).
    for n in range(3):
        identity.add_login_attempt(
            db,
            email=f"other-{n}@example.com",
            client_ip=USER_IP,
            succeeded=False,
            at=now - timedelta(minutes=2),
        )
    for _ in range(2):
        identity.add_login_attempt(
            db, email=email, client_ip=USER_IP, succeeded=False, at=now - timedelta(minutes=10)
        )
    # 5 IP failures over a cap of 3: it frees up when the 3rd oldest (2 min old) expires.
    async with _client(db, login_max_failures_per_account=2, login_max_failures_per_ip=3) as c:
        retry_after = _assert_throttled(await _login(c, email))

    assert 770 <= retry_after <= 780  # the per-IP wait, not the per-account one (~300)


async def test_a_throttled_attempt_writes_no_audit_entry(db: Session) -> None:
    email = _user_email(db)
    async with _client(db, login_max_failures_per_account=1) as client:
        await _fail(client, email, 1)
        _assert_throttled(await _login(client, email))

    assert db.scalars(select(AuditLog).where(AuditLog.action == "auth.login")).first() is None


# --- Client IP ----------------------------------------------------------------------------


async def test_a_spoofed_forwarded_for_from_an_untrusted_peer_is_ignored(db: Session) -> None:
    email = _user_email(db)
    async with _client(db, peer=ATTACKER_IP, trusted_proxies=["10.0.0.0/8"]) as attacker:
        for n in range(5):
            response = await _login(attacker, email, WRONG, **{"X-Forwarded-For": f"192.0.2.{n}"})
            assert response.status_code == 401

        throttled = await _login(attacker, email, **{"X-Forwarded-For": "192.0.2.200"})

    _assert_throttled(throttled)
    assert {a.client_ip for a in _attempts(db)} == {ATTACKER_IP}


async def test_forwarded_for_without_any_trusted_proxy_is_ignored(db: Session) -> None:
    async with _client(db, peer="127.0.0.1") as client:
        await _login(client, "someone@example.com", WRONG, **{"X-Forwarded-For": "192.0.2.7"})

    assert [a.client_ip for a in _attempts(db)] == ["127.0.0.1"]


async def test_the_trusted_proxy_supplies_the_client_ip(db: Session) -> None:
    async with _client(db, peer="10.0.0.2", trusted_proxies=["10.0.0.0/8"]) as proxy:
        await _login(proxy, "someone@example.com", WRONG, **{"X-Forwarded-For": "192.0.2.7"})

    assert [a.client_ip for a in _attempts(db)] == ["192.0.2.7"]


async def test_a_client_supplied_forwarded_for_entry_before_the_real_one_is_ignored(
    db: Session,
) -> None:
    # Caddy appends the real client after whatever the client sent; the rightmost untrusted
    # address is the one that counts.
    async with _client(db, peer="10.0.0.2", trusted_proxies=["10.0.0.0/8"]) as proxy:
        await _login(
            proxy, "someone@example.com", WRONG, **{"X-Forwarded-For": "192.0.2.99, 192.0.2.7"}
        )

    assert [a.client_ip for a in _attempts(db)] == ["192.0.2.7"]


@pytest.mark.parametrize(("proxies", "warned"), [([], True), (["172.18.0.0/16"], False)])
def test_production_without_trusted_proxies_logs_a_warning(
    capfd: pytest.CaptureFixture[str], proxies: list[str], warned: bool
) -> None:
    create_app(
        Settings(
            _env_file=None,
            env="production",
            site_origin="https://rg.example.com",
            database_url="postgresql+psycopg://u@127.0.0.1/x",
            trusted_proxies=proxies,
        )
    )

    assert ("TRUSTED_PROXIES is empty in production" in capfd.readouterr().err) is warned


@pytest.mark.parametrize(
    ("host", "key"),
    [
        ("192.0.2.7", "192.0.2.7"),
        ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
        ("2001:db8:1:2:bbbb::9", "2001:db8:1:2::/64"),
        ("::ffff:192.0.2.7", "192.0.2.7"),
        (None, "unknown"),
        ("not-an-ip", "unknown"),
    ],
)
def test_client_key_buckets_ipv6_by_slash_64(host: str | None, key: str) -> None:
    assert client_key(host) == key


# --- What is stored and logged ------------------------------------------------------------


def test_the_attempts_table_has_no_password_column(db: Session) -> None:
    columns = {column["name"] for column in inspect(db.get_bind()).get_columns("login_attempts")}

    assert columns == {"id", "email", "client_ip", "succeeded", "created_at"}


async def test_throttled_attempts_are_logged_without_email_or_password(db: Session) -> None:
    email = _user_email(db)
    async with _client(db, login_max_failures_per_account=1) as client:
        stream = io.StringIO()
        configure_logging("INFO", stream=stream)  # after the app configured it
        await _fail(client, email, 1)
        _assert_throttled(await _login(client, email))

    output = stream.getvalue()
    lines = [json.loads(line) for line in output.splitlines() if line.strip()]
    throttled = [line for line in lines if line.get("event") == "login throttled"]
    assert [line["reason"] for line in throttled] == ["account_limit"]
    assert email not in output
    assert DEFAULT_PASSWORD not in output
    assert WRONG not in output
