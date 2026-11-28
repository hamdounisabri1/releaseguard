"""Schema integration tests against real Postgres: migrations, tenancy FKs, append-only audit."""

import io

import pytest
from alembic import command
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.models import AuditLog, Environment
from app.models.enums import ActorType, EnvironmentType
from tests.conftest import alembic_config, build_app, client_for
from tests.factories import make_application, make_environment, make_user, make_workspace

TABLES = {
    "users",
    "workspaces",
    "workspace_members",
    "sessions",
    "applications",
    "environments",
    "audit_logs",
    "login_attempts",
    "releases",
    "deployments",
    "deployment_events",
    "integrations",
    "webhook_deliveries",
    "jobs",
}


def test_migrations_downgrade_upgrade_and_match_the_models(engine: Engine) -> None:
    config = alembic_config()

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}

    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) >= TABLES

    command.check(config)  # raises if the models and the migrations have drifted


def test_environment_cannot_reference_an_application_in_another_workspace(db: Session) -> None:
    own, other = make_workspace(db), make_workspace(db)
    application = make_application(db, own)

    db.add(
        Environment(
            workspace_id=other.id,
            application_id=application.id,
            environment_type=EnvironmentType.DEVELOPMENT.value,
        )
    )
    with pytest.raises(IntegrityError, match="fk_environments_application_id_applications"):
        db.flush()


def test_application_has_one_environment_per_type(db: Session) -> None:
    application = make_application(db, make_workspace(db))
    make_environment(db, application, EnvironmentType.PRODUCTION)

    with pytest.raises(IntegrityError, match="uq_environments_application_id_environment_type"):
        make_environment(db, application, EnvironmentType.PRODUCTION)


def test_emails_must_be_stored_lowercase(db: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_users_email_lowercase"):
        make_user(db, email="Admin@Example.com")


def _audit_row(db: Session) -> AuditLog:
    workspace = make_workspace(db)
    row = AuditLog(
        workspace_id=workspace.id,
        actor_type=ActorType.SYSTEM.value,
        action="test.action",
        target_type="workspace",
        target_id=workspace.id,
    )
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_logs SET action = 'tampered' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ],
)
def test_audit_logs_refuse_update_and_delete(db: Session, statement: str) -> None:
    row = _audit_row(db)

    with pytest.raises(DBAPIError, match="audit_logs is append-only"):
        db.execute(text(statement), {"id": row.id})


def test_audit_logs_refuse_truncate(db: Session) -> None:
    _audit_row(db)

    with pytest.raises(DBAPIError, match="audit_logs is append-only"):
        db.execute(text("TRUNCATE audit_logs"))


def test_user_actor_must_name_the_user(db: Session) -> None:
    workspace = make_workspace(db)
    db.add(
        AuditLog(
            workspace_id=workspace.id,
            actor_type=ActorType.USER.value,
            action="test.action",
            target_type="workspace",
        )
    )
    with pytest.raises(IntegrityError, match="ck_audit_logs_actor_id"):
        db.flush()


def test_sqlalchemy_hides_bound_parameters(engine: Engine) -> None:
    with engine.connect() as connection, pytest.raises(DBAPIError) as caught:
        connection.execute(text("SELECT CAST(:value AS integer)"), {"value": "token-abc-123"})

    assert "SQL parameters hidden" in str(caught.value)


async def test_a_database_error_500_never_logs_row_values() -> None:
    """Postgres echoes values in its own messages; the 500 handler must not log them."""
    app = build_app()
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    async with client_for(app) as client:
        response = await client.get("/api/v1/_test/db-error")

    assert response.status_code == 500
    output = stream.getvalue()
    assert "token-abc-123" not in output
    assert "unhandled database error" in output
    assert "InvalidTextRepresentation" in output
