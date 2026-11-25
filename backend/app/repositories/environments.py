"""Environments, always scoped to one workspace."""

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import Environment
from app.models.enums import EnvironmentType

# Development, then staging, then production (the promotion order).
_PROMOTION_ORDER = case(
    {t.value: i for i, t in enumerate(EnvironmentType)}, value=Environment.environment_type
)


def add_all(
    db: Session, workspace_id: uuid.UUID, environments: Iterable[Environment]
) -> list[Environment]:
    rows = list(environments)
    if any(row.workspace_id != workspace_id for row in rows):
        raise ValueError("environment belongs to another workspace")
    db.add_all(rows)
    db.flush()
    return rows


def get(db: Session, workspace_id: uuid.UUID, environment_id: uuid.UUID) -> Environment | None:
    return db.scalar(
        select(Environment).where(
            Environment.workspace_id == workspace_id, Environment.id == environment_id
        )
    )


def list_for_application(
    db: Session, workspace_id: uuid.UUID, application_id: uuid.UUID
) -> Sequence[Environment]:
    return db.scalars(
        select(Environment)
        .where(
            Environment.workspace_id == workspace_id,
            Environment.application_id == application_id,
        )
        .order_by(_PROMOTION_ORDER)
    ).all()
