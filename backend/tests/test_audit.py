"""record_audit: one row per call, redacted details, and it shares the caller's transaction."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import REDACTED
from app.models import AuditLog
from app.repositories import audit as audit_repository
from app.services.audit import Actor, AuditTarget, record_audit
from tests.factories import make_user, make_workspace


def test_record_audit_writes_one_row_with_actor_target_details_and_request_id(
    db: Session,
) -> None:
    workspace, user = make_workspace(db), make_user(db)
    target_id = uuid.uuid4()
    structlog.contextvars.bind_contextvars(request_id="req-audit-1")
    try:
        record_audit(
            db,
            Actor.user(workspace.id, user.id),
            "application.created",
            AuditTarget("application", target_id),
            {"name": "TaskFlow", "environments": [uuid.UUID(int=1)]},
        )
    finally:
        structlog.contextvars.clear_contextvars()

    (row,) = audit_repository.list_for_target(db, workspace.id, "application", target_id)
    assert row.actor_id == user.id
    assert row.actor_type == "user"
    assert row.action == "application.created"
    assert row.details_json == {
        "name": "TaskFlow",
        "environments": ["00000000-0000-0000-0000-000000000001"],
    }
    assert row.request_id == "req-audit-1"
    db.refresh(row)
    assert row.created_at.utcoffset() == timedelta(0)
    assert abs(row.created_at - datetime.now(UTC)) < timedelta(minutes=5)


def test_system_actor_has_no_user(db: Session) -> None:
    workspace = make_workspace(db)

    row = record_audit(db, Actor.system(workspace.id), "seed.ran", AuditTarget("workspace", None))

    assert row.actor_type == "system"
    assert row.actor_id is None


def test_record_audit_redacts_secrets_in_details(db: Session) -> None:
    workspace = make_workspace(db)

    row = record_audit(
        db,
        Actor.system(workspace.id),
        "auth.login",
        AuditTarget("workspace", workspace.id),
        {"password": "hunter2", "nested": {"session_token": "tok"}, "cookie": "rg=1", "ok": 1},
    )

    assert row.details_json == {
        "password": REDACTED,
        "nested": {"session_token": REDACTED},
        "cookie": REDACTED,
        "ok": 1,
    }


def test_no_audit_row_remains_when_the_callers_transaction_rolls_back(db: Session) -> None:
    workspace = make_workspace(db)
    db.commit()  # the workspace survives; only the next unit of work is rolled back

    record_audit(db, Actor.system(workspace.id), "x.changed", AuditTarget("workspace", None))
    db.rollback()

    count = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.workspace_id == workspace.id)
    )
    assert count == 0
