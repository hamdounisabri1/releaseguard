"""The job runner and sweeps (SCRUM-41, ADR-0004), one iteration at a time with a controlled
clock. Most tests share the rolled-back test session; the concurrency tests need rows committed
for real (``SKIP LOCKED`` works across transactions) and clean up after themselves.
"""

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Job
from app.models.enums import JobStatus
from app.repositories import job_queue
from app.schemas.jobs import JobKind, VerifyInstallationPayload
from app.services.jobs import enqueue
from app.worker.runner import (
    LEASE_EXPIRED,
    ClaimedJob,
    JobContext,
    JobSpec,
    Sweep,
    Worker,
    WorkerConfig,
)
from app.worker.sweeps import retention
from tests.factories import make_workspace

KIND = JobKind.VERIFY_GITHUB_INSTALLATION
CONFIG = WorkerConfig(lease_seconds=60, backoff_base_seconds=5, backoff_max_seconds=600)


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC) + timedelta(seconds=1)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class Recorder:
    """A handler that records what it ran and fails while ``failures`` is positive."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.ran: list[ClaimedJob] = []
        self.dead: list[ClaimedJob] = []

    async def handler(self, context: JobContext) -> None:
        self.ran.append(context.job)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("upstream said: token ghs_secret123")

    def on_dead(self, db: Session, job: ClaimedJob) -> None:
        self.dead.append(job)

    def spec(self) -> JobSpec:
        return JobSpec(self.handler, self.on_dead)


def _worker(db: Session, recorder: Recorder, clock: Clock, **kinds: JobSpec) -> Worker:
    return Worker(
        session=lambda: nullcontext(db),
        jobs={KIND.value: recorder.spec(), **kinds},
        config=CONFIG,
        clock=clock,
    )


def _enqueue(db: Session, clock: Clock, *, max_attempts: int = 5, **kwargs: object) -> uuid.UUID:
    job_id = enqueue(
        db,
        make_workspace(db).id,
        KIND,
        VerifyInstallationPayload(integration_id=uuid.uuid4()),
        run_after=clock.now,
        max_attempts=max_attempts,
        **kwargs,  # type: ignore[arg-type]
    )
    assert job_id is not None
    db.commit()  # the API's transaction ends; the worker sees the job from here
    return job_id


def _job(db: Session, job_id: uuid.UUID) -> Job:
    db.expire_all()
    job = db.get(Job, job_id)
    assert job is not None
    return job


# --- Running jobs ---------------------------------------------------------------------------


async def test_a_job_enqueued_in_a_transaction_is_picked_up_and_run(db: Session) -> None:
    clock, recorder = Clock(), Recorder()
    job_id = _enqueue(db, clock)

    assert await _worker(db, recorder, clock).run_once() == 1

    job = _job(db, job_id)
    assert (job.status, job.attempts, job.locked_until) == (JobStatus.DONE.value, 1, None)
    assert [run.id for run in recorder.ran] == [job_id]
    assert recorder.ran[0].payload.keys() == {"integration_id"}


async def test_a_job_that_is_not_due_yet_waits(db: Session) -> None:
    clock, recorder = Clock(), Recorder()
    later = Clock()
    later.now = clock.now + timedelta(seconds=30)  # from the same base, not a second now()
    job_id = _enqueue(db, later)

    assert await _worker(db, recorder, clock).run_once() == 0
    clock.advance(30)
    assert await _worker(db, recorder, clock).run_once() == 1
    assert _job(db, job_id).status == JobStatus.DONE.value


async def test_a_kind_without_a_handler_is_never_claimed(db: Session) -> None:
    clock = Clock()
    job_id = _enqueue(db, clock)
    worker = Worker(session=lambda: nullcontext(db), jobs={}, config=CONFIG, clock=clock)

    assert await worker.run_once() == 0
    assert _job(db, job_id).status == JobStatus.PENDING.value


async def test_enqueue_is_idempotent_by_dedupe_key(db: Session) -> None:
    workspace = make_workspace(db)
    payload = VerifyInstallationPayload(integration_id=uuid.uuid4())

    first = enqueue(db, workspace.id, KIND, payload, dedupe_key="verify:1")
    second = enqueue(db, workspace.id, KIND, payload, dedupe_key="verify:1")

    assert first is not None and second is None
    count = db.scalar(select(text("count(*)")).select_from(Job).where(Job.dedupe_key == "verify:1"))
    assert count == 1


# --- Failures: backoff, dead, the failure hook ----------------------------------------------


async def test_a_job_that_keeps_failing_backs_off_and_ends_dead(db: Session) -> None:
    clock, recorder = Clock(), Recorder(failures=10)
    job_id = _enqueue(db, clock, max_attempts=3)
    worker = _worker(db, recorder, clock)

    assert await worker.run_once() == 1  # attempt 1 fails → retry in 5 s
    job = _job(db, job_id)
    assert (job.status, job.attempts) == (JobStatus.PENDING.value, 1)
    assert job.run_after == clock.now + timedelta(seconds=5)
    assert job.last_error == "RuntimeError"  # the class only, never the message

    clock.advance(4)
    assert await worker.run_once() == 0  # not due yet
    clock.advance(1)
    assert await worker.run_once() == 1  # attempt 2 fails → retry in 10 s
    assert _job(db, job_id).run_after == clock.now + timedelta(seconds=10)

    clock.advance(10)
    assert await worker.run_once() == 1  # attempt 3 fails → dead
    job = _job(db, job_id)
    assert (job.status, job.attempts, job.last_error) == (JobStatus.DEAD.value, 3, "RuntimeError")
    assert [dead.id for dead in recorder.dead] == [job_id]
    assert "secret" not in (job.last_error or "")

    clock.advance(3600)
    assert await worker.run_once() == 0  # dead jobs are never claimed again
    assert len(recorder.ran) == 3


async def test_a_job_that_recovers_on_retry_finishes(db: Session) -> None:
    clock, recorder = Clock(), Recorder(failures=1)
    job_id = _enqueue(db, clock)
    worker = _worker(db, recorder, clock)

    await worker.run_once()
    clock.advance(5)
    await worker.run_once()

    job = _job(db, job_id)
    assert (job.status, job.attempts, job.last_error) == (JobStatus.DONE.value, 2, None)
    assert recorder.dead == []


def test_backoff_doubles_and_is_capped() -> None:
    config = WorkerConfig(backoff_base_seconds=5, backoff_max_seconds=60)
    delays = [config.backoff(attempt).total_seconds() for attempt in range(1, 7)]
    assert delays == [5, 10, 20, 40, 60, 60]


async def test_a_handler_that_overruns_its_lease_is_stopped_and_retried(db: Session) -> None:
    clock = Clock()
    job_id = _enqueue(db, clock)

    async def hang(context: JobContext) -> None:
        await asyncio.sleep(10)

    worker = Worker(
        session=lambda: nullcontext(db),
        jobs={KIND.value: JobSpec(hang)},
        config=WorkerConfig(lease_seconds=0.05),
        clock=clock,
    )
    assert await worker.run_once() == 1

    job = _job(db, job_id)
    assert (job.status, job.last_error) == (JobStatus.PENDING.value, "TimeoutError")


# --- Crash recovery -------------------------------------------------------------------------


def _claim_and_crash(db: Session, clock: Clock) -> None:
    """A worker claims a job and dies before finishing it."""
    job = job_queue.claim_next(db, [KIND.value], clock.now)
    assert job is not None
    job_queue.start(db, job, locked_until=clock.now + timedelta(seconds=CONFIG.lease_seconds))
    db.commit()


async def test_a_job_whose_worker_crashed_runs_again_after_its_lease(db: Session) -> None:
    clock, recorder = Clock(), Recorder()
    job_id = _enqueue(db, clock)
    _claim_and_crash(db, clock)
    worker = _worker(db, recorder, clock)

    clock.advance(CONFIG.lease_seconds - 1)
    assert await worker.run_once() == 0  # still leased to the crashed worker
    clock.advance(2)
    assert await worker.run_once() == 1

    job = _job(db, job_id)
    assert (job.status, job.attempts) == (JobStatus.DONE.value, 2)


async def test_a_crash_on_the_last_attempt_buries_the_job(db: Session) -> None:
    clock, recorder = Clock(), Recorder()
    job_id = _enqueue(db, clock, max_attempts=1)
    _claim_and_crash(db, clock)

    clock.advance(CONFIG.lease_seconds + 1)
    assert await _worker(db, recorder, clock).run_once() == 0

    job = _job(db, job_id)
    assert (job.status, job.last_error) == (JobStatus.DEAD.value, LEASE_EXPIRED)
    assert [dead.id for dead in recorder.dead] == [job_id]
    assert recorder.ran == []


async def test_a_stale_attempt_cannot_overwrite_the_newer_one(db: Session) -> None:
    clock = Clock()
    job_id = _enqueue(db, clock)
    _claim_and_crash(db, clock)  # attempt 1
    clock.advance(CONFIG.lease_seconds + 1)
    _claim_and_crash(db, clock)  # attempt 2 took over

    assert job_queue.finish(db, job_id, attempt=1) is False
    assert job_queue.retry(db, job_id, 1, run_after=clock.now, error="X") is False
    assert job_queue.bury(db, job_id, 1, error="X") is False
    assert _job(db, job_id).status == JobStatus.RUNNING.value


# --- Sweeps ---------------------------------------------------------------------------------


async def test_retention_deletes_old_done_jobs_only(db: Session) -> None:
    clock = Clock()
    old_done, new_done, old_dead = (_enqueue(db, clock) for _ in range(3))
    db.execute(
        text(
            "UPDATE jobs SET status = 'done', updated_at = now() - interval '8 days' WHERE id = :id"
        ),
        {"id": old_done},
    )
    db.execute(text("UPDATE jobs SET status = 'done' WHERE id = :id"), {"id": new_done})
    db.execute(
        text(
            "UPDATE jobs SET status = 'dead', updated_at = now() - interval '30 days' "
            "WHERE id = :id"
        ),
        {"id": old_dead},
    )

    retention(db, datetime.now(UTC))

    db.expire_all()
    assert db.get(Job, old_done) is None
    assert db.get(Job, new_done) is not None
    assert db.get(Job, old_dead) is not None


async def test_sweeps_run_on_their_interval_and_a_failure_does_not_stop_the_others(
    db: Session,
) -> None:
    clock, calls = Clock(), []

    def broken(db: Session, now: datetime) -> None:
        raise ConnectionError("postgresql://user:hunter2@db")

    def counted(db: Session, now: datetime) -> None:
        calls.append(now)

    worker = Worker(
        session=lambda: nullcontext(db),
        jobs={},
        sweeps=[
            Sweep("broken", timedelta(seconds=60), broken),
            Sweep("counted", timedelta(seconds=60), counted),
        ],
        clock=clock,
    )

    assert await worker.run_sweeps() == ["counted"]
    clock.advance(59)
    assert await worker.run_sweeps() == []
    clock.advance(1)
    assert await worker.run_sweeps() == ["counted"]
    assert len(calls) == 2


async def test_run_forever_stops_when_asked(db: Session) -> None:
    stop = asyncio.Event()
    stop.set()
    worker = Worker(session=lambda: nullcontext(db), jobs={}, config=CONFIG)

    await asyncio.wait_for(worker.run_forever(stop), timeout=5)


# --- Concurrency: real, committed rows across connections -----------------------------------


@pytest.fixture
def committed(engine: Engine) -> Iterator[tuple[sessionmaker[Session], str]]:
    """A real session factory and a job kind unique to this test; its jobs are deleted after."""
    factory = sessionmaker(engine, expire_on_commit=False)
    kind = f"test.concurrency.{uuid.uuid4().hex}"
    try:
        yield factory, kind
    finally:
        with factory() as db:
            db.execute(delete(Job).where(Job.kind == kind))
            db.commit()


def _commit_jobs(factory: sessionmaker[Session], kind: str, count: int) -> set[uuid.UUID]:
    with factory() as db:
        jobs = [
            Job(kind=kind, run_after=datetime.now(UTC) - timedelta(seconds=1)) for _ in range(count)
        ]
        db.add_all(jobs)
        db.commit()
        return {job.id for job in jobs}


def test_skip_locked_hands_a_locked_job_to_nobody_else(
    committed: tuple[sessionmaker[Session], str],
) -> None:
    factory, kind = committed
    ids = _commit_jobs(factory, kind, 2)
    now = datetime.now(UTC)

    with factory() as first, factory() as second:
        held = job_queue.claim_next(first, [kind], now)  # row lock held until first commits
        other = job_queue.claim_next(second, [kind], now)  # skips the locked row
        assert held is not None and other is not None
        assert {held.id, other.id} == ids
        with factory() as late:
            assert job_queue.claim_next(late, [kind], now) is None  # both rows are locked
        first.rollback()
        second.rollback()


async def test_two_workers_never_run_the_same_job(
    committed: tuple[sessionmaker[Session], str],
) -> None:
    factory, kind = committed
    ids = _commit_jobs(factory, kind, 30)
    ran: list[uuid.UUID] = []

    async def handler(context: JobContext) -> None:
        ran.append(context.job.id)
        await asyncio.sleep(0)

    def worker() -> Worker:
        return Worker(session=factory, jobs={kind: JobSpec(handler)}, config=CONFIG)

    async def drain(w: Worker) -> None:
        while await w.run_once():
            pass

    await asyncio.gather(drain(worker()), drain(worker()))

    assert sorted(ran) == sorted(ids)  # every job ran, and none twice
    with factory() as db:
        statuses = db.scalars(select(Job.status).where(Job.kind == kind)).all()
    assert set(statuses) == {JobStatus.DONE.value}
