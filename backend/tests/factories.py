"""Plain builders for test data. Each one adds rows to the given session and flushes."""

import uuid
from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.core.permissions import Role
from app.models import Application, Environment, User, Workspace, WorkspaceMember
from app.models.enums import EnvironmentType

DEFAULT_PASSWORD = "correct horse battery staple"  # noqa: S105 (test fixture)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def make_workspace(db: Session, *, slug: str | None = None) -> Workspace:
    slug = slug or f"ws-{_suffix()}"
    workspace = Workspace(name=slug.title(), slug=slug)
    db.add(workspace)
    db.flush()
    return workspace


@lru_cache(maxsize=1)
def default_password_hash() -> str:
    """argon2id is slow on purpose; hash the shared test password once per run."""
    return hash_password(DEFAULT_PASSWORD)


def make_user(db: Session, *, email: str | None = None, status: str = "active") -> User:
    user = User(
        email=email or f"user-{_suffix()}@example.com",
        display_name="Test User",
        password_hash=default_password_hash(),
        status=status,
    )
    db.add(user)
    db.flush()
    return user


def make_member(db: Session, workspace: Workspace, user: User, role: Role) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role.value)
    db.add(member)
    db.flush()
    return member


def make_workspace_user(db: Session, workspace: Workspace, role: Role) -> User:
    """A user with an active membership in ``workspace``."""
    user = make_user(db)
    make_member(db, workspace, user, role)
    return user


def make_application(db: Session, workspace: Workspace, *, name: str = "TaskFlow") -> Application:
    application = Application(
        workspace_id=workspace.id,
        name=name,
        repository_owner="octo",
        repository_name=f"repo-{_suffix()}",
    )
    db.add(application)
    db.flush()
    return application


def make_environment(
    db: Session,
    application: Application,
    environment_type: EnvironmentType = EnvironmentType.DEVELOPMENT,
) -> Environment:
    environment = Environment(
        workspace_id=application.workspace_id,
        application_id=application.id,
        environment_type=environment_type.value,
    )
    db.add(environment)
    db.flush()
    return environment
