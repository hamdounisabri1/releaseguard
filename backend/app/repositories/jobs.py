"""Enqueueing jobs inside the caller's transaction (the outbox, ADR-0004)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Job


def add(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    kind: str,
    payload: dict[str, Any],
    dedupe_key: str | None,
    run_after: datetime | None,
    max_attempts: int,
) -> uuid.UUID | None:
    """Insert a pending job; ``None`` when a job with the same ``dedupe_key`` already exists."""
    values: dict[str, Any] = {
        "workspace_id": workspace_id,
        "kind": kind,
        "payload": payload,
        "dedupe_key": dedupe_key,
        "max_attempts": max_attempts,
    }
    if run_after is not None:
        values["run_after"] = run_after
    statement = (
        insert(Job)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
        .returning(Job.id)
    )
    return db.scalar(statement)
