"""The ``jobs`` table: outbox, retry queue and scheduler in one (ADR-0004)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in
from app.models._columns import CreatedAt, Timestamp, UuidPk
from app.models.enums import JobStatus

DEFAULT_MAX_ATTEMPTS = 5


class Job(Base):
    """One unit of worker work. Inserted in the caller's transaction (the outbox), claimed with
    ``FOR UPDATE SKIP LOCKED``, retried with backoff and ``dead`` after ``max_attempts``.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        check_in("status", JobStatus),
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint("max_attempts >= 1", name="max_attempts"),
        # NULLs never collide: jobs without a dedupe key are never de-duplicated.
        Index("uq_jobs_dedupe_key", "dedupe_key", unique=True),
        # Due pending jobs, and running jobs whose lease ran out (a crashed worker).
        Index(
            "ix_jobs_pending_run_after", "run_after", postgresql_where=text("status = 'pending'")
        ),
        Index(
            "ix_jobs_running_locked_until",
            "locked_until",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[UuidPk]
    # NULL only for work that belongs to no workspace.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    kind: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), server_default=JobStatus.PENDING.value)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(server_default=text(str(DEFAULT_MAX_ATTEMPTS)))
    locked_until: Mapped[Timestamp | None]
    # The exception class of the last failure, never its message (it can carry tokens or URLs).
    last_error: Mapped[str | None] = mapped_column(String(200))
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
