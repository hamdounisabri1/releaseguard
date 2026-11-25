"""``record_audit``: the one way state-changing services write the audit trail.

It runs inside the caller's transaction (it flushes, never commits), so the audit row and the
change it describes are committed or rolled back together.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from pydantic_core import to_jsonable_python
from sqlalchemy.orm import Session

from app.core.logging import redact
from app.core.request_id import current_request_id
from app.models import AuditLog
from app.models.enums import ActorType
from app.repositories import audit as audit_repository


@dataclass(frozen=True, slots=True)
class Actor:
    """Who did it, and in which workspace."""

    workspace_id: uuid.UUID
    type: ActorType
    user_id: uuid.UUID | None = None

    @classmethod
    def user(cls, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Self:
        return cls(workspace_id=workspace_id, type=ActorType.USER, user_id=user_id)

    @classmethod
    def system(cls, workspace_id: uuid.UUID) -> Self:
        return cls(workspace_id=workspace_id, type=ActorType.SYSTEM)


@dataclass(frozen=True, slots=True)
class AuditTarget:
    """What it was done to: a type (``application``, ``environment``, …) and its id."""

    type: str
    id: uuid.UUID | None


def record_audit(
    db: Session,
    actor: Actor,
    action: str,
    target: AuditTarget,
    details: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Add one audit row: actor, ``action`` (``<area>.<verb>``, e.g. ``application.created``),
    target, details and the current request id. ``created_at`` is set by the database (UTC).

    Sensitive keys in ``details`` (passwords, tokens, cookies, …) are redacted.
    """
    row = AuditLog(
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        actor_type=actor.type.value,
        action=action,
        target_type=target.type,
        target_id=target.id,
        details_json=to_jsonable_python(redact(dict(details or {}))),
        request_id=current_request_id(),
    )
    return audit_repository.add(db, actor.workspace_id, row)
