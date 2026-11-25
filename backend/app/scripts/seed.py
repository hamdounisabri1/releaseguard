"""Seed local development data: ``uv run python -m app.scripts.seed``.

Creates one workspace (``acme``), one user per role and the TaskFlow application with its three
environments. Idempotent: anything that already exists is left as it is. Refuses to run with
``ENV=production``.

The users' password is ``SEED_PASSWORD`` (default ``releaseguard-dev``): non-production
credentials, documented in ``backend/README.md``.
"""

import os
import sys
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.passwords import hash_password
from app.core.permissions import Role
from app.db.session import create_db_engine, create_session_factory
from app.models import User, Workspace, WorkspaceMember
from app.repositories import applications as application_repository
from app.repositories import identity
from app.schemas.applications import ApplicationCreate
from app.services.application_service import provision_application
from app.services.audit import Actor, AuditTarget, record_audit

DEFAULT_SEED_PASSWORD = "releaseguard-dev"  # noqa: S105 (documented local-only credential)
WORKSPACE_SLUG = "acme"
WORKSPACE_NAME = "Acme"
USERS: list[tuple[Role, str, str]] = [
    (Role.ADMIN, "admin@example.com", "Ada Admin"),
    (Role.DEVELOPER, "developer@example.com", "Dev Developer"),
    (Role.REVIEWER, "reviewer@example.com", "Riley Reviewer"),
    (Role.VIEWER, "viewer@example.com", "Vic Viewer"),
]
TASKFLOW = ApplicationCreate(
    name="TaskFlow",
    description="Sample application deployed through ReleaseGuard.",
    repository_owner="hamdounisabri1",
    repository_name="taskflow",
    repository_id=1469892209,  # public GitHub repository id of hamdounisabri1/taskflow
)

logger = get_logger(__name__)


@dataclass
class SeedResult:
    created: list[str] = field(default_factory=list)


def seed(db: Session, password: str) -> SeedResult:
    """Create whatever is missing, then commit."""
    result = SeedResult()

    workspace = identity.get_workspace_by_slug(db, WORKSPACE_SLUG)
    if workspace is None:
        workspace = Workspace(
            name=WORKSPACE_NAME, slug=WORKSPACE_SLUG, settings={"block_self_approval": True}
        )
        identity.add(db, workspace)
        result.created.append(f"workspace {WORKSPACE_SLUG}")
    actor = Actor.system(workspace.id)

    password_hash: str | None = None
    for role, email, display_name in USERS:
        user = identity.get_user_by_email(db, email)
        if user is None:
            password_hash = password_hash or hash_password(password)
            user = User(email=email, display_name=display_name, password_hash=password_hash)
            identity.add(db, user)
            result.created.append(f"user {email}")
        if identity.get_membership(db, workspace.id, user.id) is None:
            identity.add(
                db, WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role.value)
            )
            result.created.append(f"membership {email} ({role.value})")

    if result.created:
        record_audit(
            db,
            actor,
            "workspace.seeded",
            AuditTarget("workspace", workspace.id),
            {"created": list(result.created)},
        )
    db.commit()

    owner, name = TASKFLOW.repository_owner, TASKFLOW.repository_name
    # Matched by name or by repository id, so a renamed TaskFlow still counts as seeded.
    existing = application_repository.get_by_repository(db, workspace.id, owner, name)
    if existing is None and TASKFLOW.repository_id is not None:
        existing = application_repository.get_by_repository_id(
            db, workspace.id, TASKFLOW.repository_id
        )
    if existing is None:
        provision_application(db, actor, TASKFLOW)  # audits and commits
        result.created.append(f"application {owner}/{name}")
    return result


def run(settings: Settings) -> int:
    if settings.env == "production":
        logger.error("seed refused", reason="ENV=production")
        return 1
    engine = create_db_engine(settings.database_url)
    try:
        with create_session_factory(engine)() as db:
            result = seed(db, os.environ.get("SEED_PASSWORD") or DEFAULT_SEED_PASSWORD)
    finally:
        engine.dispose()
    logger.info("seed finished", created=result.created or "nothing (already seeded)")
    return 0


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())
