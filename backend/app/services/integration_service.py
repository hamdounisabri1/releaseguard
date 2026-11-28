"""The GitHub App integration: link an installation to a workspace, verify it, disconnect it.

The install callback is **untrusted**: its ``installation_id`` comes from a browser redirect and
the API makes no outbound calls. So it only records a ``pending`` link and enqueues a job; the
worker asks GitHub whether the installation exists for our App and then marks it ``active`` or
``invalid``. Only ``active`` installations are used for dispatches.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.permissions import Capability
from app.models import Integration
from app.models.enums import LINKED_INTEGRATION_STATUSES, IntegrationProvider, IntegrationStatus
from app.models.integrations import INSTALLATION_LINKED, WORKSPACE_PROVIDER_LINKED
from app.repositories import integrations as integration_repository
from app.schemas.integrations import GitHubInstallCallback
from app.schemas.jobs import JobKind, VerifyInstallationPayload
from app.services.audit import Actor, AuditTarget, record_audit
from app.services.auth_service import Principal
from app.services.authz import ensure_can, found
from app.services.jobs import enqueue


class InstallationUnavailableError(ConflictError):
    """Deliberately vague: it doesn't say which workspace holds the installation."""

    code = "installation_unavailable"
    message = "This GitHub App installation can't be linked to this workspace."


class IntegrationExistsError(ConflictError):
    code = "integration_exists"
    message = "The workspace already has a GitHub installation. Disconnect it first."


@dataclass(frozen=True, slots=True)
class InstallationInfo:
    """What the worker learned from GitHub about an installation of our App."""

    account_login: str
    permissions: Mapping[str, str]


def _target(integration: Integration) -> AuditTarget:
    return AuditTarget("integration", integration.id)


def list_integrations(db: Session, principal: Principal) -> Sequence[Integration]:
    ensure_can(principal, Capability.MANAGE_GITHUB_INTEGRATION)
    return integration_repository.list_for_workspace(db, principal.workspace_id)


def connect_github(
    db: Session, principal: Principal, data: GitHubInstallCallback
) -> tuple[Integration, bool]:
    """Record the installation as ``pending`` and enqueue its verification. Returns the
    integration and whether it was created (``False``: this installation was already linked
    here, e.g. GitHub's ``setup_action=update`` redirect).
    """
    ensure_can(principal, Capability.MANAGE_GITHUB_INTEGRATION)
    workspace_id = principal.workspace_id
    linked = integration_repository.get_linked(db, workspace_id, IntegrationProvider.GITHUB)
    if linked is not None:
        if linked.installation_id == data.installation_id:
            return linked, False
        raise IntegrationExistsError()

    integration = Integration(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        provider=IntegrationProvider.GITHUB.value,
        installation_id=data.installation_id,
        status=IntegrationStatus.PENDING.value,
    )
    try:
        with db.begin_nested():
            integration_repository.add(db, workspace_id, integration)
    except IntegrityError as exc:
        if INSTALLATION_LINKED in str(exc.orig):
            raise InstallationUnavailableError() from None
        if WORKSPACE_PROVIDER_LINKED in str(exc.orig):  # a concurrent callback won
            raise IntegrationExistsError() from None
        raise
    enqueue(
        db,
        workspace_id,
        JobKind.VERIFY_GITHUB_INSTALLATION,
        VerifyInstallationPayload(integration_id=integration.id),
        dedupe_key=f"{JobKind.VERIFY_GITHUB_INSTALLATION}:{integration.id}",
    )
    record_audit(
        db,
        principal.actor,
        "integration.requested",
        _target(integration),
        {"provider": integration.provider, "installation_id": integration.installation_id},
    )
    db.commit()
    db.refresh(integration)
    return integration, True


def disconnect(db: Session, principal: Principal, integration_id: uuid.UUID) -> None:
    """Unlink the installation: the worker stops using it at once (``get_active_github``).
    Idempotent: an integration that is no longer linked is left as it is.
    """
    ensure_can(principal, Capability.MANAGE_GITHUB_INTEGRATION)
    integration = found(
        integration_repository.get_for_update(db, principal.workspace_id, integration_id)
    )
    if IntegrationStatus(integration.status) not in LINKED_INTEGRATION_STATUSES:
        return
    previous = integration.status
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.disconnected_at = datetime.now(UTC)
    record_audit(
        db,
        principal.actor,
        "integration.disconnected",
        _target(integration),
        {"installation_id": integration.installation_id, "from_status": previous},
    )
    db.commit()


def pending_installation_id(
    db: Session, workspace_id: uuid.UUID, integration_id: uuid.UUID
) -> int | None:
    """The installation to verify, or ``None`` when the integration is no longer pending
    (disconnected meanwhile, or verified by an earlier attempt).
    """
    integration = integration_repository.get(db, workspace_id, integration_id)
    if integration is None or integration.status != IntegrationStatus.PENDING.value:
        return None
    return integration.installation_id


def complete_verification(
    db: Session,
    workspace_id: uuid.UUID,
    integration_id: uuid.UUID,
    info: InstallationInfo | None,
    *,
    reason: str = "not_found",
) -> None:
    """Worker side: ``active`` with the account and permissions GitHub reported, or ``invalid``
    when GitHub doesn't know the installation (or never answered). Only a still-pending
    integration changes, so a disconnect in the meantime wins. The caller commits (the failure
    hook runs inside the worker's own transaction).
    """
    integration = integration_repository.get_for_update(db, workspace_id, integration_id)
    if integration is None or integration.status != IntegrationStatus.PENDING.value:
        return
    actor = Actor.system(workspace_id)
    details: dict[str, Any] = {"installation_id": integration.installation_id}
    if info is None:
        integration.status = IntegrationStatus.INVALID.value
        record_audit(
            db,
            actor,
            "integration.verification_failed",
            _target(integration),
            details | {"reason": reason},
        )
    else:
        integration.status = IntegrationStatus.ACTIVE.value
        integration.account_login = info.account_login
        integration.permissions_summary = dict(info.permissions)
        integration.connected_at = datetime.now(UTC)
        record_audit(
            db,
            actor,
            "integration.connected",
            _target(integration),
            details | {"account_login": info.account_login, "permissions": dict(info.permissions)},
        )
