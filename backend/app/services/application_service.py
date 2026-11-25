"""Applications: create (with their three environments), read, update and archive."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnprocessableError
from app.core.permissions import Capability
from app.models import Application, Environment
from app.models.enums import ApplicationStatus, EnvironmentType
from app.repositories import applications as application_repository
from app.repositories import environments as environment_repository
from app.schemas.applications import ApplicationCreate, ApplicationUpdate
from app.schemas.environments import EnvironmentPolicy
from app.services.audit import Actor, AuditTarget, record_audit
from app.services.auth_service import Principal
from app.services.authz import ensure_can, found

# Partial unique index: one *active* application per repository id in a workspace, so archiving
# an application frees its repository for a new one.
_REPOSITORY_ID_TAKEN = "uq_applications_active_repository_id"


class RepositoryAlreadyRegisteredError(ConflictError):
    code = "repository_already_registered"
    message = "Another application in this workspace already uses this repository."


class RepositoryIdRequiredError(UnprocessableError):
    code = "repository_id_required"
    message = "Changing the repository also needs repository_id: the new repository's id, or null."


class ApplicationArchivedError(ConflictError):
    code = "application_archived"
    message = "The application is archived and can't be changed."


def default_environments(application: Application) -> list[Environment]:
    """Development auto-deploys; staging promotes from development; production needs one
    approval and promotes from staging (guide §4.4).
    """
    ids = {t: uuid.uuid4() for t in EnvironmentType}
    policies = {
        EnvironmentType.DEVELOPMENT: EnvironmentPolicy(auto_deploy_on_release=True),
        EnvironmentType.STAGING: EnvironmentPolicy(
            promote_from_environment_id=ids[EnvironmentType.DEVELOPMENT]
        ),
        EnvironmentType.PRODUCTION: EnvironmentPolicy(
            requires_approval=True,
            min_approvals=1,
            promote_from_environment_id=ids[EnvironmentType.STAGING],
        ),
    }
    return [
        Environment(
            id=ids[t],
            workspace_id=application.workspace_id,
            application_id=application.id,
            environment_type=t.value,
            policy=policies[t].model_dump(mode="json"),
        )
        for t in EnvironmentType
    ]


def _insert_or_conflict(db: Session, workspace_id: uuid.UUID, application: Application) -> None:
    try:
        with db.begin_nested():
            application_repository.add(db, workspace_id, application)
    except IntegrityError as exc:
        if _REPOSITORY_ID_TAKEN in str(exc.orig):
            raise RepositoryAlreadyRegisteredError() from None
        raise


def provision_application(db: Session, actor: Actor, data: ApplicationCreate) -> Application:
    """Create the application and its three environments, audited and committed.

    No permission check: for trusted callers (the seed script); requests go through
    ``create_application``.
    """
    application = Application(id=uuid.uuid4(), workspace_id=actor.workspace_id, **data.model_dump())
    _insert_or_conflict(db, actor.workspace_id, application)
    environments = environment_repository.add_all(
        db, actor.workspace_id, default_environments(application)
    )
    record_audit(
        db,
        actor,
        "application.created",
        AuditTarget("application", application.id),
        {
            "name": application.name,
            "repository": f"{application.repository_owner}/{application.repository_name}",
            "environments": {env.environment_type: env.id for env in environments},
        },
    )
    db.commit()
    return application


def create_application(db: Session, principal: Principal, data: ApplicationCreate) -> Application:
    ensure_can(principal, Capability.MANAGE_APPLICATIONS)
    return provision_application(db, principal.actor, data)


def list_applications(
    db: Session, principal: Principal, *, include_archived: bool, page: int, page_size: int
) -> tuple[Sequence[Application], int]:
    ensure_can(principal, Capability.VIEW)
    return application_repository.list_page(
        db,
        principal.workspace_id,
        include_archived=include_archived,
        offset=(page - 1) * page_size,
        limit=page_size,
    )


def get_application(db: Session, principal: Principal, application_id: uuid.UUID) -> Application:
    ensure_can(principal, Capability.VIEW)
    return found(application_repository.get(db, principal.workspace_id, application_id))


def _check_repository_binding(application: Application, data: ApplicationUpdate) -> None:
    """``repository_id`` binds CI OIDC tokens to the app (ADR-0006). Pointing the app at another
    repository without restating the id would leave the old repository's CI trusted.
    """
    moved = any(
        field in data.model_fields_set
        and str(getattr(data, field)).lower() != str(getattr(application, field)).lower()
        for field in ("repository_owner", "repository_name")
    )
    if (
        moved
        and application.repository_id is not None
        and "repository_id" not in data.model_fields_set
    ):
        raise RepositoryIdRequiredError()


def update_application(
    db: Session, principal: Principal, application_id: uuid.UUID, data: ApplicationUpdate
) -> Application:
    ensure_can(principal, Capability.MANAGE_APPLICATIONS)
    application = found(application_repository.get(db, principal.workspace_id, application_id))
    if application.status == ApplicationStatus.ARCHIVED:
        raise ApplicationArchivedError()

    changes: dict[str, dict[str, Any]] = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if getattr(application, field) != value:
            changes[field] = {"from": getattr(application, field), "to": value}
    if not changes:
        return application
    _check_repository_binding(application, data)

    try:
        with db.begin_nested():
            for field, change in changes.items():
                setattr(application, field, change["to"])
            db.flush()
    except IntegrityError as exc:
        if _REPOSITORY_ID_TAKEN in str(exc.orig):
            raise RepositoryAlreadyRegisteredError() from None
        raise
    record_audit(
        db,
        principal.actor,
        "application.updated",
        AuditTarget("application", application.id),
        {"changes": changes},
    )
    db.commit()
    db.refresh(application)  # updated_at is set by the database
    return application


def archive_application(
    db: Session, principal: Principal, application_id: uuid.UUID
) -> Application:
    """Hide the application from lists; its environments and history stay. Idempotent."""
    ensure_can(principal, Capability.MANAGE_APPLICATIONS)
    application = found(application_repository.get(db, principal.workspace_id, application_id))
    if application.status == ApplicationStatus.ARCHIVED:
        return application
    application.status = ApplicationStatus.ARCHIVED.value
    application.archived_at = datetime.now(UTC)
    record_audit(
        db, principal.actor, "application.archived", AuditTarget("application", application.id)
    )
    db.commit()
    db.refresh(application)
    return application
