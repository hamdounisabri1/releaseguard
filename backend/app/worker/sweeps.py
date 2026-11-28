"""Periodic sweeps run by the worker loop (ADR-0004). Each one is idempotent.

Sprint 2 ships ``retention``; ``expire_approvals``, ``reconcile_runs`` and ``health_checks_due``
join as their Tasks land.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories import job_queue
from app.worker.runner import Sweep

logger = get_logger(__name__)

DONE_JOB_RETENTION = timedelta(days=7)


def retention(db: Session, now: datetime) -> None:
    """Delete ``done`` jobs older than 7 days (dead jobs stay for inspection)."""
    purged = job_queue.purge_done(db, before=now - DONE_JOB_RETENTION)
    if purged:
        logger.info("retention purged done jobs", count=purged)


def default_sweeps() -> list[Sweep]:
    return [Sweep("retention", timedelta(days=1), retention)]
