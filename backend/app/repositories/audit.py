"""Audit log rows: insert and read only (the table is append-only)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def add(db: Session, workspace_id: uuid.UUID, row: AuditLog) -> AuditLog:
    if row.workspace_id != workspace_id:
        raise ValueError("audit row belongs to another workspace")
    db.add(row)
    db.flush()
    return row


def list_for_target(
    db: Session, workspace_id: uuid.UUID, target_type: str, target_id: uuid.UUID
) -> Sequence[AuditLog]:
    statement = (
        select(AuditLog)
        .where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.target_type == target_type,
            AuditLog.target_id == target_id,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    return db.scalars(statement).all()
