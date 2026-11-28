"""GitHub App installations linked to a workspace, always scoped to one workspace."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Integration
from app.models.enums import LINKED_INTEGRATION_STATUSES, IntegrationProvider, IntegrationStatus

_LINKED = [status.value for status in LINKED_INTEGRATION_STATUSES]


def add(db: Session, workspace_id: uuid.UUID, integration: Integration) -> Integration:
    if integration.workspace_id != workspace_id:
        raise ValueError("integration belongs to another workspace")
    db.add(integration)
    db.flush()
    return integration


def get(db: Session, workspace_id: uuid.UUID, integration_id: uuid.UUID) -> Integration | None:
    return db.scalar(
        select(Integration).where(
            Integration.workspace_id == workspace_id, Integration.id == integration_id
        )
    )


def get_for_update(
    db: Session, workspace_id: uuid.UUID, integration_id: uuid.UUID
) -> Integration | None:
    """Like ``get``, holding a row lock until the transaction ends."""
    return db.scalar(
        select(Integration)
        .where(Integration.workspace_id == workspace_id, Integration.id == integration_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def list_for_workspace(db: Session, workspace_id: uuid.UUID) -> Sequence[Integration]:
    """Every integration, newest first (disconnected and invalid ones too: they are history)."""
    return db.scalars(
        select(Integration)
        .where(Integration.workspace_id == workspace_id)
        .order_by(Integration.created_at.desc(), Integration.id)
    ).all()


def get_linked(
    db: Session, workspace_id: uuid.UUID, provider: IntegrationProvider
) -> Integration | None:
    """The workspace's pending or active integration for ``provider`` (at most one, by index)."""
    return db.scalar(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == provider.value,
            Integration.status.in_(_LINKED),
        )
    )


def get_active_github(db: Session, workspace_id: uuid.UUID) -> Integration | None:
    """The installation the worker may use for this workspace's GitHub calls (dispatch, runs).
    ``None`` once it is disconnected (or before it is verified), which stops dispatches.
    """
    return db.scalar(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == IntegrationProvider.GITHUB.value,
            Integration.status == IntegrationStatus.ACTIVE.value,
        )
    )
