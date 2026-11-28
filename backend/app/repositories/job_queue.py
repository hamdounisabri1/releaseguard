"""The worker's side of the jobs table: claim, finish, retry, bury, purge (ADR-0004).

Not scoped to one workspace: the worker serves every workspace, and each job carries its own
``workspace_id``, which handlers pass to the scoped repositories. Only ``app.worker`` uses this
module (``tests/test_scoping.py`` lists the exemption).

Every write after the claim is conditional on ``attempts`` still matching the claimed attempt,
so a worker whose lease ran out (and whose job another worker took over) can't overwrite the
newer attempt's outcome.
"""

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus


def claim_next(db: Session, kinds: Collection[str], now: datetime) -> Job | None:
    """Lock the next due job of one of ``kinds`` (``FOR UPDATE SKIP LOCKED``): a pending job whose
    ``run_after`` has come, or a running one whose lease ran out (its worker crashed). Rows another
    transaction holds are skipped, so two workers never claim the same job. Nothing is changed:
    the caller starts or buries it, then commits.
    """
    if not kinds:
        return None
    due = or_(
        and_(Job.status == JobStatus.PENDING.value, Job.run_after <= now),
        and_(Job.status == JobStatus.RUNNING.value, Job.locked_until < now),
    )
    return db.scalar(
        select(Job)
        .where(Job.kind.in_(list(kinds)), due)
        .order_by(Job.run_after, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def start(db: Session, job: Job, *, locked_until: datetime) -> None:
    """Mark a claimed job running for one more attempt, leased until ``locked_until``."""
    job.status = JobStatus.RUNNING.value
    job.attempts += 1
    job.locked_until = locked_until
    db.flush()


def _owned(job_id: uuid.UUID, attempt: int) -> list[ColumnElement[bool]]:
    return [Job.id == job_id, Job.status == JobStatus.RUNNING.value, Job.attempts == attempt]


def finish(db: Session, job_id: uuid.UUID, attempt: int) -> bool:
    """``done``. False when the attempt no longer owns the job."""
    result = db.execute(
        update(Job)
        .where(*_owned(job_id, attempt))
        .values(status=JobStatus.DONE.value, locked_until=None, last_error=None)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


def retry(db: Session, job_id: uuid.UUID, attempt: int, *, run_after: datetime, error: str) -> bool:
    """Back to ``pending`` for a later attempt. False when the attempt no longer owns the job."""
    result = db.execute(
        update(Job)
        .where(*_owned(job_id, attempt))
        .values(
            status=JobStatus.PENDING.value, run_after=run_after, locked_until=None, last_error=error
        )
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


def bury(db: Session, job_id: uuid.UUID, attempt: int, *, error: str) -> bool:
    """``dead``: no more attempts. False when the attempt no longer owns the job."""
    result = db.execute(
        update(Job)
        .where(*_owned(job_id, attempt))
        .values(status=JobStatus.DEAD.value, locked_until=None, last_error=error)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


def purge_done(db: Session, *, before: datetime) -> int:
    """Delete ``done`` jobs last updated before ``before`` (retention). Dead jobs stay."""
    result = db.execute(
        delete(Job).where(Job.status == JobStatus.DONE.value, Job.updated_at < before)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
