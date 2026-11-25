"""Applications, always scoped to one workspace."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application
from app.models.enums import ApplicationStatus


def add(db: Session, workspace_id: uuid.UUID, application: Application) -> Application:
    if application.workspace_id != workspace_id:
        raise ValueError("application belongs to another workspace")
    db.add(application)
    db.flush()
    return application


def get(db: Session, workspace_id: uuid.UUID, application_id: uuid.UUID) -> Application | None:
    return db.scalar(
        select(Application).where(
            Application.workspace_id == workspace_id, Application.id == application_id
        )
    )


def get_by_repository(
    db: Session, workspace_id: uuid.UUID, owner: str, name: str
) -> Application | None:
    return db.scalar(
        select(Application).where(
            Application.workspace_id == workspace_id,
            func.lower(Application.repository_owner) == owner.lower(),
            func.lower(Application.repository_name) == name.lower(),
        )
    )


def list_page(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    include_archived: bool,
    offset: int,
    limit: int,
) -> tuple[Sequence[Application], int]:
    """One page, newest first, plus the total count."""
    condition = Application.workspace_id == workspace_id
    if not include_archived:
        condition = condition & (Application.status == ApplicationStatus.ACTIVE.value)
    total = db.scalar(select(func.count()).select_from(Application).where(condition)) or 0
    items = db.scalars(
        select(Application)
        .where(condition)
        .order_by(Application.created_at.desc(), Application.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return items, total
