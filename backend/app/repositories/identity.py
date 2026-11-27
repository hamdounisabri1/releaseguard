"""Users, memberships and sessions, for authentication.

Not workspace-scoped on purpose: these lookups run *before* the caller's workspace is known
(login, resolving a session cookie). Exempt from the scoping rule in ``tests/test_scoping.py``.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import LoginAttempt, User, UserSession, Workspace, WorkspaceMember
from app.models.enums import MembershipStatus, UserStatus


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_workspace(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return db.get(Workspace, workspace_id)


def get_workspace_by_slug(db: Session, slug: str) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == slug))


def add(db: Session, row: User | Workspace | WorkspaceMember) -> None:
    """Insert a user, workspace or membership (used by the seed; member management is S6)."""
    db.add(row)
    db.flush()


def get_membership(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return db.get(WorkspaceMember, (workspace_id, user_id))


def first_active_membership(db: Session, user_id: uuid.UUID) -> WorkspaceMember | None:
    """The workspace a login lands in. v1 has one workspace per user; the oldest one wins."""
    statement = (
        select(WorkspaceMember)
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.membership_status == MembershipStatus.ACTIVE.value,
        )
        .order_by(WorkspaceMember.joined_at, WorkspaceMember.workspace_id)
        .limit(1)
    )
    return db.scalar(statement)


def get_active_membership(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    """The membership, only while both it and its user are active."""
    statement = (
        select(WorkspaceMember)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.membership_status == MembershipStatus.ACTIVE.value,
            User.status == UserStatus.ACTIVE.value,
        )
    )
    return db.scalar(statement)


def add_session(db: Session, session: UserSession) -> UserSession:
    db.add(session)
    db.flush()
    return session


def get_session_by_token_hash(db: Session, token_hash: bytes) -> UserSession | None:
    return db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


def delete_session(db: Session, session_id: uuid.UUID) -> None:
    db.execute(delete(UserSession).where(UserSession.id == session_id))


# --- Login attempts (throttling, SCRUM-110) ------------------------------------------------


def add_login_attempt(
    db: Session, *, email: str, client_ip: str, succeeded: bool, at: datetime
) -> None:
    db.add(LoginAttempt(email=email, client_ip=client_ip, succeeded=succeeded, created_at=at))
    db.flush()


def count_login_failures(
    db: Session, *, client_ip: str, since: datetime, email: str | None = None
) -> int:
    """Failures from ``client_ip`` since ``since``; for one email only when ``email`` is given."""
    statement = select(func.count()).where(*_failure_filter(client_ip, since, email))
    return db.scalar(statement) or 0


def nth_oldest_login_failure(
    db: Session, *, client_ip: str, since: datetime, n: int, email: str | None = None
) -> datetime | None:
    """The time of the ``n``-th oldest failure (0-based) in the same set as the count above."""
    statement = (
        select(LoginAttempt.created_at)
        .where(*_failure_filter(client_ip, since, email))
        .order_by(LoginAttempt.created_at)
        .offset(n)
        .limit(1)
    )
    return db.scalar(statement)


def _failure_filter(client_ip: str, since: datetime, email: str | None) -> list[Any]:
    conditions: list[Any] = [
        LoginAttempt.client_ip == client_ip,
        LoginAttempt.succeeded.is_(False),
        LoginAttempt.created_at >= since,
    ]
    if email is not None:
        conditions.append(LoginAttempt.email == email)
    return conditions


def last_login_success(
    db: Session, *, email: str, client_ip: str, since: datetime
) -> datetime | None:
    """The latest successful login for (email, client IP) since ``since``, if any."""
    statement = select(func.max(LoginAttempt.created_at)).where(
        LoginAttempt.email == email,
        LoginAttempt.client_ip == client_ip,
        LoginAttempt.succeeded.is_(True),
        LoginAttempt.created_at >= since,
    )
    return db.scalar(statement)


def purge_login_attempts(db: Session, *, before: datetime) -> None:
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < before))
