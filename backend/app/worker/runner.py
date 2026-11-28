"""The worker loop (ADR-0004): claim due jobs, run their handlers, retry with backoff, bury the
ones that keep failing, and run the periodic sweeps, all in one async loop.

Database work runs in threads (``asyncio.to_thread``; DB access is synchronous) and is committed
before any handler starts, so no transaction stays open across a handler's HTTP calls. Handlers
open their own short transactions through ``JobContext.session``.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import Job
from app.models.enums import JobStatus
from app.repositories import job_queue

logger = get_logger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]
Clock = Callable[[], datetime]

# Stored in last_error when a worker died mid-attempt and the lease ran out on the last one.
LEASE_EXPIRED = "LeaseExpired"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    """A detached copy of a claimed job: safe to use after its session closed."""

    id: uuid.UUID
    kind: str
    workspace_id: uuid.UUID | None
    payload: Mapping[str, Any]
    attempt: int
    max_attempts: int

    @classmethod
    def of(cls, job: Job) -> "ClaimedJob":
        return cls(
            id=job.id,
            kind=job.kind,
            workspace_id=job.workspace_id,
            payload=dict(job.payload),
            attempt=job.attempts,
            max_attempts=job.max_attempts,
        )


@dataclass(frozen=True, slots=True)
class JobContext:
    job: ClaimedJob
    session: SessionFactory
    now: datetime


Handler = Callable[[JobContext], Awaitable[None]]
# Runs in the transaction that marks the job dead (in a savepoint), e.g. dispatch: queued →
# failed. It must not commit. If it raises, the job is still dead and the error is logged.
DeadHook = Callable[[Session, ClaimedJob], None]


@dataclass(frozen=True, slots=True)
class JobSpec:
    """A job kind's handler and failure hook.

    Handlers must be idempotent and **tolerate overlap**: the lease timeout cancels the
    coroutine, but work already handed to a thread keeps running while the retry may start.
    Before a side effect (a dispatch), re-check the state under a row lock in a fresh
    transaction.
    """

    handler: Handler
    on_dead: DeadHook | None = None


@dataclass(frozen=True, slots=True)
class Sweep:
    """Periodic, idempotent work run in the loop, in its own committed transaction."""

    name: str
    interval: timedelta
    run: Callable[[Session, datetime], None]


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    poll_interval_seconds: float = 1.0
    lease_seconds: float = 300
    backoff_base_seconds: int = 5
    backoff_max_seconds: int = 600
    # Jobs run per iteration before the sweeps get their turn.
    batch_size: int = 10

    @classmethod
    def from_settings(cls, settings: Settings) -> "WorkerConfig":
        return cls(
            poll_interval_seconds=settings.worker_poll_interval_seconds,
            lease_seconds=settings.worker_job_lease_seconds,
            backoff_base_seconds=settings.worker_backoff_base_seconds,
            backoff_max_seconds=settings.worker_backoff_max_seconds,
        )

    def backoff(self, attempt: int) -> timedelta:
        """Delay after failed attempt ``attempt`` (1-based): base, 2·base, 4·base, … capped."""
        seconds = self.backoff_base_seconds * 2 ** max(attempt - 1, 0)
        return timedelta(seconds=min(seconds, self.backoff_max_seconds))


def error_name(exc: BaseException) -> str:
    """What ``last_error`` and the logs keep of a failure: its class, never its message (which
    can carry a token, a URL with credentials or a response body).
    """
    return type(exc).__name__[:200]


@dataclass
class Worker:
    session: SessionFactory
    jobs: Mapping[str, JobSpec]
    sweeps: Sequence[Sweep] = ()
    config: WorkerConfig = field(default_factory=WorkerConfig)
    clock: Clock = utc_now
    _next_sweep: dict[str, datetime] = field(default_factory=dict, init=False)

    # --- jobs -------------------------------------------------------------------------------

    async def run_once(self) -> int:
        """Run up to ``batch_size`` due jobs, one after another. Returns how many ran."""
        ran = 0
        while ran < self.config.batch_size:
            claimed = await asyncio.to_thread(self._claim, self.clock())
            if claimed is None:
                break
            await self._run(claimed)
            ran += 1
        return ran

    def _claim(self, now: datetime) -> ClaimedJob | None:
        with self.session() as db:
            while True:
                job = job_queue.claim_next(db, self.jobs.keys(), now)
                if job is None:
                    db.commit()
                    return None
                if job.status == JobStatus.RUNNING.value and job.attempts >= job.max_attempts:
                    # Its worker died during the last attempt: no attempt is left to retry with.
                    claimed = ClaimedJob.of(job)
                    self._bury(db, claimed, LEASE_EXPIRED)
                    db.commit()
                    continue
                job_queue.start(
                    db, job, locked_until=now + timedelta(seconds=self.config.lease_seconds)
                )
                claimed = ClaimedJob.of(job)
                db.commit()
                return claimed

    async def _run(self, job: ClaimedJob) -> None:
        spec = self.jobs[job.kind]
        with structlog.contextvars.bound_contextvars(
            job_id=str(job.id),
            job_kind=job.kind,
            workspace_id=str(job.workspace_id) if job.workspace_id else None,
        ):
            logger.info("job started", attempt=job.attempt, max_attempts=job.max_attempts)
            try:
                # Stop before the lease runs out, so no other worker takes the job over while
                # this attempt is still running.
                async with asyncio.timeout(self.config.lease_seconds * 0.9):
                    await spec.handler(JobContext(job=job, session=self.session, now=self.clock()))
            except Exception as exc:  # any handler failure is retried, then buried
                await asyncio.to_thread(self._failed, job, error_name(exc))
                return
            await asyncio.to_thread(self._finished, job)

    def _finished(self, job: ClaimedJob) -> None:
        with self.session() as db:
            owned = job_queue.finish(db, job.id, job.attempt)
            db.commit()
        if owned:
            logger.info("job finished", attempt=job.attempt)
        else:
            logger.warning("job lease lost before it finished", attempt=job.attempt)

    def _failed(self, job: ClaimedJob, error: str) -> None:
        with self.session() as db:
            if job.attempt >= job.max_attempts:
                self._bury(db, job, error)
            else:
                run_after = self.clock() + self.config.backoff(job.attempt)
                if job_queue.retry(db, job.id, job.attempt, run_after=run_after, error=error):
                    logger.warning(
                        "job failed, will retry",
                        attempt=job.attempt,
                        error=error,
                        run_after=run_after.isoformat(),
                    )
            db.commit()

    def _bury(self, db: Session, job: ClaimedJob, error: str) -> None:
        """Mark the job dead and run its failure hook, in the caller's transaction."""
        if not job_queue.bury(db, job.id, job.attempt, error=error):
            return
        logger.error(
            "job dead", job_id=str(job.id), job_kind=job.kind, attempt=job.attempt, error=error
        )
        spec = self.jobs.get(job.kind)
        if spec is None or spec.on_dead is None:
            return
        # In a savepoint, so a failing hook rolls back only its own writes: the job still ends
        # dead. Otherwise it would stay `running`, be re-claimed after its lease, fail again,
        # and stall the loop (and the sweeps behind it) for good.
        try:
            with db.begin_nested():
                spec.on_dead(db, job)
        except Exception as exc:  # logged; the job stays dead for inspection
            logger.error("job failure hook failed", job_id=str(job.id), error=error_name(exc))

    # --- sweeps -----------------------------------------------------------------------------

    async def run_sweeps(self) -> list[str]:
        """Run every sweep that is due; one failing sweep doesn't stop the others. Returns the
        names that ran.
        """
        now = self.clock()
        ran = []
        for sweep in self.sweeps:
            if self._next_sweep.get(sweep.name, now) > now:
                continue
            self._next_sweep[sweep.name] = now + sweep.interval
            try:
                await asyncio.to_thread(self._sweep, sweep, now)
            except Exception as exc:  # logged; the sweep runs again next interval
                logger.error("sweep failed", sweep=sweep.name, error=error_name(exc))
                continue
            ran.append(sweep.name)
        return ran

    def _sweep(self, sweep: Sweep, now: datetime) -> None:
        with self.session() as db:
            sweep.run(db, now)
            db.commit()

    # --- the loop ---------------------------------------------------------------------------

    async def run_forever(self, stop: asyncio.Event) -> None:
        logger.info("worker started", kinds=sorted(self.jobs), sweeps=[s.name for s in self.sweeps])
        while not stop.is_set():
            try:
                ran = await self.run_once()
                await self.run_sweeps()
            except Exception as exc:  # e.g. the database is down: wait, then try again
                logger.error("worker iteration failed", error=error_name(exc))
                ran = 0
            if ran == 0:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self.config.poll_interval_seconds)
        logger.info("worker stopped")
