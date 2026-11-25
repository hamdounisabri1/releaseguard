"""Users, memberships and sessions, for authentication.

Not workspace-scoped on purpose: these lookups run *before* the caller's workspace is known
(login, resolving a session cookie). Exempt from the scoping rule in ``tests/test_scoping.py``.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import User, UserSession, Workspace, WorkspaceMember
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
