"""The seed script: idempotent, users can log in, refuses production."""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Application, Environment, User, Workspace, WorkspaceMember
from app.scripts.seed import USERS, WORKSPACE_SLUG, run, seed
from tests.conftest import SITE_ORIGIN

PASSWORD = "seed-test-password"  # noqa: S105 (test fixture)


def _counts(db: Session) -> dict[str, int]:
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
        for model in (Workspace, User, WorkspaceMember, Application, Environment)
    }


def test_seed_creates_a_workspace_four_users_and_taskflow(db: Session) -> None:
    result = seed(db, PASSWORD)

    workspace = db.scalar(select(Workspace).where(Workspace.slug == WORKSPACE_SLUG))
    assert workspace is not None
    roles = dict(
        db.execute(
            select(User.email, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == workspace.id)
        ).all()
    )
    assert roles == {email: role.value for role, email, _ in USERS}
    (app,) = db.scalars(select(Application).where(Application.workspace_id == workspace.id))
    assert (app.repository_owner, app.repository_name) == ("hamdounisabri1", "taskflow")
    assert db.scalar(select(func.count()).where(Environment.application_id == app.id)) == 3
    assert "application hamdounisabri1/taskflow" in result.created


def test_running_the_seed_twice_creates_no_duplicates(db: Session) -> None:
    seed(db, PASSWORD)
    after_first = _counts(db)

    second = seed(db, PASSWORD)

    assert second.created == []
    assert _counts(db) == after_first


async def test_seeded_users_can_log_in(db_client: AsyncClient, db: Session) -> None:
    seed(db, PASSWORD)

    for role, email, _ in USERS:
        response = await db_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": PASSWORD},
            headers={"Origin": SITE_ORIGIN},
        )
        assert response.status_code == 200, email
        assert response.json()["role"] == role.value


def test_seed_refuses_production() -> None:
    settings = Settings(
        _env_file=None,
        env="production",
        site_origin="https://rg.example.com",
        database_url="postgresql+psycopg://nobody@127.0.0.1:1/none",
    )

    assert run(settings) == 1


def test_a_renamed_taskflow_still_counts_as_seeded(db: Session) -> None:
    seed(db, PASSWORD)
    app = db.scalar(select(Application).where(Application.repository_name == "taskflow"))
    assert app is not None
    app.repository_name = "taskflow-renamed"
    db.commit()

    result = seed(db, PASSWORD)

    assert result.created == []
    assert db.scalar(select(func.count()).select_from(Application)) == 1
