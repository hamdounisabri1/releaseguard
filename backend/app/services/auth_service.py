"""Login, logout and session resolution (server-side sessions, ADR-0007).

The cookie holds a random 256-bit token; the ``sessions`` table stores only its SHA-256, so a
database leak doesn't hand out live sessions. Sessions end after 12 h idle or 7 days, whichever
comes first, and every login issues a fresh token (the previous one, if sent, is deleted).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.logging import get_logger
from app.core.passwords import (
    burn_verification_time,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.core.permissions import Capability, Role, has_capability
from app.models import User, UserSession, Workspace
from app.models.enums import UserStatus
from app.repositories import identity
from app.services.audit import Actor, AuditTarget, record_audit

SESSION_COOKIE = "rg_session"
IDLE_TIMEOUT = timedelta(hours=12)
ABSOLUTE_LIFETIME = timedelta(days=7)
# last_seen_at is written at most this often, so reads don't each cost a write.
LAST_SEEN_RESOLUTION = timedelta(minutes=1)

logger = get_logger(__name__)


class InvalidCredentialsError(UnauthorizedError):
    """The same error for an unknown email, a wrong password and a disabled account."""

    code = "invalid_credentials"
    message = "Invalid email or password."


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


def login(
    db: Session, email: str, password: str, *, previous_token: str | None = None
) -> LoginResult:
    user = identity.get_user_by_email(db, email.strip().lower())
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

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    # Rotation: a login never reuses the session it arrived with.
    if previous_token:
        previous = identity.get_session_by_token_hash(db, hash_token(previous_token))
        if previous is not None:
            identity.delete_session(db, previous.id)
    token = create_session(db, user.id, workspace.id)
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
