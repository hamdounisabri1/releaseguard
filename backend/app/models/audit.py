"""The append-only audit log. A database trigger refuses UPDATE, DELETE and TRUNCATE."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in
from app.models._columns import CreatedAt, UuidPk
from app.models.enums import ActorType


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        check_in("actor_type", ActorType),
        # A user actor always names the user; system and CI actors never do.
        CheckConstraint("(actor_type = 'user') = (actor_id IS NOT NULL)", name="actor_id"),
        Index(
            "ix_audit_logs_target",
            "workspace_id",
            "target_type",
            "target_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[uuid.UUID | None]
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[CreatedAt]
