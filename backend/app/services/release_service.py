"""Release registration: from CI with a GitHub OIDC token (ADR-0006), or manually.

CI binding: the verified token's ``repository_id`` must name exactly one active application, its
``workflow_ref`` must be that application's CI workflow on the default branch or a tag, and the
body's commit SHA and run id must equal the token's ``sha`` and ``run_id``. Any mismatch is a
403 and nothing is written. CI registration is idempotent per ``(application, version)``: the
same digest and SHA again return the existing release; anything else is a 409.
"""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError
from app.core.logging import get_logger
from app.core.oidc import GitHubOidcClaims
from app.core.permissions import Capability
from app.models import Application, Release
from app.models.enums import ApplicationStatus, ReleaseSource
from app.repositories import applications as application_repository
from app.repositories import ci_identity
from app.repositories import releases as release_repository
from app.schemas.releases import ReleaseCiCreate, ReleaseCreate
from app.services.application_service import ApplicationArchivedError
from app.services.audit import Actor, AuditTarget, record_audit
from app.services.auth_service import Principal
from app.services.authz import ensure_can, found

logger = get_logger(__name__)

_VERSION_TAKEN = "uq_releases_application_id_version"


class OidcBindingError(ForbiddenError):
    """One message for every binding failure: the reason is logged, not returned."""

    code = "oidc_binding_mismatch"
    message = "The token doesn't match a registered application's CI workflow and commit."


class RepositoryAmbiguousError(ConflictError):
    code = "repository_ambiguous"
    message = "More than one application is bound to this repository; register manually."


class ReleaseVersionConflictError(ConflictError):
    code = "release_version_exists"
    message = "This version is already registered for the application with another build."


def _refuse(reason: str, claims: GitHubOidcClaims) -> OidcBindingError:
    logger.warning(
        "ci release refused",
        reason=reason,
        repository_id=claims.repository_id,
        run_id=claims.run_id,
    )
    return OidcBindingError()


def _bound_application(db: Session, claims: GitHubOidcClaims, body: ReleaseCiCreate) -> Application:
    applications = ci_identity.find_active_applications_by_repository_id(db, claims.repository_id)
    if not applications:
        raise _refuse("unknown_repository", claims)
    if len(applications) > 1:
        logger.warning("ci release refused", reason="ambiguous_repository")
        raise RepositoryAmbiguousError()
    application = applications[0]

    # `<owner>/<repo>/<path>@<ref>`; the repository part comes from the token itself (it is bound
    # by repository_id, and survives a repository rename).
    prefix = f"{claims.repository}/{application.ci_workflow_path}@"
    if not claims.workflow_ref.startswith(prefix):
        raise _refuse("workflow_mismatch", claims)
    ref = claims.workflow_ref.removeprefix(prefix)
    if ref != f"refs/heads/{application.default_branch}" and not ref.startswith("refs/tags/"):
        raise _refuse("ref_not_allowed", claims)
    if body.commit_sha != claims.sha:
        raise _refuse("sha_mismatch", claims)
    if body.workflow_run_id != claims.run_id:
        raise _refuse("run_id_mismatch", claims)
    return application


def _insert(db: Session, release: Release) -> Release | None:
    """The new release, or ``None`` when its version is already registered for the app."""
    try:
        with db.begin_nested():
            return release_repository.add(db, release.workspace_id, release)
    except IntegrityError as exc:
        if _VERSION_TAKEN in str(exc.orig):
            return None
        raise


def _audit_details(release: Release) -> dict[str, Any]:
    return {
        "version": release.version,
        "image_digest": release.image_digest,
        "commit_sha": release.commit_sha,
        "source": release.source,
    }


def register_ci_release(
    db: Session, claims: GitHubOidcClaims, body: ReleaseCiCreate
) -> tuple[Release, bool]:
    """Register (or replay) a release from CI. Returns it and whether it was created."""
    application = _bound_application(db, claims, body)
    workspace_id = application.workspace_id
    release = Release(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        application_id=application.id,
        source=ReleaseSource.CI.value,
        workflow_url=f"https://github.com/{claims.repository}/actions/runs/{claims.run_id}",
        created_by=None,
        **body.model_dump(),
    )
    created = _insert(db, release)
    if created is None:
        existing = release_repository.get_by_version(db, workspace_id, application.id, body.version)
        if (
            existing is not None
            and existing.image_digest == body.image_digest
            and existing.commit_sha == body.commit_sha
        ):
            return existing, False  # a CI retry of the same build: nothing to write
        raise ReleaseVersionConflictError()
    record_audit(
        db,
        Actor.ci(workspace_id),
        "release.registered",
        AuditTarget("release", created.id),
        _audit_details(created)
        | {
            "workflow_run_id": claims.run_id,
            "workflow_ref": claims.workflow_ref,
            "github_actor": claims.actor,
        },
    )
    db.commit()
    db.refresh(created)
    return created, True


def register_manual_release(db: Session, principal: Principal, body: ReleaseCreate) -> Release:
    """Admin/Developer fallback (cut list #7): same identity rules, no OIDC. 409 on any
    duplicate version.
    """
    ensure_can(principal, Capability.REGISTER_RELEASES)
    application = found(application_repository.get(db, principal.workspace_id, body.application_id))
    if application.status == ApplicationStatus.ARCHIVED.value:
        raise ApplicationArchivedError()
    release = Release(
        id=uuid.uuid4(),
        workspace_id=principal.workspace_id,
        source=ReleaseSource.MANUAL.value,
        created_by=principal.user_id,
        **body.model_dump(),
    )
    created = _insert(db, release)
    if created is None:
        raise ReleaseVersionConflictError()
    record_audit(
        db,
        principal.actor,
        "release.registered",
        AuditTarget("release", created.id),
        _audit_details(created),
    )
    db.commit()
    db.refresh(created)
    return created
