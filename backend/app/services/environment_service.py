"""Environments: read, and update health-check timing and policy (Admin only)."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import UnprocessableError
from app.core.permissions import Capability
from app.models import Environment
from app.models.enums import ApplicationStatus
from app.repositories import applications as application_repository
from app.repositories import environments as environment_repository
from app.schemas.environments import EnvironmentPolicy, EnvironmentUpdate
from app.services.application_service import ApplicationArchivedError
from app.services.audit import AuditTarget, record_audit
from app.services.auth_service import Principal
from app.services.authz import ensure_can, found


class InvalidPolicyError(UnprocessableError):
    code = "invalid_policy"


def list_environments(
    db: Session, principal: Principal, application_id: uuid.UUID
) -> Sequence[Environment]:
    ensure_can(principal, Capability.VIEW)
    found(application_repository.get(db, principal.workspace_id, application_id))
    return environment_repository.list_for_application(db, principal.workspace_id, application_id)


def get_environment(db: Session, principal: Principal, environment_id: uuid.UUID) -> Environment:
    ensure_can(principal, Capability.VIEW)
    return found(environment_repository.get(db, principal.workspace_id, environment_id))


def _check_promotion(
    environment: Environment, policy: EnvironmentPolicy, siblings: Sequence[Environment]
) -> None:
    """``promote_from`` must name another environment of the same application, without a cycle."""
    source_id = policy.promote_from_environment_id
    if source_id is None:
        return
    by_id = {sibling.id: sibling for sibling in siblings}
    if source_id == environment.id or source_id not in by_id:
        raise InvalidPolicyError(
            "promote_from_environment_id must be another environment of this application."
        )
    seen = {environment.id}
    current: uuid.UUID | None = source_id
    while current is not None:
        if current in seen:
            raise InvalidPolicyError("promote_from_environment_id would create a promotion cycle.")
        seen.add(current)
        current = EnvironmentPolicy.model_validate(
            by_id[current].policy
        ).promote_from_environment_id


def update_environment(
    db: Session, principal: Principal, environment_id: uuid.UUID, data: EnvironmentUpdate
) -> Environment:
    ensure_can(principal, Capability.CONFIGURE_ENVIRONMENTS)
    environment = found(environment_repository.get(db, principal.workspace_id, environment_id))
    application = found(
        application_repository.get(db, principal.workspace_id, environment.application_id)
    )
    if application.status == ApplicationStatus.ARCHIVED:
        raise ApplicationArchivedError()

    changes: dict[str, dict[str, Any]] = {}
    for field, value in data.model_dump(exclude_unset=True, exclude={"policy"}).items():
        if value is not None and getattr(environment, field) != value:
            changes[field] = {"from": getattr(environment, field), "to": value}

    if data.policy is not None:
        current = EnvironmentPolicy.model_validate(environment.policy)
        merged = EnvironmentPolicy.model_validate(
            {**current.model_dump(), **data.policy.model_dump(exclude_unset=True)}
        )
        siblings = environment_repository.list_for_application(
            db, principal.workspace_id, environment.application_id
        )
        _check_promotion(environment, merged, siblings)
        old, new = current.model_dump(mode="json"), merged.model_dump(mode="json")
        policy_changes = {k: {"from": old[k], "to": new[k]} for k in new if old[k] != new[k]}
        if policy_changes:
            changes["policy"] = policy_changes
            environment.policy = new

    if not changes:
        return environment
    for field, change in changes.items():
        if field != "policy":
            setattr(environment, field, change["to"])
    record_audit(
        db,
        principal.actor,
        "environment.updated",
        AuditTarget("environment", environment.id),
        {"changes": changes},
    )
    db.commit()
    return environment
