"""Login, logout and session resolution (server-side sessions, ADR-0007).

The cookie holds a random 256-bit token; the ``sessions`` table stores only its SHA-256, so a
database leak doesn't hand out live sessions. Sessions end after 12 h idle or 7 days, whichever
comes first, and every login issues a fresh token (the previous one, if sent, is deleted).

Logins are throttled (SCRUM-110) with counters in Postgres (``login_attempts``; v1 has no Redis):
at most N failures per (email, client IP) and M per client IP in a sliding window, checked
before the account is even looked up, so a 429 says nothing about whether the account exists.
"""

import hashlib
import ipaddress
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.logging import get_logger
from app.core.passwords import (
    burn_verification_time,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.core.permissions import Capability, Role, has_capability
from app.models import User, UserSession, Workspace, WorkspaceMember
from app.models.enums import UserStatus
from app.repositories import identity
from app.services.audit import Actor, AuditTarget, record_audit

SESSION_COOKIE = "rg_session"
IDLE_TIMEOUT = timedelta(hours=12)
ABSOLUTE_LIFETIME = timedelta(days=7)
# last_seen_at is written at most this often, so reads don't each cost a write.
LAST_SEEN_RESOLUTION = timedelta(minutes=1)
# Login attempts older than this are deleted on the login path (no worker sweep needed).
LOGIN_ATTEMPT_RETENTION = timedelta(hours=24)
# Failures strictly after a success count toward the (email, IP) cap.
_AFTER = timedelta(microseconds=1)

logger = get_logger(__name__)


class InvalidCredentialsError(UnauthorizedError):
    """The same error for an unknown email, a wrong password and a disabled account."""

    code = "invalid_credentials"
    message = "Invalid email or password."


class TooManyAttemptsError(TooManyRequestsError):
    """Identical for known and unknown emails; ``Retry-After`` says when to try again."""

    code = "too_many_attempts"
    message = "Too many failed sign-in attempts. Try again later."


class SessionExpiredError(UnauthorizedError):
    code = "session_expired"
    message = "Your session has expired. Sign in again."


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller: who, in which workspace, with which role."""

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    role: Role
    session_id: uuid.UUID

    @property
    def actor(self) -> Actor:
        return Actor.user(self.workspace_id, self.user_id)

    def can(self, capability: Capability) -> bool:
        return has_capability(self.role, capability)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    workspace: Workspace
    role: Role


@dataclass(frozen=True, slots=True)
class LoginResult:
    token: str
    current: CurrentUser


@dataclass(frozen=True, slots=True)
class LoginThrottle:
    max_failures_per_account: int = 5
    max_failures_per_ip: int = 30
    window: timedelta = timedelta(minutes=15)

    @classmethod
    def from_settings(cls, settings: Settings) -> "LoginThrottle":
        return cls(
            max_failures_per_account=settings.login_max_failures_per_account,
            max_failures_per_ip=settings.login_max_failures_per_ip,
            window=timedelta(seconds=settings.login_throttle_window_seconds),
        )


def client_key(host: str | None) -> str:
    """The throttling key for a client address: the IPv4 address, or an IPv6 /64.

    One IPv6 host usually controls a whole /64, so a per-address cap would be trivial to dodge.
    An address that doesn't parse (no socket peer) shares the ``unknown`` bucket.
    """
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return "unknown"
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _now() -> datetime:
    return datetime.now(UTC)


def create_session(
    db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID, *, now: datetime | None = None
) -> str:
    """Store a new session and return its token (only the hash is stored). Doesn't commit."""
    now = now or _now()
    token = secrets.token_urlsafe(32)
    identity.add_session(
        db,
        UserSession(
            token_hash=hash_token(token),
            user_id=user_id,
            workspace_id=workspace_id,
            last_seen_at=now,
            expires_at=now + ABSOLUTE_LIFETIME,
        ),
    )
    return token


def _retry_after(
    db: Session,
    *,
    client_ip: str,
    since: datetime,
    limit: int,
    count: int,
    now: datetime,
    window: timedelta,
    email: str | None = None,
) -> int | None:
    """Seconds until the count drops below ``limit`` again, or None while it's under it."""
    if count < limit:
        return None
    # Once the (count - limit)-th oldest failure leaves the window, limit - 1 remain.
    expiring = identity.nth_oldest_login_failure(
        db, client_ip=client_ip, since=since, n=count - limit, email=email
    )
    if expiring is None:  # pragma: no cover - rows vanished between the two queries
        return 1
    return max(1, math.ceil((expiring + window - now).total_seconds()))


def _check_throttle(
    db: Session, email: str, client_ip: str, throttle: LoginThrottle, now: datetime
) -> None:
    """Raise 429 when either cap is reached. Runs before the account lookup and argon2.

    A success resets the (email, IP) count by moving its start past the success, not by
    deleting rows: the failures still count toward the per-IP cap, so an attacker who owns one
    account can't refund their IP's budget by signing in to it.
    """
    since = now - throttle.window
    last_success = identity.last_login_success(db, email=email, client_ip=client_ip, since=since)
    account_since = max(since, last_success + _AFTER) if last_success else since
    per_account = identity.count_login_failures(
        db, client_ip=client_ip, since=account_since, email=email
    )
    per_ip = identity.count_login_failures(db, client_ip=client_ip, since=since)
    waits = {
        "account_limit": _retry_after(
            db,
            client_ip=client_ip,
            since=account_since,
            limit=throttle.max_failures_per_account,
            count=per_account,
            now=now,
            window=throttle.window,
            email=email,
        ),
        "ip_limit": _retry_after(
            db,
            client_ip=client_ip,
            since=since,
            limit=throttle.max_failures_per_ip,
            count=per_ip,
            now=now,
            window=throttle.window,
        ),
    }
    hit = {reason: wait for reason, wait in waits.items() if wait is not None}
    if hit:
        # The reason only: never the email (it may not be an account) or the password.
        logger.warning("login throttled", reason=",".join(sorted(hit)))
        raise TooManyAttemptsError(headers={"Retry-After": str(max(hit.values()))})


def _authenticate(
    db: Session, email: str, password: str
) -> tuple[User, WorkspaceMember, Workspace]:
    user = identity.get_user_by_email(db, email)
    if user is None:
        burn_verification_time(password)
        logger.info("login refused", reason="invalid_credentials")
        raise InvalidCredentialsError()
    if not verify_password(user.password_hash, password) or user.status != UserStatus.ACTIVE:
        logger.info("login refused", reason="invalid_credentials")
        raise InvalidCredentialsError()
    membership = identity.first_active_membership(db, user.id)
    workspace = identity.get_workspace(db, membership.workspace_id) if membership else None
    if membership is None or workspace is None:
        logger.info("login refused", reason="no_active_membership")
        raise InvalidCredentialsError()
    return user, membership, workspace


def login(
    db: Session,
    email: str,
    password: str,
    *,
    client_ip: str,
    throttle: LoginThrottle | None = None,
    previous_token: str | None = None,
    now: datetime | None = None,
) -> LoginResult:
    """Sign in, or raise 401 ``invalid_credentials`` / 429 ``too_many_attempts``.

    ``client_ip`` is a key from ``client_key``. Under parallel requests the check-then-insert
    can let a few extra attempts through before a cap bites; that's accepted rather than
    serializing logins behind a lock.
    """
    now = now or _now()
    throttle = throttle or LoginThrottle()
    email = email.strip().lower()  # LoginRequest already did this; kept for direct callers
    # Its own short transaction, so the deleted rows' locks aren't held through argon2.
    identity.purge_login_attempts(db, before=now - LOGIN_ATTEMPT_RETENTION)
    db.commit()
    _check_throttle(db, email, client_ip, throttle, now)
    try:
        user, membership, workspace = _authenticate(db, email, password)
    except InvalidCredentialsError:
        identity.add_login_attempt(db, email=email, client_ip=client_ip, succeeded=False, at=now)
        db.commit()
        raise

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    # Rotation: a login never reuses the session it arrived with.
    if previous_token:
        previous = identity.get_session_by_token_hash(db, hash_token(previous_token))
        if previous is not None:
            identity.delete_session(db, previous.id)
    # Recorded with the session: it restarts this (email, IP)'s failure count (see above).
    identity.add_login_attempt(db, email=email, client_ip=client_ip, succeeded=True, at=now)
    token = create_session(db, user.id, workspace.id, now=now)
    record_audit(db, Actor.user(workspace.id, user.id), "auth.login", AuditTarget("user", user.id))
    db.commit()
    return LoginResult(token, CurrentUser(user, workspace, Role(membership.role)))


def _expired(session: UserSession, now: datetime) -> bool:
    return now >= session.expires_at or now >= session.last_seen_at + IDLE_TIMEOUT


def logout(db: Session, token: str | None) -> None:
    """End the session behind ``token``, if there is one. Idempotent.

    An already-expired session is just deleted: it ended earlier, so no ``auth.logout`` entry.
    """
    if not token:
        return
    session = identity.get_session_by_token_hash(db, hash_token(token))
    if session is None:
        return
    identity.delete_session(db, session.id)
    if _expired(session, _now()):
        db.commit()
        return
    record_audit(
        db,
        Actor.user(session.workspace_id, session.user_id),
        "auth.logout",
        AuditTarget("user", session.user_id),
    )
    db.commit()


def resolve_session(db: Session, token: str, *, now: datetime | None = None) -> Principal:
    """The caller behind a session token, or 401. Deletes the session once it has expired."""
    now = now or _now()
    session = identity.get_session_by_token_hash(db, hash_token(token))
    if session is None:
        raise UnauthorizedError()
    if _expired(session, now):
        identity.delete_session(db, session.id)
        db.commit()
        raise SessionExpiredError()
    membership = identity.get_active_membership(db, session.workspace_id, session.user_id)
    if membership is None:  # user or membership disabled since login
        identity.delete_session(db, session.id)
        db.commit()
        raise UnauthorizedError()
    if now - session.last_seen_at >= LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return Principal(session.user_id, session.workspace_id, Role(membership.role), session.id)


def current_user(db: Session, principal: Principal) -> CurrentUser:
    user = identity.get_user(db, principal.user_id)
    workspace = identity.get_workspace(db, principal.workspace_id)
    if user is None or workspace is None:
        raise UnauthorizedError()
    return CurrentUser(user, workspace, principal.role)
