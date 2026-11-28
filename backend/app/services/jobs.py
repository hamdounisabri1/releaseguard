"""``enqueue``: how services hand work to the worker.

The job row is inserted in the caller's transaction and never committed here, so the state change
and the work it implies are committed together or not at all (ADR-0004).
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.jobs import DEFAULT_MAX_ATTEMPTS
from app.repositories import jobs as job_repository
from app.schemas.jobs import JobKind, JobPayload


def enqueue(
    db: Session,
    workspace_id: uuid.UUID,
    kind: JobKind,
    payload: JobPayload,
    *,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> uuid.UUID | None:
    """Add a pending job (due now unless ``run_after``). Returns its id, or ``None`` when a job
    with the same ``dedupe_key`` exists already (enqueueing is idempotent).

    A key stays taken while its job exists: done jobs for 7 days (retention), dead ones for
    good. So a key names one piece of work (``dispatch:<deployment_id>``); work that may be
    repeated needs a key per repetition.
    """
    return job_repository.add(
        db,
        workspace_id,
        kind=kind.value,
        payload=payload.model_dump(mode="json"),
        dedupe_key=dedupe_key,
        run_after=run_after,
        max_attempts=max_attempts,
    )
