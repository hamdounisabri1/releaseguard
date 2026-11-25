"""Users, workspaces, memberships and server-side sessions."""

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import Role
from app.db.base import Base, check_in
from app.models._columns import CreatedAt, Timestamp, UuidPk
from app.models.enums import MembershipStatus, UserStatus


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Emails are stored lowercased (no citext extension needed), so the unique key is
        # effectively case-insensitive.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        check_in("status", UserStatus),
    )

    id: Mapped[UuidPk]
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default=UserStatus.ACTIVE.value)
    created_at: Mapped[CreatedAt]


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UuidPk]
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(63), unique=True)
    # Workspace policy, e.g. {"block_self_approval": true}.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[CreatedAt]


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        check_in("role", Role),
        check_in("membership_status", MembershipStatus),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    membership_status: Mapped[str] = mapped_column(
        String(20), server_default=MembershipStatus.ACTIVE.value
    )
    joined_at: Mapped[CreatedAt]


class UserSession(Base):
    """A login. The cookie holds a random token; only its SHA-256 is stored (ADR-0007)."""

    __tablename__ = "sessions"
    __table_args__ = (
        # A session always belongs to a membership: removing the member ends their sessions.
        ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_sessions_user_id", "user_id"),
    )

    id: Mapped[UuidPk]
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    user_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    created_at: Mapped[CreatedAt]
    last_seen_at: Mapped[Timestamp]  # the idle timeout counts from here
    expires_at: Mapped[Timestamp]  # absolute expiry
